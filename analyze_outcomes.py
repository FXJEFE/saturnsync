# -*- coding: utf-8 -*-
"""Summarize trade outcomes. An empty book is a report, not a broker call."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("analyze_outcomes.log", project_dir=project_dir, dry_run=dry_run)
    path = os.path.join(ctx["config"]["data_output_path"], "FXJEFE_trades_outcomes.csv")
    if not os.path.isfile(path):
        logging.info("No outcomes file yet: %s", path)
        return 0
    import pandas as pd

    frame = pd.read_csv(path)
    if frame.empty or "profit" not in frame.columns:
        logging.info("Outcomes file has nothing to summarize")
        return 0
    profit = pd.to_numeric(frame["profit"], errors="coerce").fillna(0.0)
    win_rate = float((profit > 0).mean() * 100.0) if len(profit) else 0.0
    logging.info("Trades=%s profit=%s win_rate=%.2f", len(frame), float(profit.sum()), win_rate)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
