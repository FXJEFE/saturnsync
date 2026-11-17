# -*- coding: utf-8 -*-
"""Fill feature gaps and report high correlations. Does not send orders."""
from __future__ import annotations

import logging
import os
import sys

EXPECTED = [
    "time", "symbol", "price", "atr", "ema_diff", "rsi", "macd_diff", "vwap",
    "price_vwap_diff", "bb_position", "roc", "stochastic", "cci", "williams",
    "momentum", "realized_vol", "chaikin_vol", "adx", "rvi", "obv", "volume_delta",
    "ad_line", "vol_osc", "supertrend", "hma", "ichimoku_tenkan", "sar", "dpo",
    "spread", "sentiment", "signal",
]


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("clean_training_data.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    import pandas as pd

    source = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    target = os.path.join(config["data_output_path"], "FXJEFE_Features_clean.csv")
    if not os.path.isfile(source):
        logging.error("Input file not found: %s", source)
        return 1
    frame = pd.read_csv(source, encoding="utf-8-sig", low_memory=False)
    for column in EXPECTED:
        if column not in frame.columns:
            frame[column] = "" if column in ("time", "symbol", "signal") else 0.0
    numeric = [column for column in EXPECTED if column not in ("time", "symbol", "signal")]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    if len(frame) >= 5:
        corr = frame[numeric].corr().abs()
        high = (corr > 0.8) & (corr < 1.0)
        logging.info("High-correlation pairs: %s", int(high.sum().sum() // 2))
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s (%s rows)", target, len(frame))
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
