# -*- coding: utf-8 -*-
"""Pipeline order, PROJECT_ROOT, and FTMO fail-closed checks. Python 3.8 compatible."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["FXJEFE_MT5_MOCK"] = "1"
os.environ.pop("FXJEFE_PROJECT_DIR", None)
os.environ.pop("FXJEFE_PROJECT_ROOT", None)


class ProjectRootTests(unittest.TestCase):
    def test_default_is_documents_fxjefe(self):
        from path_resolver import resolve_project_root

        home = Path("/tmp/fxjefe-home")
        path, source = resolve_project_root(environ={}, home=home)
        self.assertEqual(path, Path("/tmp/fxjefe-home/Documents/FXJEFE_Project"))
        self.assertEqual(source, "default")

    def test_env_and_cli_order(self):
        from path_resolver import resolve_project_root

        env = {"FXJEFE_PROJECT_DIR": "/tmp/from-env", "FXJEFE_PROJECT_ROOT": "/tmp/legacy"}
        path, source = resolve_project_root(environ=env, home=Path("/tmp/home"))
        self.assertEqual(source, "FXJEFE_PROJECT_DIR")
        self.assertTrue(str(path).endswith("from-env"))
        path, source = resolve_project_root(cli_dir="/tmp/from-cli", environ=env, home=Path("/tmp/home"))
        self.assertEqual(source, "--project-dir")
        self.assertTrue(str(path).endswith("from-cli"))

    def test_missing_root_fails(self):
        from path_resolver import ProjectRootError, require_project_root
        import run_pipeline

        missing = Path(tempfile.mkdtemp()) / "does-not-exist"
        with self.assertRaises(ProjectRootError) as caught:
            require_project_root(str(missing))
        self.assertIn("does not exist", str(caught.exception))
        code = run_pipeline.main(["--project-dir", str(missing)])
        self.assertEqual(code, 1)


class FtmoTests(unittest.TestCase):
    def test_missing_config_does_not_invent_limits(self):
        from ftmo_rules import NOT_FOUND_MESSAGE, validate_rules

        root = Path(tempfile.mkdtemp())
        (root / "config.json").write_text("{}", encoding="utf-8")
        result = validate_rules(root, {"balance": 100000, "equity": 100000})
        self.assertFalse(result["ok"])
        self.assertIn("Refusing to invent", result["reasons"][0])
        self.assertIn("Refusing to invent", NOT_FOUND_MESSAGE)
        self.assertEqual(result["limits"], {})
        shutil.rmtree(root)

    def test_breach_blocks_before_any_order(self):
        from ftmo_rules import evaluate

        limits = {"daily_loss_pct": 5.0, "_source_daily_loss_pct": "max_daily_loss_pct"}
        ok, reasons = evaluate(
            limits,
            {"balance": 100000, "equity": 90000, "day_start_balance": 100000, "initial_balance": 100000},
        )
        self.assertFalse(ok)
        self.assertTrue(any("breach" in reason for reason in reasons))


class PipelineOrderTests(unittest.TestCase):
    def test_stage_groups(self):
        import run_pipeline

        groups = [item[0] for item in run_pipeline.PIPELINE_STAGES]
        self.assertEqual(groups[0], "project")
        self.assertLess(groups.index("project"), groups.index("mt5_health"))
        self.assertLess(groups.index("mt5_health"), groups.index("data"))
        self.assertLess(groups.index("data"), groups.index("features"))
        self.assertLess(groups.index("features"), groups.index("model"))
        self.assertLess(groups.index("model"), groups.index("signals"))
        self.assertLess(groups.index("signals"), groups.index("ftmo_risk_gate"))
        self.assertLess(groups.index("ftmo_risk_gate"), groups.index("execution"))
        self.assertLess(groups.index("execution"), groups.index("monitoring"))
        modules = [item[1] for item in run_pipeline.PIPELINE_STAGES]
        self.assertLess(modules.index("risk_management"), modules.index("process_trades"))
        self.assertIn("ftmo_rules", modules)
        self.assertIn("mt5_health", modules)

    def test_stage_modules_import_without_a_project_root(self):
        import importlib
        import run_pipeline

        for _group, name, _fn in run_pipeline.PIPELINE_STAGES:
            module = importlib.import_module(name)
            self.assertTrue(callable(getattr(module, "run")))


class PaperRunTests(unittest.TestCase):
    def _project(self, rules):
        root = Path(tempfile.mkdtemp(prefix="fxjefe-paper-"))
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
        if rules is not None:
            (root / "ftmo_config.json").write_text(json.dumps(rules), encoding="utf-8")
        return root

    def test_missing_ftmo_file_stops_pipeline(self):
        import run_pipeline
        from mt5_client import paper_terminal

        paper_terminal().order_send_calls = 0
        root = self._project(None)
        code = run_pipeline.run(project_dir=str(root), dry_run=True, retry=1)
        self.assertNotEqual(code, 0)
        self.assertEqual(paper_terminal().order_send_calls, 0)
        self.assertFalse((root / "data" / "FXJEFE_trades.csv").exists())
        shutil.rmtree(root)

    def test_paper_run_does_not_send_orders(self):
        import run_pipeline
        from mt5_client import paper_terminal

        paper_terminal().order_send_calls = 0
        root = self._project(
            {
                "max_daily_loss_pct": 5,
                "max_overall_loss_pct": 10,
                "max_risk_per_trade_pct": 1,
                "max_lot": 1.0,
                "max_positions": 5,
                "max_daily_trades": 10,
            }
        )
        code = run_pipeline.run(project_dir=str(root), dry_run=True, retry=1)
        self.assertEqual(code, 0, "paper pipeline failed; see %s" % (root / "Logs" / "pipeline.log"))
        self.assertEqual(paper_terminal().order_send_calls, 0)
        self.assertTrue((root / "state" / "ftmo_gate.json").is_file())
        gate = json.loads((root / "state" / "ftmo_gate.json").read_text(encoding="utf-8"))
        self.assertTrue(gate["passed"])
        self.assertEqual(gate["orders_sent"], 0)
        log_text = (root / "Logs" / "pipeline.log").read_text(encoding="utf-8", errors="replace")
        self.assertIn(str(root), log_text)
        shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
