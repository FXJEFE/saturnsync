# -*- coding: utf-8 -*-
"""MetaTrader5 access. Dry-run uses an in-process paper terminal.

The paper terminal has no account number and its ``order_send`` records a
refusal instead of transmitting an order. Live mode imports the real
MetaTrader5 package and never supplies a hardcoded login, password, or server.
"""
from __future__ import annotations

import os
import time
from types import SimpleNamespace


class OrderSendRefused(RuntimeError):
    pass


class PaperTerminal(object):
    """Small MT5 stand-in for Linux and for Windows paper mode."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.initialized = False
        self.order_send_calls = 0
        self._login_attempts = 0

    def initialize(self, *args, **kwargs):
        self.initialized = True
        return True

    def shutdown(self):
        self.initialized = False

    def last_error(self):
        return (1, "paper")

    def login(self, account, password="", server=""):
        self._login_attempts += 1
        if not password or not server or not account:
            return False
        return True

    def account_info(self):
        if not self.initialized:
            return None
        return SimpleNamespace(
            login=0,
            server=os.environ.get("MT5_SERVER", "") or "paper",
            balance=100000.0,
            equity=100000.0,
            margin=0.0,
            margin_free=100000.0,
            leverage=100,
        )

    def symbol_info(self, symbol):
        point = 0.01 if "JPY" in symbol or "XAU" in symbol or "BTC" in symbol else 0.00001
        return SimpleNamespace(
            visible=True,
            spread=10,
            point=point,
            trade_mode=4,
            volume_step=0.01,
            volume_min=0.01,
            volume_max=50.0,
            trade_contract_size=100000.0,
            trade_stops_level=0,
        )

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info_tick(self, symbol):
        price = 1900.0 if "XAU" in symbol else (30000.0 if "BTC" in symbol else 1.1)
        return SimpleNamespace(time=int(time.time()), bid=price, ask=price + 0.0001, last=price, volume=1)

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        count = int(count or 0)
        if count <= 0:
            return None
        # Keep paper history small even if the caller asks for tens of thousands.
        count = min(count, 300)
        if start and start >= 300:
            return None
        price = 1900.0 if "XAU" in symbol else (30000.0 if "BTC" in symbol or "ETH" in symbol or "XRP" in symbol else 1.1)
        rows = []
        base = int(time.time()) - count * 60
        for index in range(count):
            drift = ((index % 17) - 8) * (price * 0.0001)
            close = price + drift
            rows.append(
                {
                    "time": base + index * 60,
                    "open": close - price * 0.00005,
                    "high": close + price * 0.0002,
                    "low": close - price * 0.0002,
                    "close": close,
                    "tick_volume": 100 + (index % 20),
                    "spread": 10,
                    "real_volume": 0,
                }
            )
        return rows

    def order_calc_margin(self, order_type, symbol, volume, price):
        info = self.symbol_info(symbol)
        contract = float(getattr(info, "trade_contract_size", 100000) or 100000)
        leverage = float(getattr(self.account_info(), "leverage", 100) or 100)
        return contract * float(volume) * float(price) / max(leverage, 1.0)

    def order_send(self, request):
        self.order_send_calls += 1
        raise OrderSendRefused("paper terminal refuses order_send")


_PAPER = PaperTerminal()


def paper_terminal():
    return _PAPER


def real_mt5_available():
    try:
        import MetaTrader5  # noqa: F401
    except ImportError:
        return False
    return True


def get_mt5(dry_run=True):
    """Return the paper terminal in dry-run, otherwise the real package."""
    forced = os.environ.get("FXJEFE_MT5_MOCK", "")
    if dry_run or forced == "1":
        return _PAPER
    import MetaTrader5 as mt5

    return mt5


def credentials_from_env():
    """Read login material from the environment. Never returns hardcoded values."""
    account = (os.environ.get("MT5_ACCOUNT") or "").strip()
    password = os.environ.get("MT5_PASSWORD") or ""
    server = (os.environ.get("MT5_SERVER") or "").strip()
    if not account or not password or not server:
        return None
    return {"account": int(account), "password": password, "server": server}
