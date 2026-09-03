"""Tests for retaining short-lived Windows spooler jobs."""

from __future__ import annotations

import time
import unittest

from spooler_observer_runtime import SpoolerJobObserver


class SequencedQueue:
    """Return deterministic queue snapshots to the observer thread."""

    def __init__(self, snapshots: list[list[dict[str, object]]]) -> None:
        self.snapshots = snapshots
        self.index = 0

    def __call__(self, _printer_name: str) -> list[dict[str, object]]:
        index = min(self.index, len(self.snapshots) - 1)
        self.index += 1
        return self.snapshots[index]


class SpoolerJobObserverTests(unittest.TestCase):
    def test_retains_job_that_clears_before_completion_wait(self) -> None:
        queue = SequencedQueue(
            [
                [],
                [{"JobId": 41, "pDocument": "QR_label_1_line_horz_24mm"}],
                [],
            ]
        )
        messages: list[str] = []
        observer = SpoolerJobObserver(
            printer_name="Brother PT-P950NW",
            known_job_ids=set(),
            expected_document="QR_label_1_line_horz_24mm",
            read_jobs=queue,
            log_message=messages.append,
            poll_interval_seconds=0.001,
        )

        observer.start()
        try:
            time.sleep(0.02)
            seen = observer.wait_for_completion(
                appear_timeout_seconds=0.1,
                clear_timeout_seconds=0.1,
            )
        finally:
            observer.stop()

        self.assertEqual(seen, {41})
        self.assertTrue(any("observed" in message for message in messages))
        self.assertTrue(any("cleared successfully" in message for message in messages))

    def test_rejects_submission_when_no_new_job_is_observed(self) -> None:
        observer = SpoolerJobObserver(
            printer_name="Brother PT-P950NW",
            known_job_ids=set(),
            expected_document="controller",
            read_jobs=lambda _printer_name: [],
            log_message=lambda _message: None,
            poll_interval_seconds=0.001,
        )

        observer.start()
        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "No new spooler job was observed",
            ):
                observer.wait_for_completion(
                    appear_timeout_seconds=0.02,
                    clear_timeout_seconds=0.02,
                )
        finally:
            observer.stop()

    def test_rejects_observed_job_that_never_clears(self) -> None:
        job = [{"JobId": 99, "pDocument": "controller"}]
        observer = SpoolerJobObserver(
            printer_name="Brother PT-P950NW",
            known_job_ids=set(),
            expected_document="controller",
            read_jobs=lambda _printer_name: job,
            log_message=lambda _message: None,
            poll_interval_seconds=0.001,
        )

        observer.start()
        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "did not clear",
            ):
                observer.wait_for_completion(
                    appear_timeout_seconds=0.02,
                    clear_timeout_seconds=0.02,
                )
        finally:
            observer.stop()

    def test_ignores_jobs_present_before_submission(self) -> None:
        baseline_job = [{"JobId": 7, "pDocument": "unrelated"}]
        observer = SpoolerJobObserver(
            printer_name="Brother PT-P950NW",
            known_job_ids={7},
            expected_document="controller",
            read_jobs=lambda _printer_name: baseline_job,
            log_message=lambda _message: None,
            poll_interval_seconds=0.001,
        )

        observer.start()
        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "No new spooler job was observed",
            ):
                observer.wait_for_completion(
                    appear_timeout_seconds=0.02,
                    clear_timeout_seconds=0.02,
                )
        finally:
            observer.stop()


if __name__ == "__main__":
    unittest.main()
