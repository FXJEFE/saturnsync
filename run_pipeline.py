# -*- coding: utf-8 -*-
"""Start every FXJEFE MT5 pipeline stage in dependency order.

Default mode is dry-run / paper: no live order is sent. ``--live`` is required
before any stage is allowed to call the broker. A failed stage or an FTMO
breach stops the pipeline.

Stage order
===========
1. PROJECT_ROOT, config.json, FTMO rule file
2. MT5 connection health
3. Data
4. Features and labels
5. Model
6. Signals
7. FTMO risk gate (before any order)
8. Execution
9. Monitoring
"""
from __future__ import annotations

import argparse
import importlib
import logging
import os
import subprocess
import sys
import time
import traceback

from path_resolver import ENV_VAR, ProjectRootError, load_config, require_project_root

# TA-Lib / TensorFlow 2.10.1 stack. Everything else uses the Python 3.11 fxjefe venv.
FXJEFE38_MODULES = frozenset(("feature_engineering", "get_lstm_prediction", "full_pipeline"))
STRATEGY_TIMEFRAMES = ("M1", "M5", "M15", "H1")
STRATEGY_SYMBOLS = ("EURUSD", "USDJPY", "XAUUSD", "AUDUSD", "GBPUSD", "USDCAD")

# (group, module, callable). Every module exposes run(project_dir, dry_run).
PIPELINE_STAGES = (
    ("project", "path_validate", "run"),
    ("project", "validate_config", "run"),
    ("project", "ftmo_rules", "run"),
    ("mt5_health", "mt5_health", "run"),
    ("data", "mt5_data_sync", "run"),
    ("data", "mt5_generate_features", "run"),
    ("data", "mt5_generate_crypto_features", "run"),
    ("data", "validate_data", "run"),
    ("data", "Load_and_Process", "run"),
    ("data", "fix_csv", "run"),
    ("data", "fix_csv_encoding", "run"),
    ("data", "adjust_headers", "run"),
    ("data", "convert_encoding", "run"),
    ("features", "generate_training_data", "run"),
    ("features", "generate_labels", "run"),
    ("features", "generate_new_csv", "run"),
    ("features", "clean_training_data", "run"),
    ("model", "train_models", "run"),
    ("model", "feature_engineering", "run"),
    ("model", "check_model_features", "run"),
    ("model", "full_pipeline", "run"),
    ("model", "model_deploy", "run"),
    ("signals", "ensemble_predictions", "run"),
    ("signals", "generate_signals_with_xgboost", "run"),
    ("signals", "get_lstm_prediction", "run"),
    ("signals", "signal_processor", "run"),
    ("signals", "signal_gate", "run"),
    ("signals", "mt5_signal_script", "run"),
    ("ftmo_risk_gate", "risk_management", "run"),
    ("execution", "process_trades", "run"),
    ("monitoring", "merge_datasets", "run"),
    ("monitoring", "analyze_outcomes", "run"),
    ("monitoring", "update_database", "run"),
    ("monitoring", "check_integrity", "run"),
    ("monitoring", "check_labels", "run"),
    ("monitoring", "log_summary", "run"),
)


def configure_logging(log_dir):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    path = os.path.join(log_dir, "pipeline.log")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream)
    return path


def interpreter_for(module_name, project_dir):
    """Pick fxjefe38 for feature engineering and LSTM, fxjefe for every other stage."""
    from fxjefe_paths import venv_python

    root = project_dir
    name = "fxjefe38" if module_name in FXJEFE38_MODULES else "fxjefe"
    candidate = venv_python(root, name)
    if candidate.is_file():
        return str(candidate)
    return sys.executable


def run_stage(module_name, project_dir, dry_run):
    py = interpreter_for(module_name, project_dir)
    if os.path.normcase(os.path.abspath(py)) != os.path.normcase(os.path.abspath(sys.executable)):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_dir)
        env[ENV_VAR] = str(project_dir)
        env["FXJEFE_DRY_RUN"] = "1" if dry_run else "0"
        code = (
            "import %s; raise SystemExit(%s.run(project_dir=%r, dry_run=%s))"
            % (module_name, module_name, str(project_dir), "True" if dry_run else "False")
        )
        logging.info("interpreter %s for %s", py, module_name)
        completed = subprocess.run([py, "-c", code], env=env, cwd=str(project_dir))
        return int(completed.returncode or 0)
    module = importlib.import_module(module_name)
    runner = getattr(module, "run", None)
    if runner is None:
        raise RuntimeError("%s has no run()" % module_name)
    code = runner(project_dir=project_dir, dry_run=dry_run)
    if code is None:
        return 0
    return int(code)


def _sentiment(symbol):
    """Pluggable sentiment. Neutral 0.0 when the provider is missing. Never raises in paper mode."""
    provider = (os.environ.get("FXJEFE_SENTIMENT") or "").strip()
    if not provider:
        return 0.0
    try:
        module = importlib.import_module(provider)
        return float(module.score(symbol))
    except Exception as exc:
        logging.info("sentiment unavailable for %s (%s); using neutral 0.0", symbol, exc)
        return 0.0


def _local_prediction(cfg, symbol):
    from feature_hash import CONTRACT_FEATURES, align_contract_row

    model_path = os.path.join(cfg["models_path"], "my_model.pkl")
    if not os.path.isfile(model_path):
        return "hold", 0.0
    import joblib

    model = joblib.load(model_path)
    expected = int(getattr(model, "n_features_in_", 0) or 0)
    if expected != len(CONTRACT_FEATURES):
        logging.error(
            "local model signature %s != contract %s; refusing local prediction",
            expected,
            len(CONTRACT_FEATURES),
        )
        return "hold", 0.0
    row = align_contract_row({}, CONTRACT_FEATURES)
    import numpy as np

    proba = model.predict_proba(np.asarray([row], dtype="float64"))[0]
    classes = list(getattr(model, "classes_", []))
    index = int(proba.argmax())
    label = classes[index] if index < len(classes) else 0
    mapping = {1: "buy", -1: "sell", 0: "hold", "buy": "buy", "sell": "sell", "hold": "hold"}
    return mapping.get(label, "hold"), float(proba[index])


def _golden_prediction(url, symbol, timeframe, payload):
    try:
        import requests
    except ImportError:
        return "hold", 0.0, False
    try:
        health = requests.get(url + "/health", timeout=2)
        if health.status_code != 200:
            return "hold", 0.0, False
        body = dict(payload)
        body["symbol"] = symbol
        body["timeframe"] = timeframe
        response = requests.post(url + "/predict", json=body, timeout=3)
        if response.status_code != 200:
            return "hold", 0.0, True
        data = response.json()
        return str(data.get("signal") or "hold").lower(), float(data.get("confidence") or 0.0), True
    except Exception as exc:
        logging.info("golden server %s unavailable (%s)", url, exc)
        return "hold", 0.0, False


def run_strategy_cycle(root, cfg, dry_run):
    """One multi-symbol, multi-timeframe pass. Paper mode is not blocked by a missing provider."""
    symbols = list(cfg.get("symbols") or STRATEGY_SYMBOLS)
    timeframes = list(cfg.get("timeframes") or STRATEGY_TIMEFRAMES)
    gate = float(cfg.get("min_confidence_threshold") or 0.77)
    url = str(cfg.get("golden_server_url") or cfg.get("ai_server_url") or "http://127.0.0.1:8080").rstrip("/")
    rows = []
    for symbol in symbols:
        sentiment = _sentiment(symbol)
        for timeframe in timeframes:
            local_signal, local_conf = _local_prediction(cfg, symbol)
            golden_signal, golden_conf, golden_up = _golden_prediction(url, symbol, timeframe, {})
            votes = []
            if golden_signal in ("buy", "sell") and golden_conf >= gate:
                votes.append((golden_signal, golden_conf))
            if local_signal in ("buy", "sell") and local_conf >= gate:
                votes.append((local_signal, local_conf))
            if not votes or len(set(item[0] for item in votes)) != 1:
                final, confidence = "hold", 0.0
            else:
                final = votes[0][0]
                confidence = sum(item[1] for item in votes) / float(len(votes))
                if confidence < gate:
                    final = "hold"
            rows.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "signal": final,
                "confidence": round(confidence, 4),
                "sentiment": sentiment,
                "golden_up": golden_up,
                "dry_run": bool(dry_run),
            })
    import pandas as pd

    frame = pd.DataFrame(rows)
    target = os.path.join(cfg["data_output_path"], "strategy_signals.csv")
    frame.to_csv(target, index=False, encoding="utf-8")
    logging.info(
        "strategy cycle symbols=%s timeframes=%s rows=%s min_confidence=%s wrote %s",
        ",".join(symbols),
        ",".join(timeframes),
        len(frame),
        gate,
        target,
    )
    return 0


def run_verification(project_dir=None, dry_run=True):
    """runtime_lock, feature_hash, signal_gate, verify_checksums, then golden /health."""
    root = require_project_root(project_dir)
    os.environ[ENV_VAR] = str(root)
    steps = (
        ("runtime_lock", "runtime_lock"),
        ("feature_hash", "feature_hash"),
        ("signal_gate", "signal_gate"),
        ("verify_checksums", "verify_checksums"),
    )
    for label, module_name in steps:
        logging.info("verify %s", label)
        code = run_stage(module_name, str(root), dry_run)
        if code != 0:
            logging.error("verification failed at %s exit=%s", label, code)
            return code
    return _golden_health(root, dry_run)


def _golden_health(root, dry_run):
    cfg = load_config(root)
    url = str(cfg.get("golden_server_url") or cfg.get("ai_server_url") or "http://127.0.0.1:8080").rstrip("/")
    try:
        import requests
    except ImportError:
        logging.error("requests is not installed; cannot hit %s/health", url)
        return 1
    try:
        response = requests.get(url + "/health", timeout=2)
        if response.status_code == 200:
            logging.info("golden /health %s", response.status_code)
            return 0
    except Exception:
        response = None
    py = interpreter_for("ai_server_golden", root)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env[ENV_VAR] = str(root)
    logging.info("starting ai_server_golden.py to check /health")
    proc = subprocess.Popen([py, os.path.join(str(root), "ai_server_golden.py")], cwd=str(root), env=env)
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                response = requests.get(url + "/health", timeout=1)
                if response.status_code == 200:
                    logging.info("golden /health ok %s", response.text[:200])
                    return 0
            except Exception:
                time.sleep(0.5)
        logging.error("ai_server_golden.py did not answer %s/health", url)
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def run(project_dir=None, dry_run=True, retry=1):
    root = require_project_root(project_dir)
    os.environ[ENV_VAR] = str(root)
    os.environ["FXJEFE_DRY_RUN"] = "1" if dry_run else "0"
    cfg = load_config(root)
    log_path = configure_logging(cfg["log_path"])
    logging.info("PROJECT_ROOT=%s", root)
    logging.info("config=%s", cfg["config_path"])
    logging.info("dry_run=%s log=%s", dry_run, log_path)
    logging.info("stage_count=%s", len(PIPELINE_STAGES))
    total = len(PIPELINE_STAGES)
    for index, (group, module_name, _fn) in enumerate(PIPELINE_STAGES, start=1):
        if group == "ftmo_risk_gate":
            logging.info("strategy cycle before the FTMO gate")
            cycle = run_strategy_cycle(root, cfg, dry_run)
            if cycle != 0:
                logging.error("Pipeline aborted at strategy cycle exit=%s", cycle)
                return cycle
        logging.info("[%s/%s] %s :: %s", index, total, group, module_name)
        success = False
        last_code = 1
        attempts = max(1, int(retry))
        for attempt in range(1, attempts + 1):
            try:
                last_code = run_stage(module_name, str(root), dry_run)
            except ProjectRootError:
                raise
            except Exception:
                last_code = 1
                logging.error("%s raised:\n%s", module_name, traceback.format_exc())
            if last_code == 0:
                success = True
                logging.info("OK %s", module_name)
                break
            if attempt < attempts:
                logging.warning("retry %s (%s/%s)", module_name, attempt, attempts)
                time.sleep(1)
        if not success:
            logging.error(
                "Pipeline aborted at %s/%s %s (%s) exit=%s",
                index,
                total,
                group,
                module_name,
                last_code,
            )
            return last_code or 1
    logging.info("Pipeline completed dry_run=%s", dry_run)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="FXJEFE MT5 pipeline (paper by default)")
    parser.add_argument("--project-dir", default=None, help="PROJECT_ROOT. Overrides %s." % ENV_VAR)
    parser.add_argument("--config", default=None, help="Accepted for compatibility; config.json is read from PROJECT_ROOT.")
    parser.add_argument("--retry", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--live", action="store_true", help="Allow live broker actions after the FTMO gate.")
    parser.add_argument("--dry-run", action="store_true", help="Paper mode (default).")
    parser.add_argument("--skip-server", action="store_true", help="Accepted for compatibility. The AI server is not started.")
    parser.add_argument("--skip-mt5", action="store_true", help="Accepted for compatibility. Health still runs in paper mode.")
    parser.add_argument("--verify", action="store_true", help="Run runtime_lock, feature_hash, signal_gate, verify_checksums, and golden /health.")
    args = parser.parse_args(argv)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    dry_run = not args.live
    try:
        if args.verify:
            return run_verification(project_dir=args.project_dir, dry_run=dry_run)
        return run(project_dir=args.project_dir, dry_run=dry_run, retry=args.retry)
    except ProjectRootError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
