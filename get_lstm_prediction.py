# -*- coding: utf-8 -*-
"""LSTM scoring hook.

The previous script referenced ``lstm_model``, ``models_loaded``, and
``feature_history`` without defining them, and it exited while importing.
There is still no LSTM artifact in this repo. Paper mode records that and
continues. Live mode fails instead of inventing a network.
"""
from __future__ import annotations

import logging
import os
import sys


def get_lstm_prediction(symbol, features_array, model=None, history=None, sequence_length=20):
    """Score one vector when the caller supplies a loaded model. Otherwise return no signal."""
    if model is None or history is None:
        return None, 0.0
    bucket = history.setdefault(symbol, [])
    bucket.append(list(features_array))
    del bucket[:-sequence_length]
    if len(bucket) < sequence_length:
        return None, 0.0
    import numpy as np

    sequence = np.asarray(bucket, dtype="float32").reshape(1, sequence_length, len(features_array))
    prediction = model.predict(sequence, verbose=0)[0]
    labels = {0: "neutral", 1: "buy", 2: "sell"}
    chosen = int(np.argmax(prediction))
    return labels.get(chosen, "neutral"), float(prediction[chosen])


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("get_lstm_prediction.log", project_dir=project_dir, dry_run=dry_run)
    from fxjefe_paths import config_path, models_dir

    # Config is PROJECT_ROOT/config.json (or FXJEFE_CONFIG), not the parent directory.
    logging.info("config=%s", config_path(ctx["root"]))
    model_path = os.path.join(str(models_dir(ctx["root"])), "lstm_model.h5")
    if not os.path.isfile(model_path):
        message = "No LSTM model at %s. This repo does not ship one." % model_path
        if dry_run:
            logging.warning("%s Paper mode skips LSTM scoring.", message)
            return 0
        logging.error(message)
        return 1
    logging.error("LSTM file %s is present but no loader is configured in this repo", model_path)
    return 1


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
