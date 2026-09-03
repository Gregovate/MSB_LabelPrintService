"""Continuously capture Brother status while a physical print job is active.

This observer is evidence-only.  It records raw status transitions and periodic
heartbeats, but it never interprets an unknown byte as a stop condition and it
never controls database or print state.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from brother_status_runtime import BrotherStatus


ReadStatus = Callable[[], BrotherStatus]
LogMessage = Callable[[str], None]


class BrotherStatusSampler:
    """Sample Brother status throughout one b-PAC/spooler print window."""

    def __init__(
        self,
        *,
        context: str,
        read_status: ReadStatus,
        log_message: LogMessage,
        poll_interval_seconds: float = 0.25,
        heartbeat_seconds: float = 5.0,
        startup_timeout_seconds: float = 5.0,
        stop_timeout_seconds: float = 5.0,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be greater than zero")
        if startup_timeout_seconds <= 0:
            raise ValueError("startup_timeout_seconds must be greater than zero")
        if stop_timeout_seconds <= 0:
            raise ValueError("stop_timeout_seconds must be greater than zero")

        self.context = context
        self.read_status = read_status
        self.log_message = log_message
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.startup_timeout_seconds = startup_timeout_seconds
        self.stop_timeout_seconds = stop_timeout_seconds

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._startup_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._startup_error: Exception | None = None
        self._last_raw_hex: str | None = None
        self._last_logged_at: float | None = None
        self._last_error_text: str | None = None
        self._sample_count = 0
        self._change_count = 0
        self._error_count = 0

    def start(self) -> None:
        """Start sampling and require one successful sample before printing."""
        if self._thread is not None:
            raise RuntimeError("Brother status sampler has already been started")

        self.log_message(
            "BROTHER_STATUS_SAMPLER_START "
            f"context='{self.context}' "
            f"interval_seconds={self.poll_interval_seconds:g} "
            f"heartbeat_seconds={self.heartbeat_seconds:g}"
        )
        self._thread = threading.Thread(
            target=self._observe,
            name="msb-brother-status-sampler",
            daemon=True,
        )
        self._thread.start()

        if not self._startup_event.wait(self.startup_timeout_seconds):
            self.stop()
            raise RuntimeError(
                "Brother status sampler did not complete its initial sample"
            )

        with self._lock:
            startup_error = self._startup_error

        if startup_error is not None:
            self.stop()
            raise RuntimeError(
                "Brother status sampler failed before print submission: "
                f"{startup_error}"
            ) from startup_error

    def _observe(self) -> None:
        first_attempt = True

        while not self._stop_event.is_set():
            try:
                status = self.read_status()
            except Exception as exc:
                self._record_error(exc, first_attempt=first_attempt)
            else:
                self._record_status(status)
            finally:
                if first_attempt:
                    self._startup_event.set()
                    first_attempt = False

            self._stop_event.wait(self.poll_interval_seconds)

    def _record_status(self, status: BrotherStatus) -> None:
        now = time.monotonic()
        message: str | None = None

        with self._lock:
            self._sample_count += 1
            sample_number = self._sample_count

            if self._last_raw_hex is None:
                event = "INITIAL"
            elif self._last_error_text is not None:
                event = "RECOVERED"
            elif status.raw_hex != self._last_raw_hex:
                event = "CHANGED"
                self._change_count += 1
            elif (
                self._last_logged_at is None
                or now - self._last_logged_at >= self.heartbeat_seconds
            ):
                event = "HEARTBEAT"
            else:
                event = ""

            self._last_raw_hex = status.raw_hex
            self._last_error_text = None

            if event:
                self._last_logged_at = now
                errors = ",".join(status.errors) if status.errors else "<none>"
                message = (
                    f"BROTHER_STATUS_SAMPLE event={event} "
                    f"context='{self.context}' sample={sample_number} "
                    f"width={status.media_width_mm} "
                    f"media='{status.media_type}' "
                    f"error1=0x{status.error_info_1:02X} "
                    f"error2=0x{status.error_info_2:02X} "
                    f"status=0x{status.status_type_code:02X} "
                    f"phase=0x{status.phase_type_code:02X} "
                    f"notification=0x{status.notification_code:02X} "
                    f"errors='{errors}' raw={status.raw_hex}"
                )

        if message is not None:
            self.log_message(message)

    def _record_error(self, exc: Exception, *, first_attempt: bool) -> None:
        now = time.monotonic()
        error_text = f"{type(exc).__name__}: {exc}"
        message: str | None = None

        with self._lock:
            self._error_count += 1
            if first_attempt:
                self._startup_error = exc

            should_log = (
                error_text != self._last_error_text
                or self._last_logged_at is None
                or now - self._last_logged_at >= self.heartbeat_seconds
            )
            self._last_error_text = error_text

            if should_log:
                self._last_logged_at = now
                message = (
                    "BROTHER_STATUS_SAMPLE_ERROR "
                    f"context='{self.context}' "
                    f"error_count={self._error_count} error='{error_text}'"
                )

        if message is not None:
            self.log_message(message)

    def stop(self, *, post_observation_seconds: float = 0.0) -> None:
        """Stop sampling, optionally observing briefly after spooler clearing."""
        if post_observation_seconds < 0:
            raise ValueError("post_observation_seconds cannot be negative")

        thread = self._thread
        if thread is None:
            return

        if post_observation_seconds:
            self.log_message(
                "BROTHER_STATUS_SAMPLER_POST_SPOOLER "
                f"context='{self.context}' "
                f"seconds={post_observation_seconds:g}"
            )
            self._stop_event.wait(post_observation_seconds)

        self._stop_event.set()
        thread.join(timeout=self.stop_timeout_seconds)

        with self._lock:
            sample_count = self._sample_count
            change_count = self._change_count
            error_count = self._error_count
            last_raw_hex = self._last_raw_hex or "<none>"

        if thread.is_alive():
            self.log_message(
                "WARNING BROTHER_STATUS_SAMPLER_THREAD_STILL_RUNNING "
                f"context='{self.context}'"
            )

        self.log_message(
            "BROTHER_STATUS_SAMPLER_STOP "
            f"context='{self.context}' samples={sample_count} "
            f"changes={change_count} errors={error_count} "
            f"last_raw={last_raw_hex}"
        )
        if not thread.is_alive():
            self._thread = None
