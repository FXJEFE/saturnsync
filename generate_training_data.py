# -*- coding: utf-8 -*-
"""Build training_data_from_signals.csv from the signal column.

``training_data.csv`` is owned by generate_labels.py, which runs after this
stage, so this script no longer overwrites that file at import time.
"""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("generate_training_data.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    import pandas as pd

    source = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    target = os.path.join(config["data_output_path"], "training_data_from_signals.csv")
    if not os.path.isfile(source):
        logging.error("Features file not found: %s", source)
        return 1
    frame = pd.read_csv(source, encoding="utf-8-sig", low_memory=False)
    if "signal" not in frame.columns:
        logging.error("signal column missing in %s", source)
        return 1
    frame["signal"] = pd.to_numeric(frame["signal"], errors="coerce")
    frame["label"] = frame["signal"].map({1: 1, -1: -1, 0: 0}).fillna(0)
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s (%s rows)", target, len(frame))
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
