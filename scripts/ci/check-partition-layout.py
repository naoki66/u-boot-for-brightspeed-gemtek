"""Cross-source consistency check for the AN7581 NAND partition layout.

Why this exists
---------------

The partition layout of these boards is written down in *four* independent
places, and nothing used to tie them together:

  1. ``arch/arm/dts/<board>.dts`` -- ``fixed-partitions``. This is the only
     table U-Boot itself reads, so it is the anchor for every check below.
  2. ``board/airoha/an7581/an7581_rfb.c`` -- the ``XG2010G_UBI_*`` constants
     that ``recovery_board_ops`` publishes. The web recovery server *refuses*
     to touch a ``ubi`` MTD whose geometry does not match them, so a drift
     here is a silent on-device failure with no build-time signal.
  3. ``board/airoha/an7581/<board>.env`` plus ``include/env/airoha/an7581-tftp.env``
     -- the TFTP rescue helpers assert an exact image size before erasing
     (``itest.l ${filesize} -eq 0x200000``). If a partition is resized and the
     assertion is not, the helper fails closed but with a misleading message.
  4. ``.github/workflows/build-mtd0.yml`` -- the composed mtd0 image geometry
     (``DEFAULT_MTD0_SIZE``, ``DEFAULT_FIP_OFFSET``, ``BL23_FIP_MAX_SIZE``).

The boot chain adds a fifth, harder constraint that lives in the pinned TF-A
tree, not in this repository:

  * BL23 reads the second-stage FIP from ``PLAT_ECNT_FIP_OFFSET`` in mtd0 into
    RAM at ``PLAT_ECNT_FIP_BASE`` and never reads more than
    ``PLAT_ECNT_FIP_MAX_SIZE`` bytes. So the ``bootloader`` partition must be
    at least ``PLAT_ECNT_FIP_OFFSET + PLAT_ECNT_FIP_MAX_SIZE`` long, or the
    FIP runs off the end of its own partition.
  * BL23 *can* be built to load the FIP from a UBI volume instead
    (``fip_ubi_policy``, volume name hard-coded to ``fip``). That path locates
    the UBI partition at ``UBI_START_ADDR``, which defaults to ``0x20000`` --
    incompatible with this repository's layout, where ``ubi`` starts at
    ``0x600000``.

    ``plat_ecnt_io_setup()`` assigns ``fip_memmap_policy`` unconditionally and
    only overwrites it with ``fip_ubi_policy`` under ``TCSUPPORT_UBI_SUPPORT``,
    so the mtd0 path is the default and the UBI path is the opt-in. The v2.15
    Makefile provides no ``add_define`` for that macro, so it can only reach
    the compiler through ``BSP_CFLAGS``; ``build-atf.sh`` passes no
    ``BSP_CFLAGS`` at all. Load-bearing checks ``fip-flag-vs-layout``,
    ``xmodem-vs-atf`` and ``ecc-dma-vs-atf`` below keep it that way.
  * ``build-atf.sh`` must keep ``TCSUPPORT_EMMC=1``. ``bl2_image_load_v2.c``
    gates the memmap/XMODEM rescue path (``bl2_mem_params_backup()``,
    ``plat_ecnt_io_switch_to_memmap()``, ``fip_image_xmodem_load()``) and the
    matching stubs in ``ecnt_bl2_mem_params_desc.c`` on
    ``TCSUPPORT_UBI_SUPPORT || TCSUPPORT_EMMC``. These boards have no eMMC; the
    switch is purely the key that keeps the serial recovery path compiled in.
  * ``build-atf.sh`` must keep ``TCSUPPORT_SPI_NAND_FLASH_ECC_DMA`` *undefined*.
    ``SPI_NAND_Flash_Init()`` declares ``dma_on`` unconditionally but only ever
    touches it inside that macro's block, so the tree compiles only with the
    macro set -- which is how the vendor's own ``build.sh`` builds it, through
    ``BSP_CFLAGS``. We keep it off because the guard around that block,
    ``defined(TCSUPPORT_SPI_NAND_FLASH_ECC_DMA) && (!defined(IMAGE_BL2) ||
    defined(IMAGE_BL23))``, does not do what it says: ``IMAGE_BL2`` is defined
    nowhere in the tree, so ``!defined(IMAGE_BL2)`` is always true, the ``||``
    clause is dead, and the guard collapses to the bare macro. Defining it
    would therefore pull SPI controller DMA into BL21 and BL22 as well -- the
    two stages Airoha's own comment in that block rules out ("SPI controller
    DMA does not support these two SRAM"). Both the image currently flashed on
    these boards and the tree of the project that ships this board
    (``pbs05/uboot-an758x``, TF-A v2.10 lineage) run with the macro undefined.
    Check ``ecc-dma-vs-atf`` holds the line; the source patch that lets the
    macro stay off lives in ``board/airoha/xg2010g/atf/prepare-atf.py``.

Note what is deliberately *not* checked: the ``flash_table.bin`` that
``spi_nand_flash_table.c`` emits is a NAND *device* table (manufacturer/device
id, page/erase/OOB geometry), not a partition table, and BL2 carries no copy of
this repository's partition names. The two are related only through the chip
geometry, which check ``ubi-geometry`` covers.

Run from the repo root, once per board:

    python3 scripts/ci/check-partition-layout.py --board xg2010g
    python3 scripts/ci/check-partition-layout.py --board xg2010g \\
        --atf-dir trusted-firmware-a --require-atf

Exits 0 when every check passes, 1 (with a clear message) otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BOARD_SRC = REPO / "board" / "airoha" / "an7581" / "an7581_rfb.c"
ATF_BUILD = REPO / "board" / "airoha" / "xg2010g" / "atf" / "build-atf.sh"
TFTP_ENV = REPO / "include" / "env" / "airoha" / "an7581-tftp.env"
WORKFLOW = REPO / ".github" / "workflows" / "build-mtd0.yml"

# The boards this repository ships. Both reuse one board source file, so the
# board-side geometry is shared and only the DTS/env/defconfig differ.
BOARDS = ("xg2010g", "xr1710g")

# W25N04K geometry, as measured on the target (doc/board/airoha/xg2010g.rst:
# "512 MiB W25N04K, erase block 128 KiB, page 2 KiB, OOB 128 bytes").
CHIP_SIZE = 0x20000000
CHIP_ERASE_SIZE = 0x20000
CHIP_WRITE_SIZE = 0x800
CHIP_OOB_SIZE = 0x80

REQUIRED_LABELS = ("bootloader", "uenv", "dsd", "ubi", "reserved_bmt")

# Where the shared env file and the board env file are expected to agree: the
# helper name whose literal size assertion must equal the partition it writes.
# Every entry is helper -> partition label, and each helper must assert the
# size with 'itest.l ${filesize} -eq <len>' before erasing, so the comparison
# in check_env() only has to cover the two 2 MiB calibration partitions.  The
# mtd0 helper needs no entry: it asserts ${tftpboot_size}, and that variable is
# already checked against the bootloader partition below.
TFTP_ENV_SIZE_RULES = {
    "tftp_flash_uenv": "uenv",
    "tftp_flash_dsd": "dsd",
}


@dataclass
class Part:
    label: str
    start: int
    size: int
    read_only: bool
    node: str

    @property
    def end(self) -> int:
        return self.start + self.size


@dataclass
class CheckResult:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, check: str, msg: str) -> None:
        self.failures.append(f"[{check}] {msg}")

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures


def strip_c_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def strip_shell_comments(text: str) -> str:
    """Drop shell comments so that flag detection reads code, not prose.

    build-atf.sh documents *why* it leaves ``TCSUPPORT_UBI_SUPPORT`` off, so a
    plain substring search would find the macro in a comment and conclude the
    opposite. Only an unquoted ``#`` that starts a word begins a comment.
    """
    out_lines: list[str] = []
    for line in text.splitlines():
        quote = ""
        cut = len(line)
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = ""
                continue
            if ch in "'\"":
                quote = ch
                continue
            if ch == "#" and (i == 0 or line[i - 1] in " \t"):
                cut = i
                break
        out_lines.append(line[:cut])
    return "\n".join(out_lines)


def parse_int(text: str) -> int:
    """Accept 0x... / decimal, tolerating C spellings.

    Real inputs include ``(0x800)``, ``UL(0x100000)`` and
    ``0x1b800000ULL``, so unwrap macros and expressions before converting.
    """
    text = text.strip()
    text = re.sub(r"\s*(//.*|/\*.*)$", "", text).strip()
    text = re.sub(r"(ULL|UL|U|L|ll|ul|u|llu|LLU)$", "", text.strip())
    # Unwrap one macro call or parenthesised expression, then retry.
    m = re.match(r"^([A-Za-z_]\w*)?\s*\((?P<inner>.*)\)$", text.strip(), re.DOTALL)
    if m:
        return parse_int(m.group("inner"))
    return int(text, 0)


def is_power_of_two(value: int) -> bool:
    """Mirror fiptool's ``is_power_of_2()``, where zero is *not* a power of two.

    ``tools/fiptool/fiptool.c`` in the pinned TF-A tree parses ``--align`` with::

        align = strtoul(arg, &endptr, 0);
        if (*endptr != '\\0' || !is_power_of_2(align) || errno != 0)
            log_errx("Invalid alignment: %s", arg);

    and defines ``is_power_of_2(x)`` as ``x && !(x & (x - 1))``. So a value
    like ``0x300`` is rejected outright. Note that ``strtoul`` with base 0 makes
    a leading ``0`` mean octal, which is also what the shell's ``$(( ))`` does,
    so the workflow's own coercion agrees with fiptool and the two can share
    this predicate.
    """
    return value > 0 and (value & (value - 1)) == 0


# ---------------------------------------------------------------------------
# 1. DTS fixed-partitions -- the anchor table
# ---------------------------------------------------------------------------


def parse_dts_partitions(path: Path, result: CheckResult) -> list[Part]:
    text = strip_c_comments(path.read_text(encoding="utf-8"))
    block = re.search(
        r"partitions\s*\{(?P<body>.*?)\n\t\};", text, re.DOTALL
    )
    if not block:
        result.fail("dts", f"{path}: fixed-partitions block not found")
        return []

    parts: list[Part] = []
    for node in re.finditer(
        r"(?P<node>[\w-]+@[0-9a-fA-F]+)\s*\{(?P<body>[^}]*)\}", block.group("body")
    ):
        body = node.group("body")
        label = re.search(r'label\s*=\s*"([^"]+)"', body)
        reg = re.search(r"reg\s*=\s*<\s*([^>]+)>", body)
        if not label or not reg:
            result.fail(
                "dts",
                f"{path}: partition {node.group('node')} lacks label or reg",
            )
            continue
        cells = reg.group(1).split()
        if len(cells) != 2:
            result.fail(
                "dts",
                f"{path}: partition {label.group(1)} reg must have 2 cells, "
                f"got {len(cells)}",
            )
            continue
        parts.append(
            Part(
                label=label.group(1),
                start=parse_int(cells[0]),
                size=parse_int(cells[1]),
                read_only="read-only" in body,
                node=node.group("node"),
            )
        )
    if not parts:
        result.fail("dts", f"{path}: no partitions parsed")
    return parts


def check_partition_table(result: CheckResult, dts_path: Path, parts: list[Part]) -> None:
    if not parts:
        return

    found = [p.label for p in parts]
    missing = [lbl for lbl in REQUIRED_LABELS if lbl not in found]
    if missing:
        result.fail(
            "dts-table",
            f"{dts_path.name}: missing required partitions: {', '.join(missing)}",
        )
    extra = [lbl for lbl in found if lbl not in REQUIRED_LABELS]
    if extra:
        result.note(f"{dts_path.name}: unexpected partitions: {', '.join(extra)}")

    if parts[0].start != 0:
        result.fail(
            "dts-table",
            f"{dts_path.name}: first partition starts at 0x{parts[0].start:x}, "
            f"must start at 0x0",
        )

    for prev, cur in zip(parts, parts[1:]):
        if cur.start < prev.end:
            result.fail(
                "dts-table",
                f"{dts_path.name}: {cur.label}@0x{cur.start:x} overlaps "
                f"{prev.label} (ends 0x{prev.end:x})",
            )
        elif cur.start > prev.end:
            result.fail(
                "dts-table",
                f"{dts_path.name}: gap of 0x{cur.start - prev.end:x} bytes "
                f"between {prev.label} and {cur.label}",
            )

    total = parts[-1].end
    if total != CHIP_SIZE:
        result.fail(
            "dts-table",
            f"{dts_path.name}: partitions end at 0x{total:x}, chip is "
            f"0x{CHIP_SIZE:x}",
        )

    last = parts[-1]
    if last.label == "reserved_bmt" and not last.read_only:
        result.fail(
            "dts-table",
            f"{dts_path.name}: reserved_bmt must be read-only (it holds the "
            f"bad-block table and must never be written by OpenWrt)",
        )


def part_by_label(parts: list[Part], label: str) -> Part | None:
    for p in parts:
        if p.label == label:
            return p
    return None


# ---------------------------------------------------------------------------
# 2. Board-side geometry (board/airoha/an7581/an7581_rfb.c)
# ---------------------------------------------------------------------------


def parse_board_geometry(path: Path, result: CheckResult) -> dict[str, object]:
    text = strip_c_comments(path.read_text(encoding="utf-8"))

    def macro(name: str) -> str | None:
        m = re.search(rf"#define\s+{name}\s+(?P<val>[^\n]+)", text)
        return m.group("val").strip() if m else None

    out: dict[str, object] = {}
    int_macros = {
        "ubi_size": "XG2010G_UBI_SIZE",
        "ubi_erase": "XG2010G_UBI_ERASE_SIZE",
        "ubi_write": "XG2010G_UBI_WRITE_SIZE",
        "ubi_oob": "XG2010G_UBI_OOB_SIZE",
        "uenv_payload": "XG2010G_UENV_SIZE",
        "uenv_erase": "XG2010G_UENV_ERASE_SIZE",
    }
    for key, name in int_macros.items():
        raw = macro(name)
        if raw is None:
            result.fail("board", f"{path.name}: #define {name} not found")
            continue
        try:
            out[key] = parse_int(raw)
        except ValueError:
            result.fail("board", f"{path.name}: cannot parse {name} = {raw!r}")

    for key, name in (
        ("ubi_part", "XG2010G_UBI_PART"),
        ("uenv_part", "XG2010G_UENV_PART"),
        ("dsd_part", "XG2010G_DSD_PART"),
    ):
        raw = macro(name)
        if raw is None:
            result.fail("board", f"{path.name}: #define {name} not found")
            continue
        out[key] = raw.strip().strip('"')
    return out


def check_board_geometry(
    result: CheckResult, board: dict[str, object], parts: list[Part]
) -> None:
    if not board or not parts:
        return

    if board.get("ubi_erase") != CHIP_ERASE_SIZE:
        result.fail(
            "ubi-geometry",
            f"XG2010G_UBI_ERASE_SIZE = 0x{board.get('ubi_erase', 0):x}, "
            f"chip erase block is 0x{CHIP_ERASE_SIZE:x}",
        )
    if board.get("ubi_write") != CHIP_WRITE_SIZE:
        result.fail(
            "ubi-geometry",
            f"XG2010G_UBI_WRITE_SIZE = 0x{board.get('ubi_write', 0):x}, "
            f"chip page size is 0x{CHIP_WRITE_SIZE:x}",
        )
    if board.get("ubi_oob") != CHIP_OOB_SIZE:
        result.fail(
            "ubi-geometry",
            f"XG2010G_UBI_OOB_SIZE = 0x{board.get('ubi_oob', 0):x}, "
            f"chip OOB is 0x{CHIP_OOB_SIZE:x}",
        )

    ubi = part_by_label(parts, "ubi")
    if ubi is None:
        return
    if board.get("ubi_part") != ubi.label:
        result.fail(
            "board-vs-dts",
            f"XG2010G_UBI_PART = {board.get('ubi_part')!r} but the DTS labels "
            f"the UBI partition {ubi.label!r}",
        )
    if board.get("ubi_size") != ubi.size:
        result.fail(
            "board-vs-dts",
            f"XG2010G_UBI_SIZE = 0x{board.get('ubi_size', 0):x} but the DTS "
            f"ubi partition is 0x{ubi.size:x} -- recovery_board_ops.mtd_ubi_valid() "
            f"would reject the real MTD at runtime",
        )

    uenv = part_by_label(parts, "uenv")
    if uenv is not None:
        if board.get("uenv_part") != uenv.label:
            result.fail(
                "board-vs-dts",
                f"XG2010G_UENV_PART = {board.get('uenv_part')!r} but the DTS "
                f"labels it {uenv.label!r}",
            )
        if uenv.size < int(board.get("uenv_erase", 0)):
            result.fail(
                "board-vs-dts",
                f"uenv partition is 0x{uenv.size:x} but "
                f"XG2010G_UENV_ERASE_SIZE is 0x{int(board.get('uenv_erase', 0)):x}",
            )

    dsd = part_by_label(parts, "dsd")
    if dsd is not None and board.get("dsd_part") != dsd.label:
        result.fail(
            "board-vs-dts",
            f"XG2010G_DSD_PART = {board.get('dsd_part')!r} but the DTS labels "
            f"it {dsd.label!r}",
        )


# ---------------------------------------------------------------------------
# 3. Environment helpers
# ---------------------------------------------------------------------------


def parse_board_env(path: Path, result: CheckResult) -> dict[str, int]:
    if not path.exists():
        result.fail("env", f"{path}: board environment file not found")
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for key in ("tftpboot_size", "recovery_size_uboot"):
        m = re.search(rf"^{key}\s*=\s*(?P<val>[0-9a-fA-Fx]+)\s*$", text, re.MULTILINE)
        if not m:
            result.fail("env", f"{path.name}: {key} not found")
            continue
        out[key] = parse_int(m.group("val"))
    return out


def parse_tftp_env_sizes(path: Path, result: CheckResult) -> dict[str, int]:
    """Extract the literal size each tftp_flash_* helper asserts before erasing."""
    if not path.exists():
        result.fail("env", f"{path}: shared tftp environment not found")
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, int] = {}
    for helper in ("tftp_flash_uenv", "tftp_flash_dsd"):
        # The helper reads "itest.l ${filesize} -eq 0x200000", so the closing
        # brace of the variable reference has to be part of the pattern.
        m = re.search(
            rf"^{helper}=.*?filesize\}}\s+-eq\s+(?P<val>0x[0-9a-fA-F]+)",
            text,
            re.MULTILINE,
        )
        if not m:
            result.fail(
                "env",
                f"{path.name}: {helper} no longer asserts an exact filesize",
            )
            continue
        out[helper] = parse_int(m.group("val"))
    return out


def check_env(
    result: CheckResult,
    env: dict[str, int],
    tftp: dict[str, int],
    parts: list[Part],
    defconfig: Path,
) -> None:
    if not parts:
        return
    bootloader = part_by_label(parts, "bootloader")
    uenv = part_by_label(parts, "uenv")
    dsd = part_by_label(parts, "dsd")

    if bootloader and "tftpboot_size" in env:
        if env["tftpboot_size"] != bootloader.size:
            result.fail(
                "env-vs-dts",
                f"tftpboot_size = 0x{env['tftpboot_size']:x} but the bootloader "
                f"partition is 0x{bootloader.size:x}; tftp_flash would refuse "
                f"every correctly sized mtd0 image",
            )
    if bootloader and "recovery_size_uboot" in env:
        if env["recovery_size_uboot"] != bootloader.size:
            result.fail(
                "env-vs-dts",
                f"recovery_size_uboot = 0x{env['recovery_size_uboot']:x} but the "
                f"bootloader partition is 0x{bootloader.size:x}",
            )

    parts_by_label = {"uenv": uenv, "dsd": dsd}
    for helper, label in TFTP_ENV_SIZE_RULES.items():
        part = parts_by_label.get(label)
        if part is None or helper not in tftp:
            continue
        if tftp[helper] != part.size:
            result.fail(
                "env-vs-dts",
                f"{helper} asserts filesize == 0x{tftp[helper]:x} but the "
                f"{part.label} partition is 0x{part.size:x}",
            )

    if uenv is not None and defconfig.exists():
        cfg = defconfig.read_text(encoding="utf-8")

        def cfg_val(name: str) -> str | None:
            m = re.search(rf"^{name}=(?P<val>[^\n]+)", cfg, re.MULTILINE)
            return m.group("val").strip() if m else None

        env_size = cfg_val("CONFIG_ENV_SIZE")
        if env_size is None:
            result.fail("env", f"{defconfig.name}: CONFIG_ENV_SIZE not set")
        else:
            size = parse_int(env_size)
            if size > uenv.size:
                result.fail(
                    "env-vs-dts",
                    f"CONFIG_ENV_SIZE = 0x{size:x} does not fit the uenv "
                    f"partition (0x{uenv.size:x})",
                )

        env_dev = cfg_val("CONFIG_ENV_MTD_DEV")
        if env_dev is not None:
            dev = env_dev.strip().strip('"')
            if dev != uenv.label:
                result.fail(
                    "env-vs-dts",
                    f"CONFIG_ENV_MTD_DEV = {dev!r} but the DTS labels the "
                    f"environment partition {uenv.label!r} -- saveenv would "
                    f"target a non-existent MTD",
                )
        env_off = cfg_val("CONFIG_ENV_OFFSET")
        if env_off is not None and parse_int(env_off) != 0:
            result.note(
                f"{defconfig.name}: CONFIG_ENV_OFFSET = 0x{parse_int(env_off):x}; "
                f"the recovery uenv consumers assume the environment starts at "
                f"the partition base"
            )


# ---------------------------------------------------------------------------
# 4. Workflow geometry
# ---------------------------------------------------------------------------


def parse_workflow_env(path: Path, result: CheckResult) -> dict[str, int]:
    if not path.exists():
        result.fail("workflow", f"{path}: workflow not found")
        return {}
    text = path.read_text(encoding="utf-8")
    wanted = (
        "DEFAULT_MTD0_SIZE",
        "DEFAULT_FIP_OFFSET",
        "DEFAULT_FIP_ALIGN",
        "BL23_FIP_MAX_SIZE",
        "BL2_XMODEM_MAX_SIZE",
    )
    out: dict[str, int] = {}
    for key in wanted:
        m = re.search(rf'^\s*{key}:\s*"(?P<val>[^"]+)"', text, re.MULTILINE)
        if not m:
            result.fail("workflow", f"{path.name}: {key} not found in env block")
            continue
        out[key] = parse_int(m.group("val"))
    return out


def check_workflow(
    result: CheckResult, wf: dict[str, int], parts: list[Part]
) -> None:
    bootloader = part_by_label(parts, "bootloader")
    if bootloader and "DEFAULT_MTD0_SIZE" in wf:
        if wf["DEFAULT_MTD0_SIZE"] != bootloader.size:
            result.fail(
                "workflow-vs-dts",
                f"DEFAULT_MTD0_SIZE = 0x{wf['DEFAULT_MTD0_SIZE']:x} but the "
                f"bootloader partition is 0x{bootloader.size:x}; the composed "
                f"mtd0 image would not exactly fill its partition",
            )
    if wf and "BL2_XMODEM_MAX_SIZE" in wf:
        # The mtd_write_bl2 helper blanks 0x20000 bytes before the payload.
        bl2_stage = 0x20000
        if wf["BL2_XMODEM_MAX_SIZE"] >= bl2_stage:
            result.fail(
                "workflow",
                f"BL2_XMODEM_MAX_SIZE = 0x{wf['BL2_XMODEM_MAX_SIZE']:x} does not "
                f"leave room in the 0x{bl2_stage:x} BL2 staging window",
            )
    if "DEFAULT_FIP_ALIGN" in wf and not is_power_of_two(wf["DEFAULT_FIP_ALIGN"]):
        # fiptool's get_image_align() rejects a non-power-of-two --align while
        # packing, which is far too late: it runs after the full U-Boot and
        # TF-A build. Validate the committed default here so the seconds-level
        # gate catches it, locally as well as in CI.
        #
        # The value that actually reaches --align is the per-board
        # ${BOARD_UPPER}_FIP_ALIGN variable, which lives in the repository's
        # GitHub settings rather than in the tree and therefore cannot be read
        # from here. Passing that resolved value in as a parameter would be
        # dead code, because the build-mtd0 "Resolve per-board identifiers and
        # parameters" step already rejects it with the same predicate before
        # this gate runs. The two checks are complementary: this one owns the
        # committed default, that one owns the variable.
        result.fail(
            "workflow",
            f"DEFAULT_FIP_ALIGN = 0x{wf['DEFAULT_FIP_ALIGN']:x} is not a power "
            f"of two; fiptool aborts with \"Invalid alignment\" while packing "
            f"the FIP, after the whole U-Boot and TF-A chain has been built",
        )


# ---------------------------------------------------------------------------
# 5. Pinned TF-A boot-chain constraints
# ---------------------------------------------------------------------------


def parse_atf(path: Path, result: CheckResult) -> dict[str, int]:
    plat_def = path / "plat" / "ecnt" / "en7523" / "include" / "platform_def.h"
    ubi_src = path / "plat" / "ecnt" / "en7523" / "bl2_boot_nand_ubi.c"
    if not plat_def.exists():
        result.fail("atf", f"{plat_def}: not found -- is --atf-dir a TF-A tree?")
        return {}

    text = strip_c_comments(plat_def.read_text(encoding="utf-8"))
    out: dict[str, int] = {}

    m = re.search(r"#define\s+PLAT_ECNT_FIP_OFFSET\s+(?P<val>[^\n]+)", text)
    if not m:
        result.fail("atf", f"{plat_def}: PLAT_ECNT_FIP_OFFSET not found")
    else:
        out["fip_offset"] = parse_int(m.group("val"))

    # PLAT_ECNT_FIP_MAX_SIZE is defined several times behind #if branches; pick
    # the one selected by TCSUPPORT_TCBOOT_1MB_SIZE, which build-atf.sh sets.
    m = re.search(r"TCSUPPORT_TCBOOT_1MB_SIZE(?P<tail>.*?)#endif", text, re.DOTALL)
    if m and (mm := re.search(r"#define\s+PLAT_ECNT_FIP_MAX_SIZE\s+(?P<val>[^\n]+)", m.group("tail"))):
        out["fip_max_size"] = parse_int(mm.group("val"))
    else:
        result.note(
            "could not resolve PLAT_ECNT_FIP_MAX_SIZE for "
            "TCSUPPORT_TCBOOT_1MB_SIZE; skipping the window check"
        )

    if ubi_src.exists():
        ubi_text = strip_c_comments(ubi_src.read_text(encoding="utf-8"))
        m = re.search(
            r"#define\s+UBI_START_ADDR\s+0x(?P<val>[0-9a-fA-F]+)", ubi_text
        )
        if m:
            out["ubi_start_default"] = int(m.group("val"), 16)
        if "OVERRIDE_UBI_START_ADDR" in ubi_text:
            out["ubi_start_overridable"] = 1
    return out


def read_atf_build(result: CheckResult) -> str:
    """build-atf.sh with shell comments removed, or "" when it is missing."""
    if not ATF_BUILD.exists():
        result.fail("atf-mode", f"{ATF_BUILD} not found")
        return ""
    return strip_shell_comments(ATF_BUILD.read_text(encoding="utf-8"))


def atf_build_flags(code: str) -> dict[str, bool]:
    """Read the load-bearing switches out of build-atf.sh.

    ``ubi`` must stay False: defining ``TCSUPPORT_UBI_SUPPORT`` (as a make
    variable or through ``-D``) makes ``plat_ecnt_io_setup()`` replace the
    unconditional ``fip_memmap_policy`` with ``fip_ubi_policy`` and BL23 then
    looks for the FIP in the UBI volume ``fip``. ``emmc`` must stay True: it is
    the only thing that keeps the XMODEM rescue path compiled in, since the
    boards have no eMMC. ``nand_ecc_dma`` must stay False: it switches
    ``SPI_NAND_Flash_Init()`` to SPI controller DMA reads, and the guard that
    is supposed to keep that off for the BL21/BL22 stages cannot fire because
    ``IMAGE_BL2`` is defined nowhere in the tree.
    """
    return {
        "ubi": "TCSUPPORT_UBI_SUPPORT" in code,
        "emmc": bool(re.search(r"TCSUPPORT_EMMC\s*=\s*1", code)),
        "nand_ecc_dma": "TCSUPPORT_SPI_NAND_FLASH_ECC_DMA" in code,
    }


def atf_build_provides(code: str) -> set[str]:
    """The ``TCSUPPORT_*`` names build-atf.sh passes to make as variables."""
    return set(re.findall(r"^\s*(TCSUPPORT_[A-Z0-9_]+)\s*=", code, re.M))


def check_atf(
    result: CheckResult,
    atf: dict[str, int],
    wf: dict[str, int],
    parts: list[Part],
    flags: dict[str, bool],
    atf_available: bool,
) -> None:
    bootloader = part_by_label(parts, "bootloader")
    ubi = part_by_label(parts, "ubi")

    if atf_available and "fip_offset" in atf and "DEFAULT_FIP_OFFSET" in wf:
        if atf["fip_offset"] != wf["DEFAULT_FIP_OFFSET"]:
            result.fail(
                "workflow-vs-atf",
                f"workflow DEFAULT_FIP_OFFSET = 0x{wf['DEFAULT_FIP_OFFSET']:x} "
                f"but TF-A PLAT_ECNT_FIP_OFFSET = 0x{atf['fip_offset']:x}; the "
                f"composed image and BL23 would disagree about where the FIP is",
            )
    if atf_available and "fip_max_size" in atf and "BL23_FIP_MAX_SIZE" in wf:
        if atf["fip_max_size"] != wf["BL23_FIP_MAX_SIZE"]:
            result.fail(
                "workflow-vs-atf",
                f"workflow BL23_FIP_MAX_SIZE = 0x{wf['BL23_FIP_MAX_SIZE']:x} but "
                f"TF-A PLAT_ECNT_FIP_MAX_SIZE = 0x{atf['fip_max_size']:x}; the "
                f"FIP size gate would not match what BL23 will read",
            )

    if bootloader and "fip_offset" in atf and "fip_max_size" in atf:
        need = atf["fip_offset"] + atf["fip_max_size"]
        if bootloader.size < need:
            result.fail(
                "boot-window",
                f"bootloader partition is 0x{bootloader.size:x} but BL23 may "
                f"read up to 0x{need:x} (FIP offset 0x{atf['fip_offset']:x} + "
                f"max size 0x{atf['fip_max_size']:x}); shrink the FIP window or "
                f"grow the partition",
            )
        else:
            result.note(
                f"bootloader window: 0x{bootloader.size - need:x} bytes of slack "
                f"after the maximum FIP BL23 can read"
            )

    if not flags["emmc"]:
        result.fail(
            "xmodem-vs-atf",
            "build-atf.sh no longer sets TCSUPPORT_EMMC=1. bl2_image_load_v2.c "
            "gates bl2_mem_params_backup(), plat_ecnt_io_switch_to_memmap() and "
            "fip_image_xmodem_load() on (TCSUPPORT_UBI_SUPPORT || "
            "TCSUPPORT_EMMC); without either macro a damaged FIP can only be "
            "recovered by an external programmer. These boards have no eMMC, "
            "so the flag is purely the key for the serial recovery path",
        )

    if flags["nand_ecc_dma"]:
        result.fail(
            "ecc-dma-vs-atf",
            "build-atf.sh defines TCSUPPORT_SPI_NAND_FLASH_ECC_DMA, which makes "
            "SPI_NAND_Flash_Init() program the SPI controller for DMA reads. The "
            "guard is defined(TCSUPPORT_SPI_NAND_FLASH_ECC_DMA) && "
            "(!defined(IMAGE_BL2) || defined(IMAGE_BL23)), and IMAGE_BL2 is "
            "defined nowhere in the tree, so the second clause is dead: DMA "
            "would also land in BL21 and BL22, the two stages Airoha's own "
            "comment says cannot do controller DMA. Turning it on is a "
            "deliberate change - drop the __attribute__((unused)) patch in "
            "board/airoha/xg2010g/atf/prepare-atf.py in the same commit",
        )

    # All three load-bearing checks below are properties of this repository, not
    # of the ATF checkout, so they fire in the cheap gate too. The UBI_START_ADDR
    # value from the ATF tree only improves the message.
    if ubi is None:
        return
    start = atf.get("ubi_start_default")
    if flags["ubi"]:
        where = (
            f"UBI_START_ADDR 0x{start:x}" if start is not None else "its UBI_START_ADDR"
        )
        result.fail(
            "fip-flag-vs-layout",
            f"build-atf.sh defines TCSUPPORT_UBI_SUPPORT, so BL23 would switch "
            f"to fip_ubi_policy and look for the FIP in the UBI volume 'fip' at "
            f"{where}, but this layout puts ubi at 0x{ubi.start:x}. Drop the "
            f"flag, or set OVERRIDE_UBI_START_ADDR=0x{ubi.start:x} in the same tree",
        )
    elif start is not None and ubi.start == start:
        result.note(
            f"ubi starts at ATF's default UBI_START_ADDR (0x{start:x}) "
            f"although the build selects the mtd0 FIP path; harmless today"
        )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def mk_conditional_flags(atf_dir: Path) -> dict[str, str]:
    """Macros the pinned tree reads as *make* variables in its own conditionals.

    ``add_define`` only emits a compiler ``-D``; it does not create a make
    variable. A macro that is derived inside the top-level Makefile therefore
    looks satisfied from C but reads as empty in a ``$(...)`` test, which is how
    a flag can silently flip a make-side default.
    """
    out: dict[str, str] = {}
    candidates = [p for p in atf_dir.rglob("*.mk")] + [atf_dir / "Makefile"]
    for path in candidates:
        if ".git" in path.parts or not path.is_file():
            continue
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            stripped = line.strip()
            if not re.match(r"^(ifneq|ifeq|ifdef|ifndef)\b", stripped):
                continue
            for token in re.findall(r"\$\((TCSUPPORT_[A-Z0-9_]+)\)", stripped):
                out.setdefault(token, f"{path.relative_to(atf_dir)}:{line_no}")
    return out


def check_mk_flag_coverage(
    result: CheckResult, atf_dir: Path, provided: set[str]
) -> None:
    unknown = {
        name: where
        for name, where in mk_conditional_flags(atf_dir).items()
        if name not in provided and name not in MK_FLAG_ALLOWLIST
    }
    for name, where in sorted(unknown.items()):
        result.fail(
            "mk-flag-coverage",
            f"{where} tests $({name}) as a make variable but build-atf.sh does "
            f"not set it. A define derived inside the top-level Makefile does "
            f"not create a make variable, so a derived -D reads as empty here "
            f"and silently picks the unset branch. Pass it explicitly, or add "
            f"it to MK_FLAG_ALLOWLIST in this script with the reason the unset "
            f"default is the wanted one",
        )


# Macros the pinned TF-A tree tests as make variables but build-atf.sh
# deliberately leaves unset. Every entry has to be justified: the point of the
# list is that a newly pinned tree which starts reading one of these must fail
# the build rather than silently pick the unset branch. See
# check_mk_flag_coverage().
MK_FLAG_ALLOWLIST = {
    # Feature switches this board does not use. Each is off unless asked for.
    "TCSUPPORT_ARM_MULTIBOOT": "multiboot layout; unset selects the single image",
    "TCSUPPORT_ARM_SECURE_BOOT": "secure boot chain; not enabled on these boards",
    "TCSUPPORT_ARM_SECURE_BOOT_FLASH_KEY": "secure boot chain; not enabled",
    "TCSUPPORT_ARM_SECURE_BOOT_FW_ENC": "encrypted firmware; not enabled",
    "TCSUPPORT_AUTOBENCH": "lab-only benchmark flavour",
    "TCSUPPORT_BOARD_SELECT": "multi-board SDK selector; we pin one board per build",
    "TCSUPPORT_CPU_AN7552": "other SoC",
    "TCSUPPORT_CPU_AN7583": "other SoC",
    "TCSUPPORT_DUAL_KEY": "two-key secure boot; not enabled",
    "TCSUPPORT_GPT_ATF_SUPPORT": "eMMC/GPT FIP placement; this board is NAND only",
    "TCSUPPORT_OPTEE": "no BL32 on these boards",
    "TCSUPPORT_PARALLEL_NAND": "the boot strap is SPI-NAND; raw NAND backend unused",
    "TCSUPPORT_TPL_SUPPORT": "TPL image; not part of this boot chain",
    "TCSUPPORT_UBI_SUPPORT": "switching it on would move the FIP into a UBI volume",
    # Not a feature switch. Empty means "not zero", which is the branch the
    # previous tree always took: the un-open (blob linked) sources get built.
    "TCSUPPORT_BB_FIX_UNOPEN": "empty reads as non-zero, i.e. include the un-open sources",
    # Same shape: empty is the configured branch, so BL2_UNOPEN_SOURCES carries
    # the vendor DDR/eFuse objects.
    "TCSUPPORT_ATF_RELEASE": "empty selects the non-ATF-release source list",
}


def check_board(board: str, atf_dir: Path | None, require_atf: bool) -> CheckResult:
    result = CheckResult()
    dts_path = REPO / "arch" / "arm" / "dts" / f"{board}.dts"
    board_env = REPO / "board" / "airoha" / "an7581" / f"{board}.env"
    defconfig = REPO / "configs" / f"{board}_defconfig"

    if not dts_path.exists():
        result.fail("dts", f"{dts_path}: board device tree not found")
        return result

    parts = parse_dts_partitions(dts_path, result)
    check_partition_table(result, dts_path, parts)

    board_geo = parse_board_geometry(BOARD_SRC, result)
    check_board_geometry(result, board_geo, parts)

    env = parse_board_env(board_env, result)
    tftp = parse_tftp_env_sizes(TFTP_ENV, result)
    check_env(result, env, tftp, parts, defconfig)

    wf = parse_workflow_env(WORKFLOW, result)
    check_workflow(result, wf, parts)

    build_code = read_atf_build(result)
    flags = atf_build_flags(build_code)
    atf: dict[str, int] = {}
    if atf_dir is not None:
        atf = parse_atf(atf_dir, result)
        if not atf and require_atf:
            result.fail("atf", f"{atf_dir}: no TF-A constants parsed")
        check_mk_flag_coverage(result, atf_dir, atf_build_provides(build_code))
    elif require_atf:
        result.fail("atf", "--require-atf given but no --atf-dir")
    else:
        result.note(
            f"atf checks skipped for {board} (pass --atf-dir to enable); the "
            f"workflow-vs-atf and boot-window checks did not run"
        )

    # The memmap path is only valid if the FIP window is derived from TF-A; when
    # ATF is absent we still verify that the mtd0 image leaves room for the
    # documented 0x100000 window.
    if not atf:
        bootloader = part_by_label(parts, "bootloader")
        if bootloader and "DEFAULT_FIP_OFFSET" in wf:
            fallback_window = 0x100000
            if bootloader.size < wf["DEFAULT_FIP_OFFSET"] + fallback_window:
                result.fail(
                    "boot-window",
                    f"bootloader partition is 0x{bootloader.size:x}, smaller "
                    f"than the documented FIP window 0x"
                    f"{wf['DEFAULT_FIP_OFFSET'] + fallback_window:x}",
                )

    check_atf(result, atf, wf, parts, flags, bool(atf))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--board",
        action="append",
        choices=BOARDS,
        help="board to check (repeatable); defaults to every supported board",
    )
    parser.add_argument(
        "--atf-dir",
        type=Path,
        default=None,
        help="path to the pinned TF-A source tree for boot-chain cross-checks",
    )
    parser.add_argument(
        "--require-atf",
        action="store_true",
        help="fail instead of skipping when --atf-dir is absent or unparsable",
    )
    args = parser.parse_args()

    boards = args.board or list(BOARDS)
    failed = False
    for board in boards:
        result = check_board(
            board, args.atf_dir.resolve() if args.atf_dir else None, args.require_atf
        )
        for note in result.notes:
            print(f"note: {board}: {note}")
        if not result.ok:
            failed = True
            for fail in result.failures:
                print(f"FAIL: {board}: {fail}", file=sys.stderr)
        else:
            print(f"{board}: partition layout consistent")

    if failed:
        return 1
    print("partition layout cross-checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
