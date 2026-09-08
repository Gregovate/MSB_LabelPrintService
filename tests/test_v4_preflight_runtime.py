"""Tests for non-blocking automatic printer preflight recovery."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from brother_status_runtime import decode_brother_status
from v4_preflight_runtime import (
    AutomaticPreflightRecovery,
    send_preflight_operator_notice,
    snmp_family_preflight,
)


READY_STATUS = bytes.fromhex(
    "80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 "
    "00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00"
)


class FakeClock:
    """Controllable monotonic clock for retry-state tests."""

    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class FakeWindowsFunction:
    """Callable stand-in that accepts ctypes signature attributes."""

    def __init__(self, result: int) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *args: object) -> int:
        self.calls.append(args)
        return self.result


class AutomaticPreflightRecoveryTests(unittest.TestCase):
    def test_waits_without_blocking_and_recovers_on_later_poll(self) -> None:
        clock = FakeClock()
        notices: list[tuple[str, str]] = []
        results = iter(
            [
                (False, "Required: 24 mm. Detected: 36 mm."),
                (False, "Required: 24 mm. Detected: 36 mm."),
                (True, "24 mm ready"),
            ]
        )
        recovery = AutomaticPreflightRecovery(
            notice_heartbeat_seconds=60.0,
            monotonic=clock,
            notify_operator=lambda workload, reason: (
                notices.append((workload, reason)) or True
            ),
        )

        self.assertFalse(
            recovery.check_once(
                workload_name="Controller labels (24 mm)",
                check_once=lambda: next(results),
            )
        )
        clock.value = 15.0
        self.assertFalse(
            recovery.check_once(
                workload_name="Controller labels (24 mm)",
                check_once=lambda: next(results),
            )
        )
        clock.value = 30.0
        with self.assertLogs(level="INFO") as captured:
            self.assertTrue(
                recovery.check_once(
                    workload_name="Controller labels (24 mm)",
                    check_once=lambda: next(results),
                )
            )

        self.assertEqual(len(notices), 1)
        self.assertIn("Required: 24 mm", notices[0][1])
        self.assertTrue(
            any("PREFLIGHT_RECOVERED" in item for item in captured.output)
        )

    def test_changed_wrong_media_reason_sends_new_notice(self) -> None:
        clock = FakeClock()
        notices: list[str] = []
        recovery = AutomaticPreflightRecovery(
            notice_heartbeat_seconds=60.0,
            monotonic=clock,
            notify_operator=lambda _workload, reason: (
                notices.append(reason) or True
            ),
        )

        self.assertFalse(
            recovery.check_once(
                workload_name="Controller labels (24 mm)",
                check_once=lambda: (False, "No cassette; required 24 mm"),
            )
        )
        clock.value = 15.0
        self.assertFalse(
            recovery.check_once(
                workload_name="Controller labels (24 mm)",
                check_once=lambda: (
                    False,
                    "Wrong tape; required 24 mm; detected 36 mm",
                ),
            )
        )

        self.assertEqual(len(notices), 2)
        self.assertIn("detected 36 mm", notices[1])

    def test_failed_notice_delivery_is_retried_at_heartbeat(self) -> None:
        clock = FakeClock()
        notice_attempts: list[float] = []
        recovery = AutomaticPreflightRecovery(
            notice_heartbeat_seconds=60.0,
            monotonic=clock,
            notify_operator=lambda _workload, _reason: (
                notice_attempts.append(clock.value) or False
            ),
        )

        for current_time in (0.0, 15.0, 60.0):
            clock.value = current_time
            self.assertFalse(
                recovery.check_once(
                    workload_name="Controller labels (24 mm)",
                    check_once=lambda: (False, "Required 24 mm"),
                )
            )

        self.assertEqual(notice_attempts, [0.0, 60.0])

    def test_notice_targets_active_console_without_blocking_worker(self) -> None:
        get_session = FakeWindowsFunction(7)
        get_error = FakeWindowsFunction(0)
        send_message = FakeWindowsFunction(1)
        fake_windll = SimpleNamespace(
            kernel32=SimpleNamespace(
                WTSGetActiveConsoleSessionId=get_session,
                GetLastError=get_error,
            ),
            wtsapi32=SimpleNamespace(WTSSendMessageW=send_message),
        )

        with (
            patch("v4_preflight_runtime.os.name", "nt"),
            patch(
                "v4_preflight_runtime.ctypes.windll",
                fake_windll,
                create=True,
            ),
        ):
            sent = send_preflight_operator_notice(
                "Controller labels (24 mm)",
                "Wrong tape width loaded. Required: 24 mm laminated tape. "
                "Detected: 36 mm Laminated tape.",
            )

        self.assertTrue(sent)
        self.assertEqual(len(send_message.calls), 1)
        call = send_message.calls[0]
        self.assertEqual(call[1], 7)
        self.assertIn("Required: 24 mm", call[4])
        self.assertIn("Detected: 36 mm", call[4])
        self.assertIn("resume", call[4])
        self.assertFalse(call[9])


class SnmpFamilyPreflightTests(unittest.TestCase):
    def test_rejects_active_brother_phase_before_new_batch(self) -> None:
        raw = bytearray(READY_STATUS)
        raw[19] = 0x01
        status = decode_brother_status(bytes(raw))

        with patch(
            "v4_preflight_runtime.query_brother_snmp_status",
            return_value=status,
        ):
            ok, reason = snmp_family_preflight(
                host="192.168.5.12",
                family_code="QR_24MM_HORIZONTAL",
                expected_width_mm=24,
                expected_media_type="LAMINATED_TAPE",
                oid="test",
                community="public",
                port=161,
                timeout=0.1,
            )

        self.assertFalse(ok)
        self.assertIn("phase=0x01", reason)
        self.assertIn("retry automatically", reason)

    def test_wrong_width_names_required_and_detected_media(self) -> None:
        raw = bytearray(READY_STATUS)
        raw[10] = 36
        status = decode_brother_status(bytes(raw))

        with patch(
            "v4_preflight_runtime.query_brother_snmp_status",
            return_value=status,
        ):
            ok, reason = snmp_family_preflight(
                host="192.168.5.12",
                family_code="QR_24MM_HORIZONTAL",
                expected_width_mm=24,
                expected_media_type="LAMINATED_TAPE",
                oid="test",
                community="public",
                port=161,
                timeout=0.1,
            )

        self.assertFalse(ok)
        self.assertIn("Required: 24 mm laminated tape", reason)
        self.assertIn("Detected: 36 mm Laminated tape", reason)


if __name__ == "__main__":
    unittest.main()
