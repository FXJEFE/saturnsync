# -*- coding: utf-8 -*-
"""FTMO rules, feature-hash contract, checksum manifest, and strategy combine."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FeatureHashTests(unittest.TestCase):
    def test_reverse_changes_ordered_hash_only(self):
        from feature_hash import CONTRACT_FEATURES, feature_hash

        names = ["price", "atr", "rsi"]
        reversed_names = list(reversed(names))
        self.assertEqual(feature_hash(names, mode="set"), feature_hash(reversed_names, mode="set"))
        self.assertNotEqual(feature_hash(names, mode="ordered"), feature_hash(reversed_names, mode="ordered"))
        self.assertEqual(len(feature_hash(names, length=16)), 16)
        self.assertEqual(len(CONTRACT_FEATURES), 29)

    def test_pair_and_empty_roles(self):
        from feature_hash import all_roles_match, feature_hash_pair

        pair = feature_hash_pair(["rsi", "rsi", " atr "])
        self.assertEqual(pair["count"], 3)
        self.assertEqual(pair["unique"], 2)
        self.assertEqual(len(pair["hash_set_short"]), 16)
        ok, info = all_roles_match({"model": ["rsi"], "ea": [], "server": ["rsi"]}, mode="ordered")
        self.assertTrue(ok)
        self.assertEqual(info["reference"], "model")
        ok, info = all_roles_match({"ea": [], "server": []})
        self.assertFalse(ok)

    def test_missing_key_becomes_zero_and_28_model_fails(self):
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier

        from feature_hash import CONTRACT_FEATURES, align_contract_row

        row = align_contract_row({"price": 1.25})
        self.assertEqual(len(row), 29)
        self.assertEqual(row[0], 1.25)
        self.assertEqual(row[1], 0.0)
        model = RandomForestClassifier(n_estimators=1, random_state=0)
        model.fit(np.zeros((8, 28)), np.array([0, 1] * 4))
        self.assertEqual(int(model.n_features_in_), 28)
        self.assertNotEqual(int(model.n_features_in_), len(CONTRACT_FEATURES))


class FtmoRuleTests(unittest.TestCase):
    def test_example_file_and_primary_name(self):
        from ftmo_rules import CANDIDATE_NAMES, extract_limits, load_ftmo_file

        self.assertEqual(CANDIDATE_NAMES[0], "configftmo.json")
        example = load_ftmo_file(ROOT / "configftmo.example.json")
        self.assertEqual(example["account"], "demo-200k")
        self.assertEqual(example["account_balance_ref"], 200000)
        self.assertEqual(example["max_drawdown_percent"], 6.66)
        self.assertEqual(example["risk_percent"], 33.3)
        self.assertEqual(example["profit_target_percent"], 11.1)
        self.assertFalse(example["close_positions_on_stop"])
        self.assertEqual(example["max_position_size"], 1.0)
        self.assertEqual(example["max_leverage"], 100)
        self.assertEqual(example["min_margin_level_percent"], 300)
        self.assertNotIn("password", example)
        self.assertTrue(str(example["python_executable"]).startswith("fxjefe/"))
        limits, _recognized = extract_limits(example)
        self.assertEqual(limits["drawdown_pct"], 6.66)
        self.assertEqual(limits["risk_percent"], 33.3)
        self.assertFalse(limits["close_positions_on_stop"])

    def test_drawdown_and_profit_stop_new_entries_only(self):
        from ftmo_rules import evaluate, extract_limits, load_ftmo_file

        limits, _recognized = extract_limits(load_ftmo_file(ROOT / "configftmo.example.json"))
        ok, reasons = evaluate(limits, {"balance": 200000, "equity": 186680, "initial_balance": 200000})
        self.assertFalse(ok)
        self.assertTrue(any("drawdown" in reason for reason in reasons))
        self.assertTrue(any("not closed" in reason for reason in reasons))
        ok, _reasons = evaluate(limits, {"balance": 200000, "equity": 186681, "initial_balance": 200000})
        self.assertTrue(ok)
        ok, reasons = evaluate(limits, {"balance": 222200, "equity": 222200, "initial_balance": 200000})
        self.assertFalse(ok)
        self.assertTrue(any("profit target" in reason for reason in reasons))

    def test_old_alias_still_reads(self):
        from ftmo_rules import extract_limits

        limits, _recognized = extract_limits({"max_overall_loss_pct": 10, "max_risk_per_trade_pct": 1})
        self.assertEqual(limits["drawdown_pct"], 10.0)
        self.assertEqual(limits["risk_percent"], 1.0)

    def test_margin_guard_shrinks_or_skips(self):
        from ftmo_rules import extract_limits, load_ftmo_file, size_lot
        from mt5_client import paper_terminal

        terminal = paper_terminal()
        terminal.initialize()
        try:
            limits, _recognized = extract_limits(load_ftmo_file(ROOT / "configftmo.example.json"))
            snapshot = {"balance": 200000, "equity": 200000, "initial_balance": 200000}
            lot, reason = size_lot(terminal, "EURUSD", "buy", snapshot, limits)
            self.assertIsNotNone(lot)
            self.assertLessEqual(lot, 1.0)
            self.assertIn("margin guard", reason)
            terminal.order_send_calls = 0
            self.assertEqual(terminal.order_send_calls, 0)
        finally:
            terminal.shutdown()


class ChecksumTests(unittest.TestCase):
    def test_missing_manifest_message(self):
        import verify_checksums

        root = Path(tempfile.mkdtemp())
        (root / "config.json").write_text("{}", encoding="utf-8")
        code = verify_checksums.verify(root)
        self.assertEqual(code, 1)
        # generator creates a manifest; a second verify then passes
        verify_checksums.write_manifest(root)
        self.assertTrue((root / "checksums.json").is_file())
        self.assertEqual(verify_checksums.verify(root), 0)


class LiveDefaultTests(unittest.TestCase):
    def test_cli_defaults_to_live_and_paper_alias(self):
        import run_pipeline

        self.assertFalse(run_pipeline.dry_run_from_args(run_pipeline.parse_cli([])))
        self.assertFalse(run_pipeline.dry_run_from_args(run_pipeline.parse_cli(["--live"])))
        self.assertTrue(run_pipeline.dry_run_from_args(run_pipeline.parse_cli(["--paper"])))
        self.assertTrue(run_pipeline.dry_run_from_args(run_pipeline.parse_cli(["--dry-run"])))
        self.assertTrue(run_pipeline.dry_run_from_args(run_pipeline.parse_cli(["--live", "--paper"])))

    def test_live_fails_closed_without_rules_or_credentials(self):
        import os
        import run_pipeline
        from mt5_client import paper_terminal

        paper_terminal().order_send_calls = 0
        root = Path(tempfile.mkdtemp(prefix="fxjefe-live-"))
        (root / "config.json").write_text((ROOT / "config.json").read_text(encoding="utf-8"), encoding="utf-8")
        saved = {key: os.environ.pop(key, None) for key in ("MT5_ACCOUNT", "MT5_PASSWORD", "MT5_SERVER")}
        try:
            code = run_pipeline.run(project_dir=str(root), dry_run=False, retry=1)
            self.assertEqual(code, 1)
            self.assertEqual(paper_terminal().order_send_calls, 0)
            log_text = (root / "Logs" / "pipeline.log").read_text(encoding="utf-8", errors="replace")
            self.assertIn("LIVE MODE", log_text)
            self.assertIn("configftmo.json is missing", log_text)
            (root / "configftmo.json").write_text((ROOT / "configftmo.json").read_text(encoding="utf-8"), encoding="utf-8")
            code = run_pipeline.run(project_dir=str(root), dry_run=False, retry=1)
            self.assertEqual(code, 1)
            log_text = (root / "Logs" / "pipeline.log").read_text(encoding="utf-8", errors="replace")
            self.assertIn("MT5 credentials are missing", log_text)
            self.assertEqual(paper_terminal().order_send_calls, 0)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class StrategyTests(unittest.TestCase):
    def test_sentiment_neutral_does_not_block_paper_cycle(self):
        import os
        import run_pipeline

        root = Path(tempfile.mkdtemp())
        (root / "config.json").write_text((ROOT / "config.json").read_text(encoding="utf-8"), encoding="utf-8")
        os.environ.pop("FXJEFE_SENTIMENT", None)
        from path_resolver import load_config

        cfg = load_config(root)
        code = run_pipeline.run_strategy_cycle(root, cfg, dry_run=True)
        self.assertEqual(code, 0)
        frame_path = root / "data" / "strategy_signals.csv"
        self.assertTrue(frame_path.is_file())
        text = frame_path.read_text(encoding="utf-8")
        self.assertIn("M1", text)
        self.assertIn("H1", text)
        self.assertIn("EURUSD", text)


if __name__ == "__main__":
    unittest.main()
