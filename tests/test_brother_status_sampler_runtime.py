"""Tests for observation-only Brother status sampling during print jobs."""

from __future__ import annotations

import threading
import time
import unittest

from brother_status_runtime import BrotherStatus, decode_brother_status
from brother_status_sampler_runtime import BrotherStatusSampler


READY_STATUS = bytes.fromhex(
    "80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 "
    "00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00"
)

ACTIVE_STATUS = bytearray(READY_STATUS)
ACTIVE_STATUS[19] = 0x01
ACTIVE_STATUS = bytes(ACTIVE_STATUS)

END_OF_MEDIA_STATUS = bytearray(ACTIVE_STATUS)
END_OF_MEDIA_STATUS[8] = 0x02
END_OF_MEDIA_STATUS[18] = 0x02
END_OF_MEDIA_STATUS = bytes(END_OF_MEDIA_STATUS)

WRONG_WIDTH_STATUS = bytearray(ACTIVE_STATUS)
WRONG_WIDTH_STATUS[10] = 36
WRONG_WIDTH_STATUS = bytes(WRONG_WIDTH_STATUS)


def changed_status() -> BrotherStatus:
    """Return an unknown notification transition without interpreting it."""
    raw = bytearray(READY_STATUS)
    raw[22] = 0x01
    return decode_brother_status(bytes(raw))


class SequencedStatus:
    """Return deterministic statuses or exceptions to the sampler thread."""

    def __init__(self, values: list[BrotherStatus | Exception]) -> None:
        self.values = values
        self.index = 0

    def __call__(self) -> BrotherStatus:
        index = min(self.index, len(self.values) - 1)
        self.index += 1
        value = self.values[index]
        if isinstance(value, Exception):
            raise value
        return value


class MutableStatus:
    """Return a status that a recovery test can change over time."""

    def __init__(self, status: BrotherStatus) -> None:
        self.status = status

    def __call__(self) -> BrotherStatus:
        return self.status


class BrotherStatusSamplerTests(unittest.TestCase):
    def test_logs_initial_change_heartbeat_and_final_summary(self) -> None:
        ready = decode_brother_status(READY_STATUS)
        sequence = SequencedStatus(
            [ready, ready, changed_status(), changed_status()]
        )
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="Controller family=QR_24MM_HORIZONTAL labels=2",
            read_status=sequence,
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.005,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        time.sleep(0.02)
        sampler.stop()

        self.assertTrue(any("event=INITIAL" in item for item in messages))
        self.assertTrue(any("event=CHANGED" in item for item in messages))
        self.assertTrue(any("event=HEARTBEAT" in item for item in messages))
        self.assertTrue(any("notification=0x01" in item for item in messages))
        self.assertTrue(any("raw=80 20 42 30" in item for item in messages))
        self.assertTrue(any("BROTHER_STATUS_SAMPLER_STOP" in item for item in messages))

    def test_rejects_print_start_when_initial_status_sample_fails(self) -> None:
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="initial failure",
            read_status=lambda: (_ for _ in ()).throw(TimeoutError("SNMP")),
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.01,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "failed before print submission",
        ):
            sampler.start()

        self.assertTrue(
            any("BROTHER_STATUS_SAMPLE_ERROR" in item for item in messages)
        )

    def test_runtime_error_is_logged_and_sampling_recovers(self) -> None:
        ready = decode_brother_status(READY_STATUS)
        sequence = SequencedStatus(
            [ready, TimeoutError("temporary SNMP timeout"), ready]
        )
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="recovery",
            read_status=sequence,
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.05,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        time.sleep(0.02)
        sampler.stop()

        self.assertTrue(
            any("BROTHER_STATUS_SAMPLE_ERROR" in item for item in messages)
        )
        self.assertTrue(any("event=RECOVERED" in item for item in messages))

    def test_waits_past_spooler_for_stable_physical_idle(self) -> None:
        ready = decode_brother_status(READY_STATUS)
        active = decode_brother_status(ACTIVE_STATUS)
        sequence = SequencedStatus([ready, active, active, ready, ready])
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="physical idle",
            read_status=sequence,
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.05,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        observation = sampler.wait_for_physical_completion(
            timeout_seconds=0.1,
            idle_stable_seconds=0.002,
        )
        sampler.stop()

        self.assertEqual(observation.outcome, "READY_IDLE")
        self.assertTrue(
            any(
                "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=READY_IDLE" in item
                for item in messages
            )
        )

    def test_captures_end_of_media_after_spooler_clears(self) -> None:
        ready = decode_brother_status(READY_STATUS)
        active = decode_brother_status(ACTIVE_STATUS)
        end_of_media = decode_brother_status(END_OF_MEDIA_STATUS)
        sequence = SequencedStatus([ready, active, end_of_media])
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="natural runout",
            read_status=sequence,
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.05,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        observation = sampler.wait_for_physical_completion(
            timeout_seconds=0.1,
            idle_stable_seconds=0.002,
        )
        sampler.stop()

        self.assertEqual(observation.outcome, "END_OF_MEDIA")
        self.assertEqual(observation.status.error_info_1, 0x02)
        self.assertTrue(
            any(
                "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=END_OF_MEDIA" in item
                for item in messages
            )
        )

    def test_accepts_end_of_media_sample_captured_before_completion_wait(self) -> None:
        end_of_media = decode_brother_status(END_OF_MEDIA_STATUS)
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="already exhausted",
            read_status=lambda: end_of_media,
            log_message=messages.append,
            poll_interval_seconds=0.05,
            heartbeat_seconds=1.0,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        observation = sampler.wait_for_physical_completion(
            timeout_seconds=0.01,
            idle_stable_seconds=0.002,
        )
        sampler.stop()

        self.assertEqual(observation.outcome, "END_OF_MEDIA")

    def test_pauses_physical_timeout_until_correct_media_is_ready(self) -> None:
        ready = decode_brother_status(READY_STATUS)
        active = decode_brother_status(ACTIVE_STATUS)
        end_of_media = decode_brother_status(END_OF_MEDIA_STATUS)
        wrong_width = decode_brother_status(WRONG_WIDTH_STATUS)
        source = MutableStatus(ready)
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="retained job recovery",
            read_status=source,
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.05,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        source.status = end_of_media
        time.sleep(0.005)

        def replace_media() -> None:
            time.sleep(0.03)
            source.status = wrong_width
            time.sleep(0.03)
            source.status = active
            time.sleep(0.005)
            source.status = ready

        replacement = threading.Thread(target=replace_media)
        replacement.start()
        try:
            observation = sampler.wait_for_physical_completion(
                timeout_seconds=0.02,
                idle_stable_seconds=0.003,
                recoverable_reason=lambda status: (
                    "Recoverable media wait"
                    if "End of media" in status.errors
                    or status.media_width_mm != 24
                    else None
                ),
            )
        finally:
            replacement.join()
            sampler.stop()

        self.assertEqual(observation.outcome, "READY_IDLE")
        self.assertTrue(
            any("PHYSICAL_WAIT_PAUSED" in item for item in messages)
        )
        self.assertTrue(
            any("PHYSICAL_WAIT_RESUMED" in item for item in messages)
        )

    def test_physical_completion_timeout_preserves_last_raw_status(self) -> None:
        ready = decode_brother_status(READY_STATUS)
        active = decode_brother_status(ACTIVE_STATUS)
        sequence = SequencedStatus([ready, active])
        messages: list[str] = []
        sampler = BrotherStatusSampler(
            context="stuck active",
            read_status=sequence,
            log_message=messages.append,
            poll_interval_seconds=0.001,
            heartbeat_seconds=0.05,
            startup_timeout_seconds=0.1,
            stop_timeout_seconds=0.1,
        )

        sampler.start()
        with self.assertRaisesRegex(
            RuntimeError,
            "did not reach physical idle or a reported error",
        ):
            sampler.wait_for_physical_completion(
                timeout_seconds=0.01,
                idle_stable_seconds=0.002,
            )
        sampler.stop()


if __name__ == "__main__":
    unittest.main()
