# -*- coding: utf-8 -*-
"""Single PROJECT_ROOT resolution for every FXJEFE pipeline stage.

Order:
  1. ``--project-dir`` (the ``cli_dir`` argument)
  2. ``FXJEFE_PROJECT_DIR``
  3. ``FXJEFE_PROJECT_ROOT`` (legacy; used only when FXJEFE_PROJECT_DIR is unset)
  4. ``Path.home() / "Documents" / "FXJEFE_Project"``

Data, model, log, and config paths are resolved under that root.
``require_project_root`` logs the choice and raises ``ProjectRootError``
when the directory does not exist. Importing this module does not touch
the filesystem.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ENV_VAR = "FXJEFE_PROJECT_DIR"
LEGACY_ENV_VAR = "FXJEFE_PROJECT_ROOT"


class ProjectRootError(Exception):
    """PROJECT_ROOT is missing or config.json cannot be read."""


class _Paths(object):
    """Attribute access for older callers (``paths.scripts_path``)."""

    def __init__(self, mapping):
        self._mapping = dict(mapping)
        for key, value in self._mapping.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._mapping[key]

    def get(self, key, default=None):
        return self._mapping.get(key, default)


def resolve_project_root(cli_dir=None, environ=None, home=None):
    """Return ``(path, source)`` without requiring the directory to exist."""
    env = os.environ if environ is None else environ
    if cli_dir:
        raw = str(cli_dir)
        source = "--project-dir"
    elif (env.get(ENV_VAR) or "").strip():
        raw = env.get(ENV_VAR).strip()
        source = ENV_VAR
    elif (env.get(LEGACY_ENV_VAR) or "").strip():
        raw = env.get(LEGACY_ENV_VAR).strip()
        source = LEGACY_ENV_VAR
    else:
        base = Path(home) if home is not None else Path.home()
        raw = str(base / "Documents" / "FXJEFE_Project")
        source = "default"
    root = Path(os.path.abspath(os.path.expanduser(raw)))
    return root, source


def require_project_root(cli_dir=None, environ=None, home=None):
    """Log the resolved root and fail when it is not an existing directory."""
    root, source = resolve_project_root(cli_dir=cli_dir, environ=environ, home=home)
    message = "PROJECT_ROOT=%s (source=%s)" % (root, source)
    logging.info(message)
    print(message)
    if not root.is_dir():
        raise ProjectRootError(
            "PROJECT_ROOT does not exist: %s. Create %s "
            "(the default is the current user's Documents\\FXJEFE_Project) "
            "or set %s, or pass --project-dir."
            % (root, root, ENV_VAR)
        )
    return root


def project_root():
    """Resolved root. Does not check that the directory exists."""
    root, _source = resolve_project_root()
    return root


def _under_root(root, value, default_rel):
    text = "" if value is None else str(value).strip()
    if not text:
        return root / default_rel
    path = Path(text)
    if not path.is_absolute():
        return root / path
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        logging.warning(
            "Ignoring path outside PROJECT_ROOT (%s); using %s",
            path,
            root / default_rel,
        )
        return root / default_rel
    return path


def config_file(root):
    """FXJEFE_CONFIG overrides the config path. Relative values stay under PROJECT_ROOT."""
    root = Path(root)
    override = (os.environ.get("FXJEFE_CONFIG") or "").strip()
    if override:
        path = Path(os.path.expanduser(override))
        if not path.is_absolute():
            path = root / path
        return path
    return root / "config.json"


def load_config(root):
    """Load config.json and force data/model/log paths under ``root``."""
    root = Path(root)
    path = config_file(root)
    if not path.is_file():
        raise ProjectRootError("config.json not found under PROJECT_ROOT: %s" % path)
    last_error = None
    data = None
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            data = json.loads(raw.decode(enc))
            break
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            last_error = exc
            data = None
    if not isinstance(data, dict):
        raise ProjectRootError("Cannot load config %s: %s" % (path, last_error))
    data["project_root"] = str(root)
    data["config_path"] = str(path)
    data["scripts_path"] = str(root)
    data["data_path"] = str(_under_root(root, data.get("data_path"), "data"))
    output = data.get("data_output_path") or data.get("data_path")
    data["data_output_path"] = str(_under_root(root, output, "data"))
    data["models_path"] = str(_under_root(root, data.get("models_path"), "models"))
    data["log_path"] = str(_under_root(root, data.get("log_path"), "Logs"))
    data["state_path"] = str(root / "state")
    for folder in (
        data["data_path"],
        data["data_output_path"],
        data["models_path"],
        data["log_path"],
        data["state_path"],
    ):
        Path(folder).mkdir(parents=True, exist_ok=True)
    return data


def resolve(root=None):
    """Read-only path map. Does not create directories."""
    if root is None:
        root = project_root()
    else:
        root = Path(root)
    return {
        "project_root": str(root),
        "venv_dir": str(root / ".venv"),
        "scripts_path": str(root),
        "models_path": str(root / "models"),
        "data_path": str(root / "data"),
        "data_output_path": str(root / "data"),
        "log_path": str(root / "Logs"),
        "state_path": str(root / "state"),
        "config_path": str(root / "config.json"),
    }


def get_paths(cli_dir=None):
    root, _source = resolve_project_root(cli_dir)
    mapping = resolve(root)
    mapping["scripts_path"] = Path(mapping["scripts_path"])
    mapping["project_root"] = Path(mapping["project_root"])
    return _Paths(mapping)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Print the resolved FXJEFE PROJECT_ROOT")
    parser.add_argument("--project-dir", default=None)
    args = parser.parse_args(argv)
    try:
        root = require_project_root(args.project_dir)
    except ProjectRootError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(resolve(root), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
