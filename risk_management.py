# -*- coding: utf-8 -*-
"""FTMO risk gate. This stage never sends an order.

It re-reads the FTMO rules file and writes state/ftmo_gate.json. Execution
must refuse to continue unless that file says the gate passed.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from ftmo_rules import evaluate, load_snapshot, size_lot, validate_rules


def _latest_signal_file(config, name):
    path = os.path.join(config["data_output_path"], name)
    if not os.path.isfile(path):
        return None
    import pandas as pd

    frame = pd.read_csv(path, encoding="utf-8", low_memory=False)
    if frame.empty or "signal" not in frame.columns:
        return None
    directional = frame[frame["signal"].astype(str).str.lower().isin(["buy", "sell"])]
    row = directional.iloc[-1] if not directional.empty else frame.iloc[-1]
    return {
        "symbol": str(row["symbol"]) if "symbol" in frame.columns else "",
        "signal": str(row["signal"]).lower(),
        "price": float(row["price"]) if "price" in frame.columns else 0.0,
    }


def _latest_signal(config):
    return _latest_signal_file(config, "signals_output.csv")


def run(project_dir=None, dry_run=True):
    from stage_support import activate
    from mt5_client import get_mt5

    ctx = activate("risk_management.log", project_dir=project_dir, dry_run=dry_run)
    root = ctx["root"]
    config = ctx["config"]
    terminal = get_mt5(dry_run=dry_run)
    terminal.initialize()
    try:
        snapshot = load_snapshot(root, terminal)
        loaded = validate_rules(root, snapshot)
        if not loaded["ok"]:
            for reason in loaded["reasons"]:
                logging.error(reason)
            _write_gate(config, False, loaded["reasons"], None)
            return 1
        limits = loaded["limits"]
        signal = _latest_signal(config)
        strategy_signal = _latest_signal_file(config, "strategy_signals.csv")
        if strategy_signal:
            signal = strategy_signal
        proposed = None
        ok, reasons = evaluate(limits, snapshot, None)
        if ok and signal and signal["signal"] in ("buy", "sell"):
            lot, sizing_reason = size_lot(terminal, signal["symbol"], signal["signal"], snapshot, limits)
            logging.info(sizing_reason)
            if lot is None:
                reasons = list(reasons) + [sizing_reason]
            else:
                proposed = {
                    "symbol": signal["symbol"],
                    "side": signal["signal"],
                    "lot": lot,
                    "risk_per_trade_pct": float(limits.get("risk_percent") or 0.0),
                    "open_positions": float((snapshot or {}).get("open_positions") or 0) + 1,
                    "close_positions_on_stop": bool(limits.get("close_positions_on_stop")),
                }
                ok, reasons = evaluate(limits, snapshot, proposed)
        elif not signal or signal["signal"] not in ("buy", "sell"):
            reasons = list(reasons) + ["No directional signal; account limits already checked"]
        if not dry_run and limits.get("allow_live_trading") is False:
            ok = False
            reasons = list(reasons) + ["FTMO config allow_live_trading is false"]
        if limits.get("close_positions_on_stop"):
            logging.error("close_positions_on_stop is true in the rules file; this pipeline still does not close positions")
        for reason in reasons:
            if ok:
                logging.info(reason)
            else:
                logging.error(reason)
        _write_gate(config, ok, reasons, proposed)
        return 0 if ok else 1
    finally:
        terminal.shutdown()


def _write_gate(config, passed, reasons, proposed):
    payload = {
        "passed": bool(passed),
        "reasons": list(reasons),
        "proposed": proposed,
        "orders_sent": 0,
    }
    path = Path(config["state_path"]) / "ftmo_gate.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logging.info("FTMO gate passed=%s wrote %s", passed, path)


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
