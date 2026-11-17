# -*- coding: utf-8 -*-
"""One-shot MT5 signal snapshot.

Paper mode writes a bar snapshot under the project data directory and does
not loop, log in, or hardcode an account, password, or server. Live mode
uses MT5_ACCOUNT, MT5_PASSWORD, and MT5_SERVER together, or the terminal
session that is already logged in.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone


def run(project_dir=None, dry_run=True):
    from stage_support import activate
    from mt5_client import credentials_from_env, get_mt5

    ctx = activate("mt5_signal_script.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    terminal = get_mt5(dry_run=dry_run)
    if not terminal.initialize():
        logging.error("MT5 initialize failed: %s", terminal.last_error())
        return 1
    try:
        creds = credentials_from_env()
        if creds and not dry_run:
            if not terminal.login(creds["account"], password=creds["password"], server=creds["server"]):
                logging.error("MT5 login failed")
                return 1
        elif not dry_run and creds is None:
            logging.info("Live signal snapshot is using the terminal's existing session")
        import pandas as pd

        rows = []
        for symbol in ("EURUSD", "USDJPY", "XAUUSD"):
            rates = terminal.copy_rates_from_pos(symbol, terminal.TIMEFRAME_M1, 0, 100)
            if rates is None or len(rates) == 0:
                logging.warning("No bars for %s", symbol)
                continue
            frame = pd.DataFrame(rates)
            last = frame.iloc[-1]
            rows.append(
                {
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "symbol": symbol,
                    "price": float(last["close"]),
                    "dry_run": bool(dry_run),
                }
            )
        if not rows:
            logging.error("Signal snapshot produced no rows")
            return 1
        target = os_path(config, "signal_snapshot.csv")
        pd.DataFrame(rows).to_csv(target, index=False, encoding="utf-8")
        logging.info("Wrote %s", target)
        return 0
    finally:
        terminal.shutdown()


def os_path(config, name):
    import os

    return os.path.join(config["data_output_path"], name)


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
