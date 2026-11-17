# -*- coding: utf-8 -*-
"""Compatibility launcher. The stage order lives in run_pipeline.py."""
from __future__ import annotations

import sys


def run(project_dir=None, dry_run=False, retry=1):
    from run_pipeline import run as run_pipeline

    return run_pipeline(project_dir=project_dir, dry_run=dry_run, retry=retry)


def main(argv=None):
    from run_pipeline import main as run_main

    return run_main(argv)


if __name__ == "__main__":
    sys.exit(main())
