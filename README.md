<!-- SPDX-License-Identifier: GPL-2.0+ -->

<a id="top"></a>

<h1 align="center">Brightspeed Gemtek XG2010G &amp; XR1710G U-Boot Bootloader</h1>

<p align="center">
  <strong>用于替换 Brightspeed Gemtek XG2010G / XR1710G 原厂 <code>/dev/mtd0</code> 的 signed U-Boot/FIP 启动镜像。</strong><br>
  <sub>本仓库为社区非官方固件 · 刷写有变砖风险，请先完整备份</sub>
</p>

<p align="center">
  <img alt="Target: Brightspeed Gemtek XG2010G & XR1710G" src="https://img.shields.io/badge/Target-XG2010G%20%7C%20XR1710G-0f766e?style=for-the-badge">
  <img alt="SoC: Airoha AN7581 class" src="https://img.shields.io/badge/SoC-Airoha%20AN7581%20class-1f6feb?style=for-the-badge">
  <img alt="NAND: 512 MiB SLC" src="https://img.shields.io/badge/NAND-512%20MiB%20SLC-7c3aed?style=for-the-badge">
</p>

<p align="center">
  <a href="https://github.com/naoki66/u-boot-for-brightspeed-gemtek/releases">
    <img alt="Download" src="https://img.shields.io/badge/Download-Latest%20signed%20mtd0-0f766e?style=for-the-badge&logo=github">
  </a>
  <a href="https://github.com/naoki66/u-boot-for-brightspeed-gemtek/actions/workflows/build-mtd0.yml">
    <img alt="CI Build" src="https://img.shields.io/badge/Actions-CI%20Build-1f6feb?style=for-the-badge&logo=githubactions&logoColor=white">
  </a>
  <a href="doc/board/airoha/xg2010g.rst">
    <img alt="Board manual" src="https://img.shields.io/badge/Docs-board%20manual-7c3aed?style=for-the-badge&logo=readthedocs&logoColor=white">
  </a>
  <a href="board/airoha/xg2010g/firmware/README.md">
    <img alt="Firmware blobs" src="https://img.shields.io/badge/Firmware-BL2%2FBL31%20blobs-d97706?style=for-the-badge">
  </a>
</p>

<p align="center">
  <a href="https://github.com/naoki66/u-boot-for-brightspeed-gemtek/actions/workflows/build-mtd0.yml">
    <img alt="Build signed Brightspeed Gemtek mtd0" src="https://github.com/naoki66/u-boot-for-brightspeed-gemtek/actions/workflows/build-mtd0.yml/badge.svg">
  </a>
  <a href="https://github.com/naoki66/u-boot-for-brightspeed-gemtek/releases">
    <img alt="GitHub release" src="https://img.shields.io/github/v/release/naoki66/u-boot-for-brightspeed-gemtek?include_prereleases&label=release">
  </a>
  <a href="https://github.com/naoki66/u-boot-for-brightspeed-gemtek/releases">
    <img alt="Downloads" src="https://img.shields.io/github/downloads/naoki66/u-boot-for-brightspeed-gemtek/total?label=downloads">
  </a>
  <img alt="U-Boot 2026.10-rc3 mainline" src="https://img.shields.io/badge/U--Boot-2026.10--rc3%20mainline-0f766e">
  <img alt="License GPL-2.0+" src="https://img.shields.io/badge/license-GPL--2.0%2B-2ea043">
</p>

<p align="center">
  <sub>
    mtd0 固定 2 MiB · BL2/BL31 与 U-Boot 均由源码构建 · 仅产出 signed artifact
  </sub>
</p>

---

## 📚 目录

**概览**

- [📌 项目定位](#-项目定位)
- [✨ 特性速览](#-特性速览)
- [🚀 快速开始（TL;DR）](#-快速开始tldr)
- [🔒 安全边界](#-安全边界)

**启动链与分区**

- [🔗 启动链图](#-启动链图)
- [🔑 BL2、BL31 与签名](#-bl2bl31-与签名)
- [📊 NAND 分区图](#-nand-分区图)

**刷机与救砖**

- [📦 Releases 文件怎么用](#-releases-文件怎么用)
- [⚡ TTL/TFTP 刷入 mtd0](#-ttltftp-刷入-mtd0)
- [🆘 X 模式与 Web Recovery](#-x-模式与-web-recovery)
- [🔄 首启环境迁移](#-首启环境迁移)
- [🧭 bootargs 参数说明](#-bootargs-参数说明)
- [✅ 正常引导与回退](#-正常引导与回退)
- [🧯 常见问题排查](#-常见问题排查)

**构建与法律**

- [🔧 本地构建](#-本地构建)
- [📄 GPL 说明](#-gpl-说明)

---

## 📌 项目定位

本仓库基于当前主线 U-Boot，加入 Brightspeed Gemtek XG2010G 与 XR1710G 的
Airoha AN7581 类平台板级支持（`xg2010g_defconfig` / `xr1710g_defconfig`），
用于替换原厂被限制功能的 `mtd0 bootloader`。
刷写 bootloader 存在变砖风险，请自行评估并承担操作后果。

| 项目 | 当前约束 |
| --- | --- |
| 设备 | Brightspeed Gemtek XG2010G · XR1710G（两板共用同一启动链与分区布局） |
| 平台 | Airoha AN7581/AN7583 类启动链 |
| bootloader 分区 | `0x00000000-0x00200000`，固定 2 MiB |
| 工具版本 | TF-A tooling `v2.13.0`；Airoha TF-A 基于 `v2.10` 与固定 overlay commit |

XG2010G 的 `mtd0` 通常不是裸 `u-boot.bin`，而是一个从 BL2 开始验证的完整
启动包/FIP，包含 BL2、BL31、U-Boot/BL33 和证书材料。本仓库本地编译出的
`u-boot.bin` 只是 BL33 候选文件；正式刷机请使用 Actions/Releases 生成的
signed mtd0/FIP。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## ✨ 特性速览

| 图标 | 特性 | 说明 |
| --- | --- | --- |
| 🧩 | 主线 U-Boot | 基于 U-Boot `2026.10-rc3` 主线，新增 XG2010G/XR1710G 板级 DTS 与 `xg2010g_defconfig`/`xr1710g_defconfig` |
| 🔐 | 强制 Trusted Boot | 设备只接受 signed 镜像，自行编译须自行完成签名 |
| 🧱 | mtd0 边界硬校验 | workflow 强制 mtd0 = `0x200000`（2 MiB），越界直接构建失败 |
| 🧬 | 源码构建 BL2/BL31 | 固定 Airoha TF-A、Mbed TLS、Arm GNU Toolchain 与 LZMA 版本 |
| 🔧 | 固定签名工具链 | TF-A tooling 锁定 `v2.13.0`，用于生成 FIP 与证书 |
| 🛟 | 双救砖路径 | BootROM X 模式 XMODEM 两段传输 + Web Recovery 重建 UBI |
| 📦 | 完整交付物 | 每次构建附带 `sha256sums.txt` 与 `build-info.txt`（commit、日期、边界） |

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🚀 快速开始（TL;DR）

> [!TIP]
> 先判断你处在哪种情况，再选择对应文件。**只有 `mtd0-signed.bin` 可以写 bootloader 分区。**

| 你的情况 | 使用的产物 | 操作要点 |
| --- | --- | --- |
| 🟢 能进原厂 U-Boot / TTL，要替换 bootloader | `<board>-...-mtd0-signed.bin`（`xg2010g-…` / `xr1710g-…`，按你的设备选择） | [TTL/TFTP 刷入](#-ttltftp-刷入-mtd0)，只擦写 `0x000000` 起 `0x200000` |
| 🔴 mtd0 写坏、NAND 无法启动 | `<board>-...-ubi-preloader.bin` + `<board>-...-ubi-bl31-uboot.fip` | [X 模式 XMODEM 救砖](#-x-模式与-web-recovery)，再走 Web Recovery |
| 🔵 只升级系统，不动 bootloader | `ubi-squashfs-sysupgrade.itb` | 只刷 `ubi` 区域（`0x00600000` 起，440 MiB），必须重建 UBI |

**关键参数速查：**

| 参数 | 值 |
| --- | --- |
| `mtd0` 偏移 / 长度 | `0x00000000` / `0x200000`（2 MiB，擦写长度禁止超过此值） |
| `uenv` / `dsd` | 分别从 `0x00200000` / `0x00400000` 起，各 2 MiB，默认保留 |
| `ubi` 区域 | 偏移 `0x00600000`，长度 `0x1b800000`（440 MiB） |
| signed FIP 在 mtd0 内偏移 | `0x800` |
| U-Boot 加载地址 | `0x81800000` |
| TTL/TFTP 网段 | U-Boot `192.168.0.1`，电脑 `192.168.0.205/24`（网线接设备 1G 口） |
| Web Recovery | 无痕模式打开 `http://192.168.1.1/`，系统固件上传会自动重建 UBI |
| 救砖文件 | `<board>-...-ubi-preloader.bin` + `<board>-...-ubi-bl31-uboot.fip`（XMODEM 两段） |

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🔒 安全边界

> [!WARNING]
> `mtd0` 的正确长度是 `0x200000`，即 2 MiB。使用其他擦写长度会越过
> `uenv`、`dsd`，破坏系统区域。

> [!CAUTION]
> 刷写 bootloader 前必须保存完整原厂备份，并确认 NAND 型号、页大小、
> 擦除块大小、ECC/OOB、BootROM 镜像格式和 Trusted Boot 策略与本项目匹配。

| 保护项 | 要求 |
| --- | --- |
| `bootloader` | 只允许写 `0x00000000-0x00200000` 的完整 signed mtd0 |
| `uenv` | 默认保留；`saveenv` 会写这里，改环境前先 `printenv` 备份 |
| `dsd` | 原厂校准数据，必须保留 |
| `reserved_bmt` | NAND 坏块替代/BMT 预留，不能被系统镜像覆盖 |

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🔗 启动链图

```mermaid
flowchart LR
    A["Power on / Reset"] --> B["BootROM<br/>片内固化代码"]
    B --> C["BL2 / preloader<br/>DDR 初始化 + 校验后续阶段"]
    C --> D["BL31<br/>EL3 Secure Monitor"]
    D --> E["U-Boot / BL33<br/>本仓库构建"]
    E --> F["Linux / OpenWrt<br/>FIT + UBI"]

    classDef rom fill:#0f172a,stroke:#334155,color:#ffffff;
    classDef fw fill:#e0f2fe,stroke:#0284c7,color:#0f172a;
    classDef ub fill:#dcfce7,stroke:#16a34a,color:#0f172a;
    classDef os fill:#fef3c7,stroke:#d97706,color:#0f172a;

    class A,B rom;
    class C,D fw;
    class E ub;
    class F os;
```

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🔑 BL2、BL31 与签名

当前构建方案：

1. 在 TF-A `v2.10` 基础上叠加固定版本的 Airoha AN7581 平台源码。
2. 分别编译 BL21、BL22、BL23，加入 NAND flash table 后组装 BL2/preloader。
3. 编译 BL31，并按 Airoha 启动格式进行 LZMA 压缩。
4. 编译本仓库的 `u-boot.bin`，生成 Airoha LZMA 格式的 BL33 镜像。
5. 使用 `fiptool` 和 `cert_create` 生成证书链与 signed FIP。
6. 将 signed FIP 放入 2 MiB `mtd0` 镜像的 `0x800` 偏移，保留原厂前导区。

签名构建流水线：

```mermaid
flowchart LR
    U["U-Boot 源码<br/>xg2010g / xr1710g defconfig"] --> B["u-boot.bin<br/>LZMA BL33 镜像"]
    T["TF-A v2.10 + Airoha overlay<br/>固定源码版本"] --> L2["BL21 + BL22 + BL23<br/>编译并组装 BL2"]
    T --> L31["BL31 源码构建<br/>Airoha LZMA"]
    K["XG2010G_TB_PRIVATE_KEY<br/>仅存 GitHub Secret"] --> C["cert_create<br/>Trusted Boot 证书链"]
    L2 --> C
    L31 --> C
    B --> C
    L2 --> F["fiptool create<br/>signed FIP"]
    L31 --> F
    B --> F
    C --> F
    P["mtd0-prefix.bin<br/>0x800 前导区"] --> M["2 MiB mtd0 镜像<br/>FIP @ 0x800，尾部 0xff"]
    F --> M
    M --> A["Artifact / Release<br/>仅 signed 产物"]

    classDef src fill:#dcfce7,stroke:#16a34a,color:#0f172a;
    classDef stock fill:#fef3c7,stroke:#d97706,color:#0f172a;
    classDef key fill:#fee2e2,stroke:#dc2626,color:#0f172a;
    classDef out fill:#e0f2fe,stroke:#0284c7,color:#0f172a;

    class U,B,T,L2,L31 src;
    class P stock;
    class K,C key;
    class F,M,A out;
```

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 📊 NAND 分区图

<p align="center">
  <img width="380" alt="XG2010G 512 MiB NAND 单柱布局图（真实比例）" src="doc/board/airoha/xg2010g-nand-layout.svg">
</p>

### 本项目 NAND 目标边界

| 区域 | 起始 | 结束（不含） | 大小 | 用途 |
| --- | --- | --- | --- | --- |
| `bootloader` | `0x00000000` | `0x00200000` | 2 MiB | 完整 signed mtd0/FIP，只在确认后替换 |
| `uenv` | `0x00200000` | `0x00400000` | 2 MiB | U-Boot 环境，默认保留 |
| `dsd` | `0x00400000` | `0x00600000` | 2 MiB | 原厂校准数据，必须保留 |
| `ubi` | `0x00600000` | `0x1be00000` | 440 MiB | 项目后续系统 UBI，必须包含 `fit` 卷 |
| `reserved_bmt` | `0x1be00000` | `0x20000000` | 66 MiB | NAND 坏块替代/BMT 预留 |

后续系统升级只应刷写 `ubi` 区域，也就是偏移 `0x00600000`、长度
`0x1b800000`。不要覆盖 `bootloader`、`uenv`、`dsd` 或尾部 BMT 预留区。

<details>
<summary>📂 查看原厂可见分区（legacy 布局参考，点击展开）</summary>

| 地址范围 | 分区名 |
| --- | --- |
| `0x00000000-0x00200000` | `bootloader` |
| `0x00200000-0x00400000` | `uenv` |
| `0x00400000-0x00600000` | `dsd` |
| `0x00600000-0x00964842` | `kernel` |
| `0x00964940-0x025d4940` | `rootfs` |
| `0x00600000-0x04600000` | `tclinux` |
| `0x04600000-0x04964842` | `kernel_slave` |
| `0x04964940-0x065d4940` | `rootfs_slave` |
| `0x04600000-0x08600000` | `tclinux_slave` |
| `0x08600000-0x1be00000` | `system` |

该表仅用于对照原厂 TTL 日志和确认硬件范围，不是本项目的启动布局，
也不表示项目 U-Boot/Recovery 会挂载或回退到这些分区。

</details>

原厂固件该 NAND 曾使用 `tclinux`、`tclinux_slave`、`system` 分区，
且原厂 UBI 挂载在 `system`。这些名称和布局仅用于硬件校核，本项目不识别、
不挂载、也不回退到原厂分区；刷入项目 U-Boot 后必须使用上表中的新 `ubi` 布局。
TTL 同时确认 NAND 几何为 512 MiB、128 KiB 擦除块、2 KiB 页、128 字节 OOB；
U-Boot/Recovery 会校验项目 `ubi` 的 440 MiB 分区及 128 KiB/2 KiB 几何，
不满足时按 UBI 启动失败处理并进入 Recovery。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 📦 Releases 文件怎么用

```mermaid
flowchart TD
    R["GitHub Release / workflow artifact"] --> M["mtd0-signed.bin<br/>完整 2 MiB bootloader"]
    R --> P["&lt;board&gt;-ubi-preloader.bin<br/>XMODEM 第一段"]
    R --> F["&lt;board&gt;-ubi-bl31-uboot.fip<br/>XMODEM 第二段 / Web Recovery"]
    R --> S["&lt;board&gt;-sha256sums.txt<br/>校验所有产物"]
    R --> U["u-boot-raw.bin<br/>仅调试"]

    M --> T["TTL/TFTP 写入<br/>flash erase/write 0x200000"]
    P --> X["X 模式救砖"]
    F --> X

    classDef root fill:#0f172a,stroke:#334155,color:#ffffff;
    classDef art fill:#e0f2fe,stroke:#0284c7,color:#0f172a;
    classDef use fill:#dcfce7,stroke:#16a34a,color:#0f172a;

    class R root;
    class M,P,F,S,U art;
    class T,X use;
```

其中 `<board>` 为 `xg2010g`（Brightspeed Gemtek XG2010G）或 `xr1710g`（Brightspeed Gemtek XR1710G），
请按自己的设备选择对应前缀的文件，两板镜像不可互换刷写。

| 文件 | 用途 |
| --- | --- |
| `<board>-...-mtd0-signed.bin` | 完整 2 MiB `/dev/mtd0` bootloader 镜像，用于替换 `bootloader` 分区 |
| `<board>-...-fip-signed.bin` | signed FIP 本体，位于完整 mtd0 镜像的 `0x800` 偏移 |
| `<board>-...-ubi-preloader.bin` | 包含 BL2 和 `tb-fw-cert` 的 signed FIP，用于 X 模式第一段 XMODEM |
| `<board>-...-ubi-bl31-uboot.fip` | BL31 + U-Boot/BL33 FIP，用于 X 模式第二段 XMODEM 和 Web Recovery |
| `<board>-...-bl31.bin` | 源码构建的 BL31 Airoha LZMA 固件，便于核对和离线调试 |
| `<board>-...-u-boot-raw.bin` | 裸 U-Boot/BL33，仅供调试 |
| `<board>-...-sha256sums.txt` | 该板所有产物 SHA256 |
| `<board>-...-build-info.txt` | 该板构建 commit、日期、签名状态和镜像边界 |

校验 Release 文件：

```console
# Linux / WSL
sha256sum -c <board>-...-sha256sums.txt

# Windows
CertUtil -hashfile <board>-...-mtd0-signed.bin SHA256
```

> [!IMPORTANT]
> 只有 `<board>-...-mtd0-signed.bin` 是完整 2 MiB `mtd0` 镜像。其它裸文件或
> FIP 文件用于救砖、调试或 Web Recovery，不要当作完整 `mtd0` 直接写入
> `0x00000000`。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## ⚡ TTL/TFTP 刷入 mtd0

适用于已经能进原厂 U-Boot/TTL 命令行，并且当前 bootloader 提供 Airoha
`flash` 命令的情况。

连接参数（网段、加载地址、待刷文件与大小）见[关键参数速查](#-快速开始tldr)。
电脑运行 TFTP server，U-Boot 主动拉取：

```console
setenv ipaddr 192.168.0.1
setenv serverip 192.168.0.205
setenv loadaddr 0x81800000
tftpboot ${loadaddr} <board>-...-mtd0-signed.bin
echo ${filesize}
crc32 ${loadaddr} ${filesize}
```

确认 `filesize` 为 `200000` 或 `0x200000` 后，只擦写 mtd0 的 2 MiB：

```console
flash erase 0x000000 0x200000
flash write 0x000000 0x200000 0x81800000
reset
```

原厂/Airoha `flash` 参数顺序：

| 命令 | 参数 |
| --- | --- |
| `flash erase [addr] [len]` | 起始地址 + 长度 |
| `flash write [dst] [len] *[src]` | 目的 NAND 地址 + 长度 + 来源内存地址 |

> [!NOTE]
> 如果当前 bootloader 处在 TFTP receive/server 模式，电脑侧可能需要执行
> `tftp -i 192.168.0.1 put image.ub`。这种情况下也应发送同一个 signed mtd0
> 产物；`image.ub` 只能作为传输文件名示例，不能把系统镜像 `image.ub` 当
> bootloader 写入 mtd0。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🆘 X 模式与 Web Recovery

如果 `mtd0` 写坏导致 NAND 无法启动，Airoha BootROM 通常仍可进入串口
X 模式加载临时引导。该流程需要 TTL 串口和支持 XMODEM 的终端工具。

```mermaid
sequenceDiagram
    participant U as User
    participant B as BootROM X mode
    participant T as Terminal XMODEM
    participant W as Web Recovery

    U->>B: Hold RESET and power on
    B-->>T: CCCC
    U->>T: Send &lt;board&gt;-ubi-preloader.bin
    B-->>U: Auto reboot
    U->>B: Hold RESET, power on, press x
    B-->>T: Press x to load BL31 + U-Boot FIP
    U->>T: Send &lt;board&gt;-ubi-bl31-uboot.fip
    U->>B: Hold RESET before 100%, release after flowing LEDs
    U->>W: Open http://192.168.1.1/ (incognito)
    W-->>U: Flash sysupgrade + BL2 + U-Boot, rebuild UBI
```

### 首次 bootext.ram

首次使用救砖链时，可能需要先加载一次 `bootext.ram`：

1. 断电。
2. 按住 <kbd>RESET</kbd> 键，同时通电启动。
3. 终端显示 `CCCC` 时表示设备已进入 X 模式。
4. 打开终端菜单：文件 -> 传输 -> XMODEM -> 发送。
5. 选择 `bootext.ram`，等待传输完成。之后通常不再需要重复加载该文件。

> [!NOTE]
> `bootext.ram` 属于平台救援链文件，不由本仓库的 U-Boot 编译生成；需要
> 保留已验证可用的原厂/平台版本。

### 正式救砖/刷机

1. 断电，按住 <kbd>RESET</kbd> 键，同时通电启动。
2. 按 <kbd>X</kbd> 或 <kbd>x</kbd>，终端显示 `CCCC` 后进入 XMODEM 接收。
3. 打开：文件 -> 传输 -> XMODEM -> 发送。
4. 发送 `<board>-...-ubi-preloader.bin` 或 `ubi-preloader.bin`。
5. 传输完成后设备会自动重启。
6. 再次断电，按住 <kbd>RESET</kbd> 键，同时通电启动。
7. 提示 `Press x to load BL31 + U-Boot FIP` 时输入 <kbd>x</kbd>。
8. 再次打开 XMODEM 发送。
9. 发送 `<board>-...-ubi-bl31-uboot.fip`。
10. 第二段 XMODEM 进度到 100% 前按住 <kbd>RESET</kbd>，等设备灯进入流水式闪烁后再松开。
11. 浏览器使用**无痕模式**访问 `http://192.168.1.1/`（网线可接设备任一网口，含 WAN 口）。
12. 选择系统镜像 `ubi-squashfs-sysupgrade.itb`。
13. `BL2` 选择 `<board>-...-ubi-preloader.bin`。
14. `U-Boot` 选择 `<board>-...-ubi-bl31-uboot.fip`。
15. 系统固件上传会自动擦除并重建完整 `ubi` 布局，无需额外勾选。
16. 等待数分钟完成刷写，之后务必断电重启设备。

> [!CAUTION]
> 必须使用**无痕（隐私）窗口**打开 `http://192.168.1.1/`。设备此前运行 OpenWrt 时，
> 同一地址曾由 LuCI 提供 301 跳转到登录页 `http://192.168.1.1/cgi-bin/luci/`，普通
> 浏览器窗口会命中本地缓存的跳转记录，直接打开 OpenWrt 登录页而非 Recovery 页。
> 无痕窗口不带缓存和 Cookie，可避开该问题；若仍出现 LuCI 页面，按 `Ctrl+F5` 强制
> 刷新，或换用其他浏览器验证。

> [!NOTE]
> 恢复页在**所有网口**（含 WAN 口）同时接受 DHCP 与 HTTP，设备地址统一为 `192.168.1.1/24`，PC 从任一口都能拿到 `192.168.1.2` 并打开页面；建议只插一根网线，多口同时插线时上传链路可能不稳定。恢复页运行期间，面板状态灯 sts 红/绿/蓝/白做呼吸跑马灯：XG2010G 为 GPIO 43/44/45/33（对应原厂 FDT 0x0f 控制器 11/12/13/1），XR1710G 为 GPIO 29/17/19/20，均为低有效；网口绿/黄灯由软件按链路速度点亮（千兆亮绿灯、10/100M 亮黄灯，有流量时 100ms 周期闪烁）：XG2010G 为 LAN4 口（绿 46/黄 42），XR1710G 为 LAN1/LAN2 口（绿 43/44、黄 33/34）。启动日志应出现 `Recovery status LEDs: ...`（XG2010G: `gpio43(L) gpio44(L) gpio45(L) gpio33(L)`；XR1710G: `gpio29(L) gpio17(L) gpio19(L) gpio20(L)`，software PWM）；若某盏灯明暗相反，把该灯的 `GPIO_ACTIVE_LOW` 改为 `GPIO_ACTIVE_HIGH` 即可。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🔄 首启环境迁移

原厂 `mtd1/uenv` 中的环境会被新 U-Boot 读取，但原厂
`bootcmd=flash imgread 2048;bootm` 属于旧布局，不能继续使用。项目只支持
新 `ubi` 分区和 `fit` 卷；启动失败时由 `bootcmd` 自动转入 Web Recovery。
板级初始化还会识别并替换带有 `ubi.mtd=system/tclinux*` 或
`root=/dev/mtdblock*` 的旧 `bootargs`，避免 Linux 继续挂载原厂布局。

首次刷入 signed `mtd0` 后，先通过 TTL 中断自动启动，执行一次环境迁移。
这些命令会写入 `uenv`，建议先用 `printenv` 保存当前环境：

```console
setenv ipaddr 192.168.0.1
setenv serverip 192.168.0.205
setenv loadaddr 0x81800000
setenv bootdelay 4
setenv bootflag 0
setenv serdes_ethernet 411
setenv boot_ubi 'ubi part ubi && run boot_production'
setenv boot_production 'run ubi_read_production && bootm ${loadaddr}#${bootconf}'
setenv ubi_read_production 'ubi read ${loadaddr} fit'
setenv bootconf config-1
setenv bootcmd 'run boot_ubi || http_recovery'
setenv bootargs 'sdram_conf=0x00108893 vendor_name=ECONET Technologies Corp. product_name=xPON ONU ubi.mtd=ubi snmp_sysobjid=1.2.3.4.5 country_code=ff ether_gpio=0c power_gpio=1515 dsl_gpio=0b internet_gpio=02 multi_upgrade_gpio=0b020400000000000000000000000000 onu_type=71 qdma_init=69bb console=ttyS0,115200n8 earlycon bootflag=0 serdes_sel=0 serdes_pon=000 serdes_ethernet=411 serdes_wifi1=005 serdes_wifi2=413 serdes_usb1=111 serdes_usb2=000 ubi.block=0,fit root=/dev/fit0 rootwait ramdisk_size=65536 rdinit=/sbin/init'
saveenv
reset
```

迁移说明：

- `ubi.mtd=system` 应改为 `ubi.mtd=ubi`，匹配本项目 DTS 中的新 UBI 分区名。
- `root=/dev/mtdblock4 ro` 是原厂旧 `rootfs` 分区路径；新 UBI 布局下不应写入。
  默认启动必须从 `fit` 卷读取 FIT，root 参数由 FIT/系统镜像布局决定。
- 新 U-Boot 会在检测到上述旧参数时自动替换为项目默认 bootargs；其他自定义
  启动参数如需保留，应在项目默认 bootargs 基础上追加。
- `bootcmd` 必须保留 `run boot_ubi || http_recovery`，这样 UBI attach、`fit`
  卷读取或 FIT 启动失败时会自动进入 Recovery。
- 不要把示例 `ethaddr=00:AA:BB:01:23:40` 写进 `bootargs`；真实 MAC 应保留在
  U-Boot 环境变量 `ethaddr` 或由设备树/系统配置传递。
- `console`、`sdram_conf`、`qdma_init`、`*_gpio`、`onu_type`、`country_code` 和
  `serdes_*` 建议保留，它们可能被原厂内核、Airoha 驱动或用户态脚本读取。


<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🧭 bootargs 参数说明

本节根据 XG2010G 原厂 TTL、Airoha/ECONET SDK 中的启动参数解析代码和实机
PHY 初始化日志校核。参数名中的下划线是名称的一部分；文档或聊天中出现的
`\_` 只是 Markdown 转义，实际传给内核时不能包含反斜杠。

`onu_type`、`qdma_init`、`bootflag` 和各个 `serdes_*` 参数由 SDK 使用
`%x`、`%hx` 或 `%hhx` 读取，因此没有 `0x` 前缀时仍按**十六进制**解释。
例如 `onu_type=71` 是 `0x71`，并不是十进制 71。

### 基础与平台参数

| 参数 | 当前值 | 说明 |
| --- | --- | --- |
| `sdram_conf` | `0x00108893` | Airoha/ECONET 平台的 SDRAM 配置标识。DDR 的实际早期初始化由匹配硬件的 BL2 完成；当前 SDK 没有公开该值的完整位定义，应保留原厂值。 |
| `vendor_name` | `ECONET Technologies Corp.` | 厂商名称，供厂商系统接口或用户态组件识别，不决定 U-Boot/FIT 启动。 |
| `product_name` | `xPON ONU` | 通用产品类别名称。 |
| `snmp_sysobjid` | `1.2.3.4.5` | SNMP `sysObjectID`；当前值是原厂通用占位 OID，不影响启动。 |
| `country_code` | `ff` | 一字节区域字段；`0xff` 更接近默认/未指定值，不能直接解释为 ISO 国家代码。 |
| `console` | `ttyS0,115200n8` | Linux 主控制台为 `ttyS0`，115200 波特率、8 数据位、无校验、1 停止位。 |
| `earlycon` | 无值 | 在正式串口驱动初始化前启用早期内核日志。 |
| `bootflag` | `0` | 原厂双镜像布局中表示 Main Image。项目不再使用原厂双分区回退，它只作为兼容字段保留；实际失败回退由 `bootcmd=run boot_ubi || http_recovery` 控制。 |

`vendor_name` 和 `product_name` 的值包含空格，这是原厂命令行的既有写法。标准
Linux 命令行解析器可能把它们分别截断为 `vendor_name=ECONET` 和
`product_name=xPON`，其余单词成为独立参数。原厂实机可正常启动，说明它不是启动
阻断项；需要由 Linux 可靠读取完整值时，应使用带内嵌双引号的值，或改用不含空格
的标识。

### UBI 与根文件系统

| 参数 | 说明 |
| --- | --- |
| `ubi.mtd=ubi` | 将项目中名为 `ubi` 的 MTD 分区挂接为 `ubi0`。这是新布局的正确值，不能改回原厂的 `ubi.mtd=system`。 |
| `ubi.block=0,fit` | 请求从 `ubi0` 中名为 `fit` 的卷建立块设备/供 FIT rootfs 路径使用。 |
| `root=/dev/fit0` | 把 FIT 中导出的根文件系统作为 Linux 根设备。 |
| `rootwait` | 等待根设备出现后再挂载，避免 UBI/FIT 初始化时序造成误判。 |
| `ramdisk_size=65536` | 保留 64 MiB ramdisk 上限，兼容可能带 initramfs 的 FIT。 |
| `rdinit=/sbin/init` | 使用 initramfs 时指定首个用户态进程；没有 initramfs 时不会替代正常根文件系统的 `init` 流程。 |

只有 `ubi.mtd=ubi` 并不足以选择根文件系统。项目默认 `bootargs` 已包含上述
`ubi.block`、`root` 和等待参数；不要使用只到 `serdes_usb2=000` 为止的不完整
命令行。

### GPIO/LED 兼容字段

| 参数 | 当前值 | 说明 |
| --- | --- | --- |
| `ether_gpio` | `0c` | 原厂 Ethernet/LED GPIO 字段；若按单字节看为 `0x0c`。 |
| `power_gpio` | `1515` | 厂商 GPIO/LED 打包字段，可能包含两个 `0x15`，不能解释为十进制 GPIO 1515。 |
| `dsl_gpio` | `0b` | 共用 DSL/xPON SDK 遗留的指示 GPIO 字段；若按单字节看为 `0x0b`。 |
| `internet_gpio` | `02` | Internet 状态指示字段；若按单字节看为 `0x02`。 |
| `multi_upgrade_gpio` | `0b020400000000000000000000000000` | 16 字节升级状态 GPIO/LED 配置表，前三字节为 `0b 02 04`，其余为零，不是单一 GPIO 编号。 |

当前公开 SDK 只列出了这些环境字段，没有给出 `power_gpio` 和
`multi_upgrade_gpio` 的完整打包格式。它们也不等同于板级 DTS 中的 Linux
`gpio-leds` 编号，未取得对应厂商解码实现前不应自行改写。

### ONU 类型：`onu_type=71`

`onu_type` 是一个按位打包的十六进制字节，不是单一的模式编号。SDK 使用
`ONUTYPE_MASK=0x03`、`COMBOPON_MASK=0x04`、`BBF247_MASK=0x08` 和
`ONUMODE_MASK=0xf0` 解码，其组合公式为：

```text
onu_type = (PON_MODE << 4) | (BBF247_BIT << 3) | (COMBO_BIT << 2) | ONU_TYPE
```

低位字段定义：

| 位 | 值 | 含义 |
| --- | --- | --- |
| `[1:0]` | `0` | unknown，未知 ONU 类型 |
| `[1:0]` | `1` | SFU，偏桥接型 ONU |
| `[1:0]` | `2` | HGU，家庭网关型 ONU |
| `2` | `0/1` | 非 Combo PON / Combo PON |
| `3` | `0/1` | 非 BBF.247 / BBF.247 |

高四位 `[7:4]` 是 SDK 的 `XMCSIF_WanDetectionMode_t`（`ONUMODE_MASK`）枚举：

| 高四位 | SDK 枚举 | SDK 打印名 | 协议/速率含义 |
| --- | --- | --- | --- |
| `0x0` | `AUTO` | `auto` | 自动检测（兼容旧版 preversion） |
| `0x1` | `GPON` | `GPON` | GPON |
| `0x2` | `EPON` | `EPON` | 普通 1G EPON |
| `0x3` | `10G_1G_EPON` | `XEPON-ASYM` | XE-PON 非对称：下行 10G、上行 1G |
| `0x4` | `10G_10G_EPON` | `XEPON-SYM` | XE-PON 对称：下行/上行均 10G |
| `0x5` | `1G_1G_EPON` | `XEPON_1G` | XEPON 1G+1G（10G MAC 的 1G/1G 模式） |
| `0x6` | `XGPON` | `XGPON` | XG-PON |
| `0x7` | `XGSPON` | `XGSPON` | XGS-PON（对称 10G） |
| `0x8` | `NGPON2_10G_10G` | `NGPON2-10G_10G` | NG-PON2：10G/10G |
| `0x9` | `NGPON2_10G_2G` | `NGPON2-10G_2G` | NG-PON2：10G/2G |
| `0xA` | `NGPON2_2G_2G` | `NGPON2-2G_2G` | NG-PON2：2G/2G |
| `0xB` | `GPON_SYM` | `GPON-SYM` | GPON 对称模式 |
| `0xC` | `TURBO_EPON` | `TURBO-EPON` | Turbo EPON |

常用编码示例（低位取非 Combo、非 BBF.247）：

| 组合 | `onu_type` |
| --- | --- |
| GPON + SFU | `0x11`（命令行可写 `11`） |
| EPON + SFU | `0x21`（命令行可写 `21`） |
| XGPON + SFU | `0x61`（命令行可写 `61`） |
| XGSPON + SFU | `0x71`（命令行可写 `71`） |
| XGSPON + HGU | `0x72`（命令行可写 `72`） |

因此 `onu_type=71` 中的 `71` 实际是十六进制 `0x71`：高四位 `0x7` 为
XGS-PON，低两位 `0x1` 为 SFU，bit 2/3 均为 0，即 **XGS-PON + SFU、非 Combo、
非 BBF.247**。这与原厂 TTL 中的 `PON MAC GET ONU_TYPE = SFU` 和
`PON MAC GET ONU_MODE = XGSPON` 完全一致。

### QDMA：`qdma_init=69bb`

`0x69bb` 用于指定 QDMA 缓冲档位、描述符所在内存和高速数据路径：

| 字段 | 解码结果 |
| --- | --- |
| LAN payload `[1:0]` | `3`，256 字节档 |
| LAN DSCP/描述符 bit 3 | 使用 SRAM 路径 |
| WAN payload `[5:4]` | `3`，256 字节档 |
| WAN DSCP/描述符 bit 7 | 使用 SRAM 路径 |
| `FAST_WAN` | 开启 |
| `FAST_XSI_PCIE1` | 开启 |
| `FAST_XSI_ETHER` | 开启 |
| `FAST_XSI_PON` | 开启 |

在 EN7581 的 SDK 缓冲表中，这一组合会预留 LAN 4 MiB、WAN 5 MiB，合计
9 MiB。原厂 TTL 输出的 `QDMA LAN buffer_size = 0x400000` 和
`QDMA WAN buffer_size = 0x500000` 与计算结果一致。

### SerDes 参数

EN7581 使用六个独立的 `serdes_*` 参数。每个值都是 12 位十六进制配置字：

```text
[11:8] PHY 类型
 [7:4] Ethernet 类型：0=无，1=LAN，2=WAN
 [3:0] 当前 SerDes 物理通道选择的接口
```

低四位的接口值必须结合参数所属物理通道解释，不能把相同数字跨通道直接套用。

| 参数 | 解码 | 实机对应 |
| --- | --- | --- |
| `serdes_pon=000` | PON 通道使用原生 PON 接口；Ethernet/外接 PHY 字段为零 | XGS-PON |
| `serdes_ethernet=411` | PHY profile C + LAN + USXGMII | RTL8261N，MDIO 地址 5 |
| `serdes_wifi1=005` | WiFi1/PCIe0 SerDes 选择 `NONE` | 通道关闭 |
| `serdes_wifi2=413` | PHY profile C + LAN + USXGMII | WiFi2/PCIe1 通道改作 RTL8261N Ethernet，MDIO 地址 8 |
| `serdes_usb1=111` | AN8811 profile + LAN + HSGMII | USB1 通道改作 EN8811H 2.5G，MDIO 地址 `0xf` |
| `serdes_usb2=000` | USB2 SerDes 保持 USB3 接口，Ethernet/PHY 字段为零 | 未改作 Ethernet |

`WiFi2`、`USB1` 是 SoC SerDes 复用通道名称，不表示 XG2010G 实际装有 Wi-Fi
或使用该 USB 功能。原厂日志表明这些通道已经复用给外部 Ethernet PHY。

`serdes_sel=0` 是旧平台使用的统一选择字段。在 SDK 的 EN7581 分支中，驱动
注册并读取的是上述六个独立参数，通用 `serdes_sel` 主要属于兼容残留，不会覆盖
六路独立配置。尤其不要把原厂 `serdes_ethernet=411` 改为 `421`：中间十六进制
位从 `1` 变成 `2` 会把该 SerDes 的角色从 LAN 改成 WAN，与原厂 TTL 和现有
端口映射不符。

### 校核依据

- 原厂 TTL：内核命令行、QDMA 缓冲区输出、PHY 初始化和 XGS-PON/SFU 输出。
- SDK `linux/arch/arm64/mach-econet/ecnt_bootargs.c`：`onu_type`、`qdma_init`、
  `bootflag` 的十六进制解析。
- SDK `private/xpon_10g/src/ic/AN7581.c` 与 `union_ic_init.c`：ONU 类型和
  PON 模式位域。
- SDK `private/install_bsp/inc/blapi_system_bsp.h`：QDMA 掩码、系统环境字段。
- SDK `linux/include/global_inc/uapi/ecnt_event_global/ecnt_event_serdes.h` 与
  `linux/drivers/char/arht_serdes_cfg.c`：SerDes 位域、接口和 PHY 类型。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## ✅ 正常引导与回退

Web Recovery 刷写 `ubi-squashfs-sysupgrade.itb` 并自动重建 UBI 后，正常
启动应直接断电重启，不再按 <kbd>RESET</kbd>，让 U-Boot 执行迁移后的
`bootcmd`。

U-Boot 启动后会对 RESET GPIO 做确认：默认需要持续按住 3 秒才进入 Web
Recovery，并在串口打印倒计时。中途松开会取消恢复并继续正常启动。可通过环境变量
调整等待时间：

```console
setenv recovery_button_timeout 5
saveenv
```

设置为 `0` 可恢复为检测到按键后立即进入恢复。

项目不提供原厂 `tclinux/tclinux_slave/system` 回退命令。若新 UBI 未格式化、
缺少 `fit` 卷或 FIT 校验/启动失败，`run boot_ubi || http_recovery` 会直接
启动 Web Recovery；上传完整项目系统镜像时 Recovery 会自动重建 UBI。

如果系统已经启动到 OpenWrt/failsafe，需要清理 overlay 或重新设置密码：

```console
rm -rf /overlay
mount_root
passwd
reboot
```

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🧯 常见问题排查

| 症状 | 可能原因 | 处理 |
| --- | --- | --- |
| 自动启动停在 `Unknown command 'flash'` | 还在用原厂 `bootcmd`，未迁移环境 | 按[首启环境迁移](#-首启环境迁移)执行一次 `setenv`/`saveenv` |
| `tftpboot` 超时 / 下载失败 | IP 不对、TFTP 被防火墙拦截、网线没接 1G 口 | 确认电脑为 `192.168.0.205/24`、TFTP server 已运行并放行、网线接设备 1G 口 |
| `filesize` 不是 `0x200000` 或 CRC 与发布值不符 | 文件下载不完整或拿错产物 | 用 Release 内 `<board>-...-sha256sums.txt` 校验，重新下载 `mtd0-signed.bin` |
| `project UBI ... has no 'fit' volume` | NAND 仍是原厂 UBI 布局，还没有刷入项目系统镜像 | 先执行 `http_recovery`，上传 `ubi-squashfs-sysupgrade.itb`，由 Recovery 重建带 `fit` 卷的 `ubi` 分区 |
| 第二段 XMODEM 后进不了 Web Recovery | <kbd>RESET</kbd> 时序不对 | 传输 100% 前按住 <kbd>RESET</kbd>，等流水灯亮起再松开，无痕模式访问 |
| 打开 `http://192.168.1.1/` 却显示 OpenWrt LuCI 登录页 | 普通窗口命中浏览器缓存的旧 301 跳转（原 `uboot.html` 入口也已移除，`/` 即恢复页） | 改用无痕模式，或按 `Ctrl+F5` 强制刷新 |
| UBI 启动失败 | UBI 未格式化、缺少 `fit` 卷或 FIT 无法启动 | 等待自动进入 Web Recovery，上传完整项目系统镜像，Recovery 自动重建 UBI |

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🔧 本地构建

推荐在 WSL/Linux 文件系统中构建，或用 `git archive` 导出临时构建副本，避免
Windows drvfs 上脚本可执行位和符号链接问题：

```console
# Brightspeed Gemtek XG2010G
make CROSS_COMPILE=aarch64-linux-gnu- xg2010g_defconfig

# Brightspeed Gemtek XR1710G
make CROSS_COMPILE=aarch64-linux-gnu- xr1710g_defconfig

make CROSS_COMPILE=aarch64-linux-gnu- -j$(nproc)
```

> [!IMPORTANT]
> 本地构建出的 `u-boot.bin` 只是 BL33 候选文件。正式可刷写 `mtd0` 镜像请使用
> GitHub Actions/Releases 生成的 signed artifact。

更多板级细节见 [doc/board/airoha/xg2010g.rst](doc/board/airoha/xg2010g.rst)；
保留的 mtd0 前导区说明见
[board/airoha/xg2010g/firmware/README.md](board/airoha/xg2010g/firmware/README.md)。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 📄 GPL 说明

Upstream U-Boot remains GPL-2.0+ licensed. The original upstream notice is:

> (C) Copyright 2000 - 2013 Wolfgang Denk, DENX Software Engineering,
> wd@denx.de.

See [`COPYING`](COPYING) and [`Licenses/README`](Licenses/README) for the
complete U-Boot licensing information. This project keeps that GPL basis and
adds XG2010G/XR1710G board files, documentation, and GitHub Actions packaging.

---

<p align="center">
  <sub>
    Upstream <a href="https://github.com/u-boot/u-boot">U-Boot</a> (GPL-2.0+) · XG2010G/XR1710G board support by this project ·
    与 Brightspeed / Gemtek / Airoha 无从属关系
  </sub>
</p>

<p align="center">
  <a href="#top"><b>↑ 返回顶部</b></a>
</p>
