# -*- coding: utf-8 -*-
"""Do not inject a hardcoded config path into other scripts.

Paths resolve through fxjefe_paths (PROJECT_ROOT / FXJEFE_PROJECT_DIR).
"""
from __future__ import annotations

import sys


def run(project_dir=None, dry_run=True):
    from fxjefe_paths import project_root

    root = project_root(project_dir)
    print("update_scripts skipped. PROJECT_ROOT=%s" % root)
    print("Scripts must load config through fxjefe_paths, not a copied absolute path.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
