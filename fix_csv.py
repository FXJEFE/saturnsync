# -*- coding: utf-8 -*-
"""Fill missing feature columns on FXJEFE_Features.csv and write a UTF-8 copy."""
from __future__ import annotations

import logging
import os
import sys

EXPECTED = [
    "time", "symbol", "price", "atr", "ema_diff", "rsi", "macd_diff", "vwap",
    "price_vwap_diff", "bb_position", "roc", "stochastic", "cci", "williams",
    "momentum", "realized_vol", "chaikin_vol", "adx", "rvi", "obv",
    "volume_delta", "ad_line", "vol_osc", "supertrend", "hma", "ichimoku_tenkan",
    "sar", "dpo", "spread", "sentiment", "signal", "confidence",
]


def _sentiment(symbol):
    try:
        from textblob import TextBlob
    except ImportError:
        return 0.0
    text = {
        "EURUSD": "Bullish trend expected",
        "USDJPY": "Neutral market",
        "XAUUSD": "Bearish sentiment",
        "AUDUSD": "Positive outlook",
        "GBPUSD": "Strong buy signals",
        "USDCAD": "Sell pressure",
    }.get(str(symbol).replace(".r", "").replace(".R", ""), "Neutral")
    try:
        return float(TextBlob(text).sentiment.polarity)
    except Exception:
        return 0.0


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("fix_csv.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    import pandas as pd

    source = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    target = os.path.join(config["data_output_path"], "FXJEFE_Features_fixed.csv")
    if not os.path.isfile(source):
        logging.error("Input file not found: %s", source)
        return 1
    frame = None
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            frame = pd.read_csv(source, encoding=encoding, low_memory=False)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    if frame is None or frame.empty:
        logging.error("Could not read a non-empty CSV at %s", source)
        return 1
    for column in EXPECTED:
        if column not in frame.columns:
            frame[column] = "" if column in ("time", "symbol", "signal") else 0.0
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce").ffill()
    for column in EXPECTED:
        if column in ("time", "symbol", "signal"):
            continue
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "symbol" in frame.columns:
        frame["sentiment"] = frame["symbol"].map(_sentiment)
    frame[EXPECTED].to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s (%s rows)", target, len(frame))
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
