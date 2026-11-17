# -*- coding: utf-8 -*-
"""Shared startup for pipeline stages. Nothing here runs at import time."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from path_resolver import ProjectRootError, load_config, require_project_root


def parse_stage_args(argv=None, description="FXJEFE pipeline stage"):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--project-dir",
        default=None,
        help="PROJECT_ROOT. Overrides FXJEFE_PROJECT_DIR.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Accepted for compatibility. Live trading is the default.",
    )
    parser.add_argument("--paper", action="store_true", help="Paper mode. No orders are sent.")
    parser.add_argument("--dry-run", action="store_true", help="Alias of --paper.")
    args, _unknown = parser.parse_known_args(argv)
    args.dry_run = bool(args.paper or args.dry_run)
    return args


def activate(log_name, project_dir=None, dry_run=True):
    """Resolve PROJECT_ROOT, load config, and attach a stage log file."""
    root = require_project_root(project_dir)
    os.environ["FXJEFE_PROJECT_DIR"] = str(root)
    os.environ["FXJEFE_DRY_RUN"] = "1" if dry_run else "0"
    cfg = load_config(root)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    log_path = os.path.join(cfg["log_path"], log_name)
    already = False
    for handler in logger.handlers:
        if getattr(handler, "baseFilename", None) == os.path.abspath(log_path):
            already = True
            break
    if not already:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    if not any(type(handler) is logging.StreamHandler for handler in logger.handlers):
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        logger.addHandler(stream)
    logging.info("PROJECT_ROOT=%s dry_run=%s stage_log=%s", root, dry_run, log_name)
    return {"root": root, "config": cfg, "dry_run": bool(dry_run), "log_name": log_name}


def call_main(run, argv=None):
    args = parse_stage_args(argv)
    try:
        code = run(project_dir=args.project_dir, dry_run=args.dry_run)
    except ProjectRootError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if code is None:
        return 0
    return int(code)
