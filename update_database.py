# -*- coding: utf-8 -*-
"""Load FXJEFE_trades.csv into a SQLite file under the project data directory."""
from __future__ import annotations

import logging
import os
import sqlite3
import sys


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("update_database.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    csv_path = os.path.join(config["data_output_path"], "FXJEFE_trades.csv")
    db_path = os.path.join(config["data_output_path"], "fxjefe_trades.db")
    if not os.path.isfile(csv_path):
        logging.info("No trades file to load: %s", csv_path)
        return 0
    import pandas as pd

    frame = pd.read_csv(csv_path)
    connection = sqlite3.connect(db_path)
    try:
        frame.to_sql("trades", connection, if_exists="replace", index=False)
    finally:
        connection.close()
    logging.info("Updated %s", db_path)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
