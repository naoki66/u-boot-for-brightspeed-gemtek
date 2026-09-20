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

---

## 📚 索引

- [📌 项目定位](#-项目定位)
- [🚀 快速开始](#-快速开始)
- [⚡ TTL/TFTP 刷入](#-ttltftp-刷入)
- [🆘 X 模式与 Web Recovery](#-x-模式与-web-recovery)
- [🧯 串口 TFTP 救砖与启动菜单](#-串口-tftp-救砖与启动菜单)
- [↩️ 恢复分区结构](#-恢复分区结构)
- [📂 Release 文件名规范](#-release-文件名规范)
- [🔧 本地构建](#-本地构建)
- [📖 详细文档](#-详细文档)
- [📄 GPL](#-gpl)

---

## 📌 项目定位

本仓库基于当前主线 U-Boot，加入 Brightspeed Gemtek XG2010G 与 XR1710G 的
Airoha AN7581 类平台支持（`xg2010g_defconfig` / `xr1710g_defconfig`），
用于替换原厂被限制功能的 `mtd0 bootloader`。刷写 bootloader 存在变砖风险，
请自行评估并承担操作后果。

| 项目 | 当前约束 |
| --- | --- |
| 设备 | Brightspeed Gemtek XG2010G · XR1710G（其他设备未验证） |
| 平台 | Airoha AN7581/AN7583 类启动链 |
| bootloader 分区 | `0x00000000-0x00200000`，固定 2 MiB |
| 工具版本 | Airoha TF-A `v2.15.0`（`Yuzhii0718/atf-airoha`，固定 commit `6cf15a14d74d`）；Mbed TLS 3.6.6 |

整条 TF-A 链路固定在同一棵树上：这棵树同时提供 BL2、BL31、`fiptool` 和
`cert_create`，所以写 FIP 的工具与解析 FIP 的代码不会版本错配。它不再使用
「上游 TF-A（`v2.10`）基座 + Airoha overlay 叠加」的旧结构 —— 那种结构用
`rsync -a --checksum` 且不带 `--delete`，overlay 携带的每个文件都静默覆盖
基础树，是历史上一次编译失败的同源机制。

Brightspeed Gemtek 设备的 `mtd0` 通常不是裸 `u-boot.bin`，而是一个从 BL2 开始验证的完整
启动包/FIP，包含 BL2、BL31、U-Boot/BL33 和证书材料。本仓库本地编译出的
`u-boot.bin` 只是 BL33 候选文件；正式刷机请使用 Actions/Releases 生成的
signed mtd0/FIP。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🚀 快速开始

> [!TIP]
> 先判断你处在哪种情况，再选择对应文件。**只有 `mtd0-signed.bin` 可以写 bootloader 完整分区。**

| 你的情况 | 使用的产物 | 操作要点 |
| --- | --- | --- |
| 🟢 能进原厂 U-Boot / TTL，要替换 bootloader | `<board>-...-mtd0-signed.bin`（`xg2010g-…` / `xr1710g-…`，按你的设备选择） | [TTL/TFTP 刷入](#-ttltftp-刷入)，只擦写 `0x000000` 起 `0x200000` |
| 🔴 mtd0 写坏、NAND 无法启动 | `<board>-...-ubi-preloader.bin` + `<board>-...-ubi-bl31-uboot.fip` | [X 模式 XMODEM 救砖](#-x-模式与-web-recovery)，再走 Web Recovery |
| 🔵 只升级系统，不动 bootloader | `ubi-squashfs-sysupgrade.itb` | 只刷 `ubi` 区域（`0x00600000` 起，440 MiB），必须重建 UBI |

**关键参数速查：**

| 参数 | 值 |
| --- | --- |
| `mtd0` 偏移 / 长度 | `0x00000000` / `0x200000`（2 MiB，擦写长度禁止超过此值） |
| 工厂校准（`uenv` / `dsd`） | 分别从 `0x00200000` / `0x00400000` 起，各 2 MiB，默认保留 |
| `ubi` 区域 | 偏移 `0x00600000`，长度 `0x1b800000`（440 MiB） |
| signed FIP 在 mtd0 内偏移 | `0x800` |
| U-Boot 加载地址 | `0x81800000` |
| TTL/TFTP 网段 | U-Boot `192.168.0.1`，电脑 `192.168.0.205/24`（网线接设备 1G 口） |
| Web Recovery | 网线接设备 1G 口，无痕模式打开 `http://192.168.0.1/`，系统固件上传会自动重建 UBI |

> [!WARNING]
> `mtd0` 只写 `0x200000`（2 MiB）。写长了就越界覆盖 `uenv` / `dsd` 工厂校准分区，
> 表现为无 MAC、校准数据丢失。**刷之前先把 `mtd0` / `uenv` / `dsd` 备份下来**
> （恢复页有这三个分区的下载按钮）。

> [!NOTE]
> 写 `mtd0` 前确认这 2 MiB 全是好块。网页 **Update U-Boot** 会自动扫 16 个擦除块，
> 有坏块即拒绝且**一个字节都不擦**；串口 `run tftp_flash` **没有**这道预检，走之前
> 自己 `mtd bad bootloader`（无输出即无坏块）。原理见[手册的刷写边界](doc/board/airoha/xg2010g.rst)。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## ⚡ TTL/TFTP 刷入

适用于已经能进原厂 U-Boot/TTL 命令行，并且当前 bootloader 提供 Airoha
`flash` 命令的情况。完整参数见[关键参数速查](#-快速开始)。

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

首次刷入后要执行一次环境迁移，把原厂 `bootargs` 切到本项目的 `ubi` 布局，
详见[手册](doc/board/airoha/xg2010g.rst)；要退回原厂分区结构见
[恢复分区结构](#-恢复分区结构)。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🆘 X 模式与 Web Recovery

如果 `mtd0` 写坏导致 NAND 无法启动，Airoha BootROM 通常仍可进入串口
X 模式加载临时引导。

1. 断电，按住 <kbd>RESET</kbd> 键，同时通电启动。
2. 按 <kbd>X</kbd> 或 <kbd>x</kbd>，终端显示 `CCCC` 后进入 XMODEM 接收。
3. 打开：文件 -> 传输 -> XMODEM -> 发送。
4. 发送 `<board>-...-ubi-preloader.bin`。
5. 传输完成后设备会自动重启。
6. 再次断电，按住 <kbd>RESET</kbd> 键，同时通电启动。
7. 提示 `Press x to load BL31 + U-Boot FIP` 时输入 <kbd>x</kbd>。
8. 再次打开 XMODEM 发送。
9. 发送 `<board>-...-ubi-bl31-uboot.fip`。
10. 第二段 XMODEM 进度到 100% 前按住 <kbd>RESET</kbd>，等设备灯进入流水式闪烁后再松开。
11. 网线接设备 **1G 口**，用**无痕（隐私）窗口**打开 `http://192.168.0.1/`。必须无痕：
    设备此前跑 OpenWrt 时该地址由 LuCI 301 跳到 `/cgi-bin/luci/`，普通窗口会命中缓存
    直接打开 LuCI 登录页（出现就按 `Ctrl+F5`）。设备 `uenv` 里已存 `ipaddr` 时会改用
    那个地址，以串口打印的 `recovery network: ... http://<addr>/` 为准。
12. 在恢复页上传。左侧三个目标共用一个文件选择框：`Firmware Recovery` 选
    `ubi-squashfs-sysupgrade.itb`，`Update U-Boot` 选 `<board>-...-mtd0-signed.bin`
    （**必须正好 2 MiB**）。**没有单独的 BL2 字段**：mtd0 是"0x800 前导区 + 一个合并
    FIP"的整体，BL2/BL31/BL33 与证书都在同一个 FIP 里，上传裸 `u-boot.bin`、裸
    `.fip` 或 `ubi-preloader.bin` 都会被后端拒绝。
13. 等待数分钟完成刷写，之后务必断电重启设备。

> [!TIP]
> 第二段报 `ERROR: LZMA: res 2 state 0` / `Failed to decompress image` 说明发错了文件：
> 确认第二次 XMODEM 发的是同板型 `<board>-...-ubi-bl31-uboot.fip`（不是
> `mtd0-signed.bin` / `fip-signed.bin` / `ubi-preloader.bin`），且不超过 `0x60000`
> —— 超长会在第二段被截断，表现是同样的 `res 2`。重发前用 `sha256sums.txt` 校验。

> [!NOTE]
> 救砖链**不需要** `bootext.ram`。它不在仓库中维护，只在原厂 XMODEM 路径失败时才
> 用作应急垫片，优先用已验证的原厂/平台版本。

详细的 Recovery 状态灯、网口选择与 bootcmd 失败回退说明见
[doc/board/airoha/xg2010g.rst](doc/board/airoha/xg2010g.rst) 与
[doc/board/airoha/xr1710g.rst](doc/board/airoha/xr1710g.rst)。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 🧯 串口 TFTP 救砖与启动菜单

Web Recovery 依赖 U-Boot 的 lwIP 网络栈；网口起不来或恢复页挂了时，U-Boot 里还有
一条**纯串口 + TFTP** 的写入通道。能进 U-Boot 提示符就能用。

```console
setenv serverip 192.168.0.254
setenv tftpboot_file xg2010g-...-mtd0-signed.bin
run net_init
run tftp_flash          # 完整 2 MiB mtd0 -> bootloader 分区
```

| 助手 | 作用 |
| --- | --- |
| `run tftp_flash` | 写完整 2 MiB `mtd0` 到 `bootloader` 分区 |
| `run tftp_flash_fit` | 把系统固件写进 UBI 的 `fit` 卷 |
| `run tftp_flash_uenv` / `run tftp_flash_dsd` | 恢复 2 MiB 出厂校准分区 |
| `run tftp_flash_manual` | **手动指定地址**：写 `${tftpboot_file}` 到 `${tftpboot_part}` 偏移 `${tftpboot_ofs}`、长度 `${tftpboot_len}` |

**没有"只刷 BL2"的助手**：mtd0 里的启动链是一个跨约 3.6 个擦除块的合并 FIP，只写
前 `0x20000` 会丢掉 BL31/BL33，设备既不启动、也回不到串口 X 模式。整块 mtd0 一律走
`run tftp_flash`。

**每个助手写完都会读回比对**（`mtd read` + `cmp.b`），一致才报
`written and read-back verified.`。不能省：NAND 写失败或碰坏块时，不读回就会
"看起来成功"，而镜像其实起不来。

`run boot_menu` 打开启动菜单。默认 `bootcmd` **不变**，仍是
`run boot_ubi || http_recovery`，无人值守开机照常启动、失败照常落到 Web Recovery。

`tftpboot_addr`（`0x90000000`）与 `$loadaddr`（`0x81800000`）分开，避免 TFTP 传输
与 Web Recovery 的上传缓冲互踩。

> [!WARNING]
> `tftp_flash_manual` 不做任何目标合法性检查——这是它的用途也是它的风险。
> 写错区域可能覆盖 `factory` / `dsd` 校准数据，先用 `mtd list` 确认，并先备份。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## ↩️ 恢复分区结构

分区表**编译在 bootloader 里**（DTS 的 `fixed-partitions`，不依赖 env 里的 `mtdparts`），
所以写回一个正确的 `mtd0` 就等于重建了分区表，不需要手工重新分区。整片 NAND 被写乱、
或刷了别的 bootloader 之后，按下表逐项恢复。

### 本项目布局（2M uboot + 2M env + 2M dsd + ubi system + reserved_bmt）

| 分区 | 起始 / 大小 | 内容从哪来 | 怎么写 |
| --- | --- | --- | --- |
| `bootloader` | `0x000000` / 2 MiB | `<board>-...-mtd0-signed.bin` | 串口 `run tftp_flash`，或网页 **Update U-Boot** |
| `uenv` | `0x00200000` / 2 MiB | 自己的 env 备份；没有就先 `saveenv` 写编译进去的默认环境 | 串口 `run tftp_flash_uenv`，或网页 **Factory Calibration → Flash env** |
| `dsd` | `0x00400000` / 2 MiB | **自己的 dsd 备份**（出厂校准，丢了不可再生成） | 串口 `run tftp_flash_dsd`，或网页 **Factory Calibration → Flash dsd** |
| `ubi` | `0x00600000` / 440 MiB | `ubi-squashfs-sysupgrade.itb` | 网页 **Firmware Recovery**：擦掉并重建整片 `ubi` |
| `reserved_bmt` | `0x1be00000` / 66 MiB | — | **一律不写**。坏块管理与替代块预留区，写它会毁掉坏块表 |

顺序是 `bootloader` → `uenv` / `dsd` → `ubi`：分区表来自 `bootloader`，它必须最先恢复；
`reserved_bmt` 全程不碰。串口只有"往**已存在**的 `fit` 卷写固件"（`run tftp_flash_fit`），
整片 UBI 重建只能走网页。

### 原厂布局

原厂分区表在原厂 `mtd0` 里，所以**写回原厂 `mtd0` 就恢复了原厂分区结构**。

| 步骤 | 操作 |
| --- | --- |
| 1 | 写回 2 MiB 原厂 `mtd0`。首选串口 `run tftp_flash` —— 它只断言 2 MiB 加读回比对，任何 2 MiB 镜像都能写；网页 **Update U-Boot** 也行，但它会额外校验 FIP 结构（含 platform ToC flag），原厂镜像可能被拒 |
| 2 | 重启，`mtd list` 确认分区标签已回到原厂那套（`tclinux` / `tclinux_slave` / `system`） |
| 3 | 按**原厂偏移**恢复数据分区内容（需要自己的原厂固件备份） |

顺序不能反：原厂分区表在原厂 `mtd0` 里，先恢复数据分区必然写错位置。

**能力边界**

- ✅ 恢复页可下载 `mtd0`、`env`(=`uenv`)、`dsd`（各 2 MiB），也可写回 `mtd0` 与这两个校准分区。
- ❌ 仓库**不提供**完整原厂 `mtd0`，也不提供原厂固件本体（`tclinux` / `tclinux_slave` /
  `system`），只保留 `0x800` 前导区（`board/airoha/<board>/firmware/`）。这两样只能
  来自你自己的备份。
- ⚠️ 恢复页不提供 `ubi` 区（440 MiB）的下载；整片导出只能串口 `mtd read` 分段读。

> [!IMPORTANT]
> 本项目的 `ubi` 布局（`0x00600000` 起 440 MiB，单一 `ubi` 分区）与原厂的
> `tclinux` / `system` 分法**不兼容**。写回原厂 `mtd0` 只恢复分区**结构**，数据分区里的
> **内容**不会回来 —— 那必须是你刷机前自己留下的备份。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 📂 Release 文件名规范

所有产物文件名遵循 `<board>-YYYY-M-D-<commit>-<suffix>` 规范：

- `<board>` ∈ {`xg2010g`, `xr1710g`}
- `YYYY-M-D` 是触发 release 的 UTC+8 当日日期，月份和日子不带前导 0，与
  `date +%Y-%-m-%-d` 的输出一致（例如 `2026-9-6`）
- `<commit>` 是触发该次 workflow 的 commit 短哈希（前 12 位 hex）

| 文件 | 用途 |
| --- | --- |
| `<board>-...-mtd0-signed.bin` | 完整 2 MiB `/dev/mtd0` bootloader 镜像，用于替换 `bootloader` 分区 |
| `<board>-...-fip-signed.bin` | signed FIP 本体，位于完整 mtd0 镜像的 `0x800` 偏移 |
| `<board>-...-ubi-preloader.bin` | 包含 BL2 和 `tb-fw-cert` 的 signed FIP，用于 X 模式第一段 XMODEM |
| `<board>-...-ubi-bl31-uboot.fip` | BL31 + U-Boot/BL33 FIP，用于 X 模式第二段 XMODEM |
| `<board>-...-bootext-bl2.bin` | BootROM X 模式应急垫片（`mtd0-prefix.bin` + 本仓库编译的 BL2，**未真机验证**） |
| `<board>-...-bl31.bin` | 源码构建的 BL31 Airoha LZMA 固件，便于核对和离线调试 |
| `<board>-...-u-boot-raw.bin` | 裸 U-Boot/BL33，仅供调试分析 |
| `<board>-...-sha256sums.txt` | 该板所有产物 SHA256 |
| `<board>-...-build-info.txt` | 该板构建 commit、日期、签名状态和镜像边界 |

校验产物：

```console
# Linux / WSL
sha256sum -c <board>-...-sha256sums.txt

# Windows
CertUtil -hashfile <board>-...-mtd0-signed.bin SHA256
```

> [!IMPORTANT]
> 只有 `<board>-...-mtd0-signed.bin` 是完整 2 MiB `mtd0` 签名镜像。其它裸文件或
> FIP 文件用于 X 模式 XMODEM 救砖或离线调试，不要当作完整 `mtd0` 直接写入
> `0x00000000`。

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
> GitHub Actions/Releases 生成的 signed artifact（CI 流程与所需 Secrets 见
> `doc/board/airoha/xg2010g.rst`）。

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 📖 详细文档

| 主题 | 文档 |
| --- | --- |
| XG2010G 启动链、BL2/BL31、bootargs 完整解读、NAND 分区、刷写边界、CI 变量与产出 | [doc/board/airoha/xg2010g.rst](doc/board/airoha/xg2010g.rst) |
| XR1710G 硬件差异、bootargs 现状、Recovery 网口/GPIO、CI 变量 | [doc/board/airoha/xr1710g.rst](doc/board/airoha/xr1710g.rst) |
| XG2010G 内嵌 mtd0 前导区 SHA256 校验 | [board/airoha/xg2010g/firmware/README.md](board/airoha/xg2010g/firmware/README.md) |
| U-Boot 项目主文档 | [README](https://github.com/u-boot/u-boot/blob/master/README) |

<p align="right"><a href="#top"><b>↑ 返回顶部</b></a></p>

## 📄 GPL

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
