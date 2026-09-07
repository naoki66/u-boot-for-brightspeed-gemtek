#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
#
# Wrap a compiled BL2 in the Airoha BootROM XMODEM first-stage header so the
# resulting binary can be sent directly via XMODEM as a fallback for the
# vendor bootext.ram. The header layout and magic values are observed from
# stock Airoha en7523/en7581 builds; do not change them without a real-device
# verification.
#
# Layout (little-endian, 0x400-byte header):
#   0x00..0x04  MAGIC0 = 0xAA640001
#   0x04..0x08  MAGIC1 = 0x12345678
#   0x10..0x20  BL2_UUID
#   0x20..0x24  header size (HEADER_SIZE)
#   0x28..0x2C  BL2 payload size
#   0x38..0x40  vendor checksum (zero-filled; matches ImmortalWrt bootext.ram)
#   remainder    zero-padded
#
# This used to live inline inside .github/workflows/build-mtd0.yml.

import argparse
import hashlib
import sys
from pathlib import Path

HEADER_SIZE = 0x400
MAGIC0 = 0xAA640001
MAGIC1 = 0x12345678
BL2_UUID = bytes.fromhex("5ff9ec0b4d223e4da544c39d81c73f0a")
RESET_VECTOR = bytes.fromhex("0090a0e101a0a0e102b0a0e103c0a0e1")
# Vendor bootext.ram is exactly 0x1FC00 bytes (128 KiB minus the header
# region reserved by the BootROM). Anything larger will be truncated.
MAX_TOTAL_SIZE = 0x1FC00


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bl2",
        required=True,
        type=Path,
        help="path to the compiled BL2 image",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path to write the headered image",
    )
    args = parser.parse_args()

    bl2 = args.bl2.read_bytes()
    if bl2[:16] != RESET_VECTOR:
        raise SystemExit(
            "unexpected BL2 entry code, expected AArch32 reset vector:\n"
            f"  got  {bl2[:16].hex()}\n"
            f"  want {RESET_VECTOR.hex()}"
        )

    total = HEADER_SIZE + len(bl2)
    if total > MAX_TOTAL_SIZE:
        raise SystemExit(
            f"headered BL2 too large: {total} > 0x{MAX_TOTAL_SIZE:x} "
            f"(vendor bootext.ram size)"
        )

    header = bytearray(HEADER_SIZE)
    header[0:4] = MAGIC0.to_bytes(4, "little")
    header[4:8] = MAGIC1.to_bytes(4, "little")
    header[0x10:0x20] = BL2_UUID
    header[0x20:0x24] = HEADER_SIZE.to_bytes(4, "little")
    header[0x28:0x2C] = len(bl2).to_bytes(4, "little")

    payload = bytes(header) + bl2
    args.output.write_bytes(payload)

    sha = hashlib.sha256(payload).hexdigest()
    print(f"bootext-bl2 bytes: {total}")
    print(f"bootext-bl2 sha256: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())