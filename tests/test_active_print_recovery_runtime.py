"""Tests for recoverable active-print media state and notice handling."""

from __future__ import annotations

import unittest

from active_print_recovery_runtime import (
    ActivePrintMediaRecovery,
    recoverable_media_reason,
)
from brother_status_runtime import decode_brother_status


READY_36 = bytes.fromhex(
    "80 20 42 30 70 30 04 00 00 00 24 01 00 00 00 00 "
    "00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00"
)


def changed_status(**changes: int):
    """Return one decoded 36 mm status with byte-index changes."""
    raw = bytearray(READY_36)
    for index, value in changes.items():
        raw[int(index)] = value
    return decode_brother_status(bytes(raw))


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class ActivePrintRecoveryTests(unittest.TestCase):
    def test_describes_end_of_media_with_required_width(self) -> None:
        status = changed_status(**{"8": 0x02, "18": 0x02, "19": 0x01})

        reason = recoverable_media_reason(
            status,
            required_width_mm=36,
        )

        self.assertIsNotNone(reason)
        self.assertIn("end of media", reason or "")
        self.assertIn("Required: 36 mm laminated tape", reason or "")
        self.assertIn("retained Brother job", reason or "")

    def test_wrong_replacement_width_reports_required_and_detected(self) -> None:
        status = changed_status(**{"10": 24})

        reason = recoverable_media_reason(
            status,
            required_width_mm=36,
        )

        self.assertIsNotNone(reason)
        self.assertIn("Required: 36 mm", reason or "")
        self.assertIn("Detected: 24 mm", reason or "")

    def test_notice_is_deduplicated_and_retried_after_failed_delivery(self) -> None:
        clock = FakeClock()
        messages: list[str] = []
        notices: list[str] = []
        delivery_results = iter([False, True])
        recovery = ActivePrintMediaRecovery(
            workload_name="Container labels (36 mm, HORIZONTAL)",
            required_width_mm=36,
            log_message=messages.append,
            log_event=messages.append,
            notify_operator=lambda _workload, reason: (
                notices.append(reason) or next(delivery_results)
            ),
            notice_heartbeat_seconds=60,
            monotonic=clock,
        )
        end_of_media = changed_status(
            **{"8": 0x02, "18": 0x02, "19": 0x01}
        )

        self.assertIsNotNone(recovery.observe_status(end_of_media))
        self.assertIsNotNone(recovery.observe_status(end_of_media))
        self.assertEqual(len(notices), 1)

        clock.value += 61
        self.assertIsNotNone(recovery.observe_status(end_of_media))
        self.assertEqual(len(notices), 2)

        self.assertIsNone(
            recovery.observe_status(decode_brother_status(READY_36))
        )
        self.assertTrue(
            any("ACTIVE_PRINT_MEDIA_RECOVERED" in item for item in messages)
        )

    def test_successful_notice_does_not_repeat_or_flood_heartbeat(self) -> None:
        clock = FakeClock()
        messages: list[str] = []
        notices: list[str] = []
        recovery = ActivePrintMediaRecovery(
            workload_name="Container labels (36 mm, HORIZONTAL)",
            required_width_mm=36,
            log_message=messages.append,
            log_event=lambda _message: None,
            notify_operator=lambda _workload, reason: (
                notices.append(reason) or True
            ),
            notice_heartbeat_seconds=60,
            monotonic=clock,
        )
        end_of_media = changed_status(
            **{"8": 0x02, "18": 0x02, "19": 0x01}
        )

        recovery.observe_status(end_of_media)
        clock.value += 61
        recovery.observe_status(end_of_media)
        recovery.observe_status(end_of_media)

        self.assertEqual(len(notices), 1)
        self.assertEqual(
            sum("event=HEARTBEAT" in item for item in messages),
            1,
        )


if __name__ == "__main__":
    unittest.main()
