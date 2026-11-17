# -*- coding: utf-8 -*-
"""Print the label distribution in training_data.csv."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("check_labels.log", project_dir=project_dir, dry_run=dry_run)
    path = os.path.join(ctx["config"]["data_output_path"], "training_data.csv")
    if not os.path.isfile(path):
        logging.error("training_data.csv not found: %s", path)
        return 1
    import pandas as pd

    frame = pd.read_csv(path)
    if "label" not in frame.columns:
        logging.error("training_data.csv has no label column")
        return 1
    counts = frame["label"].value_counts().to_dict()
    logging.info("Label counts: %s", counts)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
