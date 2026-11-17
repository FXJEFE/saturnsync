# -*- coding: utf-8 -*-
"""MT5 connection health check. Does not send orders or embed credentials."""
from __future__ import annotations

import logging
import sys

from mt5_client import credentials_from_env, get_mt5


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    activate("mt5_health.log", project_dir=project_dir, dry_run=dry_run)
    terminal = get_mt5(dry_run=dry_run)
    if not terminal.initialize():
        logging.error("MT5 initialize failed: %s", terminal.last_error())
        return 1
    try:
        creds = credentials_from_env()
        if creds and not dry_run:
            if not terminal.login(creds["account"], password=creds["password"], server=creds["server"]):
                logging.error("MT5 login failed for the server named in MT5_SERVER")
                return 1
            logging.info("MT5 login succeeded using environment credentials")
        elif dry_run:
            logging.info("Paper mode: health check is using the in-process terminal, not a live login")
        else:
            logging.error("MT5 credentials are missing. Set MT5_ACCOUNT, MT5_PASSWORD, and MT5_SERVER.")
            return 1
        info = terminal.account_info()
        if info is None:
            logging.error("MT5 account_info returned nothing")
            return 1
        logging.info(
            "MT5 health ok server=%s balance=%s",
            getattr(info, "server", ""),
            getattr(info, "balance", ""),
        )
        return 0
    finally:
        terminal.shutdown()


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
