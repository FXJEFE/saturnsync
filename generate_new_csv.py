# -*- coding: utf-8 -*-
"""Derive a simple price-change signal column and write it under data/."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("generate_new_csv.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    import pandas as pd

    source = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    target = os.path.join(config["data_output_path"], "FXJEFE_Features_with_signals.csv")
    if not os.path.isfile(source):
        logging.error("Features file not found: %s", source)
        return 1
    frame = pd.read_csv(source, encoding="utf-8-sig", low_memory=False)
    if "symbol" not in frame.columns or "price" not in frame.columns:
        logging.error("FXJEFE_Features.csv needs symbol and price columns")
        return 1
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    signal = pd.Series(0, index=frame.index)
    for symbol in frame["symbol"].dropna().unique():
        mask = frame["symbol"] == symbol
        change = frame.loc[mask, "price"].diff()
        point = 0.01 if any(token in str(symbol) for token in ("JPY", "XAU", "BTC")) else 0.0001
        pips = change / point
        signal.loc[pips.index[pips > 10]] = 1
        signal.loc[pips.index[pips < -10]] = -1
    frame["signal"] = signal
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s", target)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
