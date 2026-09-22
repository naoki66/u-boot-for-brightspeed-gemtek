#!/usr/bin/env python3
"""Apply the Airoha TF-A patches that the XG2010G/XR1710G build still needs.

This used to carry a second patch, which stopped the BL23 I/O code from
switching the FIP source to a UBI volume. That patch is gone: the pinned
Airoha TF-A tree already gates the switch on ``TCSUPPORT_UBI_SUPPORT``, and
``build-atf.sh`` deliberately does not define that macro, so the
unconditional ``fip_memmap_policy`` assignment in ``plat_ecnt_io_setup()``
is what BL23 ends up using. Keeping the old patch would mean matching text
that no longer exists.

Three patches remain. The first fixes an uninitialised struct in the host side
flash table generator; the second marks a vendor variable as possibly unused,
because we deliberately build with SPI-NAND ECC DMA off (see below).

The third was added when the TF-A source moved to the v2.15 tree: it restores
SHA-256 to the mbed TLS configuration, because that migration swapped Airoha's
own config header for the upstream one and dropped SHA-256 out of the BL2 build
while our certificates are still PSS/SHA-256. See the comment on that patch for
the full chain, and for what removing it requires.
"""

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    """Rewrite exactly one occurrence, leaving the rest of the file byte-identical.

    Reading and writing through ``read_text``/``write_text`` would run the
    text through newline translation: on Windows that silently converts every
    line of a 90 KB vendor source from LF to CRLF, so the patched tree no
    longer matches the pinned tree except for the intended line and any diff
    taken against it is unreadable. Work on bytes and match with the file's
    own line ending instead.
    """
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    old_native = old.replace("\n", nl)
    new_native = new.replace("\n", nl)
    if text.count(old_native) != 1:
        raise SystemExit(f"unexpected source content: {path}")
    path.write_bytes(text.replace(old_native, new_native).encode("utf-8"))


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

    # SPI_NAND_Flash_Init() declares dma_on unconditionally but only ever
    # touches it inside the block below, so the build fails with
    # -Werror=unused-variable unless TCSUPPORT_SPI_NAND_FLASH_ECC_DMA is
    # defined. We keep that macro undefined on purpose:
    #
    #   * The block switches the SPI controller into DMA mode for NAND reads.
    #     Airoha's own comment in it says "BL2 is worked at L2C or FW SRAM,
    #     SPI controller DMA does not support these two SRAM", so it is meant
    #     to stay off for the BL2 stages.
    #   * It cannot be kept off for BL21/BL22 alone right now: the guard is
    #         #if defined(TCSUPPORT_SPI_NAND_FLASH_ECC_DMA) && \
    #             (!defined(IMAGE_BL2) || defined(IMAGE_BL23))
    #     and IMAGE_BL2 is not defined anywhere in the tree, so
    #     !defined(IMAGE_BL2) is always true and the || clause is dead. The
    #     guard collapses to the bare macro and would therefore pull DMA into
    #     BL21 and BL22 as well.
    #   * Both our currently flashed image and the reference project that
    #     ships this board (pbs05/uboot-an758x) run with the macro undefined,
    #     i.e. with this path off. Its tree predates dma_on and the guard, so
    #     it never has to declare the macro at all.
    #
    # Marking the declaration unused keeps Airoha's code shape and leaves the
    # build identical in behaviour to the image we know boots. Flipping to
    # DMA reads means defining the macro in build-atf.sh and dropping this
    # patch - a single, deliberate step, not something to drift into.
    replace_once(
        args.source / "plat/ecnt/common/drivers/flash/spi_nand_flash.c",
        """\tint dma_on;
""",
        """\t/* prepare-atf.py: only used when TCSUPPORT_SPI_NAND_FLASH_ECC_DMA is set. */
\tint dma_on __attribute__((unused));
""",
    )

    # v2.15 replaced Airoha's own include/drivers/auth/mbedtls/mbedtls_config-3.h
    # with the upstream include/drivers/auth/mbedtls/default_mbedtls_config.h
    # (drivers/auth/mbedtls/mbedtls_common.mk:30). That silently changed which
    # hashes exist in BL2:
    #
    #   * mbedtls_config-3.h enabled SHA-224 and SHA-256 unconditionally, and
    #     pulled SHA-384/SHA-512 in as well whenever the TBB hash was not
    #     SHA-256 - so all four were compiled in.
    #   * default_mbedtls_config.h enables exactly the hash that
    #     TF_MBEDTLS_HASH_ALG_ID selects. CONFIG_ECNT is set unconditionally
    #     (Makefile:222), which makes mbedtls_common.mk take its Airoha branch
    #     and pin TF_MBEDTLS_HASH_ALG_ID := TF_MBEDTLS_SHA512 (=3), while
    #     MEASURED_BOOT defaults to 0. Only the SHA-512 block therefore fires
    #     and MBEDTLS_SHA256_C ends up undefined.
    #
    # The certificate chain this project ships is signed with PSS/SHA-256 and
    # its content certificates carry SHA-256 digest-info extensions, because
    # the workflow calls cert_create without --hash-alg (cert_create defaults
    # to sha256). TF-A reads the digest algorithm out of the certificate
    # itself, so verify_signature()/verify_hash() call
    # mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), get NULL, and return
    # CRYPTO_ERR_SIGNATURE/CRYPTO_ERR_HASH - which surfaces as "-EAUTH" (-80)
    # on BL31, the first image of the load chain. That is exactly the failure
    # seen when the v2.15 BL2 was first loaded over XMODEM, while the v2.10
    # BL2 (built against mbedtls_config-3.h) still worked.
    #
    # Restoring SHA-256 puts the ecnt build back at the hash coverage the
    # v2.10 build and the vendor BL23 both have. SHA-256 without SHA-224 is
    # fine on mbedtls 3.6 - upstream's own SHA-256 branch defines nothing
    # else. Deliberately *not* keyed on CONFIG_ECNT: mbedtls' library
    # sources are compiled by the TF-A build system, so the macro should be
    # visible, but an unconditional define cannot depend on that.
    #
    # Removing this means also switching the workflow's cert_create to
    # --hash-alg sha512 (matching the platform's declared TBB hash and the
    # vendor's FIP); doing one without the other breaks authentication again.
    replace_once(
        args.source / "include/drivers/auth/mbedtls/default_mbedtls_config.h",
        """#if MEASURED_BOOT || (TF_MBEDTLS_HASH_ALG_ID == TF_MBEDTLS_SHA512)
\t#define MBEDTLS_SHA512_C
\t#if (ENABLE_FEAT_CRYPTO_SHA3 == 1)
\t\t#define MBEDTLS_SHA512_USE_A64_CRYPTO_ONLY
\t#endif
#endif

#define MBEDTLS_VERSION_C
""",
        """#if MEASURED_BOOT || (TF_MBEDTLS_HASH_ALG_ID == TF_MBEDTLS_SHA512)
\t#define MBEDTLS_SHA512_C
\t#if (ENABLE_FEAT_CRYPTO_SHA3 == 1)
\t\t#define MBEDTLS_SHA512_USE_A64_CRYPTO_ONLY
\t#endif
#endif

/*
 * prepare-atf.py: the TBB hash above is SHA-512, but the certificate chain
 * built for these boards is PSS/SHA-256. TF-A takes the digest algorithm
 * from the certificate itself, so without SHA-256 compiled in every
 * signature/hash check fails with -EAUTH (-80). Airoha's v2.10 config header
 * enabled SHA-256 unconditionally; this restores that coverage.
 */
#if !defined(MBEDTLS_SHA256_C)
\t#define MBEDTLS_SHA256_C
#endif

#define MBEDTLS_VERSION_C
""",
    )

if __name__ == "__main__":
    main()
