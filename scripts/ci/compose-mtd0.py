#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
#
# Compose the 2 MiB /dev/mtd0 image from either the preserved vendor prefix or
# a zero-filled prefix and the freshly signed FIP. The FIP is placed at the
# configured offset inside mtd0 (default 0x800) and the rest of the image is
# padded with 0xFF, matching the behaviour of Airoha/Brightspeed stock images
# after a blank-block erase.
#
# This used to live inline inside .github/workflows/build-mtd0.yml; extracting
# it lets the same check run locally and from CI.

import argparse
import hashlib
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prefix",
        default="signing/mtd0-prefix.bin",
        type=Path,
        help="path to the vendor mtd0 prefix (stock mode only; size must equal --fip-offset)",
    )
    parser.add_argument(
        "--prefix-mode",
        default=os.environ.get("MTD0_PREFIX_MODE", "stock"),
        choices=("stock", "erased"),
        help=(
            "prefix before the FIP: 'stock' copies the vendor mtd0 prefix, "
            "'erased' fills it with 0xFF (erased-flash value, which is what the "
            "vendor bootloader uses). A zero-filled prefix is NOT valid: it is "
            "neither the vendor prefix nor erased flash and the board will not "
            "boot from NAND."
        ),
    )
    parser.add_argument(
        "--fip",
        required=True,
        type=Path,
        help="path to the signed FIP image",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path to write the composed mtd0 image",
    )
    parser.add_argument(
        "--mtd0-size",
        default=os.environ.get("MTD0_SIZE", "0x200000"),
        help="total mtd0 size in bytes (default: $MTD0_SIZE or 0x200000)",
    )
    parser.add_argument(
        "--fip-offset",
        default=os.environ.get("FIP_OFFSET", "0x800"),
        help="FIP offset within mtd0 (default: $FIP_OFFSET or 0x800)",
    )
    args = parser.parse_args()

    mtd0_size = int(args.mtd0_size, 0)
    fip_offset = int(args.fip_offset, 0)

    if args.prefix_mode == "erased":
        # 0xFF is what an erased NAND block reads as.  The vendor's own
        # TFTP helper writes the preloader FIP into an erased 2 MiB region
        # (`mw.b $loadaddr 0xff 0x20000`), so an erased prefix is a tested
        # layout.  0x00 is not: it is neither the vendor prefix nor erased
        # flash, and the BootROM will not boot that image.
        prefix = b"\xff" * fip_offset
    else:
        prefix = args.prefix.read_bytes() if fip_offset else b""
    fip = args.fip.read_bytes()

    if len(prefix) != fip_offset:
        raise SystemExit(
            f"prefix size {len(prefix)} != FIP offset {fip_offset}"
        )
    if fip_offset and args.prefix_mode == "stock":
        if prefix[:4] == b"\x00\x00\x00\x00":
            raise SystemExit(
                "stock prefix starts with 0x00000000; expected the ARM NOP "
                "sled (0xe320f000). Use --prefix-mode erased instead."
            )
    if fip_offset + len(fip) > mtd0_size:
        raise SystemExit(
            f"signed FIP exceeds mtd0: "
            f"end={fip_offset + len(fip)} size={mtd0_size}"
        )

    mtd0 = bytearray(b"\xff" * mtd0_size)
    mtd0[:fip_offset] = prefix
    mtd0[fip_offset:fip_offset + len(fip)] = fip

    payload = bytes(mtd0)
    args.output.write_bytes(payload)

    sha = hashlib.sha256(payload).hexdigest()
    print(f"mtd0 bytes: {len(payload)}")
    print(f"prefix mode: {args.prefix_mode}")
    print(f"fip offset: 0x{fip_offset:x}")
    print(f"fip bytes: {len(fip)}")
    print(f"fip end: 0x{fip_offset + len(fip):x}")
    print(f"mtd0 sha256: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
