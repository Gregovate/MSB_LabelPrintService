from __future__ import annotations

import ctypes
import logging
import os
import socket
import tempfile
from pathlib import Path
from typing import Callable

from brother_status_runtime import query_brother_snmp_status

MB_RETRYCANCEL = 0x00000005
MB_ICONWARNING = 0x00000030
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000
IDRETRY = 4


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
            "Check printer power/network, then press Retry."
        )
    except Exception as exc:
        return False, (
            f"Printer status could not be read from {host}: {exc}. "
            "Check printer power/network and cassette/cover, then press Retry."
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
            "Close the cover, then press Retry."
        )

    if "End of media" in errors:
        return False, (
            "Tape cassette is at end of media. "
            f"Required: {expected_width_mm} mm laminated tape. "
            "Replace the cassette and close the cover, then press Retry."
        )

    if (
        "No media" in errors
        or status.media_width_mm == 0
        or status.media_type_code == 0x00
    ):
        return False, (
            "No usable tape cassette is detected. "
            f"Required: {expected_width_mm} mm laminated tape. "
            "Install the cassette and close the cover, then press Retry."
        )

    if status.media_width_mm != expected_width_mm:
        return False, (
            "Wrong tape width loaded. "
            f"Required: {expected_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Change the cassette and close the cover, then press Retry."
        )

    if (
        expected_media_type.upper() == "LAMINATED_TAPE"
        and status.media_type_code != 0x01
    ):
        return False, (
            "Wrong tape type loaded. "
            f"Required: {expected_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Change the cassette and close the cover, then press Retry."
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
            + ". Correct the printer condition, then press Retry."
        )

    if "Replace media / wrong media" in errors:
        return False, (
            "Brother printer reports replace/wrong media. "
            f"Required: {expected_width_mm} mm laminated tape. "
            f"Detected: {status.media_width_mm} mm {status.media_type}. "
            "Reseat or replace the cassette and close the cover, then press Retry."
        )

    return True, (
        f"SNMP OK: {status.media_width_mm} mm {status.media_type}; "
        f"raw={status.raw_hex}"
    )


def show_preflight_retry_cancel(workload_name: str, reason: str) -> str:
    """Show one blocking Windows Retry/Cancel dialog."""
    message = (
        f"{workload_name} cannot print yet.\n\n"
        f"{reason}\n\n"
        "Retry reruns the complete preflight and creates no batch unless "
        "every check passes.\n\n"
        "Cancel leaves all Print Label requests pending and creates no "
        "PostgreSQL execution batch."
    )

    logging.warning(
        "PREFLIGHT_DIALOG_OPEN workload=%s reason=%s",
        workload_name,
        reason,
    )

    if os.name != "nt":
        logging.error(
            "PREFLIGHT_DIALOG_UNAVAILABLE non-Windows runtime; treating as Cancel"
        )
        return "CANCEL"

    result = ctypes.windll.user32.MessageBoxW(
        0,
        message,
        "MSB Label Service - Printer Preflight",
        MB_RETRYCANCEL | MB_ICONWARNING | MB_SETFOREGROUND | MB_TOPMOST,
    )

    action = "RETRY" if result == IDRETRY else "CANCEL"
    logging.info(
        "PREFLIGHT_DIALOG_ACTION workload=%s action=%s",
        workload_name,
        action,
    )
    return action


def run_operator_preflight_loop(
    *,
    workload_name: str,
    check_once: Callable[[], tuple[bool, str]],
) -> bool:
    """Own the Retry/Cancel loop for one pending compatible workload."""
    attempt = 0

    while True:
        attempt += 1
        ok, reason = check_once()

        if ok:
            logging.info(
                "FULL_PREFLIGHT_PASS workload=%s attempt=%s detail=%s",
                workload_name,
                attempt,
                reason,
            )
            print(f"Full preflight passed: {reason}")
            return True

        logging.error(
            "FULL_PREFLIGHT_FAIL workload=%s attempt=%s reason=%s",
            workload_name,
            attempt,
            reason,
        )
        print(f"Full preflight failed: {reason}")

        action = show_preflight_retry_cancel(workload_name, reason)
        if action == "RETRY":
            logging.info(
                "FULL_PREFLIGHT_RETRY workload=%s next_attempt=%s",
                workload_name,
                attempt + 1,
            )
            continue

        logging.info(
            "FULL_PREFLIGHT_CANCEL workload=%s attempts=%s",
            workload_name,
            attempt,
        )
        return False
