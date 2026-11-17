# -*- coding: utf-8 -*-
"""Write a short count of ERROR / WARNING lines from the pipeline log."""
from __future__ import annotations

import logging
import os
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("log_summary.log", project_dir=project_dir, dry_run=dry_run)
    log_file = os.path.join(ctx["config"]["log_path"], "pipeline.log")
    summary = os.path.join(ctx["config"]["log_path"], "log_summary.txt")
    if not os.path.isfile(log_file):
        logging.info("pipeline.log does not exist yet")
        return 0
    with open(log_file, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    errors = sum(1 for line in lines if "ERROR" in line)
    warnings = sum(1 for line in lines if "WARNING" in line)
    text = "lines=%s errors=%s warnings=%s\n" % (len(lines), errors, warnings)
    with open(summary, "w", encoding="utf-8") as handle:
        handle.write(text)
    logging.info("Wrote %s %s", summary, text.strip())
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
