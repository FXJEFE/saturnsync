# -*- coding: utf-8 -*-
"""Thin path helpers. PROJECT_ROOT resolution lives in path_resolver.py."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from path_resolver import load_config as _load_config
from path_resolver import require_project_root, resolve_project_root

# Windows terminal data folder. Override with FXJEFE_MQL5_DIR or configftmo.json mt5_mql5_dir.
DEFAULT_MQL5_DIR = (
    r"C:\Users\FullSend\AppData\Roaming\MetaQuotes\Terminal"
    r"\492CD01931BD0D07A159AEF5B29BF32C\MQL5"
)


def project_root(cli_dir=None):
    root, _source = resolve_project_root(cli_dir)
    return root


def require_root(cli_dir=None):
    return require_project_root(cli_dir)


def config_path(root=None):
    """FXJEFE_CONFIG wins. Otherwise PROJECT_ROOT/config.json, never the parent directory."""
    override = (os.environ.get("FXJEFE_CONFIG") or "").strip()
    if override:
        path = Path(os.path.expanduser(override))
        if not path.is_absolute():
            path = project_root() / path
        return path
    root = Path(root) if root is not None else project_root()
    return root / "config.json"


def models_dir(root=None):
    root = Path(root) if root is not None else project_root()
    return root / "models"


def data_dir(root=None):
    root = Path(root) if root is not None else project_root()
    return root / "data"


def logs_dir(root=None):
    root = Path(root) if root is not None else project_root()
    return root / "Logs"


def features_csv(root=None):
    return data_dir(root) / "FXJEFE_Features.csv"


def venv_python(root=None, name="fxjefe"):
    """Project venv interpreter. Windows uses Scripts; other platforms use bin."""
    root = Path(root) if root is not None else project_root()
    windows = root / name / "Scripts" / "python.exe"
    posix = root / name / "bin" / "python"
    if windows.is_file():
        return windows
    if posix.is_file():
        return posix
    if sys.platform == "win32":
        return windows
    return posix


def mql5_dir(rules=None):
    env = (os.environ.get("FXJEFE_MQL5_DIR") or "").strip()
    if env:
        return Path(env)
    if rules and str(rules.get("mt5_mql5_dir") or "").strip():
        return Path(str(rules["mt5_mql5_dir"]).strip())
    return Path(DEFAULT_MQL5_DIR)


def mql5_subdir(name, rules=None):
    return mql5_dir(rules) / name


def load_config(root=None, cli_dir=None):
    root = require_project_root(cli_dir) if root is None else Path(root)
    return _load_config(root)


def setup_logging(name="pipeline.log", root=None):
    root = require_project_root() if root is None else Path(root)
    cfg = _load_config(root)
    path = Path(cfg["log_path"]) / name
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(str(path), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logging.info("PROJECT_ROOT=%s", root)
    return path
