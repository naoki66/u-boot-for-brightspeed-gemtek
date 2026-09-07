#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
#
# Validate that the BL33 LZMA payload (out/atf/bl33.bin) is consistent with the
# raw U-Boot (u-boot.bin) and fits inside BL2's fixed decompress input buffer.
#
# Airoha's BL2 consumes the classic LZMA-Alone header (5-byte properties
# followed by an 8-byte little-endian uncompressed size). The decompressed
# size must equal u-boot.bin exactly; otherwise BL2 will reject the payload
# or copy the wrong number of bytes into DDR.
#
# This used to live inline inside .github/workflows/build-mtd0.yml; extracting
# it lets the same check run locally and from CI.

import argparse
import os
import struct
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        default="u-boot.bin",
        type=Path,
        help="path to the raw U-Boot/BL33 image (default: u-boot.bin)",
    )
    parser.add_argument(
        "--payload",
        default="out/atf/bl33.bin",
        type=Path,
        help="path to the Airoha LZMA payload (default: out/atf/bl33.bin)",
    )
    parser.add_argument(
        "--max-bytes",
        default=None,
        help=(
            "BL2 decompress-input size in bytes (default: "
            "$BL_DECOMPRESS_INPUT_MAX_SIZE, 0x58000)"
        ),
    )
    args = parser.parse_args()

    raw = args.raw.read_bytes()
    payload = args.payload.read_bytes()

    if len(payload) < 13:
        raise SystemExit(
            f"BL33 LZMA payload is truncated: {len(payload)} bytes "
            f"(need at least 13 for the LZMA-Alone header)"
        )

    declared_size = struct.unpack_from("<Q", payload, 5)[0]
    if declared_size != len(raw):
        raise SystemExit(
            f"BL33 LZMA size header is {declared_size} bytes; "
            f"{args.raw} is {len(raw)} bytes"
        )

    max_bytes_env = os.environ.get("BL_DECOMPRESS_INPUT_MAX_SIZE")
    if args.max_bytes is not None:
        max_bytes = int(args.max_bytes, 0)
    elif max_bytes_env is not None:
        max_bytes = int(max_bytes_env, 0)
    else:
        max_bytes = 0x58000
    if len(payload) > max_bytes:
        raise SystemExit(
            f"BL33 payload is {len(payload)} bytes; "
            f"BL2 input buffer is {max_bytes} bytes"
        )

    print(
        f"BL33 LZMA payload: {len(payload)} bytes "
        f"(decompresses to {declared_size} bytes)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())