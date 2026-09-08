"""Capture Brother status and establish post-spooler physical completion.

Known ready/error fields control the physical-terminal wait. Unknown status
transitions remain evidence-only and never become guessed stop conditions.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from brother_status_runtime import BrotherStatus


ReadStatus = Callable[[], BrotherStatus]
LogMessage = Callable[[str], None]


@dataclass(frozen=True)
class PhysicalCompletionObservation:
    """Brother state that ended post-spooler physical observation."""

    outcome: str
    status: BrotherStatus


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
        self._last_status: BrotherStatus | None = None
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
            self._last_status = status

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

    def wait_for_physical_completion(
        self,
        *,
        timeout_seconds: float,
        idle_stable_seconds: float,
    ) -> PhysicalCompletionObservation:
        """Observe past spooler clearing until Brother is idle or errors."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if idle_stable_seconds < 0:
            raise ValueError("idle_stable_seconds cannot be negative")
        if self._thread is None:
            raise RuntimeError("Brother status sampler is not running")

        started_at = time.monotonic()
        deadline = started_at + timeout_seconds
        idle_since: float | None = None

        with self._lock:
            starting_sample_count = self._sample_count

        self.log_message(
            "BROTHER_STATUS_PHYSICAL_WAIT_START "
            f"context='{self.context}' timeout_seconds={timeout_seconds:g} "
            f"idle_stable_seconds={idle_stable_seconds:g}"
        )

        while True:
            now = time.monotonic()
            with self._lock:
                status = self._last_status
                sample_count = self._sample_count

            if status is not None:
                if "End of media" in status.errors:
                    self.log_message(
                        "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=END_OF_MEDIA "
                        f"context='{self.context}' sample={sample_count} "
                        f"raw={status.raw_hex}"
                    )
                    return PhysicalCompletionObservation(
                        outcome="END_OF_MEDIA",
                        status=status,
                    )

                if status.errors:
                    errors = ",".join(status.errors)
                    self.log_message(
                        "BROTHER_STATUS_PHYSICAL_TERMINAL outcome=ERROR "
                        f"context='{self.context}' sample={sample_count} "
                        f"errors='{errors}' raw={status.raw_hex}"
                    )
                    return PhysicalCompletionObservation(
                        outcome="ERROR",
                        status=status,
                    )

                # Require a fresh post-spooler sample before accepting ready
                # idle. Otherwise an initial packet captured before submission
                # could be mistaken for physical completion after a fast
                # Windows queue disappearance. Explicit errors are accepted
                # immediately because they cannot be confused with readiness.
                if (
                    sample_count > starting_sample_count
                    and status.phase_type_code == 0x00
                ):
                    if idle_since is None:
                        idle_since = now
                    elif now - idle_since >= idle_stable_seconds:
                        self.log_message(
                            "BROTHER_STATUS_PHYSICAL_TERMINAL "
                            "outcome=READY_IDLE "
                            f"context='{self.context}' sample={sample_count} "
                            f"idle_seconds={now - idle_since:.1f} "
                            f"raw={status.raw_hex}"
                        )
                        return PhysicalCompletionObservation(
                            outcome="READY_IDLE",
                            status=status,
                        )
                elif status.phase_type_code != 0x00:
                    idle_since = None

            remaining = deadline - now
            if remaining <= 0:
                with self._lock:
                    last_status = self._last_status
                last_raw = (
                    last_status.raw_hex
                    if last_status is not None
                    else "<none>"
                )
                raise RuntimeError(
                    "Brother printer did not reach physical idle or a "
                    f"reported error within {timeout_seconds:g} seconds; "
                    f"last_raw={last_raw}"
                )

            self._stop_event.wait(
                min(self.poll_interval_seconds, remaining)
            )

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

    def stop(self) -> None:
        """Stop sampling after the caller completes physical observation."""
        thread = self._thread
        if thread is None:
            return

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
