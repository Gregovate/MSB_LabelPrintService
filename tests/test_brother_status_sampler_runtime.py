"""Tests for observation-only Brother status sampling during print jobs."""

from __future__ import annotations

import time
import unittest

from brother_status_runtime import BrotherStatus, decode_brother_status
from brother_status_sampler_runtime import BrotherStatusSampler


READY_STATUS = bytes.fromhex(
    "80 20 42 30 70 30 04 00 00 00 18 01 00 00 00 00 "
    "00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00"
)


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
        sampler.stop(post_observation_seconds=0.005)

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


if __name__ == "__main__":
    unittest.main()
