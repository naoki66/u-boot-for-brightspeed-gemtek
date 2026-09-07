/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * Brightspeed Gemtek AN7581 board ops contract for the HTTP recovery server.
 *
 * The recovery framework in net/lwip/httpd_recovery.c needs to ask the
 * board three things: where the UBI partition lives, what geometry it
 * expects, and how to mirror DSD factory data into it.  Previously these
 * were hard-coded externs of `xg2010g_*` symbols, which both
 * over-coupled the framework to one board and duplicated the UBI layout
 * constants in two translation units.  A board (or board family) that
 * supports HTTPD_RECOVERY provides a strong `recovery_get_board_ops()`
 * returning a singleton `struct recovery_board_ops` populated with its
 * own routines.
 *
 * If a board enables HTTPD_RECOVERY without registering ops the framework
 * refuses to start the recovery server and aborts the boot of recovery,
 * so the contract is fail-fast at runtime instead of at link time.
 */

#ifndef AN7581_RECOVERY_OPS_H
#define AN7581_RECOVERY_OPS_H

#include <mtd.h>
#include <linux/types.h>

/**
 * struct recovery_ubi_geometry - NAND/UBI layout the recovery expects.
 *
 * @size:        UBI partition size in bytes (must match `mtd->size`).
 * @erase_size:  erase block in bytes.
 * @write_size:  write/page size in bytes.
 * @oob_size:    per-page OOB size in bytes.
 * @ubi_part:    UBI partition name (e.g. "ubi").
 * @version:     version string the recovery web UI advertises.
 *
 * The framework compares incoming MTD devices against these values to
 * decide whether the existing UBI geometry is one we trust.  Sharing one
 * struct between board code and the framework kills the previous
 * `RECOVERY_XG2010G_*` literal duplication.
 */
struct recovery_ubi_geometry {
	unsigned long long size;
	unsigned int erase_size;
	unsigned int write_size;
	unsigned int oob_size;
	const char *ubi_part;
	const char *version;
};

/**
 * struct recovery_board_ops - per-board recovery hooks.
 *
 * The framework calls every entry point through this struct; the names
 * are deliberately neutral so that an XR1710G or any future AN7581
 * derivative can either reuse the same struct or substitute its own.
 *
 * @match:              return true when the running device tree is one
 *                      this board file supports.  A board that supports
 *                      more than one variant should encode every
 *                      compatible string in this predicate so the
 *                      framework only acts on supported devices.
 * @ubi:                pointer to a static &struct recovery_ubi_geometry
 *                      describing the on-NAND layout.  Shared by every
 *                      detection routine so the constants live in exactly
 *                      one place per board.
 * @detect_ubi_part:    resolve the active UBI partition name; cache the
 *                      result so repeated calls return the same string.
 * @detect_ubi_version: companion to detect_ubi_part for the /about JSON.
 * @sync_factory_part:  mirror DSD factory data to a single UBI volume;
 *                      return 0 on success.
 * @sync_factory:       convenience wrapper that resolves and syncs the
 *                      active partition.
 * @mtd_ubi_valid:      used by /about and the recovery HTTP handlers to
 *                      reject partitions whose geometry doesn't match
 *                      what the board supports.
 */
struct recovery_board_ops {
	bool (*match)(void);
	const struct recovery_ubi_geometry *ubi;
	const char *(*detect_ubi_part)(void);
	const char *(*detect_ubi_version)(void);
	int (*sync_factory_part)(const char *part);
	int (*sync_factory)(void);
	bool (*mtd_ubi_valid)(const struct mtd_info *mtd);
};

/**
 * recovery_get_board_ops() - return the registered board ops singleton.
 *
 * A board that enables HTTPD_RECOVERY must provide a strong definition
 * of this symbol.  The framework installs a __weak default returning NULL
 * so an unconfigured build prints a clear error and refuses to enter the
 * recovery server, rather than silently failing at first request.
 */
const struct recovery_board_ops *recovery_get_board_ops(void);

#endif
