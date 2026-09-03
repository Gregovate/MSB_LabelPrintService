"""Static contract tests for the gated V4 Controller printing path.

The production module imports Windows-only b-PAC/spooler dependencies and reads
the local secret configuration at import time. These tests deliberately inspect
the tracked source and SQL without importing or executing printer code.
"""

from __future__ import annotations

import ast
import configparser
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE_SOURCE = ROOT / "label_poll_service_v4.py"
CONFIG_EXAMPLE = ROOT / "config.v4.example.ini"
SQL_DIR = ROOT / "sql"


class ControllerV4ContractTests(unittest.TestCase):
    def test_service_source_parses_and_defines_controller_pipeline(self) -> None:
        tree = ast.parse(SERVICE_SOURCE.read_text(encoding="utf-8"))
        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertTrue({
            "pending_controller_workload_signature",
            "pending_controller_preflight_plan",
            "create_controller_batch",
            "print_controller_batch",
            "process_controller",
            "mark_controller_batch_failed",
            "get_failed_controller_batch_id",
        }.issubset(function_names))

    def test_example_config_keeps_controller_polling_off_by_default(self) -> None:
        config = configparser.ConfigParser()
        config.read(CONFIG_EXAMPLE, encoding="utf-8")

        self.assertFalse(
            config.getboolean("features", "controller_polling_enabled")
        )
        self.assertEqual(
            config["label_family.QR_24MM_HORIZONTAL"]["media_width_mm"],
            "24",
        )
        self.assertEqual(
            config["label_family.QR_24MM_HORIZONTAL"]["media_type"],
            "LAMINATED_TAPE",
        )
        self.assertEqual(
            config["label_family.QR_24MM_HORIZONTAL"]["template_1_line"],
            "QR_label_1_line_horz_24mm.lbx",
        )

    def test_snapshot_freezes_full_url_and_visible_controller_identity(self) -> None:
        sql = (SQL_DIR / "controller_snapshot_v4.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "https://db.sheboyganlights.org/scan/CTRL/",
            sql,
        )
        self.assertIn("'CTRL:' || c.controller_id", sql)
        self.assertIn("c.controller_id = ANY(%(controller_ids)s)", sql)
        self.assertIn("lt.label_template_code = 'QR_24MM_HORIZONTAL'", sql)

    def test_finalizer_clears_only_the_snapshotted_controller_ids(self) -> None:
        sql = (SQL_DIR / "controller_finalized.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn("UPDATE ref.controller AS c", sql)
        self.assertIn(
            "i.controller_label_batch_id = %(batch_id)s",
            sql,
        )
        self.assertIn("i.controller_id = c.controller_id", sql)
        self.assertNotIn(
            "UPDATE ref.controller\nSET print_label = false;",
            sql,
        )


if __name__ == "__main__":
    unittest.main()
