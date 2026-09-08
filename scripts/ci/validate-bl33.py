#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
#
# Validate that the BL33 LZMA payload (out/atf/bl33.bin) is consistent with the
# raw U-Boot (u-boot.bin) and fits inside BL2's fixed decompress input buffer.
#
# This used to live inline inside .github/workflows/build-mtd0.yml; extracting
# it lets the same check run locally and from CI.

import argparse
import os
import sys
from pathlib import Path

from validate_lzma_alone import validate


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

    max_bytes_env = os.environ.get("BL_DECOMPRESS_INPUT_MAX_SIZE")
    if args.max_bytes is not None:
        max_bytes = int(args.max_bytes, 0)
    elif max_bytes_env is not None:
        max_bytes = int(max_bytes_env, 0)
    else:
        max_bytes = 0x58000

    print(
        validate(
            label="BL33",
            raw_path=args.raw,
            payload_path=args.payload,
            max_bytes=max_bytes,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
