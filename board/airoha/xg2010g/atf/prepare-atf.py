#!/usr/bin/env python3
"""Apply the Airoha TF-A patches that the XG2010G/XR1710G build still needs.

This used to carry a second patch, which stopped the BL23 I/O code from
switching the FIP source to a UBI volume. That patch is gone: the pinned
Airoha TF-A tree already gates the switch on ``TCSUPPORT_UBI_SUPPORT``, and
``build-atf.sh`` deliberately does not define that macro, so the
unconditional ``fip_memmap_policy`` assignment in ``plat_ecnt_io_setup()``
is what BL23 ends up using. Keeping the old patch would mean matching text
that no longer exists.

The remaining patch fixes an uninitialised struct in the host side flash
table generator.
"""

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"unexpected source content: {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Airoha TF-A for XG2010G")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    # flash_table.bin is a dump of this struct plus the entry array. The
    # generator walks it with memcpy() before every field has been filled in,
    # so the uninitialised tail of the struct would be written into the table
    # and read back by BL2 as a bogus flash geometry.
    replace_once(
        args.source / "plat/ecnt/common/drivers/flash/spi_nand_flash_table.c",
        """\tint buf_size = 1000000; //16M
\tstruct bl2_flash_H flash_h;
\tchar *buf = NULL;
""",
        """\tint buf_size = 1000000; //16M
\tstruct bl2_flash_H flash_h = {0};
\tchar *buf = NULL;
""",
    )


if __name__ == "__main__":
    main()
