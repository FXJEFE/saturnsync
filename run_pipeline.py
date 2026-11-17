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
import sys
import time
import traceback

from path_resolver import ENV_VAR, ProjectRootError, load_config, require_project_root

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


def run_stage(module_name, project_dir, dry_run):
    module = importlib.import_module(module_name)
    runner = getattr(module, "run", None)
    if runner is None:
        raise RuntimeError("%s has no run()" % module_name)
    code = runner(project_dir=project_dir, dry_run=dry_run)
    if code is None:
        return 0
    return int(code)


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
    args = parser.parse_args(argv)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    dry_run = not args.live
    try:
        return run(project_dir=args.project_dir, dry_run=dry_run, retry=args.retry)
    except ProjectRootError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
