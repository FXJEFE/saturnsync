# -*- coding: utf-8 -*-
"""Train the legacy RandomForest used by check_model_features / ai_server.

The original train_models.py was not in this repo. This stage writes
``models/my_model.pkl`` from ``data/training_data.csv`` using exactly
``config['features']`` so the feature-count check has a model to load.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("train_models.log", project_dir=project_dir, dry_run=dry_run)
    cfg = ctx["config"]
    import joblib
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier

    training_path = Path(cfg["data_output_path"]) / "training_data.csv"
    if not training_path.is_file():
        logging.error("training_data.csv not found: %s", training_path)
        return 1
    frame = pd.read_csv(training_path, encoding="utf-8", low_memory=False)
    features = list(cfg.get("features") or [])
    if not features:
        logging.error("config.json has no features list")
        return 1
    if "label" not in frame.columns:
        logging.error("training_data.csv has no label column")
        return 1
    for name in features:
        if name not in frame.columns:
            frame[name] = 0.0
    data = frame[features + ["label"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) < 10:
        logging.error("training_data.csv has only %s usable rows", len(data))
        return 1
    trees = 25 if dry_run else 200
    model = RandomForestClassifier(n_estimators=trees, random_state=42, n_jobs=1)
    model.fit(data[features], data["label"].astype(int))
    destination = Path(cfg["models_path"]) / "my_model.pkl"
    joblib.dump(model, str(destination))
    logging.info("Saved %s (%s features, %s rows, trees=%s)", destination, len(features), len(data), trees)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
