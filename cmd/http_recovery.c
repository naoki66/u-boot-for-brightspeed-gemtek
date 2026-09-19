// SPDX-License-Identifier: GPL-2.0+
/*
 * 'http_recovery' command.  The recovery server itself owns the address
 * defaults (see recovery_prepare_static_network() in net/lwip/httpd_recovery.c);
 * this stub only makes sure the network environment exists so that an
 * 'ipaddr' persisted in uenv is never overwritten by the command path.
 */

#include <command.h>
#include <env.h>

int run_http_recovery(void);

static int do_http_recovery(struct cmd_tbl *cmdtp, int flag, int argc,
			    char *const argv[])
{
	(void)cmdtp;
	(void)flag;
	(void)argc;
	(void)argv;

	if (!env_get("ipaddr"))
		env_set("ipaddr", "192.168.0.1");
	if (!env_get("netmask"))
		env_set("netmask", "255.255.255.0");
	if (!env_get("gatewayip"))
		env_set("gatewayip", "0.0.0.0");

	return run_http_recovery();
}

U_BOOT_CMD(
	http_recovery, 1, 0, do_http_recovery,
	"start the lwIP HTTP recovery server",
	"Serve http://192.168.0.1/ (open in incognito mode); connect a PC at 192.168.0.2/24"
);
