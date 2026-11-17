# -*- coding: utf-8 -*-
"""Outer-join features and trades on time + symbol when both files exist."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("merge_datasets.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    features = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    trades = os.path.join(config["data_output_path"], "FXJEFE_trades.csv")
    target = os.path.join(config["data_output_path"], "FXJEFE_merged.csv")
    if not os.path.isfile(features) or not os.path.isfile(trades):
        logging.info("Merge skipped; features=%s trades=%s", os.path.isfile(features), os.path.isfile(trades))
        return 0
    import pandas as pd

    left = pd.read_csv(features)
    right = pd.read_csv(trades)
    keys = [key for key in ("time", "symbol") if key in left.columns and key in right.columns]
    if not keys:
        logging.info("No shared time/symbol columns; wrote features only")
        left.to_csv(target, index=False, encoding="utf-8")
        return 0
    merged = pd.merge(left, right, on=keys, how="outer")
    merged.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s (%s rows)", target, len(merged))
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
