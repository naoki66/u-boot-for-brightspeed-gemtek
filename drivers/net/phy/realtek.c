// SPDX-License-Identifier: GPL-2.0+
/*
 * RealTek PHY drivers
 *
 * Copyright 2010-2011, 2015 Freescale Semiconductor, Inc.
 * author Andy Fleming
 * Copyright 2016 Karsten Merker <merker@debian.org>
 */
#include <linux/bitops.h>
#include <phy.h>
#include <linux/delay.h>

#define PHY_RTL8211x_FORCE_MASTER BIT(1)
#define PHY_RTL8211F_FORCE_EEE_RXC_ON BIT(3)
#define PHY_RTL8201F_S700_RMII_TIMINGS BIT(4)

#define PHY_AUTONEGOTIATE_TIMEOUT 5000

/* RTL8211x 1000BASE-T Control Register */
#define MIIM_RTL8211x_CTRL1000T_MSCE BIT(12);
#define MIIM_RTL8211x_CTRL1000T_MASTER BIT(11);

/* RTL8211x PHY Status Register */
#define MIIM_RTL8211x_PHY_STATUS       0x11
#define MIIM_RTL8211x_PHYSTAT_SPEED    0xc000
#define MIIM_RTL8211x_PHYSTAT_GBIT     0x8000
#define MIIM_RTL8211x_PHYSTAT_100      0x4000
#define MIIM_RTL8211x_PHYSTAT_DUPLEX   0x2000
#define MIIM_RTL8211x_PHYSTAT_SPDDONE  0x0800
#define MIIM_RTL8211x_PHYSTAT_LINK     0x0400

/* RTL8211x PHY Interrupt Enable Register */
#define MIIM_RTL8211x_PHY_INER         0x12
#define MIIM_RTL8211x_PHY_INTR_ENA     0x9f01
#define MIIM_RTL8211x_PHY_INTR_DIS     0x0000

/* RTL8211x PHY Interrupt Status Register */
#define MIIM_RTL8211x_PHY_INSR         0x13

/* RTL8211F PHY Status Register */
#define MIIM_RTL8211F_PHY_STATUS       0x1a
#define MIIM_RTL8211F_AUTONEG_ENABLE   0x1000
#define MIIM_RTL8211F_PHYSTAT_SPEED    0x0030
#define MIIM_RTL8211F_PHYSTAT_GBIT     0x0020
#define MIIM_RTL8211F_PHYSTAT_100      0x0010
#define MIIM_RTL8211F_PHYSTAT_DUPLEX   0x0008
#define MIIM_RTL8211F_PHYSTAT_SPDDONE  0x0800
#define MIIM_RTL8211F_PHYSTAT_LINK     0x0004

#define MIIM_RTL8211E_CONFREG		0x1c
#define MIIM_RTL8211E_CTRL_DELAY	BIT(13)
#define MIIM_RTL8211E_TX_DELAY		BIT(12)
#define MIIM_RTL8211E_RX_DELAY		BIT(11)

#define MIIM_RTL8211E_EXT_PAGE_SELECT  0x1e

#define MIIM_RTL8211F_PAGE_SELECT      0x1f
#define MIIM_RTL8211F_TX_DELAY		0x100
#define MIIM_RTL8211F_RX_DELAY		0x8
#define MIIM_RTL8211F_LCR		0x10

#define RTL8201F_RMSR			0x10

#define RTL8261N_PHY_ID			0x1ccaf3
#define RTL8261N_PHYSR			0xa434
#define RTL8261N_PHYSR_LINK		BIT(2)
#define RTL8261N_PHYSR_DUPLEX		BIT(3)
#define RTL8261N_PHYSR_SPEED(val)	(((((val) >> 9) & 0x3) << 2) | \
					 (((val) >> 4) & 0x3))
#define RTL8261N_SPEED_100M		0x1
#define RTL8261N_SPEED_1000M		0x2
#define RTL8261N_SPEED_2500M		0x5
#define RTL8261N_SPEED_5G		0x6
#define RTL8261N_SPEED_10G		0x4

#define RTL8261N_AN_1000T_CTRL		0xa412
#define RTL8261N_AN_1000T_FD		BIT(9)
#define RTL8261N_AN_MULTI_GBT_CTRL	0x20
#define RTL8261N_AN_2500T_FD		BIT(7)
#define RTL8261N_AN_5000T_FD		BIT(8)
#define RTL8261N_AN_10000T_FD		BIT(12)

#define RMSR_RX_TIMING_SHIFT		BIT(2)
#define RMSR_RX_TIMING_MASK		GENMASK(7, 4)
#define RMSR_RX_TIMING_VAL		0x4
#define RMSR_TX_TIMING_SHIFT		BIT(3)
#define RMSR_TX_TIMING_MASK		GENMASK(11, 8)
#define RMSR_TX_TIMING_VAL		0x5

static int rtl8211f_phy_extread(struct phy_device *phydev, int addr,
				int devaddr, int regnum)
{
	int oldpage = phy_read(phydev, MDIO_DEVAD_NONE,
			       MIIM_RTL8211F_PAGE_SELECT);
	int val;

	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, devaddr);
	val = phy_read(phydev, MDIO_DEVAD_NONE, regnum);
	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, oldpage);

	return val;
}

static int rtl8211f_phy_extwrite(struct phy_device *phydev, int addr,
				 int devaddr, int regnum, u16 val)
{
	int oldpage = phy_read(phydev, MDIO_DEVAD_NONE,
			       MIIM_RTL8211F_PAGE_SELECT);

	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, devaddr);
	phy_write(phydev, MDIO_DEVAD_NONE, regnum, val);
	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, oldpage);

	return 0;
}

static int rtl8211b_probe(struct phy_device *phydev)
{
#ifdef CONFIG_RTL8211X_PHY_FORCE_MASTER
	phydev->flags |= PHY_RTL8211x_FORCE_MASTER;
#endif

	return 0;
}

static int rtl8211e_probe(struct phy_device *phydev)
{
	return 0;
}

static int rtl8211f_probe(struct phy_device *phydev)
{
#ifdef CONFIG_RTL8211F_PHY_FORCE_EEE_RXC_ON
	phydev->flags |= PHY_RTL8211F_FORCE_EEE_RXC_ON;
#endif

	return 0;
}

static int rtl8210f_probe(struct phy_device *phydev)
{
#ifdef CONFIG_RTL8201F_PHY_S700_RMII_TIMINGS
	phydev->flags |= PHY_RTL8201F_S700_RMII_TIMINGS;
#endif

	return 0;
}

/* RealTek RTL8211x */
static int rtl8211x_config(struct phy_device *phydev)
{
	phy_write(phydev, MDIO_DEVAD_NONE, MII_BMCR, BMCR_RESET);

	/* mask interrupt at init; if the interrupt is
	 * needed indeed, it should be explicitly enabled
	 */
	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211x_PHY_INER,
		  MIIM_RTL8211x_PHY_INTR_DIS);

	if (phydev->flags & PHY_RTL8211x_FORCE_MASTER) {
		unsigned int reg;

		reg = phy_read(phydev, MDIO_DEVAD_NONE, MII_CTRL1000);
		/* force manual master/slave configuration */
		reg |= MIIM_RTL8211x_CTRL1000T_MSCE;
		/* force master mode */
		reg |= MIIM_RTL8211x_CTRL1000T_MASTER;
		phy_write(phydev, MDIO_DEVAD_NONE, MII_CTRL1000, reg);
	}
	/* read interrupt status just to clear it */
	phy_read(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211x_PHY_INER);

	genphy_config_aneg(phydev);

	return 0;
}

/* RealTek RTL8201F */
static int rtl8201f_config(struct phy_device *phydev)
{
	unsigned int reg;

	if (phydev->flags & PHY_RTL8201F_S700_RMII_TIMINGS) {
		phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT,
			  7);
		reg = phy_read(phydev, MDIO_DEVAD_NONE, RTL8201F_RMSR);
		reg &= ~(RMSR_RX_TIMING_MASK | RMSR_TX_TIMING_MASK);
		/* Set the needed Rx/Tx Timings for proper PHY operation */
		reg |= (RMSR_RX_TIMING_VAL << RMSR_RX_TIMING_SHIFT)
		       | (RMSR_TX_TIMING_VAL << RMSR_TX_TIMING_SHIFT);
		phy_write(phydev, MDIO_DEVAD_NONE, RTL8201F_RMSR, reg);
		phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT,
			  0);
	}

	genphy_config_aneg(phydev);

	return 0;
}

static int rtl8211e_config(struct phy_device *phydev)
{
	int reg, val;

	/* enable TX/RX delay for rgmii-* modes, and disable them for rgmii. */
	switch (phydev->interface) {
	case PHY_INTERFACE_MODE_RGMII:
		val = MIIM_RTL8211E_CTRL_DELAY;
		break;
	case PHY_INTERFACE_MODE_RGMII_ID:
		val = MIIM_RTL8211E_CTRL_DELAY | MIIM_RTL8211E_TX_DELAY |
		      MIIM_RTL8211E_RX_DELAY;
		break;
	case PHY_INTERFACE_MODE_RGMII_RXID:
		val = MIIM_RTL8211E_CTRL_DELAY | MIIM_RTL8211E_RX_DELAY;
		break;
	case PHY_INTERFACE_MODE_RGMII_TXID:
		val = MIIM_RTL8211E_CTRL_DELAY | MIIM_RTL8211E_TX_DELAY;
		break;
	default: /* the rest of the modes imply leaving delays as is. */
		goto default_delay;
	}

	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, 7);
	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211E_EXT_PAGE_SELECT, 0xa4);

	reg = phy_read(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211E_CONFREG);
	reg &= ~(MIIM_RTL8211E_TX_DELAY | MIIM_RTL8211E_RX_DELAY);
	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211E_CONFREG, reg | val);

	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, 0);

default_delay:
	genphy_config_aneg(phydev);

	return 0;
}

static int rtl8211f_config(struct phy_device *phydev)
{
	u16 reg;

	if (phydev->flags & PHY_RTL8211F_FORCE_EEE_RXC_ON) {
		unsigned int reg;

		reg = phy_read_mmd(phydev, MDIO_MMD_PCS, MDIO_CTRL1);
		reg &= ~MDIO_PCS_CTRL1_CLKSTOP_EN;
		phy_write_mmd(phydev, MDIO_MMD_PCS, MDIO_CTRL1, reg);
	}

	phy_write(phydev, MDIO_DEVAD_NONE, MII_BMCR, BMCR_RESET);

	phy_write(phydev, MDIO_DEVAD_NONE,
		  MIIM_RTL8211F_PAGE_SELECT, 0xd08);
	reg = phy_read(phydev, MDIO_DEVAD_NONE, 0x11);

	/* enable TX-delay for rgmii-id and rgmii-txid, otherwise disable it */
	if (phydev->interface == PHY_INTERFACE_MODE_RGMII_ID ||
	    phydev->interface == PHY_INTERFACE_MODE_RGMII_TXID)
		reg |= MIIM_RTL8211F_TX_DELAY;
	else
		reg &= ~MIIM_RTL8211F_TX_DELAY;

	phy_write(phydev, MDIO_DEVAD_NONE, 0x11, reg);

	/* enable RX-delay for rgmii-id and rgmii-rxid, otherwise disable it */
	reg = phy_read(phydev, MDIO_DEVAD_NONE, 0x15);
	if (phydev->interface == PHY_INTERFACE_MODE_RGMII_ID ||
	    phydev->interface == PHY_INTERFACE_MODE_RGMII_RXID)
		reg |= MIIM_RTL8211F_RX_DELAY;
	else
		reg &= ~MIIM_RTL8211F_RX_DELAY;
	phy_write(phydev, MDIO_DEVAD_NONE, 0x15, reg);

	/* restore to default page 0 */
	phy_write(phydev, MDIO_DEVAD_NONE,
		  MIIM_RTL8211F_PAGE_SELECT, 0x0);

	/* Set green LED for Link, yellow LED for Active */
	phy_write(phydev, MDIO_DEVAD_NONE,
		  MIIM_RTL8211F_PAGE_SELECT, 0xd04);
	phy_write(phydev, MDIO_DEVAD_NONE, 0x10, 0x617f);
	phy_write(phydev, MDIO_DEVAD_NONE,
		  MIIM_RTL8211F_PAGE_SELECT, 0x0);

	genphy_config_aneg(phydev);

	return 0;
}

static int rtl8261n_config(struct phy_device *phydev)
{
	int ret;

	phydev->supported = PHY_10G_FEATURES | SUPPORTED_2500baseX_Full |
			    SUPPORTED_Pause | SUPPORTED_Asym_Pause;
	phydev->advertising = PHY_100BT_FEATURES | PHY_1000BT_FEATURES |
			      SUPPORTED_2500baseX_Full |
			      SUPPORTED_10000baseT_Full |
			      SUPPORTED_Autoneg | SUPPORTED_TP |
			      SUPPORTED_Pause | SUPPORTED_Asym_Pause;

	ret = gen10g_discover_mmds(phydev);
	if (ret)
		return ret;

	/*
	 * The vendor OpenWrt stack advertises RTL8261N 1G through vendor
	 * MMD31 register 0xa412 and 2.5G/5G/10G through AN register 0x20.
	 * Keep 5G disabled because the Airoha PCS code in U-Boot does not
	 * currently have a SPEED_5000 path.
	 */
	ret = phy_modify_mmd(phydev, MDIO_MMD_AN, MDIO_AN_ADVERTISE,
			     ADVERTISE_10HALF | ADVERTISE_10FULL |
			     ADVERTISE_100HALF | ADVERTISE_100FULL |
			     ADVERTISE_PAUSE_CAP | ADVERTISE_PAUSE_ASYM,
			     ADVERTISE_100HALF | ADVERTISE_100FULL |
			     ADVERTISE_PAUSE_CAP | ADVERTISE_PAUSE_ASYM);
	if (ret)
		return ret;

	ret = phy_modify_mmd(phydev, MDIO_MMD_VEND2, RTL8261N_AN_1000T_CTRL,
			     RTL8261N_AN_1000T_FD, RTL8261N_AN_1000T_FD);
	if (ret)
		return ret;

	ret = phy_modify_mmd(phydev, MDIO_MMD_AN,
			     RTL8261N_AN_MULTI_GBT_CTRL,
			     RTL8261N_AN_2500T_FD | RTL8261N_AN_5000T_FD |
			     RTL8261N_AN_10000T_FD,
			     RTL8261N_AN_2500T_FD |
			     RTL8261N_AN_10000T_FD);
	if (ret)
		return ret;

	return phy_modify_mmd(phydev, MDIO_MMD_AN, MDIO_CTRL1,
			      MDIO_AN_CTRL1_ENABLE | MDIO_AN_CTRL1_RESTART,
			      MDIO_AN_CTRL1_ENABLE | MDIO_AN_CTRL1_RESTART);
}

static int rtl8211x_parse_status(struct phy_device *phydev)
{
	unsigned int speed;
	unsigned int mii_reg;

	mii_reg = phy_read(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211x_PHY_STATUS);

	if (!(mii_reg & MIIM_RTL8211x_PHYSTAT_SPDDONE)) {
		int i = 0;

		/* in case of timeout ->link is cleared */
		phydev->link = 1;
		puts("Waiting for PHY realtime link");
		while (!(mii_reg & MIIM_RTL8211x_PHYSTAT_SPDDONE)) {
			/* Timeout reached ? */
			if (i > PHY_AUTONEGOTIATE_TIMEOUT) {
				puts(" TIMEOUT !\n");
				phydev->link = 0;
				break;
			}

			if ((i++ % 1000) == 0)
				putc('.');
			udelay(1000);	/* 1 ms */
			mii_reg = phy_read(phydev, MDIO_DEVAD_NONE,
					MIIM_RTL8211x_PHY_STATUS);
		}
		puts(" done\n");
		udelay(500000);	/* another 500 ms (results in faster booting) */
	} else {
		if (mii_reg & MIIM_RTL8211x_PHYSTAT_LINK)
			phydev->link = 1;
		else
			phydev->link = 0;
	}

	if (mii_reg & MIIM_RTL8211x_PHYSTAT_DUPLEX)
		phydev->duplex = DUPLEX_FULL;
	else
		phydev->duplex = DUPLEX_HALF;

	speed = (mii_reg & MIIM_RTL8211x_PHYSTAT_SPEED);

	switch (speed) {
	case MIIM_RTL8211x_PHYSTAT_GBIT:
		phydev->speed = SPEED_1000;
		break;
	case MIIM_RTL8211x_PHYSTAT_100:
		phydev->speed = SPEED_100;
		break;
	default:
		phydev->speed = SPEED_10;
	}

	return 0;
}

static int rtl8211f_parse_status(struct phy_device *phydev)
{
	unsigned int speed;
	unsigned int mii_reg;
	int i = 0;

	phy_write(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PAGE_SELECT, 0xa43);
	mii_reg = phy_read(phydev, MDIO_DEVAD_NONE, MIIM_RTL8211F_PHY_STATUS);

	phydev->link = 1;
	while (!(mii_reg & MIIM_RTL8211F_PHYSTAT_LINK)) {
		if (i > PHY_AUTONEGOTIATE_TIMEOUT) {
			puts(" TIMEOUT !\n");
			phydev->link = 0;
			break;
		}

		if ((i++ % 1000) == 0)
			putc('.');
		udelay(1000);
		mii_reg = phy_read(phydev, MDIO_DEVAD_NONE,
				   MIIM_RTL8211F_PHY_STATUS);
	}

	if (mii_reg & MIIM_RTL8211F_PHYSTAT_DUPLEX)
		phydev->duplex = DUPLEX_FULL;
	else
		phydev->duplex = DUPLEX_HALF;

	speed = (mii_reg & MIIM_RTL8211F_PHYSTAT_SPEED);

	switch (speed) {
	case MIIM_RTL8211F_PHYSTAT_GBIT:
		phydev->speed = SPEED_1000;
		break;
	case MIIM_RTL8211F_PHYSTAT_100:
		phydev->speed = SPEED_100;
		break;
	default:
		phydev->speed = SPEED_10;
	}

	return 0;
}

static int rtl8261n_parse_status(struct phy_device *phydev)
{
	int reg, speed, speed_code;

	reg = phy_read_mmd(phydev, MDIO_MMD_VEND2, RTL8261N_PHYSR);
	if (reg < 0)
		return reg;

	phydev->link = !!(reg & RTL8261N_PHYSR_LINK);
	phydev->duplex = (reg & RTL8261N_PHYSR_DUPLEX) ?
			  DUPLEX_FULL : DUPLEX_HALF;
	speed_code = RTL8261N_PHYSR_SPEED(reg);

	switch (speed_code) {
	case RTL8261N_SPEED_100M:
		speed = SPEED_100;
		break;
	case RTL8261N_SPEED_1000M:
		speed = SPEED_1000;
		break;
	case RTL8261N_SPEED_2500M:
		speed = SPEED_2500;
		break;
	case RTL8261N_SPEED_10G:
		speed = SPEED_10000;
		break;
	case RTL8261N_SPEED_5G:
		debug("RTL8261N: 5G link is not supported by this PCS\n");
		phydev->link = 0;
		speed = SPEED_10000;
		break;
	default:
		if (phydev->link)
			debug("RTL8261N: unknown link speed code 0x%x\n",
			      speed_code);
		phydev->link = 0;
		speed = SPEED_10000;
		break;
	}

	phydev->speed = speed;

	return 0;
}

static int rtl8211x_startup(struct phy_device *phydev)
{
	int ret;

	/* Read the Status (2x to make sure link is right) */
	ret = genphy_update_link(phydev);
	if (ret)
		return ret;

	return rtl8211x_parse_status(phydev);
}

static int rtl8211f_startup(struct phy_device *phydev)
{
	int ret;

	/* Read the Status (2x to make sure link is right) */
	ret = genphy_update_link(phydev);
	if (ret)
		return ret;
	/* Read the Status (2x to make sure link is right) */

	return rtl8211f_parse_status(phydev);
}

static int rtl8261n_startup(struct phy_device *phydev)
{
	int i = 0;
	int ret;

	ret = rtl8261n_parse_status(phydev);
	if (ret)
		return ret;

	if (phydev->link)
		return 0;

	puts("Waiting for RTL8261N link");
	while (!phydev->link && i < PHY_AUTONEGOTIATE_TIMEOUT) {
		if ((i++ % 1000) == 0)
			putc('.');
		udelay(1000);

		ret = rtl8261n_parse_status(phydev);
		if (ret)
			return ret;
	}

	if (!phydev->link)
		puts(" TIMEOUT !\n");
	else
		puts(" done\n");

	return 0;
}

/* Support for RTL8211B PHY */
U_BOOT_PHY_DRIVER(rtl8211b) = {
	.name = "RealTek RTL8211B",
	.uid = 0x1cc912,
	.mask = 0xffffff,
	.features = PHY_GBIT_FEATURES,
	.probe = &rtl8211b_probe,
	.config = &rtl8211x_config,
	.startup = &rtl8211x_startup,
	.shutdown = &genphy_shutdown,
};

/* Support for RTL8211E-VB-CG, RTL8211E-VL-CG and RTL8211EG-VB-CG PHYs */
U_BOOT_PHY_DRIVER(rtl8211e) = {
	.name = "RealTek RTL8211E",
	.uid = 0x1cc915,
	.mask = 0xffffff,
	.features = PHY_GBIT_FEATURES,
	.probe = &rtl8211e_probe,
	.config = &rtl8211e_config,
	.startup = &genphy_startup,
	.shutdown = &genphy_shutdown,
};

/* Support for RTL8211DN PHY */
U_BOOT_PHY_DRIVER(rtl8211dn) = {
	.name = "RealTek RTL8211DN",
	.uid = 0x1cc914,
	.mask = 0xffffff,
	.features = PHY_GBIT_FEATURES,
	.config = &rtl8211x_config,
	.startup = &rtl8211x_startup,
	.shutdown = &genphy_shutdown,
};

/* Support for RTL8211F PHY */
U_BOOT_PHY_DRIVER(rtl8211f) = {
	.name = "RealTek RTL8211F",
	.uid = 0x1cc916,
	.mask = 0xffffff,
	.features = PHY_GBIT_FEATURES,
	.probe = &rtl8211f_probe,
	.config = &rtl8211f_config,
	.startup = &rtl8211f_startup,
	.shutdown = &genphy_shutdown,
	.readext = &rtl8211f_phy_extread,
	.writeext = &rtl8211f_phy_extwrite,
};

/* Support for RTL8211F-VD PHY */
U_BOOT_PHY_DRIVER(rtl8211fvd) = {
	.name = "RealTek RTL8211F-VD",
	.uid = 0x1cc878,
	.mask = 0xffffff,
	.features = PHY_GBIT_FEATURES,
	.probe = &rtl8211f_probe,
	.config = &rtl8211f_config,
	.startup = &rtl8211f_startup,
	.shutdown = &genphy_shutdown,
	.readext = &rtl8211f_phy_extread,
	.writeext = &rtl8211f_phy_extwrite,
};

/* Support for RTL8261N 10G PHY */
U_BOOT_PHY_DRIVER(rtl8261n) = {
	.name = "RealTek RTL8261N",
	.uid = RTL8261N_PHY_ID,
	.mask = 0xffffff,
	.features = PHY_10G_FEATURES | SUPPORTED_2500baseX_Full |
		    SUPPORTED_Pause | SUPPORTED_Asym_Pause,
	.mmds = MDIO_DEVS_PMAPMD | MDIO_DEVS_PCS | MDIO_DEVS_PHYXS |
		MDIO_DEVS_AN | MDIO_DEVS_VEND2,
	.config = &rtl8261n_config,
	.startup = &rtl8261n_startup,
	.shutdown = &gen10g_shutdown,
};

/* Support for RTL8201F PHY */
U_BOOT_PHY_DRIVER(rtl8201f) = {
	.name = "RealTek RTL8201F 10/100Mbps Ethernet",
	.uid = 0x1cc816,
	.mask = 0xffffff,
	.features = PHY_BASIC_FEATURES,
	.probe = &rtl8210f_probe,
	.config = &rtl8201f_config,
	.startup = &genphy_startup,
	.shutdown = &genphy_shutdown,
};
