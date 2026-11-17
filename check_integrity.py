# -*- coding: utf-8 -*-
"""Report whether the pipeline CSVs exist and are non-empty."""
from __future__ import annotations

import logging
import os
import sys

FILES = ("FXJEFE_Features.csv", "FXJEFE_trades.csv", "FXJEFE_trades_outcomes.csv")


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("check_integrity.log", project_dir=project_dir, dry_run=dry_run)
    import pandas as pd

    data_path = ctx["config"]["data_output_path"]
    for name in FILES:
        path = os.path.join(data_path, name)
        if name == "FXJEFE_Features.csv" and not os.path.isfile(path):
            path = os.path.join(ctx["config"]["data_path"], name)
        if not os.path.isfile(path):
            logging.info("Missing %s", path)
            continue
        frame = pd.read_csv(path)
        logging.info("%s rows=%s", path, len(frame))
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
