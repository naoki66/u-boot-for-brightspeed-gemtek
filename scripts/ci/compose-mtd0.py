#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
#
# Compose the /dev/mtd0 image from the preserved vendor prefix and the freshly
# signed FIP.  The FIP is placed at the configured offset inside mtd0 (default
# 0x800), and the image ends where the FIP ends: it is *not* padded out to the
# full 2 MiB bootloader partition.
#
# Why the image is no longer padded: mtd0 is read by the BootROM, BL1 and BL2
# through fixed windows, never by "read until EOF", so the trailing 0xFF
# padding carries no information.  It only made the artifact exactly 2 MiB,
# which the recovery page used to require.  Writing an image that ends at the
# FIP is also what the vendor helper does (pbs05/uboot-an758x writes
# mtd->erasesize worth of bytes, never the uploaded file length).
#
# The consumer (recovery page / external programmer) is responsible for
# erasing the rest of the bootloader partition.  The recovery page aligns the
# upload up to the eraseblock size and erases the whole partition before
# writing, so the 0xFF tail this script no longer emits is produced on the
# device instead.
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
        choices=("stock",),
        help=(
            "prefix before the FIP. Only 'stock' is supported: it copies the "
            "vendor mtd0 prefix. The first 0x800 bytes of mtd0 are the first "
            "executable stage of the NAND boot chain (ARM NOP sled, then "
            "ldr/bl from mtd0+0x040 on), so an erased (0xFF) or zero-filled "
            "(0x00) prefix puts an undefined instruction at mtd0+0x040 and the "
            "board produces no serial output at all; recovering it needs a "
            "NAND programmer."
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
        help=(
            "size of the mtd0 bootloader partition in bytes, used only as the "
            "upper bound for the composed image (default: $MTD0_SIZE or "
            "0x200000). The output is not padded to this size."
        ),
    )
    parser.add_argument(
        "--pad-to",
        default=os.environ.get("MTD0_PAD_TO", ""),
        help=(
            "optional pad byte value (e.g. 0xff) or length to extend the output "
            "to. Empty (default) leaves the image ending exactly at the FIP. "
            "Pass a byte value such as 0xff to reproduce the legacy fully "
            "padded 2 MiB artifact."
        ),
    )
    parser.add_argument(
        "--fip-offset",
        default=os.environ.get("FIP_OFFSET", "0x800"),
        help="FIP offset within mtd0 (default: $FIP_OFFSET or 0x800)",
    )
    args = parser.parse_args()

    mtd0_size = int(args.mtd0_size, 0)
    fip_offset = int(args.fip_offset, 0)

    prefix = args.prefix.read_bytes() if fip_offset else b""
    fip = args.fip.read_bytes()

    if not fip:
        raise SystemExit("signed FIP is empty; refusing to compose an image")

    if len(prefix) != fip_offset:
        raise SystemExit(
            f"prefix size {len(prefix)} != FIP offset {fip_offset}"
        )
    if fip_offset:
        if prefix[:4] == b"\x00\x00\x00\x00":
            raise SystemExit(
                "stock prefix starts with 0x00000000; expected the ARM NOP "
                "sled (0xe320f000). mtd0+0x000 is executable bootstrap code, "
                "so a zero-filled prefix bricks the board."
            )
        if prefix[:4] == b"\xff\xff\xff\xff":
            raise SystemExit(
                "stock prefix starts with 0xFFFFFFFF (erased); expected the "
                "ARM NOP sled (0xe320f000). mtd0+0x040 is already an ldr with "
                "no guard in front of it, so an erased prefix bricks the board."
            )
    fip_end = fip_offset + len(fip)
    if fip_end > mtd0_size:
        raise SystemExit(
            f"signed FIP exceeds mtd0: "
            f"end={fip_end} size={mtd0_size}"
        )

    # The image is the prefix followed by the FIP, and nothing else.  Every
    # byte after fip_end would be 0xFF padding that the boot chain never reads
    # (BootROM/BL1/BL2 all use fixed offsets and fixed window lengths), so
    # emitting it only inflates the artifact and forces the writer to accept a
    # 2 MiB blob regardless of how small the actual payload is.
    payload = prefix + fip

    pad = args.pad_to.strip().lower()
    if pad:
        try:
            pad_byte = int(pad, 0)
        except ValueError:
            raise SystemExit(f"--pad-to expects a byte value, got {args.pad_to!r}")
        if not 0 <= pad_byte <= 0xFF:
            raise SystemExit(f"--pad-to byte out of range: {args.pad_to!r}")
        if len(payload) > mtd0_size:
            raise SystemExit(
                f"cannot pad {len(payload)} bytes to {mtd0_size}"
            )
        payload += bytes([pad_byte]) * (mtd0_size - len(payload))

    args.output.write_bytes(payload)

    sha = hashlib.sha256(payload).hexdigest()
    print(f"mtd0 bytes: {len(payload)}")
    print(f"mtd0 partition size: {mtd0_size}")
    print(f"prefix mode: {args.prefix_mode}")
    print(f"fip offset: 0x{fip_offset:x}")
    print(f"fip bytes: {len(fip)}")
    print(f"fip end: 0x{fip_end:x}")
    print(f"pad: {pad or '(none, image ends at the FIP)'}")
    print(f"mtd0 sha256: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
