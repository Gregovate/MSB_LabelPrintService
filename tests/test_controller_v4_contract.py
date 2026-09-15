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
    def test_controller_candidate_has_distinct_service_version(self) -> None:
        tree = ast.parse(SERVICE_SOURCE.read_text(encoding="utf-8"))
        service_versions = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id == "SERVICE_VERSION"
                for target in node.targets
            ):
                service_versions.append(ast.literal_eval(node.value))

        self.assertEqual(service_versions, ["4.1.0-rc5"])

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

    def test_every_renderer_starts_spooler_observation_before_start_print(self) -> None:
        source = SERVICE_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        renderers = {
            "print_display_rows_with_template",
            "print_container_batch",
            "print_controller_batch",
        }

        functions = {
            node.name: ast.get_source_segment(source, node) or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name in renderers
        }

        self.assertEqual(set(functions), renderers)
        for name, function_source in functions.items():
            with self.subTest(renderer=name):
                observer_start = function_source.index("start_print_observers(")
                bpac_start = function_source.index(
                    'doc.StartPrint("", PRINT_FLAGS)'
                )
                completion_wait = function_source.index(
                    "spooler_observer.wait_for_completion("
                )
                physical_wait = function_source.index(
                    "wait_for_brother_physical_completion("
                )
                observer_stop = function_source.index("stop_print_observers(")

                self.assertLess(observer_start, bpac_start)
                self.assertLess(bpac_start, completion_wait)
                self.assertLess(completion_wait, physical_wait)
                self.assertLess(physical_wait, observer_stop)
                self.assertIn("status_sampler=status_sampler", function_source)

    def test_status_sampling_starts_before_spooler_observation(self) -> None:
        source = SERVICE_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper_source = next(
            ast.get_source_segment(source, node) or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "start_print_observers"
        )

        self.assertLess(
            helper_source.index("status_sampler.start()"),
            helper_source.index("spooler_observer.start()"),
        )

    def test_example_config_keeps_controller_polling_off_by_default(self) -> None:
        config = configparser.ConfigParser()
        config.read(CONFIG_EXAMPLE, encoding="utf-8")

        self.assertFalse(
            config.getboolean("features", "controller_polling_enabled")
        )
        self.assertTrue(
            config.getboolean("printing", "status_sampler_enabled")
        )
        self.assertEqual(
            config.getfloat("printing", "status_sample_interval_seconds"),
            0.25,
        )
        self.assertEqual(
            config.getfloat(
                "printing",
                "status_physical_completion_timeout_seconds",
            ),
            90.0,
        )
        self.assertEqual(
            config.getfloat(
                "printing",
                "status_physical_idle_stable_seconds",
            ),
            1.0,
        )
        self.assertNotIn(
            "status_post_spooler_seconds",
            config["printing"],
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

    def test_headless_worker_does_not_use_blocking_message_box(self) -> None:
        service_source = SERVICE_SOURCE.read_text(encoding="utf-8")
        preflight_source = (
            ROOT / "v4_preflight_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("run_operator_preflight_loop", service_source)
        self.assertNotIn("MessageBoxW", preflight_source)
        self.assertIn("WTSSendMessageW", preflight_source)
        self.assertIn("AutomaticPreflightRecovery", service_source)

    def test_active_end_of_media_sends_required_width_notice(self) -> None:
        source = SERVICE_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper_source = next(
            ast.get_source_segment(source, node) or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "wait_for_brother_physical_completion"
        )

        self.assertIn('observation.outcome == "END_OF_MEDIA"', helper_source)
        self.assertIn("Required: {required_width_mm} mm", helper_source)
        self.assertIn("send_preflight_operator_notice", helper_source)

    def test_all_renderers_pause_spooler_timeout_for_media_recovery(self) -> None:
        source = SERVICE_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        renderer_names = {
            "print_display_rows_with_template",
            "print_container_batch",
            "print_controller_batch",
        }

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in renderer_names:
                continue
            renderer_source = ast.get_source_segment(source, node) or ""
            self.assertIn(
                "pause_reason_provider=",
                renderer_source,
                node.name,
            )
            self.assertIn(
                "media_recovery=media_recovery",
                renderer_source,
                node.name,
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
