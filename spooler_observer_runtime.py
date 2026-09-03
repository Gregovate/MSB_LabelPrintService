"""Observe short-lived Windows print jobs across a b-PAC submission.

The Label Print Service starts this observer before ``StartPrint``.  The
observer retains newly seen job IDs even when Windows removes the jobs before
the main print path reaches its completion check.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from typing import Any


PrintJob = Mapping[str, Any]
ReadJobs = Callable[[str], list[PrintJob]]
LogMessage = Callable[[str], None]


class SpoolerJobObserver:
    """Continuously sample one printer queue and retain new job IDs."""

    def __init__(
        self,
        *,
        printer_name: str,
        known_job_ids: set[int],
        expected_document: str,
        read_jobs: ReadJobs,
        log_message: LogMessage,
        poll_interval_seconds: float = 0.01,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")

        self.printer_name = printer_name
        self.known_job_ids = set(known_job_ids)
        self.expected_document = expected_document
        self.read_jobs = read_jobs
        self.log_message = log_message
        self.poll_interval_seconds = poll_interval_seconds

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._sample_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_job_ids: set[int] = set()
        self._seen_job_ids: set[int] = set()
        self._first_seen_documents: dict[int, str] = {}
        self._error: Exception | None = None

    def start(self) -> None:
        """Start sampling before b-PAC is allowed to submit the job."""
        if self._thread is not None:
            raise RuntimeError("Spooler observer has already been started")

        self.log_message(
            "Spooler observation started before b-PAC submission: "
            f"printer='{self.printer_name}', "
            f"expected_document='{self.expected_document}', "
            f"known_job_ids={sorted(self.known_job_ids)}"
        )
        self._thread = threading.Thread(
            target=self._observe,
            name="msb-spooler-observer",
            daemon=True,
        )
        self._thread.start()

        # Do not let b-PAC submit until the observer thread has completed its
        # first queue sample.  This removes the startup scheduling race.
        if not self._sample_event.wait(timeout=2.0):
            self.stop()
            raise RuntimeError(
                "Spooler observer did not complete its initial queue sample"
            )

        with self._lock:
            error = self._error
        self._sample_event.clear()

        if error is not None:
            self.stop()
            raise RuntimeError(
                f"Spooler observation failed during startup: {error}"
            ) from error

    def _observe(self) -> None:
        try:
            while not self._stop_event.is_set():
                jobs = self.read_jobs(self.printer_name)
                latest_ids: set[int] = set()
                newly_seen: dict[int, str] = {}

                for job in jobs:
                    job_id = int(job.get("JobId"))
                    latest_ids.add(job_id)

                    if job_id not in self.known_job_ids:
                        document = str(job.get("pDocument") or "")
                        newly_seen[job_id] = document

                with self._lock:
                    self._latest_job_ids = latest_ids
                    self._seen_job_ids.update(newly_seen)
                    for job_id, document in newly_seen.items():
                        self._first_seen_documents.setdefault(job_id, document)

                self._sample_event.set()
                self._stop_event.wait(self.poll_interval_seconds)
        except Exception as exc:
            with self._lock:
                self._error = exc
            self._sample_event.set()

    def wait_for_completion(
        self,
        *,
        appear_timeout_seconds: float = 15,
        clear_timeout_seconds: float = 90,
    ) -> set[int]:
        """Require at least one observed new job and wait for it to clear."""
        if self._thread is None:
            raise RuntimeError("Spooler observer was not started")

        appear_deadline = time.monotonic() + appear_timeout_seconds
        seen_job_ids: set[int] = set()

        while time.monotonic() < appear_deadline:
            with self._lock:
                error = self._error
                seen_job_ids = set(self._seen_job_ids)
                documents = dict(self._first_seen_documents)

            if error is not None:
                raise RuntimeError(
                    f"Spooler observation failed: {error}"
                ) from error
            if seen_job_ids:
                self.log_message(
                    "Spooler job(s) observed: "
                    f"ids={sorted(seen_job_ids)} documents={documents}"
                )
                break

            remaining = appear_deadline - time.monotonic()
            self._sample_event.wait(max(0, min(remaining, 0.1)))
            self._sample_event.clear()

        if not seen_job_ids:
            raise RuntimeError(
                "No new spooler job was observed within "
                f"{appear_timeout_seconds:g} seconds."
            )

        clear_deadline = time.monotonic() + clear_timeout_seconds
        while time.monotonic() < clear_deadline:
            with self._lock:
                error = self._error
                latest_job_ids = set(self._latest_job_ids)

            if error is not None:
                raise RuntimeError(
                    f"Spooler observation failed: {error}"
                ) from error
            if seen_job_ids.isdisjoint(latest_job_ids):
                self.log_message(
                    "Observed spooler job(s) cleared successfully: "
                    f"{sorted(seen_job_ids)}"
                )
                return seen_job_ids

            remaining = clear_deadline - time.monotonic()
            self._sample_event.wait(max(0, min(remaining, 0.1)))
            self._sample_event.clear()

        raise RuntimeError(
            "Observed spooler job(s) did not clear within "
            f"{clear_timeout_seconds:g} seconds: {sorted(seen_job_ids)}"
        )

    def stop(self) -> None:
        """Stop the sampling thread, including after a print-path exception."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(1.0, self.poll_interval_seconds * 4))
