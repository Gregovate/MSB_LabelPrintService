from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from label_print_observability_runtime import LabelPrintObservability


class ObservabilityTests(unittest.TestCase):
    def test_disabled_adapter_does_not_connect(self) -> None:
        connect = MagicMock()
        runtime = LabelPrintObservability(
            enabled=False,
            connect_database=connect,
            service_version="test",
        )
        runtime.verify_contract()
        runtime.heartbeat("IDLE")
        runtime.observe_batch_log(
            Path("controller_batch_9_20261028_120000.log"),
            "StartPrint called with flags=0x1",
        )
        connect.assert_not_called()

    def test_batch_log_events_are_deduplicated(self) -> None:
        runtime = LabelPrintObservability(
            enabled=True,
            connect_database=MagicMock(),
            service_version="test",
        )
        runtime.checkpoint = MagicMock()
        path = Path("controller_batch_9_20261028_120000.log")
        runtime.observe_batch_log(path, "StartPrint called with flags=0x1")
        runtime.observe_batch_log(path, "StartPrint called with flags=0x1")
        self.assertEqual(runtime.checkpoint.call_count, 2)
        self.assertEqual(
            runtime.checkpoint.call_args.args[:3],
            ("CONTROLLER", 9, "SUBMISSION_STARTED"),
        )
        self.assertTrue(runtime.checkpoint.call_args.kwargs["once"])

    def test_ready_idle_maps_to_terminal_evidence(self) -> None:
        runtime = LabelPrintObservability(
            enabled=True,
            connect_database=MagicMock(),
            service_version="test",
        )
        runtime.checkpoint = MagicMock()
        runtime.observe_batch_log(
            Path("display_batch_12_20261028_120000.log"),
            "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=READY_IDLE raw=00",
        )
        runtime.checkpoint.assert_called_once()
        self.assertEqual(
            runtime.checkpoint.call_args.args[:3],
            ("DISPLAY", 12, "READY_IDLE"),
        )

    def test_non_batch_log_is_ignored(self) -> None:
        runtime = LabelPrintObservability(
            enabled=True,
            connect_database=MagicMock(),
            service_version="test",
        )
        runtime.checkpoint = MagicMock()
        runtime.observe_batch_log(Path("label_service.log"), "StartPrint called")
        runtime.checkpoint.assert_not_called()


if __name__ == "__main__":
    unittest.main()
