from __future__ import annotations

import ctypes
import logging
import os
import socket
import tempfile
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from brother_status_runtime import query_brother_snmp_status

MB_OK = 0x00000000
MB_ICONWARNING = 0x00000030
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000
WTS_CURRENT_SERVER_HANDLE = 0
WTS_NO_ACTIVE_CONSOLE_SESSION = 0xFFFFFFFF


@dataclass
class _PreflightWaitState:
    """In-memory state for one automatically rechecked workload."""

    reason: str
    attempts: int
    started_at: float
    last_notice_at: float
    notice_delivered: bool


class AutomaticPreflightRecovery:
    """Run one preflight per service poll without blocking on a GUI dialog."""

    def __init__(
        self,
        *,
        notice_heartbeat_seconds: float = 60.0,
        monotonic: Callable[[], float] = time.monotonic,
        notify_operator: Callable[[str, str], bool] | None = None,
    ) -> None:
        if notice_heartbeat_seconds <= 0:
            raise ValueError("notice_heartbeat_seconds must be greater than zero")

        self.notice_heartbeat_seconds = notice_heartbeat_seconds
        self.monotonic = monotonic
        self.notify_operator = notify_operator or send_preflight_operator_notice
        self._waiting: dict[str, _PreflightWaitState] = {}

    def clear(self) -> None:
        """Forget stale wait state after all pending work disappears."""
        self._waiting.clear()

    def check_once(
        self,
        *,
        workload_name: str,
        check_once: Callable[[], tuple[bool, str]],
    ) -> bool:
        """Run one gate attempt; the service's next poll performs the retry."""
        ok, reason = check_once()
        now = self.monotonic()
        waiting = self._waiting.get(workload_name)

        if ok:
            attempt = 1
            if waiting is not None:
                attempt = waiting.attempts + 1
                logging.info(
                    "PREFLIGHT_RECOVERED workload=%s attempts=%s "
                    "wait_seconds=%.1f detail=%s",
                    workload_name,
                    attempt,
                    now - waiting.started_at,
                    reason,
                )
                del self._waiting[workload_name]

            logging.info(
                "FULL_PREFLIGHT_PASS workload=%s attempt=%s detail=%s",
                workload_name,
                attempt,
                reason,
            )
            print(f"Full preflight passed: {reason}")
            return True

        if waiting is None:
            waiting = _PreflightWaitState(
                reason=reason,
                attempts=1,
                started_at=now,
                last_notice_at=now,
                notice_delivered=False,
            )
            self._waiting[workload_name] = waiting
            event = "ENTER"
            should_notify = True
        else:
            waiting.attempts += 1
            reason_changed = reason != waiting.reason
            heartbeat_due = (
                now - waiting.last_notice_at >= self.notice_heartbeat_seconds
            )

            if reason_changed:
                waiting.reason = reason
                waiting.last_notice_at = now
                waiting.notice_delivered = False
                event = "CHANGED"
                should_notify = True
            elif heartbeat_due:
                waiting.last_notice_at = now
                event = "HEARTBEAT"
                should_notify = not waiting.notice_delivered
            else:
                return False

        logging.warning(
            "PREFLIGHT_WAITING event=%s workload=%s attempt=%s "
            "wait_seconds=%.1f reason=%s automatic_recheck=true",
            event,
            workload_name,
            waiting.attempts,
            now - waiting.started_at,
            reason,
        )

        if event in {"ENTER", "CHANGED"}:
            logging.error(
                "FULL_PREFLIGHT_FAIL workload=%s attempt=%s reason=%s",
                workload_name,
                waiting.attempts,
                reason,
            )
            print(f"Full preflight waiting: {reason}")

        if should_notify:
            waiting.notice_delivered = self.notify_operator(
                workload_name,
                reason,
            )

        return False


def _probe_writable_directory(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"Required runtime directory does not exist: {path}"
    if not path.is_dir():
        return False, f"Required runtime path is not a directory: {path}"

    probe_path: Path | None = None
    try:
        fd, probe_name = tempfile.mkstemp(
            prefix=".msb_label_preflight_",
            dir=str(path),
        )
        os.close(fd)
        probe_path = Path(probe_name)
        probe_path.unlink()
        return True, "OK"
    except Exception as exc:
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except Exception:
                pass
        return False, f"Runtime directory is not writable: {path} ({exc})"


def validate_runtime_prerequisites(
    *,
    required_dirs: tuple[Path, ...],
    sql_paths: tuple[Path, ...],
    csv_paths: tuple[Path, ...],
) -> tuple[bool, str]:
    """Validate deterministic filesystem prerequisites without DB mutation."""
    for directory in required_dirs:
        ok, reason = _probe_writable_directory(directory)
        if not ok:
            return False, reason

    for path in sql_paths:
        if not path.exists() or not path.is_file():
            return False, f"Required SQL file is missing: {path}"
        try:
            path.read_text(encoding="utf-8")
        except Exception as exc:
            return False, f"Required SQL file is not readable: {path} ({exc})"

    for csv_path in csv_paths:
        ok, reason = _probe_writable_directory(csv_path.parent)
        if not ok:
            return False, reason

        if csv_path.exists():
            try:
                fd = os.open(str(csv_path), os.O_WRONLY | os.O_APPEND)
                os.close(fd)
            except Exception as exc:
                return False, f"Runtime CSV is not writable: {csv_path} ({exc})"

    return True, "Runtime paths and SQL files OK"


def snmp_family_preflight(
    *,
    host: str,
    family_code: str,
    expected_width_mm: int,
    expected_media_type: str,
    oid: str,
    community: str,
    port: int,
    timeout: float,
) -> tuple[bool, str]:
    """Validate PT-P950NW reachability and cassette state through SNMP."""
    try:
        status = query_brother_snmp_status(
            host=host,
            oid=oid,
            community=community,
            port=port,
            timeout=timeout,
        )
    except socket.timeout:
        return False, (
            f"Printer unavailable: SNMP status query timed out for {host}. "
            f"Required: {expected_width_mm} mm laminated tape. "
            "Check printer power/network; the service will retry automatically."
        )
    except Exception as exc:
        return False, (
            f"Printer status could not be read from {host}: {exc}. "
            "Check printer power/network and cassette/cover; the service will "
            "retry automatically."
        )

    logging.info(
        "BROTHER_SNMP_STATUS host=%s family=%s width=%s media=%s "
        "error1=0x%02X error2=0x%02X notification=0x%02X raw=%s",
        host,
        family_code,
        status.media_width_mm,
        status.media_type,
        status.error_info_1,
        status.error_info_2,
        status.notification_code,
        status.raw_hex,
    )

    errors = set(status.errors)

    if "Cover open" in errors or status.notification_code == 0x01:
        return False, (
            "Printer cover is open. "
            f"Required: {expected_width_mm} mm laminated tape with cover closed. "
            "Close the cover; the service will retry automatically."
        )

    if "End of media" in errors:
        return False, (
            "Tape cassette is at end of media. "
            f"Required: {expected_width_mm} mm laminated tape. "
            "Replace the cassette and close the cover; the service will resume "
            "automatically."
        )

    if (
        "No media" in errors
        or status.media_width_mm == 0
        or status.media_type_code == 0x00
    ):
        return False, (
            "No usable tape cassette is detected. "
            f"Required: {expected_width_mm} mm laminated tape. "
            "Install the cassette and close the cover; the service will resume "
            "automatically."
        )

    if status.media_width_mm != expected_width_mm:
        return False, (
            "Wrong tape width loaded. "
            f"Required: {expected_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Change the cassette and close the cover; the service will resume "
            "automatically."
        )

    if (
        expected_media_type.upper() == "LAMINATED_TAPE"
        and status.media_type_code != 0x01
    ):
        return False, (
            "Wrong tape type loaded. "
            f"Required: {expected_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Change the cassette and close the cover; the service will resume "
            "automatically."
        )

    remaining_errors = [
        item
        for item in status.errors
        if item
        not in {
            "Cover open",
            "End of media",
            "No media",
            "Replace media / wrong media",
        }
    ]
    if remaining_errors:
        return False, (
            "Brother printer reports an error: "
            + "; ".join(remaining_errors)
            + ". Correct the printer condition; the service will retry "
            "automatically."
        )

    if "Replace media / wrong media" in errors:
        return False, (
            "Brother printer reports replace/wrong media. "
            f"Required: {expected_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Reseat or replace the cassette and close the cover; the service "
            "will resume automatically."
        )

    if status.phase_type_code != 0x00:
        return False, (
            "Printer is still physically processing the previous job "
            f"(Brother phase=0x{status.phase_type_code:02X}). "
            "The service will wait for physical idle and retry automatically."
        )

    return True, (
        f"SNMP OK: {status.media_width_mm} mm {status.media_type}; "
        f"raw={status.raw_hex}"
    )


def send_preflight_operator_notice(workload_name: str, reason: str) -> bool:
    """Send a non-blocking warning to the active Windows console session."""
    message = (
        f"{workload_name} are waiting.\n\n"
        f"{reason}\n\n"
        "The Label Service will recheck automatically and resume after the "
        "printer is ready. Do not submit the same labels again."
    )

    if os.name != "nt":
        logging.warning(
            "PREFLIGHT_NOTICE_UNAVAILABLE workload=%s "
            "reason=non-Windows-runtime",
            workload_name,
        )
        return False

    try:
        get_active_console_session = (
            ctypes.windll.kernel32.WTSGetActiveConsoleSessionId
        )
        get_active_console_session.argtypes = []
        get_active_console_session.restype = wintypes.DWORD
        session_id = int(get_active_console_session())
        if session_id == WTS_NO_ACTIVE_CONSOLE_SESSION:
            logging.warning(
                "PREFLIGHT_NOTICE_UNAVAILABLE workload=%s "
                "reason=no-active-console-session",
                workload_name,
            )
            return False

        title = "MSB Label Service - Printer Attention"
        response = wintypes.DWORD(0)
        send_message = ctypes.windll.wtsapi32.WTSSendMessageW
        send_message.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.BOOL,
        ]
        send_message.restype = wintypes.BOOL
        sent = bool(
            send_message(
                wintypes.HANDLE(WTS_CURRENT_SERVER_HANDLE),
                session_id,
                title,
                len(title.encode("utf-16-le")),
                message,
                len(message.encode("utf-16-le")),
                MB_OK | MB_ICONWARNING | MB_SETFOREGROUND | MB_TOPMOST,
                0,
                ctypes.byref(response),
                False,
            )
        )
    except Exception as exc:
        logging.exception(
            "PREFLIGHT_NOTICE_FAILED workload=%s error=%s",
            workload_name,
            exc,
        )
        return False

    if not sent:
        logging.error(
            "PREFLIGHT_NOTICE_FAILED workload=%s session_id=%s "
            "windows_error=%s",
            workload_name,
            session_id,
            ctypes.windll.kernel32.GetLastError(),
        )
        return False

    logging.warning(
        "PREFLIGHT_NOTICE_SENT workload=%s session_id=%s reason=%s",
        workload_name,
        session_id,
        reason,
    )
    return True
