# -*- coding: utf-8 -*-
"""Re-read FXJEFE_Features.csv with a fallback encoding and write UTF-8."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("fix_csv_encoding.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    import pandas as pd

    source = os.path.join(config["data_path"], "FXJEFE_Features.csv")
    target = os.path.join(config["data_output_path"], "FXJEFE_Features_fixed.csv")
    if not os.path.isfile(source):
        logging.error("Input file not found: %s", source)
        return 1
    frame = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            frame = pd.read_csv(source, encoding=encoding, low_memory=False)
            logging.info("Read %s with %s", source, encoding)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    if frame is None:
        logging.error("Could not decode %s", source)
        return 1
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info("Wrote %s", target)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
