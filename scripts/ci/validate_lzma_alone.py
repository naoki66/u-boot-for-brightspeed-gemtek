#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0+
"""Validate an Airoha-compatible LZMA-Alone firmware payload."""

import argparse
import lzma
import struct
import sys
from pathlib import Path
from typing import List, Optional


def parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def validate(
    *,
    label: str,
    raw_path: Path,
    payload_path: Path,
    max_bytes: Optional[int] = None,
) -> str:
    raw = raw_path.read_bytes()
    payload = payload_path.read_bytes()

    if len(payload) < 13:
        raise SystemExit(
            f"{label} LZMA payload is truncated: {len(payload)} bytes "
            f"(need at least 13 for the LZMA-Alone header)"
        )

    declared_size = struct.unpack_from("<Q", payload, 5)[0]
    if declared_size != len(raw):
        raise SystemExit(
            f"{label} LZMA size header is {declared_size} bytes; "
            f"{raw_path} is {len(raw)} bytes"
        )

    try:
        decoded = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError as exc:
        raise SystemExit(f"{label} LZMA payload does not decompress: {exc}") from exc

    if decoded != raw:
        raise SystemExit(
            f"{label} LZMA output does not match {raw_path} "
            f"(decoded {len(decoded)} bytes, raw {len(raw)} bytes)"
        )

    if max_bytes is not None and len(payload) > max_bytes:
        raise SystemExit(
            f"{label} payload is {len(payload)} bytes; "
            f"input buffer is {max_bytes} bytes"
        )

    return (
        f"{label} LZMA payload: {len(payload)} bytes "
        f"(decompresses to {declared_size} bytes)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="image", help="image label for diagnostics")
    parser.add_argument("--raw", required=True, type=Path, help="uncompressed image")
    parser.add_argument("--payload", required=True, type=Path, help="LZMA-Alone payload")
    parser.add_argument(
        "--max-bytes",
        default=None,
        type=parse_int,
        help="optional compressed input-buffer limit",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        validate(
            label=args.label,
            raw_path=args.raw,
            payload_path=args.payload,
            max_bytes=args.max_bytes,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
