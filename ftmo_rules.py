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
    "configftmo.json",
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
        "drawdown_pct",
        (
            "max_drawdown_percent",
            "max_overall_loss_pct",
            "max_total_loss_pct",
            "max_loss_pct",
            "maxOverallLossPercent",
        ),
    ),
    (
        "risk_percent",
        ("risk_percent", "max_risk_per_trade_pct", "risk_per_trade_pct", "max_risk_percent"),
    ),
    (
        "open_positions",
        ("max_positions", "max_open_positions", "maxOpenPositions"),
    ),
    (
        "lot",
        ("max_position_size", "max_lot", "max_lots"),
    ),
    (
        "trades_today",
        ("max_daily_trades", "max_trades_per_day"),
    ),
)

PROFIT_TARGET_KEYS = (
    "profit_target_percent",
    "profit_target_pct",
    "max_profit_target_pct",
    "profitTargetPercent",
)
LIVE_FLAG_KEYS = ("allow_live_trading", "live_trading_allowed")

NOT_FOUND_MESSAGE = (
    "No FTMO config file was found. The primary filename is PROJECT_ROOT/configftmo.json "
    "(see configftmo.example.json). Also checked ftmo_config / FTMOConfig / ftmoconfig. "
    "Set FTMO_CONFIG to point at a file. Refusing to invent limits that are not in the file."
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
            limits["_source_profit_target_pct"] = alias
            break
    if "min_margin_level_percent" in flat and isinstance(flat["min_margin_level_percent"], (int, float)):
        limits["min_margin_level_percent"] = float(flat["min_margin_level_percent"])
    else:
        limits["min_margin_level_percent"] = 300.0
    if "max_leverage" in flat and isinstance(flat["max_leverage"], (int, float)):
        limits["max_leverage"] = float(flat["max_leverage"])
    else:
        limits["max_leverage"] = 100.0
    if "account_balance_ref" in flat and isinstance(flat["account_balance_ref"], (int, float)):
        limits["account_balance_ref"] = float(flat["account_balance_ref"])
    if isinstance(flat.get("close_positions_on_stop"), bool):
        limits["close_positions_on_stop"] = flat["close_positions_on_stop"]
    else:
        limits["close_positions_on_stop"] = False
    for text_key in ("account", "python_executable", "mt5_mql5_dir"):
        if isinstance(flat.get(text_key), str) and flat[text_key].strip():
            limits[text_key] = flat[text_key].strip()
    for alias in LIVE_FLAG_KEYS:
        if alias in flat and isinstance(flat[alias], bool):
            limits["allow_live_trading"] = flat[alias]
            break
    recognized = [key for key in limits if not key.startswith("_source_")]
    return limits, recognized


def account_metrics(snapshot, limits=None):
    snapshot = snapshot or {}
    limits = limits or {}
    balance = float(snapshot.get("balance") or 0.0)
    equity = float(snapshot.get("equity") if snapshot.get("equity") is not None else balance)
    day_start = float(snapshot.get("day_start_balance") or balance or 0.0)
    if limits.get("account_balance_ref"):
        reference = float(limits["account_balance_ref"])
    else:
        reference = float(snapshot.get("initial_balance") or day_start or 0.0)
    peak = float(snapshot.get("peak_equity") or 0.0)
    daily_loss = 0.0
    if day_start > 0:
        daily_loss = max(0.0, (day_start - equity) / day_start * 100.0)
    drawdowns = []
    if reference > 0:
        drawdowns.append((reference - equity) / reference * 100.0)
    if peak > 0:
        drawdowns.append((peak - equity) / peak * 100.0)
    drawdown = max([0.0] + drawdowns) if drawdowns else 0.0
    profit = ((equity - reference) / reference * 100.0) if reference > 0 else 0.0
    return {
        "daily_loss_pct": daily_loss,
        "drawdown_pct": drawdown,
        "total_loss_pct": drawdown,
        "profit_pct": profit,
        "open_positions": float(snapshot.get("open_positions") or 0),
        "trades_today": float(snapshot.get("trades_today") or 0),
        "lot": float(snapshot.get("lot") or 0),
        "risk_per_trade_pct": float(snapshot.get("risk_per_trade_pct") or 0),
        "reference_balance": reference,
    }


def evaluate(limits, snapshot, proposed=None):
    """Return ``(ok, reasons)``. A breach is any measured value above a supplied limit.

    ``proposed`` may set ``lot`` and ``risk_per_trade_pct`` for the order that
    would be sent. This function never sends an order.
    """
    measured = account_metrics(snapshot, limits)
    if proposed:
        if proposed.get("lot") is not None:
            measured["lot"] = float(proposed["lot"])
        if proposed.get("risk_per_trade_pct") is not None:
            measured["risk_per_trade_pct"] = float(proposed["risk_per_trade_pct"])
        if proposed.get("open_positions") is not None:
            measured["open_positions"] = float(proposed["open_positions"])
    reasons = []
    compare_keys = ("daily_loss_pct", "drawdown_pct", "open_positions", "lot", "trades_today")
    for canonical, _aliases in LIMIT_ALIASES:
        if canonical not in compare_keys or canonical not in limits:
            continue
        cap = float(limits[canonical])
        actual = float(measured.get(canonical) or 0.0)
        reached = actual >= cap if canonical == "drawdown_pct" else actual > cap
        if reached:
            reasons.append(
                "FTMO breach: %s %.6g exceeds limit %.6g (from %s)"
                % (canonical, actual, cap, limits.get("_source_%s" % canonical, canonical))
            )
    if "profit_target_pct" in limits and measured["profit_pct"] >= float(limits["profit_target_pct"]):
        reasons.append(
            "FTMO profit target reached: %.6g%% >= %.6g%%; stop opening new trades; open positions stay open"
            % (measured["profit_pct"], float(limits["profit_target_pct"]))
        )
    if reasons and not limits.get("close_positions_on_stop", False):
        reasons.append("close_positions_on_stop is false; open positions are not closed or modified")
    return (len(reasons) == 0), reasons


def size_lot(terminal, symbol, side, snapshot, limits):
    """Shrink the lot so margin level and free margin survive the new trade.

    ``order_calc_margin`` plus ``account_info`` override ``risk_percent``.
    Returns ``(lot, reason)``. ``lot`` is None when the order must be skipped.
    Never sends an order and never closes a position.
    """
    info = terminal.symbol_info(symbol)
    tick = terminal.symbol_info_tick(symbol)
    account = terminal.account_info()
    if info is None or tick is None or account is None:
        return None, "margin guard skipped the order; symbol or account info is missing"
    equity = float(getattr(account, "equity", 0) or 0)
    balance = float(getattr(account, "balance", 0) or equity)
    if snapshot:
        if snapshot.get("equity") is not None:
            equity = float(snapshot["equity"])
        if snapshot.get("balance") is not None:
            balance = float(snapshot["balance"])
    price = float(tick.ask if side == "buy" else tick.bid)
    step = float(getattr(info, "volume_step", 0.01) or 0.01)
    vmin = float(getattr(info, "volume_min", step) or step)
    vmax = float(getattr(info, "volume_max", 1.0) or 1.0)
    max_lot = float(limits.get("lot") or vmax)
    max_lot = min(max_lot, vmax)
    max_leverage = float(limits.get("max_leverage") or 100.0)
    min_level = float(limits.get("min_margin_level_percent") or 300.0)
    risk_percent = float(limits.get("risk_percent") or 0.0)
    reported_leverage = float(getattr(account, "leverage", max_leverage) or max_leverage)
    leverage = min(reported_leverage, max_leverage) if reported_leverage > 0 else max_leverage
    if snapshot is not None and snapshot.get("margin") is not None:
        margin_used = float(snapshot.get("margin") or 0.0)
    elif snapshot is not None and snapshot.get("margin_free") is not None:
        margin_used = max(0.0, equity - float(snapshot["margin_free"]))
    else:
        margin_used = float(getattr(account, "margin", 0) or 0)
        if margin_used <= 0 and getattr(account, "margin_free", None) is not None and snapshot is None:
            margin_used = max(0.0, equity - float(account.margin_free))
    order_type = terminal.ORDER_TYPE_BUY if side == "buy" else terminal.ORDER_TYPE_SELL

    def margin_for(lot):
        calc = None
        try:
            calc = terminal.order_calc_margin(order_type, symbol, float(lot), price)
        except Exception:
            calc = None
        if calc is None:
            contract = float(getattr(info, "trade_contract_size", 100000) or 100000)
            calc = contract * float(lot) * price / max(leverage, 1.0)
        else:
            calc = float(calc)
            if reported_leverage > max_leverage:
                calc *= reported_leverage / max_leverage
        return calc

    def fits(lot):
        added = margin_for(lot)
        total = margin_used + added
        free = equity - total
        if free < 0:
            return False
        if total <= 0:
            return True
        return (equity / total * 100.0) >= min_level

    budget = balance * (risk_percent / 100.0) if risk_percent > 0 else None
    lot = max_lot
    chosen = None
    while lot + 1e-12 >= vmin:
        rounded = round(round(lot / step) * step, 8)
        if rounded < vmin:
            break
        within_risk = budget is None or margin_for(rounded) <= budget + 1e-6
        if within_risk and fits(rounded):
            chosen = rounded
            break
        lot = rounded - step
    if chosen is None:
        return None, "margin guard skipped the order; lot cannot keep margin level >= %s and free margin >= 0" % min_level
    return chosen, "margin guard lot=%s (risk_percent=%s, max_leverage=%s, min_margin_level_percent=%s)" % (
        chosen, risk_percent, max_leverage, min_level,
    )


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
                "margin": float(getattr(info, "margin", 0) or 0),
                "margin_free": float(getattr(info, "margin_free", equity) or 0),
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
            "drawdown_pct",
            "risk_percent",
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
