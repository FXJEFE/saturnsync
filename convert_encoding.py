# -*- coding: utf-8 -*-
"""Rewrite known text files as UTF-8 when an MT5 files directory is configured."""
from __future__ import annotations

import logging
import os
import sys

FILES = (
    "log.txt",
    "FXJEFE_Features.csv",
    "FXJEFE_trades_outcomes.csv",
    "FXJEFE_trades.csv",
)


def _decode(raw):
    try:
        import chardet

        guess = chardet.detect(raw).get("encoding")
    except ImportError:
        guess = None
    for encoding in (guess, "utf-8-sig", "utf-8", "cp1252", "latin1"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("convert_encoding.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    bases = []
    for key in ("mt5_common_path", "mt5_files_path"):
        value = (config.get(key) or "").strip()
        if value:
            bases.append(value)
    bases.append(config["data_path"])
    converted = 0
    for base in bases:
        if not os.path.isdir(base):
            logging.info("Encoding source not present: %s", base)
            continue
        for name in FILES:
            path = os.path.join(base, name)
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as handle:
                raw = handle.read()
            text = _decode(raw)
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            converted += 1
            logging.info("UTF-8 rewrite %s", path)
    logging.info("Converted %s file(s)", converted)
    return 0


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
