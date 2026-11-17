# -*- coding: utf-8 -*-
"""Load an FTMO rules file and enforce only the limits it actually contains.

No FTMO config was found in FXJEFE/saturnsync, FXJEFE/user_documents_fxjefe_project,
or the accessible file trees of FXJEFE/420-25 and FXJEFE/April25AmenAlignment.
FXJEFE/BalalaikaBandits returned 404 for this account. This module does not
invent daily-loss, drawdown, lot, or profit-target numbers. If the file is
missing, or it contains none of the recognized limit keys, validation fails.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

CANDIDATE_NAMES = (
    "ftmo_config.json",
    "FTMOConfig.json",
    "ftmoconfig.json",
    "ftmo_config.yaml",
    "ftmo_config.yml",
    "FTMOConfig.yaml",
    "FTMOConfig.yml",
    "ftmoconfig.yaml",
    "ftmoconfig.yml",
    os.path.join("config", "ftmo_config.json"),
    os.path.join("config", "FTMOConfig.json"),
    os.path.join("config", "ftmoconfig.json"),
    os.path.join("config", "ftmo_config.yaml"),
    os.path.join("config", "ftmo_config.yml"),
)

# Aliases the loader will enforce when the file supplies them.
# Percent keys are compared as percent points (5 means 5%), never scaled.
LIMIT_ALIASES = (
    (
        "daily_loss_pct",
        ("max_daily_loss_pct", "max_daily_loss_percent", "daily_max_loss_pct", "maxDailyLossPercent"),
    ),
    (
        "total_loss_pct",
        (
            "max_overall_loss_pct",
            "max_total_loss_pct",
            "max_drawdown_percent",
            "max_loss_pct",
            "maxOverallLossPercent",
        ),
    ),
    (
        "risk_per_trade_pct",
        ("max_risk_per_trade_pct", "risk_per_trade_pct", "max_risk_percent"),
    ),
    (
        "open_positions",
        ("max_positions", "max_open_positions", "maxOpenPositions"),
    ),
    (
        "lot",
        ("max_lot", "max_lots", "max_position_size"),
    ),
    (
        "trades_today",
        ("max_daily_trades", "max_trades_per_day"),
    ),
)

PROFIT_TARGET_KEYS = ("profit_target_pct", "max_profit_target_pct", "profitTargetPercent")
LIVE_FLAG_KEYS = ("allow_live_trading", "live_trading_allowed")

NOT_FOUND_MESSAGE = (
    "No FTMO config file was found. Looked for ftmoconfig / FTMOConfig / ftmo_config "
    "under PROJECT_ROOT. None exists in this repo (saturnsync), "
    "FXJEFE/user_documents_fxjefe_project, or the other FXJEFE trees this account can read, "
    "and FXJEFE/BalalaikaBandits is not accessible (HTTP 404). "
    "Refusing to invent risk limits. Place the real FTMO rules file at "
    "PROJECT_ROOT/ftmo_config.json (or set FTMO_CONFIG) and re-run."
)


def candidate_paths(root):
    root = Path(root)
    paths = []
    env = (os.environ.get("FTMO_CONFIG") or "").strip()
    if env:
        paths.append(Path(env).expanduser())
    for name in CANDIDATE_NAMES:
        paths.append(root / name)
    return paths


def find_ftmo_config(root):
    for path in candidate_paths(root):
        if path.is_file():
            return path
    return None


def _parse_scalar(text):
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "none", "~"):
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text.strip().strip('"').strip("'")


def _parse_simple_yaml(text):
    """Flat ``key: value`` YAML, enough for a rules file without PyYAML."""
    data = {}
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith("---"):
            continue
        if ":" not in stripped:
            raise ValueError("unsupported YAML line: %s" % stripped)
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError("nested or empty YAML is not supported: %s" % stripped)
        data[key] = _parse_scalar(value)
    if not data:
        raise ValueError("YAML rules file was empty")
    return data


def load_ftmo_file(path):
    raw = Path(path).read_text(encoding="utf-8-sig")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        if Path(path).suffix.lower() in (".yaml", ".yml") or ":" in raw:
            data = _parse_simple_yaml(raw)
        else:
            raise
    if not isinstance(data, dict):
        raise ValueError("FTMO config root must be an object")
    return data


def flatten_rules(data):
    flat = {}
    for key, value in data.items():
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                if not isinstance(inner_value, dict):
                    flat.setdefault(str(inner_key), inner_value)
                    flat.setdefault("%s.%s" % (key, inner_key), inner_value)
        else:
            flat[str(key)] = value
    return flat


def extract_limits(data):
    """Map recognized keys onto canonical fields. Missing keys are omitted."""
    flat = flatten_rules(data)
    limits = {}
    for canonical, aliases in LIMIT_ALIASES:
        for alias in aliases:
            if alias in flat and isinstance(flat[alias], (int, float)) and not isinstance(flat[alias], bool):
                limits[canonical] = float(flat[alias])
                limits["_source_%s" % canonical] = alias
                break
    for alias in PROFIT_TARGET_KEYS:
        if alias in flat and isinstance(flat[alias], (int, float)) and not isinstance(flat[alias], bool):
            limits["profit_target_pct"] = float(flat[alias])
            break
    for alias in LIVE_FLAG_KEYS:
        if alias in flat and isinstance(flat[alias], bool):
            limits["allow_live_trading"] = flat[alias]
            break
    recognized = [key for key in limits if not key.startswith("_source_")]
    return limits, recognized


def account_metrics(snapshot):
    snapshot = snapshot or {}
    balance = float(snapshot.get("balance") or 0.0)
    equity = float(snapshot.get("equity") if snapshot.get("equity") is not None else balance)
    day_start = float(snapshot.get("day_start_balance") or balance or 0.0)
    initial = float(snapshot.get("initial_balance") or day_start or 0.0)
    daily_loss = 0.0
    total_loss = 0.0
    profit = 0.0
    if day_start > 0:
        daily_loss = max(0.0, (day_start - equity) / day_start * 100.0)
    if initial > 0:
        total_loss = max(0.0, (initial - equity) / initial * 100.0)
        profit = (equity - initial) / initial * 100.0
    return {
        "daily_loss_pct": daily_loss,
        "total_loss_pct": total_loss,
        "profit_pct": profit,
        "open_positions": float(snapshot.get("open_positions") or 0),
        "trades_today": float(snapshot.get("trades_today") or 0),
        "lot": float(snapshot.get("lot") or 0),
        "risk_per_trade_pct": float(snapshot.get("risk_per_trade_pct") or 0),
    }


def evaluate(limits, snapshot, proposed=None):
    """Return ``(ok, reasons)``. A breach is any measured value above a supplied limit.

    ``proposed`` may set ``lot`` and ``risk_per_trade_pct`` for the order that
    would be sent. This function never sends an order.
    """
    measured = account_metrics(snapshot)
    if proposed:
        if proposed.get("lot") is not None:
            measured["lot"] = float(proposed["lot"])
        if proposed.get("risk_per_trade_pct") is not None:
            measured["risk_per_trade_pct"] = float(proposed["risk_per_trade_pct"])
        if proposed.get("open_positions") is not None:
            measured["open_positions"] = float(proposed["open_positions"])
    reasons = []
    for canonical, _aliases in LIMIT_ALIASES:
        if canonical not in limits:
            continue
        cap = float(limits[canonical])
        actual = float(measured.get(canonical) or 0.0)
        if actual > cap:
            reasons.append(
                "FTMO breach: %s %.6g exceeds limit %.6g (from %s)"
                % (canonical, actual, cap, limits.get("_source_%s" % canonical, canonical))
            )
    if "profit_target_pct" in limits and measured["profit_pct"] >= float(limits["profit_target_pct"]):
        reasons.append(
            "FTMO profit target reached: %.6g%% >= %.6g%%; no new orders"
            % (measured["profit_pct"], float(limits["profit_target_pct"]))
        )
    return (len(reasons) == 0), reasons


def load_snapshot(root, mt5=None):
    path = Path(root) / "state" / "account_snapshot.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.pop("login", None)
            data.pop("password", None)
            data.pop("account", None)
            return data
    if mt5 is not None:
        info = mt5.account_info()
        if info is not None:
            balance = float(getattr(info, "balance", 0) or 0)
            equity = float(getattr(info, "equity", balance) or balance)
            return {
                "balance": balance,
                "equity": equity,
                "day_start_balance": balance,
                "initial_balance": balance,
                "open_positions": 0,
                "trades_today": 0,
            }
    return None


def validate_rules(root, snapshot=None):
    path = find_ftmo_config(root)
    if path is None:
        return {
            "ok": False,
            "path": None,
            "limits": {},
            "reasons": [NOT_FOUND_MESSAGE],
            "searched": [str(item) for item in candidate_paths(root)],
        }
    try:
        data = load_ftmo_file(path)
        limits, recognized = extract_limits(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "path": str(path),
            "limits": {},
            "reasons": ["FTMO config %s could not be read: %s" % (path, exc)],
            "searched": [str(item) for item in candidate_paths(root)],
        }
    enforceable = [
        key
        for key in recognized
        if key in (
            "daily_loss_pct",
            "total_loss_pct",
            "risk_per_trade_pct",
            "open_positions",
            "lot",
            "trades_today",
            "profit_target_pct",
        )
    ]
    if not enforceable:
        return {
            "ok": False,
            "path": str(path),
            "limits": limits,
            "reasons": [
                "FTMO config %s contains no recognized risk limits. "
                "Refusing to invent values. Recognized keys: %s"
                % (path, ", ".join(alias for _name, aliases in LIMIT_ALIASES for alias in aliases))
            ],
            "searched": [str(item) for item in candidate_paths(root)],
        }
    if snapshot is None:
        return {
            "ok": True,
            "path": str(path),
            "limits": limits,
            "reasons": ["FTMO config loaded from %s; no account snapshot yet" % path],
            "searched": [str(item) for item in candidate_paths(root)],
        }
    ok, reasons = evaluate(limits, snapshot)
    if ok:
        reasons = ["FTMO account check passed using %s" % path]
    return {
        "ok": ok,
        "path": str(path),
        "limits": limits,
        "reasons": reasons,
        "searched": [str(item) for item in candidate_paths(root)],
    }


def run(project_dir=None, dry_run=True):
    from stage_support import activate

    ctx = activate("ftmo_rules.log", project_dir=project_dir, dry_run=dry_run)
    snapshot = load_snapshot(ctx["root"])
    if snapshot is None:
        from mt5_client import get_mt5

        terminal = get_mt5(dry_run=dry_run)
        terminal.initialize()
        try:
            snapshot = load_snapshot(ctx["root"], terminal)
        finally:
            terminal.shutdown()
        if snapshot is not None:
            logging.info("FTMO account snapshot taken from the terminal session (account number not logged)")
    result = validate_rules(ctx["root"], snapshot)
    out = Path(ctx["config"]["state_path"]) / "ftmo_rules.json"
    payload = {
        "ok": result["ok"],
        "path": result["path"],
        "reasons": result["reasons"],
        "limits": {key: value for key, value in result["limits"].items() if not str(key).startswith("_")},
        "dry_run": dry_run,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for reason in result["reasons"]:
        if result["ok"]:
            logging.info(reason)
        else:
            logging.error(reason)
    return 0 if result["ok"] else 1


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
