# -*- coding: utf-8 -*-
"""Score the labeled feature file with models/ensemble_model.pkl when it exists."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("ensemble_predictions.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    model_path = os.path.join(config["models_path"], "ensemble_model.pkl")
    data_path = os.path.join(config["data_output_path"], "FXJEFE_Features_with_labels.csv")
    if not os.path.isfile(model_path):
        message = "ensemble_model.pkl is not in %s" % config["models_path"]
        if dry_run:
            logging.warning("%s; paper mode skips ensemble scoring", message)
            return 0
        logging.error(message)
        return 1
    if not os.path.isfile(data_path):
        logging.error("Labeled features not found: %s", data_path)
        return 1
    import joblib
    import numpy as np
    import pandas as pd

    model = joblib.load(model_path)
    frame = pd.read_csv(data_path, encoding="utf-8", low_memory=False)
    features = [name for name in (config.get("features") or []) if name in frame.columns]
    if not features:
        logging.error("No configured features are present in %s", data_path)
        return 1
    predictions = model.predict(frame[features])
    frame["signal"] = np.where(predictions == 1, "buy", np.where(predictions == -1, "sell", "hold"))
    if hasattr(model, "predict_proba"):
        frame["confidence"] = model.predict_proba(frame[features]).max(axis=1)
    target = os.path.join(config["data_output_path"], "FXJEFE_Predictions.csv")
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s", target)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
