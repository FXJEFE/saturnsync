# -*- coding: utf-8 -*-
"""Align CSV headers with config['expected_headers'] when that map is present."""
from __future__ import annotations

import logging
import os
import sys


def adjust_headers(csv_path, config):
    csv_name = os.path.basename(csv_path)
    expected = (config.get("expected_headers") or {}).get(csv_name)
    if not expected:
        logging.info("No expected headers for %s", csv_name)
        return 0
    import pandas as pd

    frame = pd.read_csv(csv_path)
    current = list(frame.columns)
    if current != expected:
        logging.info("Adjusting headers for %s", csv_name)
        for header in expected:
            if header not in current:
                frame[header] = "" if header in ("time", "symbol") else 0.0
        frame = frame[expected]
        frame.to_csv(csv_path, index=False)
    else:
        logging.info("Headers already match for %s", csv_name)
    return 0


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("adjust_headers.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    data_path = config["data_output_path"]
    if not os.path.isdir(data_path):
        logging.error("Data directory missing: %s", data_path)
        return 1
    csvs = [name for name in os.listdir(data_path) if name.endswith(".csv")]
    if not csvs:
        logging.info("No CSV files to adjust in %s", data_path)
        return 0
    for name in csvs:
        adjust_headers(os.path.join(data_path, name), config)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
