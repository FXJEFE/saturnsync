# -*- coding: utf-8 -*-
"""Execution stage. Sends an order only after the FTMO gate, and never in paper mode."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


def _read_gate(config):
    path = Path(config["state_path"]) / "ftmo_gate.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _append_trade(config, row):
    import pandas as pd

    path = Path(config["data_output_path"]) / "FXJEFE_trades.csv"
    frame = pd.DataFrame([row])
    if path.is_file():
        previous = pd.read_csv(path)
        frame = pd.concat([previous, frame], ignore_index=True)
    frame.to_csv(path, index=False, encoding="utf-8")
    outcomes = Path(config["data_output_path"]) / "FXJEFE_trades_outcomes.csv"
    outcome = dict(row)
    outcome["profit"] = 0.0
    out_frame = pd.DataFrame([outcome])
    if outcomes.is_file():
        previous = pd.read_csv(outcomes)
        out_frame = pd.concat([previous, out_frame], ignore_index=True)
    out_frame.to_csv(outcomes, index=False, encoding="utf-8")
    return path


def run(project_dir=None, dry_run=True):
    from stage_support import activate
    from mt5_client import get_mt5

    ctx = activate("process_trades.log", project_dir=project_dir, dry_run=dry_run)
    config = ctx["config"]
    gate = _read_gate(config)
    if not gate or not gate.get("passed"):
        logging.error("FTMO gate has not passed; refusing execution")
        return 1
    proposed = gate.get("proposed") or {}
    side = (proposed.get("side") or "").lower()
    if side not in ("buy", "sell"):
        logging.info("FTMO gate passed and there is no order to send")
        return 0
    row = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": proposed.get("symbol") or "",
        "side": side,
        "volume": proposed.get("lot") or 0.0,
        "price": 0.0,
        "dry_run": bool(dry_run),
        "profit": 0.0,
    }
    if dry_run:
        path = _append_trade(config, row)
        logging.info("Paper order recorded at %s (order_send not called)", path)
        return 0
    if config.get("allow_live_trading") is False:
        logging.error("Live trading is disabled")
        return 1
    terminal = get_mt5(dry_run=False)
    if not terminal.initialize():
        logging.error("MT5 initialize failed before execution: %s", terminal.last_error())
        return 1
    try:
        info = terminal.symbol_info(row["symbol"])
        tick = terminal.symbol_info_tick(row["symbol"])
        if info is None or tick is None:
            logging.error("No market data for %s", row["symbol"])
            return 1
        price = tick.ask if side == "buy" else tick.bid
        request = {
            "action": terminal.TRADE_ACTION_DEAL,
            "symbol": row["symbol"],
            "volume": float(row["volume"]),
            "type": terminal.ORDER_TYPE_BUY if side == "buy" else terminal.ORDER_TYPE_SELL,
            "price": price,
            "type_time": terminal.ORDER_TIME_GTC,
            "type_filling": terminal.ORDER_FILLING_IOC,
        }
        result = terminal.order_send(request)
        retcode = getattr(result, "retcode", None)
        if retcode != terminal.TRADE_RETCODE_DONE:
            logging.error("order_send rejected: %s", getattr(result, "comment", retcode))
            return 1
        row["price"] = price
        row["dry_run"] = False
        _append_trade(config, row)
        logging.info("Live order accepted for %s %s", side, row["symbol"])
        return 0
    finally:
        terminal.shutdown()


def main(argv=None):
    from stage_support import call_main

    return call_main(run, argv)


if __name__ == "__main__":
    sys.exit(main())
