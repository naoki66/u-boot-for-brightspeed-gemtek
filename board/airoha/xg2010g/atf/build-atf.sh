#!/usr/bin/env bash
set -euo pipefail

: "${ATF_DIR:?}"
: "${MBEDTLS_DIR:?}"
: "${ARM32_CROSS_COMPILE:?}"
: "${AARCH64_CROSS_COMPILE:?}"
: "${LZMA:?}"
: "${OUTPUT_DIR:?}"

script_dir=$(cd "$(dirname "$0")" && pwd)
jobs=${JOBS:-$(nproc)}
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/bl2.bin" "$OUTPUT_DIR/bl31.bin"

# BL2 与 BL31 共用 build/en7523/release。`make clean` 在某些环境会静默失败，
# 于是下一阶段会链到上一阶段遗留的目标文件 —— 例如 BL31 链到为 BL2 编出来的
# aarch32 libc/libmbedtls —— 产出截断或不可用的镜像，而且链得过去、不报错。
# 所以这里不以 `make clean` 的返回值为准，而是强制确认对象树真的消失。
atf_build_tree="$ATF_DIR/build/en7523/release"

clean_atf_tree() {
    make -C "$ATF_DIR" PLAT=en7523 clean >/dev/null 2>&1 || true

    local attempt=0
    while [ -d "$atf_build_tree" ] && [ "$attempt" -lt 5 ]; do
        rm -rf "$atf_build_tree" 2>/dev/null || true
        if [ -d "$atf_build_tree" ]; then
            mv "$atf_build_tree" "$atf_build_tree.stale.$$" 2>/dev/null || true
        fi
        if [ -d "$atf_build_tree" ]; then
            sleep 1
        fi
        attempt=$((attempt + 1))
    done
    rm -rf "$ATF_DIR/build/en7523/debug" 2>/dev/null || true

    if [ -d "$atf_build_tree" ]; then
        echo "cannot remove the TF-A object tree: $atf_build_tree" >&2
        echo "the next stage would be linked against the previous stage's objects" >&2
        exit 1
    fi
}

# 这套开关同时喂给 BL2 与 BL31。其中两个决定第二阶段 FIP 从哪里读，不能随手改：
#
# * 刻意**不**定义 TCSUPPORT_UBI_SUPPORT。顶层 Makefile 没有为它提供 add_define，
#   只能经 BSP_CFLAGS 传 -D，所以"不传"就等于关掉。关闭后
#   plat/ecnt/en7523/ecnt_io_storage.c 里那句无条件的
#   `policies[FIP_IMAGE_ID] = &fip_memmap_policy;` 生效，BL23 从 mtd0 的
#   PLAT_ECNT_FIP_OFFSET (0x800) 读 FIP，而不是去 UBI 卷里找。
# * TCSUPPORT_EMMC 必须保留。XMODEM 救援回退整段（bl2_image_load_v2.c 里的
#   plat_ecnt_io_switch_to_memmap() + fip_image_xmodem_load()）被
#   `UBI_SUPPORT || EMMC` 门控，而 plat_ecnt_io_switch_to_memmap() 本身也只在
#   同一条件下定义。本板不用 eMMC，这个开关纯粹是解锁 memmap/XMODEM 路径的钥匙。
#
# 这套开关是刻意挑出来的子集，不是厂商 build.sh 那一整份 BSP_CFLAGS（那份还带
# -fsigned-char、-DTCSUPPORT_LITTLE_ENDIAN、EN7521/EN7580/MT7520 等族 CPU 宏，
# 以及 UBI/GPT 两项）。其中 -DTCSUPPORT_SPI_NAND_FLASH_ECC_DMA 尤其不能照抄：
# 它会把 SPI_NAND_Flash_Init() 切到 SPI 控制器 DMA 读，而"只对 BL23 生效"的那个
# 守卫写成 (!defined(IMAGE_BL2) || defined(IMAGE_BL23))，IMAGE_BL2 在全树从未被
# 定义，于是 || 这一支是死的、守卫退化成只看这个宏，一开就连 BL21/BL22 一起编
# 进去 —— 而那正是该块内 Airoha 原注释写明"SPI 控制器 DMA 不支持这两个 SRAM"
# 的两个阶段。当前已刷入的镜像也跑在关闭状态下。因为 SPI_NAND_Flash_Init() 把
# dma_on 声明在守卫之外，prepare-atf.py 会给它加 __attribute__((unused))，让关闭
# 状态下也能过 -Werror；真正要打开就得同时删掉那处补丁。
# scripts/ci/check-partition-layout.py 的 ecc-dma-vs-atf 门会挡住误开。
common_flags=(
    PLAT=en7523
    MBEDTLS_DIR="$MBEDTLS_DIR"
    CONFIG_ECNT=1
    TCSUPPORT_OPENWRT=1
    TCSUPPORT_ATF_UNOPEN=0
    # 顶层 Makefile 由它派生 TCSUPPORT_CPU_EN7523 / EN7512 / ARMV8 / UBOOT_64BIT。
    TCSUPPORT_CPU_EN7581=1
    # 必须按 make 变量传，不能只靠上面那条派生出来的 -D。
    # plat/ecnt/en7523/platform.mk:955 读的是 make 变量：
    #     ifneq ($(TCSUPPORT_UBOOT_64BIT),1) → INIT_UNUSED_NS_EL2 := 1
    # add_define 只产生编译期 -D，不会把 make 变量本身置上，所以漏传这一条会让
    # BL31 去改写 CNTVOFF_EL2/HSTR_EL2/CPTR_EL2/CNTHCTL_EL2。本板 BL33 是
    # AArch64 U-Boot（ecnt_plat_common.c 据此选 plat_get_spsr_for_bl33_entry 的
    # AArch64 分支），EL2 由内核自己管，旧树（v2.10 overlay）里
    # INIT_UNUSED_NS_EL2 一直是 0，这里必须保持同样的取值。
    TCSUPPORT_UBOOT_64BIT=1
    TCSUPPORT_EMMC=1
    TCSUPPORT_UBOOT=1
    TCSUPPORT_BL2_OPTIMIZATION=1
    # 第二阶段 FIP 使用 1 MiB 接收区，解压工作区从其末端开始。这个值决定
    # PLAT_ECNT_FIP_MAX_SIZE（0x100000 而非 0x7f800），也是 XMODEM 救援的接收窗口，
    # mtd0 的 2 MiB 布局依赖它。
    TCSUPPORT_TCBOOT_1MB_SIZE=1
    # 顶层 Makefile 以 $(TOOLS_DIR)/lzma 调用压缩器，注意带斜杠。
    TOOLS_DIR="$(dirname "$LZMA")"
)

build_bl2_stage() {
    local stage=$1
    local output=$2

    clean_atf_tree
    make -C "$ATF_DIR" -j"$jobs" \
        "${common_flags[@]}" \
        ARCH=aarch32 \
        ARM32TOOLCHAIN_BASE="$ARM32_CROSS_COMPILE" \
        CROSS_COMPILE_ATF="$ARM32_CROSS_COMPILE" \
        "$stage=1" bl2

    if [ ! -f "$ATF_DIR/$output" ]; then
        echo "$output was not generated" >&2
        exit 1
    fi
    cp "$ATF_DIR/$output" "$work_dir/$output"
}

# 截断的 lzma 载荷意味着上一阶段的对象树没被清干净，必须当场拦下：
# 拼进 bl2.bin 之后只会在设备上表现为起不来。
require_min_size() {
    local file=$1
    local minimum=$2
    local size

    size=$(stat -c%s "$file")
    if [ "$size" -lt "$minimum" ]; then
        echo "$file looks truncated (${size} bytes) - stale object tree?" >&2
        exit 1
    fi
}

build_bl2_stage IMAGE_BL21 bl21.bin
require_min_size "$work_dir/bl21.bin" 14336

build_bl2_stage IMAGE_BL22 bl22.lzma
require_min_size "$work_dir/bl22.lzma" 8192

build_bl2_stage IMAGE_BL23 bl23.lzma
require_min_size "$work_dir/bl23.lzma" 20480

# 生成器把 NAND 器件参数表（mfr_id / page / erase / OOB 尺寸）编进自身再打印出来，
# 不是分区表。它必须与 BL2 用同一组结构体相关的开关编译，否则写进 flash_table.bin
# 的结构体偏移与 BL2 侧不一致。
cc \
    -O2 \
    -DFLASH_TABLE_OPEN \
    -DTCSUPPORT_BL2_OPTIMIZATION \
    -I"$ATF_DIR/plat/ecnt/en7523/include" \
    -o "$work_dir/spi_nand_flash_table" \
    "$ATF_DIR/plat/ecnt/common/drivers/flash/spi_nand_flash_table.c"
(
    cd "$work_dir"
    ./spi_nand_flash_table
)
"$LZMA" e "$work_dir/flash_table.bin" "$work_dir/flash_table.lzma"

python3 "$script_dir/pack-bl2.py" \
    --bl21 "$work_dir/bl21.bin" \
    --bl22 "$work_dir/bl22.lzma" \
    --bl23 "$work_dir/bl23.lzma" \
    --flash-table "$work_dir/flash_table.lzma" \
    --output "$OUTPUT_DIR/bl2.bin"

clean_atf_tree
make -C "$ATF_DIR" -j"$jobs" \
    "${common_flags[@]}" \
    ARCH=aarch64 \
    CROSS_COMPILE="$AARCH64_CROSS_COMPILE" \
    bl31

if [ ! -f "$atf_build_tree/bl31.bin" ]; then
    echo "bl31.bin was not generated" >&2
    exit 1
fi
"$LZMA" e "$atf_build_tree/bl31.bin" "$OUTPUT_DIR/bl31.bin"
