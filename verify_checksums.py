#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SHA256 manifest check.

``python verify_checksums.py --write`` creates or refreshes checksums.json.
A missing manifest is an error with the generator command in the message.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

MISSING_MANIFEST = (
    "[SHA256] checksums.json is missing. "
    "Generate it with: python verify_checksums.py --write"
)


def project_root(argv):
    from path_resolver import require_project_root

    project_dir = None
    if "--project-dir" in argv:
        project_dir = argv[argv.index("--project-dir") + 1]
    return require_project_root(project_dir)


def tracked_files(root: Path):
    names = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if path.name in ("checksums.json",) or path.name.startswith("."):
            continue
        if path.suffix.lower() in (".py", ".json", ".md", ".txt", ".ps1", ".bat") or path.name in (
            "Makefile",
            "Dockerfile",
            "env.template",
        ):
            names.append(path)
    return names


def write_manifest(root: Path) -> Path:
    manifest = {}
    existing = root / "checksums.json"
    if existing.is_file():
        previous = json.loads(existing.read_text(encoding="utf-8"))
        for name in sorted(previous):
            path = root / name
            if path.is_file():
                manifest[name.replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in tracked_files(root):
        rel = path.relative_to(root).as_posix()
        manifest[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    destination = root / "checksums.json"
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("[SHA256] wrote %s (%s files)" % (destination, len(manifest)))
    return destination


def verify(root: Path) -> int:
    sums = root / "checksums.json"
    if not sums.is_file():
        alt = root / "SHA256SUMS"
        if not alt.is_file():
            print(MISSING_MANIFEST)
            return 1
        expected = {}
        for line in alt.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                expected[parts[-1]] = parts[0]
    else:
        expected = json.loads(sums.read_text(encoding="utf-8"))
    ok, bad, missing = 0, [], []
    for name, want in sorted(expected.items()):
        path = root / name
        if not path.is_file():
            missing.append(name)
            print("[SHA256] MISSING %s" % name)
            continue
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got == want:
            ok += 1
            print("[SHA256] OK  %s" % name)
        else:
            bad.append(name)
            print("[SHA256] BAD %s" % name)
    print("[SHA256] ok=%s bad=%s missing=%s" % (ok, len(bad), len(missing)))
    if bad or missing:
        print("[SHA256] manifest does not match. Refresh with: python verify_checksums.py --write")
        return 1
    return 0


def run(project_dir=None, dry_run=True):
    from path_resolver import require_project_root

    root = require_project_root(project_dir)
    return verify(root)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        root = project_root(argv)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if "--write" in argv:
        write_manifest(root)
        return 0
    return verify(root)


if __name__ == "__main__":
    raise SystemExit(main())
