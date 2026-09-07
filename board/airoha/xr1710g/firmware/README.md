# XR1710G mtd0 prefix

`mtd0-prefix.bin` contains the first `0x800` bytes extracted from the XR1710G
stock `mtd0` bootloader data. GitHub Actions preserves it before the newly
signed FIP.

BL2 and BL31 are built from the pinned Airoha TF-A source by
`board/airoha/xg2010g/atf/build-atf.sh`.

| File | Role | Size | SHA256 |
| --- | --- | ---: | --- |
| `mtd0-prefix.bin` | First `0x800` bytes before the FIP in `mtd0` | 2,048 | `82830140f4f8842702d0569065c27071b7cc24e0876e6c487cb4d9d81c294dd7` |

This prefix was extracted from the analyzed Airoha AN7581-class XR1710G mtd0
layout. Its bytes currently match the preserved XG2010G prefix, but CI keeps a
board-local copy so each board's boot inputs remain explicit.
