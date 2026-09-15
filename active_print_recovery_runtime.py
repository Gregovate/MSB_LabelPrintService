"""Coordinate recoverable Brother media states during an active print job."""

from __future__ import annotations

import time
from collections.abc import Callable

from brother_status_runtime import BrotherStatus


LogMessage = Callable[[str], None]
NotifyOperator = Callable[[str, str], bool]


def recoverable_media_reason(
    status: BrotherStatus,
    *,
    required_width_mm: int,
) -> str | None:
    """Describe media conditions that should pause, rather than fail, a job."""
    errors = set(status.errors)

    if "Cover open" in errors or status.notification_code == 0x01:
        return (
            "The printer cover is open during an active print job. "
            f"Required: {required_width_mm} mm laminated tape. Install the "
            "correct cassette and close the cover. The retained Brother job "
            "will resume automatically; do not request the labels again."
        )

    if "End of media" in errors:
        return (
            "The tape cassette reached end of media during an active print "
            f"job. Required: {required_width_mm} mm laminated tape. Replace "
            "the cassette and close the cover. The retained Brother job will "
            "resume automatically; do not request the labels again."
        )

    if (
        "No media" in errors
        or status.media_width_mm == 0
        or status.media_type_code == 0x00
    ):
        return (
            "No usable cassette is detected during an active print job. "
            f"Required: {required_width_mm} mm laminated tape. Install the "
            "correct cassette and close the cover. The retained Brother job "
            "will resume automatically; do not request the labels again."
        )

    if status.media_width_mm != required_width_mm:
        return (
            "The wrong tape width is installed for the retained print job. "
            f"Required: {required_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Install the correct cassette and close the cover. Printing will "
            "resume automatically; do not request the labels again."
        )

    if status.media_type_code != 0x01:
        return (
            "The wrong tape type is installed for the retained print job. "
            f"Required: {required_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Install the correct cassette and close the cover. Printing will "
            "resume automatically; do not request the labels again."
        )

    if "Replace media / wrong media" in errors:
        return (
            "The printer rejected the cassette for the retained print job. "
            f"Required: {required_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Reseat or replace the cassette and close the cover. Printing "
            "will resume automatically; do not request the labels again."
        )

    return None


class ActivePrintMediaRecovery:
    """Deduplicate notices while an already-submitted job waits for media."""

    def __init__(
        self,
        *,
        workload_name: str,
        required_width_mm: int,
        log_message: LogMessage,
        log_event: LogMessage,
        notify_operator: NotifyOperator,
        notice_heartbeat_seconds: float = 60.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if notice_heartbeat_seconds <= 0:
            raise ValueError(
                "notice_heartbeat_seconds must be greater than zero"
            )

        self.workload_name = workload_name
        self.required_width_mm = required_width_mm
        self.log_message = log_message
        self.log_event = log_event
        self.notify_operator = notify_operator
        self.notice_heartbeat_seconds = notice_heartbeat_seconds
        self.monotonic = monotonic

        self._reason: str | None = None
        self._started_at: float | None = None
        self._last_notice_at: float | None = None
        self._notice_delivered = False

    def observe_status(self, status: BrotherStatus | None) -> str | None:
        """Return the current pause reason and maintain operator notice state."""
        if status is None:
            return self._reason

        reason = recoverable_media_reason(
            status,
            required_width_mm=self.required_width_mm,
        )
        now = self.monotonic()

        if reason is None:
            if self._reason is not None:
                wait_seconds = now - (self._started_at or now)
                message = (
                    "ACTIVE_PRINT_MEDIA_RECOVERED "
                    f"workload='{self.workload_name}' "
                    f"wait_seconds={wait_seconds:.1f} "
                    f"width={status.media_width_mm} "
                    f"media='{status.media_type}' raw={status.raw_hex}"
                )
                self.log_message(message)
                self.log_event(message)
                self._reason = None
                self._started_at = None
                self._last_notice_at = None
                self._notice_delivered = False
            return None

        if self._reason is None:
            event = "ENTER"
            self._started_at = now
            should_log = True
            should_notify = True
        elif reason != self._reason:
            event = "CHANGED"
            should_log = True
            should_notify = True
            self._notice_delivered = False
        elif (
            self._last_notice_at is None
            or now - self._last_notice_at >= self.notice_heartbeat_seconds
        ):
            event = "HEARTBEAT"
            should_log = True
            should_notify = not self._notice_delivered
        else:
            should_log = False
            should_notify = False
            event = ""

        self._reason = reason

        if should_log:
            wait_seconds = now - (self._started_at or now)
            message = (
                f"ACTIVE_PRINT_MEDIA_WAIT event={event} "
                f"workload='{self.workload_name}' "
                f"wait_seconds={wait_seconds:.1f} reason='{reason}'"
            )
            self.log_message(message)
            self.log_event(message)
            self._last_notice_at = now

        if should_notify:
            self._notice_delivered = self.notify_operator(
                self.workload_name,
                reason,
            )

        return reason
