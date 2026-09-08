// SPDX-License-Identifier: GPL-2.0
/*
 * Author: Christian Marangi <ansuelsmth@gmail.com>
 */

#include <asm/gpio.h>
#include <asm/global_data.h>
#include <asm/io.h>
#include <dt-bindings/gpio/gpio.h>
#include <dm/device.h>
#include <dm/ofnode.h>
#include <env.h>
#include <fdt_support.h>
#include <mtd.h>
#include <net-common.h>
#include <ubi_uboot.h>
#undef crc32
#include <u-boot/crc.h>
#include <xg2010g_version.h>
#include "recovery.h"
#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/kconfig.h>
#include <linux/string.h>
#include <time.h>

DECLARE_GLOBAL_DATA_PTR;

#define XG2010G_CHIP_SCU_BASE		0x1fa20000
#define XG2010G_GPIO_SYSCTL_BASE	0x1fbf0200

#define XG2010G_REG_GPIO_CTRL		0x0000
#define XG2010G_REG_GPIO_DATA		0x0004
#define XG2010G_REG_GPIO_OE		0x0014
#define XG2010G_REG_GPIO_CTRL1		0x0020
#define XG2010G_REG_GPIO_FLASH_MODE_CFG	0x0034
#define XG2010G_REG_GPIO_CTRL2		0x0060
#define XG2010G_REG_GPIO_CTRL3		0x0064
#define XG2010G_REG_GPIO_DATA1		0x0070
#define XG2010G_REG_GPIO_OE1		0x0078
#define XG2010G_GPIO_MAX		64

#define XG2010G_DSD_PART		"dsd"
#define XG2010G_UENV_PART		"uenv"
#define XG2010G_UENV_SIZE		0x4000
#define XG2010G_UENV_ERASE_SIZE	0x40000
#define XG2010G_UENV_DATA_SIZE		(XG2010G_UENV_SIZE - sizeof(u32))
#define XG2010G_UBI_PART		"ubi"
#define XG2010G_UBI_SIZE		0x1b800000ULL
#define XG2010G_UBI_ERASE_SIZE		0x20000U
#define XG2010G_UBI_WRITE_SIZE		0x800U
#define XG2010G_UBI_OOB_SIZE		0x80U
#define XG2010G_FACTORY_VOL		"factory"
#define XG2010G_DSD_ENV_SIZE		0x1000
#define XG2010G_FACTORY_WAN_MAC_OFFSET	0x5000
#define XG2010G_FACTORY_LAN_MAC_OFFSET	0x6000
#define XG2010G_FACTORY_SIZE		(XG2010G_FACTORY_LAN_MAC_OFFSET + ARP_HLEN)

/*
 * Single source of truth for the on-NAND UBI layout.  Both the active
 * "supported layout" table and the recovery_board_ops geometry share the
 * values defined here, so the framework and the board code cannot drift.
 */
static const struct recovery_ubi_geometry xg2010g_ubi_geometry = {
	.size		= XG2010G_UBI_SIZE,
	.erase_size	= XG2010G_UBI_ERASE_SIZE,
	.write_size	= XG2010G_UBI_WRITE_SIZE,
	.oob_size	= XG2010G_UBI_OOB_SIZE,
	.ubi_part	= XG2010G_UBI_PART,
	.version	= "2.0",
};

struct xg2010g_ubi_layout {
	const char *version;
	const char *part;
};

static const struct xg2010g_ubi_layout xg2010g_ubi_layouts[] = {
	{ xg2010g_ubi_geometry.version, xg2010g_ubi_geometry.ubi_part },
};

static const struct xg2010g_ubi_layout *xg2010g_active_ubi_layout =
	&xg2010g_ubi_layouts[0];
static bool xg2010g_ubi_layout_probed;
static bool xg2010g_ubi_layout_available;

static const char *const xg2010g_fdt_lan_mac_paths[] = {
	"/soc/ethernet@1fb50000/ethernet@1",
	"/soc/ethernet@1fb50000/ethernet@4",
};

static const char *const xg2010g_fdt_wan_mac_paths[] = {
	"/soc/ethernet@1fb50000/ethernet@2",
};

/*
 * The Brightspeed Gemtek AN7581 boards (XG2010G and XR1710G) share the
 * same NAND layout, factory calibration handling and recovery flow, so one board
 * support file serves both.
 */
static bool xg2010g_is_compatible(void)
{
	return of_machine_is_compatible("naoki,xg2010g") ||
	       of_machine_is_compatible("econet,xg2010g") ||
	       of_machine_is_compatible("econet,xg2010g-ubi") ||
	       of_machine_is_compatible("gemtek,xg2010g") ||
	       of_machine_is_compatible("gemtek,xg2010g-ubi") ||
	       of_machine_is_compatible("gemtek,xr1710g") ||
	       of_machine_is_compatible("gemtek,xr1710g-ubi") ||
	       of_machine_is_compatible("econet,xr1710g") ||
	       of_machine_is_compatible("econet,xr1710g-ubi");
}

static bool xr1710g_is_compatible(void)
{
	return of_machine_is_compatible("gemtek,xr1710g") ||
	       of_machine_is_compatible("gemtek,xr1710g-ubi") ||
	       of_machine_is_compatible("econet,xr1710g") ||
	       of_machine_is_compatible("econet,xr1710g-ubi");
}

const char *an7581_release_version(void)
{
	return XG2010G_RELEASE_VERSION;
}

const char *an7581_release_credit(void)
{
	return XG2010G_RELEASE_CREDIT;
}

static void xg2010g_clrsetbits_le32(uintptr_t addr, u32 clear, u32 set)
{
	u32 val = readl((void __iomem *)addr);

	val &= ~clear;
	val |= set;
	writel(val, (void __iomem *)addr);
}

static uintptr_t xg2010g_gpio_data_reg(u32 gpio)
{
	return XG2010G_GPIO_SYSCTL_BASE +
	       (gpio < 32 ? XG2010G_REG_GPIO_DATA : XG2010G_REG_GPIO_DATA1);
}

static uintptr_t xg2010g_gpio_oe_reg(u32 gpio)
{
	return XG2010G_GPIO_SYSCTL_BASE +
	       (gpio < 32 ? XG2010G_REG_GPIO_OE : XG2010G_REG_GPIO_OE1);
}

static uintptr_t xg2010g_gpio_dir_reg(u32 gpio)
{
	static const u16 dir_regs[] = {
		XG2010G_REG_GPIO_CTRL,
		XG2010G_REG_GPIO_CTRL1,
		XG2010G_REG_GPIO_CTRL2,
		XG2010G_REG_GPIO_CTRL3,
	};

	if (gpio >= XG2010G_GPIO_MAX)
		return 0;

	return XG2010G_GPIO_SYSCTL_BASE + dir_regs[gpio / 16];
}

static void xg2010g_gpio_direction_input(u32 gpio)
{
	u32 bank_bit = BIT(gpio % 32);
	u32 dir_bit = BIT(2 * (gpio % 16));
	uintptr_t dir_reg;

	if (gpio >= XG2010G_GPIO_MAX)
		return;

	dir_reg = xg2010g_gpio_dir_reg(gpio);
	if (!dir_reg)
		return;

	xg2010g_clrsetbits_le32(xg2010g_gpio_oe_reg(gpio), bank_bit, 0);
	xg2010g_clrsetbits_le32(dir_reg, dir_bit, 0);
}

static void xg2010g_gpio_prepare_input(u32 gpio)
{
	/*
	 * GPIO0..GPIO15 share the flash/PWM mux register. Clear the bit to
	 * force the pin back to GPIO before sampling the button.
	 */
	if (gpio < 16)
		xg2010g_clrsetbits_le32(XG2010G_CHIP_SCU_BASE +
					XG2010G_REG_GPIO_FLASH_MODE_CFG,
					BIT(gpio), 0);

	xg2010g_gpio_direction_input(gpio);
}

static int xg2010g_recovery_button_pressed_raw(ofnode root)
{
	struct ofnode_phandle_args args;
	u32 gpio, gpio_flags = 0, val;
	int ret;

	ret = ofnode_parse_phandle_with_args(root, "recovery-gpios",
					     "#gpio-cells", 0, 0, &args);
	if (ret || args.args_count < 1)
		return 0;

	gpio = args.args[0];
	if (args.args_count > 1)
		gpio_flags = args.args[1];
	if (gpio >= XG2010G_GPIO_MAX) {
		printf("XG2010G: recovery GPIO %u is out of range\n", gpio);
		return 0;
	}

	xg2010g_gpio_prepare_input(gpio);

	val = readl((void __iomem *)xg2010g_gpio_data_reg(gpio));
	ret = !!(val & BIT(gpio % 32));

	return gpio_flags & GPIO_ACTIVE_LOW ? !ret : ret;
}

static int xg2010g_read_dsd_data(size_t offset, size_t size, void *buf)
{
	struct mtd_info *mtd;
	size_t retlen = 0;
	int ret;

	mtd_probe_devices();
	mtd = get_mtd_device_nm(XG2010G_DSD_PART);
	if (IS_ERR_OR_NULL(mtd))
		return IS_ERR(mtd) ? PTR_ERR(mtd) : -ENODEV;

	ret = mtd_read(mtd, offset, size, &retlen, buf);
	put_mtd_device(mtd);
	if (ret)
		return ret;
	if (retlen != size)
		return -EIO;

	return 0;
}

static bool xg2010g_uenv_is_recovery_trigger(const char *entry, size_t len)
{
	static const char name[] = "recovery_trigger=";

	return len == sizeof(name) && !memcmp(entry, name, sizeof(name) - 1) &&
	       entry[sizeof(name) - 1] == '1';
}

static int xg2010g_uenv_write_block(struct mtd_info *mtd, const u8 *buf)
{
	struct erase_info erase = {
		.mtd = mtd,
		.addr = 0,
		.len = XG2010G_UENV_ERASE_SIZE,
	};
	size_t offset = 0;
	int ret;

	ret = mtd_erase(mtd, &erase);
	if (ret)
		return ret;

	while (offset < XG2010G_UENV_ERASE_SIZE) {
		size_t retlen = 0;
		size_t len = min_t(size_t, mtd->writesize,
				   XG2010G_UENV_ERASE_SIZE - offset);

		ret = mtd_write(mtd, offset, len, &retlen, buf + offset);
		if (ret)
			return ret;
		if (retlen != len)
			return -EIO;

		offset += len;
	}

	return 0;
}

/* Consume the one-shot software flag from the U-Boot environment. */
static int xg2010g_uenv_consume_recovery_trigger(bool *triggered)
{
	struct mtd_info *mtd;
	u8 *block = NULL, *verify = NULL;
	u8 *data, *src, *dst, *end;
	u32 stored_crc, calculated_crc;
	size_t retlen = 0;
	int ret = 0;

	*triggered = false;
	mtd_probe_devices();
	mtd = get_mtd_device_nm(XG2010G_UENV_PART);
	if (IS_ERR_OR_NULL(mtd))
		return IS_ERR(mtd) ? PTR_ERR(mtd) : -ENODEV;

	if (mtd->size < XG2010G_UENV_ERASE_SIZE ||
	    !mtd->writesize || XG2010G_UENV_ERASE_SIZE % mtd->writesize) {
		ret = -EINVAL;
		goto out;
	}

	block = malloc(XG2010G_UENV_ERASE_SIZE);
	verify = malloc(XG2010G_UENV_SIZE);
	if (!block || !verify) {
		ret = -ENOMEM;
		goto out;
	}

	ret = mtd_read(mtd, 0, XG2010G_UENV_ERASE_SIZE, &retlen, block);
	if ((ret && ret != -EUCLEAN) || retlen != XG2010G_UENV_ERASE_SIZE) {
		if (!ret)
			ret = -EIO;
		goto out;
	}
	ret = 0;

	memcpy(&stored_crc, block, sizeof(stored_crc));
	data = block + sizeof(stored_crc);
	calculated_crc = crc32(0, data, XG2010G_UENV_DATA_SIZE);
	if (stored_crc != calculated_crc) {
		ret = -EBADMSG;
		goto out;
	}

	src = data;
	dst = data;
	end = data + XG2010G_UENV_DATA_SIZE;
	while (src < end && *src) {
		size_t len = strnlen((char *)src, end - src);

		if (src + len == end) {
			ret = -EINVAL;
			goto out;
		}

		if (xg2010g_uenv_is_recovery_trigger((char *)src, len)) {
			*triggered = true;
		} else {
			memmove(dst, src, len + 1);
			dst += len + 1;
		}

		src += len + 1;
	}

	if (!*triggered)
		goto out;

	memset(dst, 0, end - dst);
	calculated_crc = crc32(0, data, XG2010G_UENV_DATA_SIZE);
	memcpy(block, &calculated_crc, sizeof(calculated_crc));

	ret = xg2010g_uenv_write_block(mtd, block);
	if (ret)
		goto out;

	retlen = 0;
	ret = mtd_read(mtd, 0, XG2010G_UENV_SIZE, &retlen, verify);
	if ((ret && ret != -EUCLEAN) || retlen != XG2010G_UENV_SIZE) {
		if (!ret)
			ret = -EIO;
		goto out;
	}
	ret = 0;
	if (memcmp(verify, block, XG2010G_UENV_SIZE))
		ret = -EIO;

out:
	if (ret)
		*triggered = false;
	free(block);
	free(verify);
	put_mtd_device(mtd);

	return ret;
}

static int xg2010g_dsd_get_var(const char *buf, size_t len, const char *key,
				 char *value, size_t value_len)
{
	size_t key_len = strlen(key);
	const char *cur = buf;
	const char *end = buf + len;

	if (!value_len)
		return -EINVAL;

	while (cur < end) {
		const char *line_end = memchr(cur, '\n', end - cur);
		size_t line_len, copy_len;

		if (!line_end)
			line_end = end;

		line_len = line_end - cur;
		if (line_len > key_len && !memcmp(cur, key, key_len)) {
			copy_len = line_len - key_len;
			if (copy_len >= value_len)
				copy_len = value_len - 1;

			memcpy(value, cur + key_len, copy_len);
			value[copy_len] = '\0';

			while (copy_len && value[copy_len - 1] == '\r')
				value[--copy_len] = '\0';

			return 0;
		}

		if (line_end == end)
			break;
		cur = line_end + 1;
	}

	return -ENOENT;
}

static int xg2010g_get_dsd_ethaddrs(u8 *lan_mac, u8 *wan_mac)
{
	char *buf;
	char lan_str[ARP_HLEN_ASCII + 1];
	char wan_str[ARP_HLEN_ASCII + 1];
	int ret;

	buf = malloc(XG2010G_DSD_ENV_SIZE + 1);
	if (!buf)
		return -ENOMEM;

	ret = xg2010g_read_dsd_data(0, XG2010G_DSD_ENV_SIZE, buf);
	if (ret)
		goto out;

	buf[XG2010G_DSD_ENV_SIZE] = '\0';

	ret = xg2010g_dsd_get_var(buf, XG2010G_DSD_ENV_SIZE, "lan_mac=",
				  lan_str, sizeof(lan_str));
	if (ret)
		goto out;

	ret = xg2010g_dsd_get_var(buf, XG2010G_DSD_ENV_SIZE, "wan_mac=",
				  wan_str, sizeof(wan_str));
	if (ret)
		goto out;

	string_to_enetaddr(lan_str, lan_mac);
	string_to_enetaddr(wan_str, wan_mac);
	if (!is_valid_ethaddr(lan_mac) || !is_valid_ethaddr(wan_mac)) {
		ret = -EINVAL;
		goto out;
	}

	ret = 0;

out:
	free(buf);
	return ret;
}

static int xg2010g_create_ubi_volume(const char *name, size_t size)
{
	struct ubi_mkvol_req req;
	struct ubi_device *ubi;
	int ret;

	if (!name || !*name)
		return -EINVAL;

	ubi = ubi_get_device(0);
	if (!ubi)
		return -ENODEV;

	memset(&req, 0, sizeof(req));
	req.vol_id = UBI_VOL_NUM_AUTO;
	req.alignment = 1;
	req.bytes = size;
	req.vol_type = UBI_STATIC_VOLUME;
	req.name_len = strlen(name);
	if (req.name_len > UBI_VOL_NAME_MAX) {
		ubi_put_device(ubi);
		return -ENAMETOOLONG;
	}
	memcpy(req.name, name, req.name_len);
	req.name[req.name_len] = '\0';

	mutex_lock(&ubi->device_mutex);
	ret = ubi_create_volume(ubi, &req);
	mutex_unlock(&ubi->device_mutex);
	ubi_put_device(ubi);

	return ret;
}

static int xg2010g_resize_ubi_volume(const char *name, size_t size)
{
	struct ubi_volume_desc *desc;
	struct ubi_volume *vol;
	int ret, needed_pebs;

	if (!name || !*name)
		return -EINVAL;

	desc = ubi_open_volume_nm(0, name, UBI_EXCLUSIVE);
	if (IS_ERR_OR_NULL(desc))
		return IS_ERR(desc) ? PTR_ERR(desc) : -ENODEV;

	vol = desc->vol;
	needed_pebs = DIV_ROUND_UP(size, vol->usable_leb_size);

	mutex_lock(&vol->ubi->device_mutex);
	ret = ubi_resize_volume(desc, needed_pebs);
	mutex_unlock(&vol->ubi->device_mutex);
	ubi_close_volume(desc);

	return ret;
}

static int xg2010g_ensure_ubi_volume(const char *name, size_t size)
{
	struct ubi_volume_desc *desc;
	unsigned long long cur_size;
	int ret;

	if (!name || !*name)
		return -EINVAL;

	desc = ubi_open_volume_nm(0, name, UBI_READWRITE);
	if (IS_ERR_OR_NULL(desc)) {
		ret = xg2010g_create_ubi_volume(name, size);
		if (!ret)
			return 0;
		return ret;
	}

	cur_size = (unsigned long long)desc->vol->reserved_pebs *
		   (unsigned long long)desc->vol->usable_leb_size;
	ubi_close_volume(desc);

	if (size <= cur_size)
		return 0;

	return xg2010g_resize_ubi_volume(name, size);
}

static const struct xg2010g_ubi_layout *
xg2010g_find_ubi_layout(const char *part)
{
	int i;

	if (!part)
		return NULL;

	for (i = 0; i < ARRAY_SIZE(xg2010g_ubi_layouts); i++) {
		if (!strcmp(part, xg2010g_ubi_layouts[i].part))
			return &xg2010g_ubi_layouts[i];
	}

	return NULL;
}

static bool xg2010g_ubi_mtd_valid(const struct mtd_info *mtd)
{
	return mtd && mtd->size == xg2010g_ubi_geometry.size &&
		mtd->erasesize == xg2010g_ubi_geometry.erase_size &&
		mtd->writesize == xg2010g_ubi_geometry.write_size &&
		mtd->oobsize == xg2010g_ubi_geometry.oob_size;
}

static bool xg2010g_bootarg_has(const char *bootargs, const char *arg)
{
	size_t len = strlen(arg);
	const char *pos = bootargs;

	while ((pos = strstr(pos, arg))) {
		bool starts_token = pos == bootargs || pos[-1] == ' ' ||
			pos[-1] == '\t';
		bool ends_token = !pos[len] || pos[len] == ' ' ||
			pos[len] == '\t';

		if (starts_token && ends_token)
			return true;
		pos += len;
	}

	return false;
}

static bool xg2010g_bootargs_need_migration(const char *bootargs)
{
	if (!bootargs || !*bootargs)
		return true;

	return !xg2010g_bootarg_has(bootargs, "ubi.mtd=ubi") ||
		!xg2010g_bootarg_has(bootargs, "ubi.block=0,fit") ||
		!xg2010g_bootarg_has(bootargs, "root=/dev/fit0") ||
		strstr(bootargs, "ubi.mtd=system") ||
		strstr(bootargs, "ubi.mtd=tclinux") ||
		strstr(bootargs, "ubi.mtd=tclinux_slave") ||
		strstr(bootargs, "root=/dev/mtdblock");
}

static int xg2010g_select_ubi(const char *part)
{
	struct ubi_device *ubi;
	bool selected = false;
	int ret;

	if (!xg2010g_find_ubi_layout(part))
		return -EINVAL;

	ubi = ubi_get_device(0);
	if (ubi) {
		selected = ubi->mtd && !strcmp(ubi->mtd->name, part);
		if (selected && !xg2010g_ubi_mtd_valid(ubi->mtd)) {
			ubi_put_device(ubi);
			return -EINVAL;
		}
		ubi_put_device(ubi);
	}

	if (selected)
		return 0;

	ret = ubi_part(part, NULL);
	if (ret)
		return ret;

	ubi = ubi_get_device(0);
	if (!ubi)
		return -ENODEV;
	selected = ubi->mtd && !strcmp(ubi->mtd->name, part) &&
		xg2010g_ubi_mtd_valid(ubi->mtd);
	ubi_put_device(ubi);

	return selected ? 0 : -EINVAL;
}

const char *xg2010g_detect_ubi_part(void)
{
	struct mtd_info *mtd;
	struct ubi_volume_desc *fit;
	int ret;

	if (xg2010g_ubi_layout_probed)
		return xg2010g_active_ubi_layout->part;

	xg2010g_ubi_layout_probed = true;
	xg2010g_ubi_layout_available = false;
	xg2010g_active_ubi_layout = &xg2010g_ubi_layouts[0];
	mtd_probe_devices();

	mtd = get_mtd_device_nm(XG2010G_UBI_PART);
	if (IS_ERR_OR_NULL(mtd)) {
		printf("XG2010G: project UBI partition '%s' is not present\n",
		       XG2010G_UBI_PART);
		return xg2010g_active_ubi_layout->part;
	}
	if (!xg2010g_ubi_mtd_valid(mtd)) {
		printf("XG2010G: '%s' has unexpected geometry (size 0x%llx, erase 0x%x, write 0x%x, oob 0x%x)\n",
		       XG2010G_UBI_PART, (unsigned long long)mtd->size,
		       mtd->erasesize, mtd->writesize, mtd->oobsize);
		put_mtd_device(mtd);
		return xg2010g_active_ubi_layout->part;
	}
	put_mtd_device(mtd);

	/*
	 * Presence of the fixed MTD partition is not enough: an erased NAND
	 * region and an attached legacy UBI must both be rejected.  The project
	 * image is considered bootable only when UBI attaches and contains the
	 * mandatory FIT volume.
	 */
	ret = xg2010g_select_ubi(XG2010G_UBI_PART);
	if (ret) {
		printf("XG2010G: project UBI attach failed on '%s': %d\n",
		       XG2010G_UBI_PART, ret);
		return xg2010g_active_ubi_layout->part;
	}

	fit = ubi_open_volume_nm(0, "fit", UBI_READONLY);
	if (IS_ERR_OR_NULL(fit)) {
		printf("XG2010G: project UBI on '%s' has no 'fit' volume\n",
		       XG2010G_UBI_PART);
		return xg2010g_active_ubi_layout->part;
	}
	ubi_close_volume(fit);
	xg2010g_ubi_layout_available = true;

	if (xg2010g_ubi_layout_available)
		printf("XG2010G: detected UBI %s on '%s'\n",
		       xg2010g_active_ubi_layout->version,
		       xg2010g_active_ubi_layout->part);

	return xg2010g_active_ubi_layout->part;
}

const char *xg2010g_detect_ubi_version(void)
{
	xg2010g_detect_ubi_part();
	return xg2010g_ubi_layout_available ?
		xg2010g_active_ubi_layout->version : "unformatted";
}

const char *env_ubi_get_part(void)
{
	return xg2010g_detect_ubi_part();
}

int xg2010g_sync_factory_part(const char *part)
{
	u8 *src = NULL, *dst = NULL;
	u8 *wan_mac, *lan_mac;
	bool same = false;
	int ret = 0;

	if (!xg2010g_is_compatible())
		return 0;

	ret = xg2010g_select_ubi(part);
	if (ret) {
		printf("XG2010G: skipping factory sync; UBI is unavailable: %d\n",
		       ret);
		return ret;
	}

	src = malloc(XG2010G_FACTORY_SIZE);
	dst = malloc(XG2010G_FACTORY_SIZE);
	if (!src || !dst) {
		ret = -ENOMEM;
		goto out;
	}

	memset(src, 0xff, XG2010G_FACTORY_SIZE);
	wan_mac = src + XG2010G_FACTORY_WAN_MAC_OFFSET;
	lan_mac = src + XG2010G_FACTORY_LAN_MAC_OFFSET;

	ret = xg2010g_get_dsd_ethaddrs(lan_mac, wan_mac);
	if (ret) {
		printf("XG2010G: failed to read MAC addresses from DSD: %d\n",
		       ret);
		goto out;
	}

	ret = ubi_volume_read(XG2010G_FACTORY_VOL, (char *)dst, 0,
			      XG2010G_FACTORY_SIZE);
	if (!ret && !memcmp(src, dst, XG2010G_FACTORY_SIZE))
		same = true;

	if (same) {
		ret = 0;
		goto out;
	}

	ret = xg2010g_ensure_ubi_volume(XG2010G_FACTORY_VOL,
					XG2010G_FACTORY_SIZE);
	if (ret) {
		printf("XG2010G: failed to prepare UBI volume '%s': %d\n",
		       XG2010G_FACTORY_VOL, ret);
		goto out;
	}

	ret = ubi_volume_write(XG2010G_FACTORY_VOL, src, 0,
			       XG2010G_FACTORY_SIZE);
	if (ret) {
		printf("XG2010G: failed to update UBI volume '%s': %d\n",
		       XG2010G_FACTORY_VOL, ret);
		goto out;
	}

	printf("XG2010G: synchronized %u bytes of DSD factory data to '%s'\n",
	       XG2010G_FACTORY_SIZE, XG2010G_FACTORY_VOL);

out:
	free(src);
	free(dst);
	return ret;
}

int xg2010g_sync_factory(void)
{
	const char *part = xg2010g_detect_ubi_part();

	if (!xg2010g_ubi_layout_available)
		return -ENODEV;

	return xg2010g_sync_factory_part(part);
}

static void xg2010g_mac_add(const u8 *base, u8 delta, u8 *mac)
{
	int i;
	unsigned int carry = delta;

	memcpy(mac, base, ARP_HLEN);
	for (i = ARP_HLEN - 1; i >= 0 && carry; i--) {
		carry += mac[i];
		mac[i] = carry & 0xff;
		carry >>= 8;
	}
}

static int xg2010g_get_runtime_ethaddrs(u8 *lan_mac, u8 *wan_mac)
{
	int ret;

	ret = xg2010g_get_dsd_ethaddrs(lan_mac, wan_mac);
	if (!ret)
		return 0;

	if (!eth_env_get_enetaddr("ethaddr", lan_mac) ||
	    !is_valid_ethaddr(lan_mac))
		return ret;

	if (!eth_env_get_enetaddr("eth1addr", wan_mac) ||
	    !is_valid_ethaddr(wan_mac))
		xg2010g_mac_add(lan_mac, 4, wan_mac);

	return 0;
}

static void xg2010g_sync_runtime_ethaddrs(void)
{
	u8 lan_mac[ARP_HLEN], wan_mac[ARP_HLEN];
	int ret;

	if (!xg2010g_is_compatible())
		return;

	ret = xg2010g_get_runtime_ethaddrs(lan_mac, wan_mac);
	if (ret) {
		printf("XG2010G: failed to obtain runtime MACs from DSD or env: %d\n",
		       ret);
		return;
	}

	eth_env_set_enetaddr("ethaddr", lan_mac);
	eth_env_set_enetaddr("eth1addr", wan_mac);
	printf("XG2010G: runtime MACs LAN=%pM WAN=%pM\n",
	       lan_mac, wan_mac);
}

static int xg2010g_fdt_set_mac(void *blob, const char *path, const u8 *mac)
{
	int node, ret;

	node = fdt_path_offset(blob, path);
	if (node < 0)
		return node;

	ret = fdt_setprop(blob, node, "mac-address", mac, ARP_HLEN);
	if (ret)
		return ret;

	return fdt_setprop(blob, node, "local-mac-address", mac, ARP_HLEN);
}

static void xg2010g_fixup_fdt_macs(void *blob)
{
	u8 lan_mac[ARP_HLEN], wan_mac[ARP_HLEN];
	int i, ret;

	if (!xg2010g_is_compatible())
		return;

	if (xg2010g_get_runtime_ethaddrs(lan_mac, wan_mac))
		return;

	for (i = 0; i < ARRAY_SIZE(xg2010g_fdt_lan_mac_paths); i++) {
		ret = xg2010g_fdt_set_mac(blob, xg2010g_fdt_lan_mac_paths[i],
					  lan_mac);
		if (ret && ret != -FDT_ERR_NOTFOUND)
			printf("XG2010G: failed to update MAC for %s: %d\n",
			       xg2010g_fdt_lan_mac_paths[i], ret);
	}

	for (i = 0; i < ARRAY_SIZE(xg2010g_fdt_wan_mac_paths); i++) {
		ret = xg2010g_fdt_set_mac(blob, xg2010g_fdt_wan_mac_paths[i],
					  wan_mac);
		if (ret && ret != -FDT_ERR_NOTFOUND)
			printf("XG2010G: failed to update MAC for %s: %d\n",
			       xg2010g_fdt_wan_mac_paths[i], ret);
	}
}

int board_init(void)
{
	/* address of boot parameters */
	gd->bd->bi_boot_params = CFG_SYS_SDRAM_BASE + 0x100;

	return 0;
}

/*
 * recovery_board_ops bridge: the recovery server in net/lwip/httpd_recovery.c
 * resolves its board-specific behaviour through this struct rather than
 * calling individual xg2010g_* externs.  Both Brightspeed Gemtek AN7581
 * boards (XG2010G and XR1710G) share the NAND/UBI layout and DSD/uenv
 * handling, so a single ops singleton covers them.
 */
const struct recovery_board_ops *recovery_get_board_ops(void)
{
	static const struct recovery_board_ops ops = {
		.match			= xg2010g_is_compatible,
		.ubi			= &xg2010g_ubi_geometry,
		.detect_ubi_part	= xg2010g_detect_ubi_part,
		.detect_ubi_version	= xg2010g_detect_ubi_version,
		.sync_factory_part	= xg2010g_sync_factory_part,
		.sync_factory		= xg2010g_sync_factory,
		.mtd_ubi_valid		= xg2010g_ubi_mtd_valid,
	};

	return &ops;
}

int run_http_recovery(void);

static int xg2010g_recovery_button_pressed(void)
{
	struct gpio_desc rec_gpio;
	ofnode root;
	int ret;

	if (!xg2010g_is_compatible())
		return 0;

	memset(&rec_gpio, 0, sizeof(rec_gpio));
	root = ofnode_path("/");
	ret = gpio_request_by_name_nodev(root, "recovery-gpios", 0, &rec_gpio,
					 GPIOD_IS_IN);
	if (ret)
		return xg2010g_recovery_button_pressed_raw(root);

	ret = dm_gpio_get_value(&rec_gpio);
	dm_gpio_free(NULL, &rec_gpio);

	return ret > 0;
}

/*
 * Require the recovery button to remain pressed for a short, configurable
 * interval.  This avoids entering recovery on a switch bounce or a brief
 * accidental press while still allowing a zero-second immediate trigger.
 */
static bool xg2010g_recovery_button_confirmed(void)
{
	ulong timeout = env_get_ulong("recovery_button_timeout", 10, 3);
	ulong start, elapsed, shown = ~0UL;

	if (!xg2010g_recovery_button_pressed())
		return false;

	if (!timeout) {
		printf("Recovery button detected, starting web recovery...\n");
		return true;
	}

	/* Avoid an unexpectedly long blocking delay from a corrupt environment. */
	if (timeout > 30)
		timeout = 30;

	printf("Recovery button detected; hold for %lu seconds", timeout);
	start = get_timer(0);
	for (;;) {
		if (!xg2010g_recovery_button_pressed()) {
			printf("\nRecovery button released; continuing normal boot\n");
			return false;
		}

		elapsed = get_timer(start);
		if (elapsed >= timeout * 1000)
			break;

		{
			ulong left = timeout - elapsed / 1000;

			if (left != shown) {
				printf("\nRecovery starts in %lu...", left);
				shown = left;
			}
		}
		mdelay(100);
	}

	printf("\nRecovery button hold confirmed, starting web recovery...\n");
	return true;
}

int board_late_init(void)
{
	char boot_ubi[64];
	const char *ubi_part;
	const char *bootcmd;
	const char *default_bootargs;
	ulong recovery_addr;
	bool uenv_triggered = false;

	printf("%s release %s - %s\n",
	       xr1710g_is_compatible() ? "Brightspeed Gemtek XR1710G"
				       : "Brightspeed Gemtek XG2010G",
	       XG2010G_RELEASE_VERSION, XG2010G_RELEASE_CREDIT);
	printf("HTTP recovery: type 'http_recovery', then open http://192.168.1.1/ in incognito mode (PC 192.168.1.2/24)\n");

	/* Read only the one-shot mtd1/uenv flag; never save mtd0 env. */
	if (xg2010g_is_compatible()) {
		int trigger_ret = xg2010g_uenv_consume_recovery_trigger(&uenv_triggered);
		if (trigger_ret && trigger_ret != -ENODEV && trigger_ret != -EBADMSG)
			printf("XG2010G: uenv trigger read failed: %d\n", trigger_ret);
	}

	/* Populate the Ethernet addresses before the network stack is initialized. */
	/*
	 * The persistent environment is in mtd1/uenv, but factory MACs are not
	 * guaranteed to be present there. Read them from dsd before
	 * eth_initialize() runs, otherwise the Ethernet uclass generates a random
	 * locally-administered address. This is a small 4 KiB read and is safe
	 * after initr_nand.
	 */
	xg2010g_sync_runtime_ethaddrs();
	ubi_part = xg2010g_detect_ubi_part();
	snprintf(boot_ubi, sizeof(boot_ubi),
		 "ubi part %s && run boot_production", ubi_part);
	/* XG2010G has one supported boot recipe. Do not allow a persistent
	 * factory environment to select a raw/legacy image path or omit the
	 * Recovery fallback. */
	bootcmd = env_get("bootcmd");
	if (!bootcmd || strcmp(bootcmd, "run boot_ubi || http_recovery")) {
		env_set("bootcmd", "run boot_ubi || http_recovery");
		printf("XG2010G: forced bootcmd to UBI FIT with recovery fallback\n");
	}
	/* These helpers are also forced because an old environment may contain
	 * an otherwise valid-looking recipe that reads tclinux/system. */
	env_set("boot_ubi", boot_ubi);
	env_set("ubi_read_production", "ubi read ${loadaddr} fit");
	env_set("boot_production",
		 "run ubi_read_production && bootm ${loadaddr}#${bootconf}");
	env_set("bootconf", "config-1");
	env_set("recovery_mtd", "fit");
	env_set("recovery_ubi_part", XG2010G_UBI_PART);
	if (xg2010g_bootargs_need_migration(env_get("bootargs"))) {
		default_bootargs = env_get_default("bootargs");
		if (default_bootargs) {
			env_set("bootargs", default_bootargs);
			printf("XG2010G: replaced bootargs incompatible with project UBI\n");
		}
	}
	/* The factory environment carries fdt_high=0xac000000 from the
	 * vendor boot flow. That fixed ceiling forces the relocated DTB into
	 * an unsuitable high-memory window on this 64-bit U-Boot. Let the
	 * normal LMB allocator choose a valid, reserved-safe address instead. */
	if (env_get("fdt_high")) {
		env_set("fdt_high", NULL);
		printf("XG2010G: cleared legacy fdt_high override\n");
	}
	/*
	 * Do not perform large raw NAND/UBI reads from board_late_init.  On this
	 * board the first-stage loader may leave SNFI/DMA active; large early
	 * reads can overwrite relocated U-Boot text before eth_initialize().
	 * Factory synchronisation is deferred to the normal production path.
	 */
	/* Either the one-shot software flag or the reset button selects recovery. */
	if (uenv_triggered) {
		printf("Factory uenv recovery trigger consumed, starting web recovery...\n");
	} else if (env_get("recovery_trigger") &&
	    !strcmp(env_get("recovery_trigger"), "1")) {
		/* The persistent clear is performed by the MTD environment backend. */
		env_set("recovery_trigger", "0");
	} else if (!xg2010g_recovery_button_confirmed()) {
		return 0;
	}

	env_set("ipaddr", "192.168.1.1");
	env_set("netmask", "255.255.255.0");
	env_set("gatewayip", "0.0.0.0");
	printf("%s recovery network: eth1/gdm1 1G switch port only\n",
	       xr1710g_is_compatible() ? "XR1710G" : "XG2010G");

	/*
	 * Keep the recovery upload buffer well away from the low-memory
	 * boot/load addresses. Large HTTP uploads are staged fully in RAM
	 * before flashing.
	 */
	recovery_addr = gd->ram_base + 0x10000000UL;
	if ((recovery_addr < gd->ram_base) ||
	    (recovery_addr >= gd->ram_base + gd->ram_size))
		recovery_addr = CONFIG_SYS_LOAD_ADDR;
	env_set_hex("recovery_addr", recovery_addr);

	if (IS_ENABLED(CONFIG_HTTPD_RECOVERY)) {
		/* Do not fall through into autoboot after Ctrl-C. Re-entering
		 * normal UBI boot while Ethernet/QDMA is being torn down can abort. */
		run_http_recovery();
		env_set("bootdelay", "-1");
		printf("Recovery stopped; autoboot disabled (reset to resume normal boot)\n");
	} else
		printf("HTTP recovery is not enabled.\n");

	return 0;
}

#if defined(CONFIG_OF_LIBFDT) && defined(CONFIG_OF_BOARD_SETUP)
int ft_board_setup(void *blob, struct bd_info *bd)
{
	if (!blob)
		return 0;

	xg2010g_fixup_fdt_macs(blob);

	return 0;
}
#endif
