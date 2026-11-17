# -*- coding: utf-8 -*-
"""Score FXJEFE_Features.csv with models/xgboost_model.json when that file exists.

This repo does not ship xgboost_model.json. Paper mode records the skip and
continues. Live mode fails closed instead of loading a model from the
working directory or inventing predictions.
"""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("generate_signals_with_xgboost.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    model_path = os.path.join(config["models_path"], "xgboost_model.json")
    features_path = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    if not os.path.isfile(model_path):
        message = "xgboost_model.json is not in %s" % config["models_path"]
        if dry_run:
            logging.warning("%s; paper mode skips XGBoost scoring", message)
            return 0
        logging.error(message)
        return 1
    if not os.path.isfile(features_path):
        logging.error("Features file not found: %s", features_path)
        return 1
    import numpy as np
    import pandas as pd
    import xgboost as xgb

    model = xgb.Booster()
    model.load_model(model_path)
    frame = pd.read_csv(features_path, encoding="utf-8-sig", low_memory=False)
    frame.columns = [str(column).lower().strip() for column in frame.columns]
    columns = ["price", "atr", "ema_diff", "rsi", "garch_vol", "macd_diff"]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        logging.error("Missing columns for xgboost_model.json: %s", missing)
        return 1
    matrix = xgb.DMatrix(frame[columns], feature_names=columns)
    predictions = model.predict(matrix)
    if getattr(predictions, "ndim", 1) == 2:
        frame["signal"] = np.argmax(predictions, axis=1) - 1
    else:
        frame["signal"] = predictions
    target = os.path.join(config["data_output_path"], "FXJEFE_Features_with_signals.csv")
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s", target)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
