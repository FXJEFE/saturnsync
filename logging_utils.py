# -*- coding: utf-8 -*-
"""Trade outcome logger. Paths come from fxjefe_paths, not a hardcoded user profile."""
from __future__ import annotations

import logging


def setup_logging(root=None):
    from fxjefe_paths import logs_dir, require_root

    root = require_root() if root is None else root
    path = logs_dir(root) / "trade_logs.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        filename=str(path),
        filemode="a",
        format="%(asctime)s - %(message)s",
        encoding="utf-8",
    )
    return path


def log_trade_outcome(data, signal, outcome):
    logging.info(
        "Trade - Symbol: %s, Time: %s, Signal: %s, Outcome: %s, Data: %s",
        data.get("symbol"),
        data.get("time"),
        signal,
        outcome,
        data,
    )


def run(project_dir=None, dry_run=True):
    from fxjefe_paths import require_root

    root = require_root(project_dir)
    setup_logging(root)
    logging.info("logging_utils ready dry_run=%s", dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
