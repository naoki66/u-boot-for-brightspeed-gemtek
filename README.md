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
| 工具版本 | TF-A tooling `v2.13.0`；Airoha TF-A 基于 `v2.10` 与固定 overlay commit |

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
| Web Recovery | 无痕模式打开 `http://192.168.1.1/`，系统固件上传会自动重建 UBI |

> [!WARNING]
> `mtd0` 的正确长度是 `0x200000`，即 2 MiB。使用其他擦写长度会越过
> 工厂校准分区（`uenv`、`dsd`），破坏系统区域，导致系统异常、无 MAC、校准文件丢失等。

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

首次刷入后还需要执行一次环境迁移，把原厂 `bootargs` 切换到本项目的
`ubi` 布局，详见 [doc/board/airoha/xg2010g.rst](doc/board/airoha/xg2010g.rst)。

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
11. 浏览器使用**无痕模式**访问 `http://192.168.1.1/`（网线可接设备任一网口，含 WAN 口）。
12. 选择系统镜像 `ubi-squashfs-sysupgrade.itb`；`BL2` 选择
    `<board>-...-ubi-preloader.bin`，`U-Boot` 选择
    `<board>-...-ubi-bl31-uboot.fip`。
13. 等待数分钟完成刷写，之后务必断电重启设备。

> [!CAUTION]
> 必须使用**无痕（隐私）窗口**打开 `http://192.168.1.1/`。设备此前运行 OpenWrt 时，
> 同一地址曾由 LuCI 提供 301 跳转到登录页 `http://192.168.1.1/cgi-bin/luci/`，普通
> 浏览器窗口会命中本地缓存的跳转记录，直接打开 OpenWrt 登录页而非 Recovery 页。
> 无痕窗口不带缓存和 Cookie，可避开该问题；若仍出现 LuCI 页面，按 `Ctrl+F5` 强制
> 刷新，或换用其他浏览器验证。

> [!NOTE]
> 救砖链**不需要** `bootext.ram`：X 模式下直接发送 `ubi-preloader.bin` 即可。
> `bootext.ram` 属于平台救援链文件，不在仓库中维护；只在原厂 XMODEM 路径失败时
> 才考虑用作应急垫片，并优先使用已验证的原厂/平台版本。

详细的 Recovery 状态灯、网口选择与 bootcmd 失败回退说明见
[doc/board/airoha/xg2010g.rst](doc/board/airoha/xg2010g.rst) 与
[doc/board/airoha/xr1710g.rst](doc/board/airoha/xr1710g.rst)。

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
| `<board>-...-ubi-bl31-uboot.fip` | BL31 + U-Boot/BL33 FIP，用于 X 模式第二段 XMODEM 和 Web Recovery |
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
> FIP 文件用于救砖、调试或 Web Recovery，不要当作完整 `mtd0` 直接写入
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
