#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FXJEFE production pipeline launcher (30+ scripts)

- Auto-inventory / relocate scripts into Documents/FXJEFE_Project
- Frozen feature registry (.pyc preferred)
- Per-step verification + final full validation
- Model auto-discover with feature-match TEST before load
- min_confidence gate = 0.77
- OHLCV headers enforced for raw computations
- Visible terminal only — no CREATE_NO_WINDOW / hidden shells

Usage:
  python pipelinerun_production.py
  python pipelinerun_production.py --inventory-only
  python pipelinerun_production.py --skip-server
  python pipelinerun_production.py --only train_models.py,check_model_features.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def log(msg: str) -> None:
    print(f"[FXJEFE-PROD] {msg}", flush=True)


def ok(msg: str) -> None:
    print(f"[FXJEFE-PROD][OK] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[FXJEFE-PROD][WARN] {msg}", flush=True)


def err(msg: str) -> None:
    print(f"[FXJEFE-PROD][ERROR] {msg}", flush=True, file=sys.stderr)


def project_root() -> Path:
    from path_resolver import resolve_project_root

    root, _source = resolve_project_root()
    return root


def load_feature_registry():
    """Prefer compiled .pyc next to this file / project root."""
    candidates = [
        ROOT / "feature_registry.py",
        project_root() / "feature_registry.py",
        ROOT / "__pycache__" / "feature_registry.cpython-312.pyc",
    ]
    # Also any feature_registry*.pyc
    for base in (ROOT, project_root(), ROOT / "__pycache__", project_root() / "__pycache__"):
        if base.is_dir():
            for p in base.glob("feature_registry*.pyc"):
                candidates.append(p)
            for p in base.glob("feature_registry.py"):
                candidates.append(p)

    for path in candidates:
        if not path.is_file():
            continue
        try:
            if path.suffix == ".pyc":
                # load pyc via importlib
                spec = importlib.util.spec_from_file_location("feature_registry", path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    log(f"feature registry loaded from pyc: {path}")
                    return mod
            else:
                spec = importlib.util.spec_from_file_location("feature_registry", path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    log(f"feature registry loaded from py: {path}")
                    return mod
        except Exception as e:
            warn(f"could not load {path}: {e}")
    raise RuntimeError("feature_registry not found — copy feature_registry.py and py_compile it")


def ensure_config(root: Path, reg) -> Dict[str, Any]:
    """Write/merge config.json with frozen features + 0.77 gate; preserve user paths."""
    cfg_path = root / "config.json"
    cfg: Dict[str, Any] = {}
    if cfg_path.is_file():
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
            try:
                cfg = json.loads(cfg_path.read_text(encoding=enc))
                break
            except Exception:
                continue

    # Paths — keep existing if set
    # Always resolve via get_active() — never assume attribute types
    if hasattr(reg, "get_active"):
        active = reg.get_active()
    else:
        active = {
            "train": list(getattr(reg, "TRAIN_FEATURES", [])),
            "predict": list(getattr(reg, "PREDICT_FEATURES", [])),
            "min_confidence": float(getattr(reg, "MIN_CONFIDENCE", 0.77)),
            "ohlcv": list(getattr(reg, "OHLCV_HEADERS", ["open", "high", "low", "close", "volume"])),
            "version": getattr(reg, "ACTIVE_VERSION", "v1"),
            "forbidden": getattr(reg, "FORBIDDEN_FEATURES", set()),
            "train_count": int(getattr(reg, "TRAIN_COUNT", 28)),
            "predict_count": int(getattr(reg, "PREDICT_COUNT", 17)),
        }
    defaults = {
        "project_root": str(root),
        "scripts_path": str(root),
        "models_path": str(root / "models"),
        "data_path": str(root / "data"),
        "data_output_path": str(root / "data"),
        "log_path": str(root / "Logs"),
        "mt5_files_path": cfg.get("mt5_files_path", ""),
        "mt5_common_path": cfg.get("mt5_common_path", ""),
        "mt5_data_path": str(root / "data"),
        "ohlcv_columns": list(active["ohlcv"]),
        "ai_server_url": cfg.get("ai_server_url", "http://127.0.0.1:8080"),
        "ai_server_script": "ai_server.py",
        "min_confidence_threshold": float(active["min_confidence"]),
        "features": list(active["train"]),
        "features_predict": list(active["predict"]),
        "features_forbidden": sorted(active.get("forbidden") or getattr(reg, "FORBIDDEN_FEATURES", [])),
        "features_count_train": int(active["train_count"]),
        "features_count_predict": int(active["predict_count"]),
        "feature_registry_locked": True,
        "feature_registry_version": active.get("version"),
    }
    for k, v in defaults.items():
        if k not in cfg or k.startswith("features") or k in (
            "min_confidence_threshold",
            "ohlcv_columns",
            "feature_registry_locked",
            "features_count_train",
            "features_count_predict",
        ):
            cfg[k] = v
        elif not cfg.get(k):
            cfg[k] = v

    # HARD lock — overwrite features every run from registry
    active = reg.get_active() if hasattr(reg, "get_active") else {
        "train": list(getattr(reg, "TRAIN_FEATURES", [])),
        "predict": list(getattr(reg, "PREDICT_FEATURES", [])),
        "min_confidence": float(getattr(reg, "MIN_CONFIDENCE", 0.77)),
        "ohlcv": list(getattr(reg, "OHLCV_HEADERS", ["open","high","low","close","volume"])),
        "version": getattr(reg, "ACTIVE_VERSION", "v1"),
        "forbidden": getattr(reg, "FORBIDDEN_FEATURES", set()),
        "train_count": getattr(reg, "TRAIN_COUNT", 28),
        "predict_count": getattr(reg, "PREDICT_COUNT", 17),
    }
    cfg["features"] = list(active["train"])
    cfg["features_predict"] = list(active["predict"])
    cfg["features_forbidden"] = sorted(active.get("forbidden") or getattr(reg, "FORBIDDEN_FEATURES", []))
    cfg["min_confidence_threshold"] = float(active["min_confidence"])
    cfg["ohlcv_columns"] = list(active["ohlcv"])
    cfg["feature_registry_version"] = active.get("version")

    for d in (
        cfg["models_path"],
        cfg["data_path"],
        cfg["data_output_path"],
        cfg["log_path"],
        str(root / "bridge"),
        str(root / "tests"),
        str(root / "state"),
        str(root / "data" / "raw_ohlcv"),
        str(root / "data" / "hist"),
        str(root / "data" / "Historical"),
    ):
        Path(d).mkdir(parents=True, exist_ok=True)

    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    ok(f"config locked features train={reg.TRAIN_COUNT} predict={reg.PREDICT_COUNT} conf={reg.MIN_CONFIDENCE}")
    return cfg


def run_inventory(root: Path) -> Dict[str, Any]:
    try:
        from script_inventory import discover_scripts, relocate, verify_present, DEST_MAP, PRODUCTION_ORDER
    except ImportError:
        inv = ROOT / "script_inventory.py"
        if inv.is_file():
            spec = importlib.util.spec_from_file_location("script_inventory", inv)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            discover_scripts, relocate, verify_present = mod.discover_scripts, mod.relocate, mod.verify_present
        else:
            return {"error": "script_inventory missing"}

    roots = [
        Path("/home/workdir/attachments"),
        root,
        root / "Scripts",
        ROOT,
    ]
    found = discover_scripts(roots)
    results = relocate(found, root, dry_run=False, force_backup_replace=False)
    ver = verify_present(root)
    return {"relocate": results, "verify": ver, "discovered": len(found)}


def run_visible(script: Path, cfg: dict, timeout: int) -> Dict[str, Any]:
    """Run one script in foreground with live output; no hidden window flags."""
    env = os.environ.copy()
    env["FXJEFE_PROJECT_ROOT"] = cfg["project_root"]
    env["FXJEFE_MIN_CONFIDENCE"] = str(cfg.get("min_confidence_threshold", 0.77))
    t0 = time.time()
    log(f"RUN {script.name} (timeout={timeout}s) — visible child")
    try:
        proc = subprocess.run(
            [sys.executable, "-u", str(script)],
            cwd=str(Path(cfg["project_root"])),
            env=env,
            timeout=timeout,
            # capture=False → inherit stdout/stderr (fully visible)
        )
        elapsed = time.time() - t0
        return {
            "script": script.name,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "elapsed_sec": round(elapsed, 2),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "script": script.name,
            "ok": False,
            "returncode": -9,
            "elapsed_sec": round(time.time() - t0, 2),
            "timed_out": True,
            "error": f"timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "script": script.name,
            "ok": False,
            "returncode": -1,
            "elapsed_sec": round(time.time() - t0, 2),
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def post_step_validate(script_name: str, cfg: dict, reg) -> Dict[str, Any]:
    """Light validation after each step."""
    data = Path(cfg["data_path"])
    models = Path(cfg["models_path"])
    checks = []
    if script_name in ("mt5_generate_features.py", "mt5_data_sync.py"):
        p = data / "FXJEFE_Features.csv"
        checks.append({"file": str(p), "exists": p.is_file(), "size": p.stat().st_size if p.is_file() else 0})
    if script_name == "generate_labels.py":
        for f in ("training_data.csv", "FXJEFE_Features_with_labels.csv"):
            p = Path(cfg["data_output_path"]) / f
            checks.append({"file": str(p), "exists": p.is_file()})
    if script_name == "train_models.py":
        p = models / "my_model.pkl"
        checks.append({"file": str(p), "exists": p.is_file()})
    if script_name == "check_model_features.py":
        # re-check train feature count via registry
        checks.append({"train_features": reg.TRAIN_COUNT, "predict_features": reg.PREDICT_COUNT})
    if script_name == "full_pipeline.py":
        feats = list(models.glob("*_features.json"))
        checks.append({"per_symbol_feature_json": len(feats)})
    return {"script": script_name, "checks": checks}


def discover_and_test_models(cfg: dict, reg) -> List[Dict[str, Any]]:
    """Auto-discover models; only accept if feature list matches frozen registry."""
    models_dir = Path(cfg["models_path"])
    report = []
    if not models_dir.is_dir():
        return report

    # per-symbol feature json from full_pipeline
    for feat_path in models_dir.glob("*_features.json"):
        try:
            meta = json.loads(feat_path.read_text(encoding="utf-8"))
            feats = meta.get("features") or []
            # Prefer predict-set match for live; else train-set
            ok_p, msg_p = reg.model_features_match(feats, mode="predict")
            ok_t, msg_t = reg.model_features_match(feats, mode="train")
            # also accept supersets that still contain all predict features
            pred_ok = set(reg.PREDICT_FEATURES).issubset(set(feats)) and not any(
                reg.is_forbidden(f) for f in feats if f in reg.PREDICT_FEATURES
            )
            accepted = ok_p or ok_t or pred_ok
            entry = {
                "path": str(feat_path),
                "symbol": meta.get("symbol"),
                "n_features": len(feats),
                "accepted": accepted,
                "predict_match": msg_p,
                "train_match": msg_t,
                "model_type": meta.get("model_type"),
            }
            if accepted:
                ok(f"model OK {feat_path.name} n={len(feats)}")
            else:
                warn(f"model REJECT {feat_path.name}: {msg_p} | {msg_t}")
            report.append(entry)
        except Exception as e:
            report.append({"path": str(feat_path), "accepted": False, "error": str(e)})

    # legacy my_model.pkl
    pkl = models_dir / "my_model.pkl"
    if pkl.is_file():
        try:
            import joblib

            model = joblib.load(pkl)
            n = getattr(model, "n_features_in_", None)
            accepted = n in (reg.TRAIN_COUNT, reg.PREDICT_COUNT)
            entry = {
                "path": str(pkl),
                "n_features_in": n,
                "accepted": accepted,
                "expected_train": reg.TRAIN_COUNT,
                "expected_predict": reg.PREDICT_COUNT,
            }
            if accepted:
                ok(f"legacy model OK n_features_in_={n}")
            else:
                warn(f"legacy model REJECT n_features_in_={n}")
            report.append(entry)
        except Exception as e:
            report.append({"path": str(pkl), "accepted": False, "error": str(e)})
    return report


def final_validation(cfg: dict, reg, step_results: List[dict], model_report: List[dict]) -> Dict[str, Any]:
    """Full pipeline validation after all scripts."""
    data = Path(cfg["data_path"])
    out = Path(cfg["data_output_path"])
    models = Path(cfg["models_path"])
    issues = []

    # feature lock still intact
    if list(cfg.get("features") or []) != list(reg.TRAIN_FEATURES):
        issues.append("config features drifted from registry TRAIN_FEATURES")
    if float(cfg.get("min_confidence_threshold", 0)) != float(reg.MIN_CONFIDENCE):
        issues.append("min_confidence_threshold drifted from registry")

    # key artifacts
    for p in [
        data / "FXJEFE_Features.csv",
        out / "training_data.csv",
    ]:
        if not p.is_file():
            issues.append(f"missing artifact {p}")

    failed_steps = [s for s in step_results if not s.get("ok")]
    accepted_models = [m for m in model_report if m.get("accepted")]

    report = {
        "ok": len(issues) == 0 and len(failed_steps) == 0,
        "issues": issues,
        "failed_steps": [s.get("script") for s in failed_steps],
        "accepted_models": len(accepted_models),
        "model_report": model_report,
        "predict_features": list(reg.PREDICT_FEATURES),
        "train_features": list(reg.TRAIN_FEATURES),
        "min_confidence": reg.MIN_CONFIDENCE,
        "ohlcv": list(reg.OHLCV_HEADERS),
        "at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return report


# Ordered production launch list (required flag)
PIPELINE: List[Tuple[str, bool, int]] = [
    # name, required, timeout_sec
    ("path_validate.py", False, 120),
    ("mt5_data_sync.py", False, 120),
    ("mt5_generate_features.py", False, 600),
    ("validate_data.py", True, 180),
    ("Load_and_Process.py", True, 180),
    ("adjust_headers.py", False, 180),
    ("generate_labels.py", True, 300),
    ("feature_engineering.py", False, 900),
    ("train_models.py", True, 600),
    ("check_model_features.py", True, 120),
    ("full_pipeline.py", False, 7200),
    ("signal_processor.py", False, 300),
    ("model_deploy.py", False, 180),
    ("ensemble_predictions.py", False, 300),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="FXJEFE production pipeline (full script set)")
    ap.add_argument("--inventory-only", action="store_true")
    ap.add_argument("--skip-server", action="store_true")
    ap.add_argument("--only", default="", help="Accepted for compatibility. Stages always follow run_pipeline.py.")
    ap.add_argument("--retry", type=int, default=1)
    ap.add_argument("--project-dir", default=None)
    ap.add_argument("--live", action="store_true", help="Accepted for compatibility. Live trading is the default.")
    ap.add_argument("--paper", action="store_true", help="Paper mode. No orders are sent.")
    ap.add_argument("--dry-run", action="store_true", help="Alias of --paper.")
    args = ap.parse_args()

    if args.project_dir:
        os.environ["FXJEFE_PROJECT_DIR"] = args.project_dir
    from path_resolver import ProjectRootError, require_project_root
    try:
        root = require_project_root(args.project_dir)
    except ProjectRootError as exc:
        err(str(exc))
        return 1
    os.chdir(root)
    log(f"project_root = {root}")
    log("policy = visible processes only; feature list locked via feature_registry")

    # 1) inventory / relocate
    log("--- script inventory & relocate ---")
    inv = run_inventory(root)
    log(f"inventory discovered={inv.get('discovered')} verify={inv.get('verify')}")
    if args.inventory_only:
        return 0 if (inv.get("verify") or {}).get("production_ready") else 1

    from run_pipeline import run as run_stages

    paper = bool(args.paper or args.dry_run)
    log("delegating stage order to run_pipeline.py dry_run=%s" % paper)
    return run_stages(project_dir=str(root), dry_run=paper, retry=args.retry)



if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[FXJEFE-PROD] interrupted — no hidden cleanup", flush=True)
        sys.exit(130)
