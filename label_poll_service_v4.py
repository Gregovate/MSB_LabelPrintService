from __future__ import annotations

import configparser
import csv
import json
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
import win32com.client
import win32print
import socket
import os

from brother_status_runtime import query_brother_snmp_status
from brother_status_sampler_runtime import BrotherStatusSampler
from v4_preflight_runtime import (
    run_operator_preflight_loop,
    snmp_family_preflight,
    validate_runtime_prerequisites,
)
from spooler_observer_runtime import SpoolerJobObserver

# ============================================================
# ============================================================
# MSB Label Polling Service
# label_poll_service_v4.py
#
# Purpose:
#   Poll ref.display / ref.container and, when explicitly enabled,
#   ref.controller for print_label = true,
#   snapshot selected rows into batch tables, generate fixed CSV files,
#   print labels through Brother b-PAC, verify print completion through
#   the Windows print queue, write history, and clear only the snapshot
#   rows that were part of the completed batch.
#
# IMPORTANT:
#   This service no longer opens P-touch Editor templates for manual
#   printing. It uses b-PAC directly for job submission.
#
# Current assumptions:
#   - Display template object names:
#       objLine1
#       objLine2
#       objQr
#
#   - v4 Container generic QR template object names:
#       objLine1
#       objQr
#
#   - Display labels print one label per row.
#   - Container labels print TWO labels per selected container.
#     This is handled by duplicating rows in memory before printing.
#
# Print verification strategy:
#   - b-PAC is used only to submit the job.
#   - Real success/failure is verified through the Windows print queue.
#   - Queue observation begins before b-PAC submission so short-lived jobs
#     are retained even when they clear before the main thread checks them.
#   - A job must be observed and then clear within timeout.
#   - If the job never appears or remains stuck, the batch is FAILED and
#     the original print_label flags remain set for operator retry.
#
# Safety:
#   - The service will not create a new PRINTING batch if one already exists.
#   - The service will not create a new batch if the printer queue is not empty.
#
# Author: Greg Liebig / Engineering Innovations, LLC
# Date: 2026-03-21
# ============================================================

# ============================================================
# CHANGE LOG
# ============================================================
## 2026-09-03 — v4.1.0-rc3
#   • INSTRUMENTATION: Sample raw Brother status throughout active print jobs
#       - Requires an initial sample before b-PAC submission
#       - Logs every raw-packet change and periodic unchanged heartbeats
#       - Continues briefly after the observed spooler job clears
#       - Observation only; no unknown status byte can stop printing
#
## 2026-09-03 — v4.1.0-rc2
#   • FIX: Observe Windows spooler jobs before b-PAC submission
#       - Prevents a fast one-label job from clearing before observation begins
#       - Retains newly observed job IDs until completion validation
#       - Still fails when no new job is observed or an observed job is stuck
#       - Applies to Display, Container, and Controller printing
#
## 2026-09-03 — v4.1.0-rc1
#   • FEATURE: Added gated permanent Controller ID label consumption
#       - Polls ref.controller.print_label only when explicitly enabled
#       - Requires the QR_24MM_HORIZONTAL family and 24 mm laminated tape
#       - Freezes exact Controller rows into immutable execution batches
#       - Prints CTRL:<controller_id> plus the full phone-compatible CTRL URL
#       - Finalizes only Controllers contained in the completed batch
#
#   • SAFETY: Controller polling remains disabled by source/config default
#       - Production activation requires an explicit local feature setting
#       - Failed preflight creates no batch and leaves requests pending
#       - Failed physical batches remain visible and block automatic replay
#
## 2026-04-16 — v3.4
#   • IMPROVEMENT: Added rotating main service log
#       - Replaced basicConfig-only file logging with RotatingFileHandler
#       - Preserves console output while preventing unlimited growth of label_service.log
#       - Keeps rolling log history for troubleshooting
#
#   • IMPROVEMENT: Added explicit pre-print batch commit logging
#       - Logs when batch rows are committed before print execution
#       - Improves traceability of batch lifecycle during troubleshooting
#
## 2026-04-16 — v3.3
#   • FIX: Prevent repeated batch requeue after print failure
#       - Added commit of batch header + batch items BEFORE physical printing
#       - Ensures failed batches persist in database instead of being rolled back
#       - Allows FAILED status to be written reliably
#       - Enables failed-batch guard logic to function correctly
#
#   • FIX: Conditional batch creation to eliminate false warnings
#       - Display batch is only created when display_pending > 0
#       - Container batch is only created when container_pending > 0
#       - Prevents misleading "Display batch actor not found" warnings during container-only runs
#
#   • IMPROVEMENT: Logging clarity during batch lifecycle
#       - Added explicit log entry when batch rows are committed prior to printing
#       - Improves traceability of batch state transitions during debugging
#
#   • OPERATIONAL FIX: Resolved repeat print storm condition
#       - Root cause: failed batches rolled back before status update, leaving print_label flags active
#       - Result: same labels requeued and printed multiple times
#       - v3.3 ensures failed batches remain visible and block retries until resolved
#
## 2026-03-30 — v3.2
#   • FEATURE: Capture true user actor for label batch creation
#       - Batch started_by_person_id / started_by_text now sourced from
#         ref.display / ref.container audit fields (updated_by*)
#       - Replaces previous static service account assignment
#
#   • IMPROVEMENT: Batch audit accuracy
#       - Batch now reflects the actual user who requested printing
#       - Print history continues to reflect service execution identity
#
#   • SAFETY: Added fallback to service identity
#       - If audit fields are missing or NULL, system falls back to
#         configured service account to prevent batch failure
#
#   • DIAGNOSTICS: Added logging for batch actor selection
#       - Logs include started_by_person_id and started_by_text
#       - Warns when multiple actors detected in a single batch
#       - Aligns batch actor tracking with ops audit model used throughout system

## 2026-03-26 — v3.1
#   • FIX: Prevent endless batch retry loop after failure
#       - Added failed-batch guard logic in main polling loop
#       - Prevents repeated batch creation when printer fails mid-run
#
#   • FIX: Resolved function/variable shadowing bug
#       - Renamed failed batch helper functions to avoid UnboundLocalError
#
#   • IMPROVEMENT: Added spooler status decoding in logs
#       - Logs now include human-readable job state (PRINTING, SPOOLING, etc.)
#       - Improves troubleshooting of printer issues (e.g., out of tape)
#
#   • IMPROVEMENT: Increased spooler timeout for real-world printing
#       - Display jobs allowed more time to complete
#
#   • BEHAVIOR CHANGE:
#       - System now blocks automatic retry after failed batch
#       - Requires operator intervention instead of silent reprocessing
#
# ------------------------------------------------------------
#  2026-03-21  — Greg Liebig
#
# v3.0  — Queue-verified printing
#   • Removed broken b-PAC callback/event sink handling
#   • Switched print verification to Windows spooler monitoring
#   • Added queue-empty guard before batch creation
#   • Added active PRINTING batch guard to prevent batch storms
#   • Updated comments to match actual runtime behavior
#
# v0.3  — Printer-safe batch creation
#   • Added pending label checks before batch creation
#   • Added printer preflight check BEFORE creating batches
#
# v0.2  — b-PAC integration
#   • Replaced P-touch Editor launch with direct b-PAC printing
#   • Implemented batch printing via StartPrint / PrintOut loop
#
# v0.1  — Initial polling service
#   • DB polling
#   • Snapshot batch tables
#   • CSV generation
#
# ============================================================

# ============================================================
# SERVICE IDENTITY
# ============================================================

SERVICE_NAME = "MSB Label Service"
SERVICE_VERSION = "4.1.0-rc3"

SCRIPT_NAME = Path(sys.argv[0]).name
HOSTNAME = socket.gethostname()
PROCESS_ID = str(os.getpid()) if 'os' in globals() else "?"
SERVICE_ID = f"{SERVICE_NAME} {SERVICE_VERSION} ({SCRIPT_NAME} @ {HOSTNAME} PID {PROCESS_ID})"

CONFIG_PATH = Path(__file__).with_name("config.v4.local.ini")

def print_banner() -> None:
    line = "=" * 60
    print(line)
    print(f"{SERVICE_NAME} — {SCRIPT_NAME}")
    print(f"Version {SERVICE_VERSION}")
    print(f"Host    : {HOSTNAME}")
    print(f"PID     : {PROCESS_ID}")
    print(line)

def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()

    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Configuration file not found: {CONFIG_PATH}")

    loaded = config.read(CONFIG_PATH, encoding="utf-8")
    if not loaded:
        raise RuntimeError(f"Could not read configuration file: {CONFIG_PATH}")

    return config


CONFIG = load_config()

BASE_DIR = Path(CONFIG["paths"]["base_dir"])
SQL_DIR = Path(CONFIG["paths"]["sql_dir"])
CSV_DIR = Path(CONFIG["paths"]["csv_dir"])
STATE_DIR = Path(CONFIG["paths"]["state_dir"])
LOG_DIR = Path(CONFIG["paths"]["log_dir"])
BATCH_LOG_DIR = LOG_DIR / "batches"

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
BATCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

LOCK_FILE = STATE_DIR / "print_service.lock"
LOG_FILE = LOG_DIR / "label_service.log"
BATCH_LOG_LOCK = threading.Lock()

POLL_SECONDS = int(CONFIG["service"]["poll_seconds"])
STARTED_BY_PERSON_ID = int(CONFIG["service"]["started_by_person_id"])
STARTED_BY_TEXT = CONFIG["service"]["started_by_text"]
CONTROLLER_POLLING_ENABLED = CONFIG.getboolean(
    "features",
    "controller_polling_enabled",
    fallback=False,
)

SNMP_OID = CONFIG.get(
    "printing",
    "snmp_oid",
    fallback="1.3.6.1.4.1.2435.3.3.9.1.6.1.0",
)
SNMP_COMMUNITY = CONFIG.get(
    "printing",
    "snmp_community",
    fallback="public",
)
SNMP_PORT = CONFIG.getint(
    "printing",
    "snmp_port",
    fallback=161,
)
SNMP_TIMEOUT_SECONDS = CONFIG.getfloat(
    "printing",
    "snmp_timeout_seconds",
    fallback=3.0,
)
STATUS_SAMPLER_ENABLED = CONFIG.getboolean(
    "printing",
    "status_sampler_enabled",
    fallback=True,
)
STATUS_SAMPLE_INTERVAL_SECONDS = CONFIG.getfloat(
    "printing",
    "status_sample_interval_seconds",
    fallback=0.25,
)
STATUS_HEARTBEAT_SECONDS = CONFIG.getfloat(
    "printing",
    "status_heartbeat_seconds",
    fallback=5.0,
)
STATUS_POST_SPOOLER_SECONDS = CONFIG.getfloat(
    "printing",
    "status_post_spooler_seconds",
    fallback=2.0,
)

if STATUS_SAMPLE_INTERVAL_SECONDS <= 0:
    raise RuntimeError("status_sample_interval_seconds must be greater than zero")
if STATUS_HEARTBEAT_SECONDS <= 0:
    raise RuntimeError("status_heartbeat_seconds must be greater than zero")
if STATUS_POST_SPOOLER_SECONDS < 0:
    raise RuntimeError("status_post_spooler_seconds cannot be negative")

DISPLAY_CSV = Path(CONFIG["csv_files"]["display"])
CONTAINER_VERTICAL_CSV = Path(CONFIG["csv_files"]["container_vertical"])
CONTAINER_HORIZONTAL_CSV = Path(CONFIG["csv_files"]["container_horizontal"])
CONTROLLER_CSV = Path(CONFIG.get(
    "csv_files",
    "controller",
    fallback=str(CSV_DIR / "controller_labels.csv"),
))


def load_printer_config(printer_key: str) -> dict[str, Any]:
    section = f"printer.{printer_key}"
    if section not in CONFIG:
        raise RuntimeError(f"Missing printer configuration section: [{section}]")

    return {
        "key": printer_key,
        "queue_name": CONFIG[section]["queue_name"],
        "host": CONFIG[section]["host"],
        "template_dir": Path(CONFIG[section]["template_dir"]),
        "enabled": CONFIG[section].getboolean("enabled", fallback=True),
    }


def load_label_family(family_code: str) -> dict[str, Any]:
    section = f"label_family.{family_code}"
    if section not in CONFIG:
        raise RuntimeError(f"Missing label family configuration section: [{section}]")

    printer_key = CONFIG[section]["printer"]
    printer = load_printer_config(printer_key)

    template_1_name = CONFIG[section].get("template_1_line", "").strip()
    template_2_name = CONFIG[section].get("template_2_line", "").strip()

    return {
        "code": family_code,
        "printer_key": printer_key,
        "printer": printer,
        "media_width_mm": CONFIG[section].getint("media_width_mm"),
        "media_type": CONFIG[section]["media_type"],
        "orientation": CONFIG[section]["orientation"],
        "template_1_line": (
            printer["template_dir"] / template_1_name
            if template_1_name
            else None
        ),
        "template_2_line": (
            printer["template_dir"] / template_2_name
            if template_2_name
            else None
        ),
    }


LABEL_FAMILIES = {
    code: load_label_family(code)
    for code in (
        "QR_36MM_HORIZONTAL",
        "QR_24MM_HORIZONTAL",
        "QR_36MM_VERTICAL",
        "WIRING_12MM_HORIZONTAL",
    )
}

# Accepted v4 Container physical templates.
# Containers remain 36 mm, with orientation determined by the existing
# database rule. Both use the generic QR one-line object contract.
CONTAINER_HORIZONTAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["template_1_line"]
CONTAINER_VERTICAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_VERTICAL"]["template_1_line"]
CONTROLLER_FAMILY_CODE = "QR_24MM_HORIZONTAL"
CONTROLLER_TEMPLATE = LABEL_FAMILIES[CONTROLLER_FAMILY_CODE]["template_1_line"]

# ------------------------------------------------------------
# Brother b-PAC print flags
# ------------------------------------------------------------
# bpoHalfCut   = 0x200
# bpoChainPrint= 0x400
# bpoCutAtEnd  = 0x04000000
#
# Note:
#   CutAtEnd has not yet behaved perfectly in testing, but we keep
#   it enabled because it is the correct intended flag for end-of-job
#   full cut.
# ------------------------------------------------------------
PRINT_FLAGS = 0x200 | 0x400 | 0x04000000

# ------------------------------------------------------------
# Windows Print Spooler Status
# ------------------------------------------------------------
def decode_spooler_status(status: int) -> str:
    flags = {
        0x0001: "PAUSED",
        0x0002: "ERROR",
        0x0004: "DELETING",
        0x0008: "SPOOLING",
        0x0010: "PRINTING",
        0x0020: "OFFLINE",
        0x0040: "PAPEROUT",
        0x0080: "PRINTED",
        0x0100: "DELETED",
        0x0200: "BLOCKED",
        0x0400: "USER_INTERVENTION",
        0x0800: "RESTART",
    }

    active = [name for bit, name in flags.items() if status & bit]
    return ", ".join(active) if active else f"UNKNOWN({status})"

# ------------------------------------------------------------
# Template object names
# ------------------------------------------------------------
DISPLAY_OBJ_LINE1 = "objLine1"
DISPLAY_OBJ_LINE2 = "objLine2"
DISPLAY_OBJ_QR = "objQr"

CONTAINER_OBJ_LINE1 = "objLine1"
CONTAINER_OBJ_QR = "objQr"

CONTROLLER_OBJ_LINE1 = "objLine1"
CONTROLLER_OBJ_QR = "objQr"

from logging.handlers import RotatingFileHandler

# ------------------------------------------------------------
# Main Service log Setup
# ------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.touch(exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

# File (rotating)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,   # 5 MB
    backupCount=10,
    encoding="utf-8",
)
file_handler.setFormatter(formatter)

# Console (so your blue window still shows activity)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ------------------------------------------------------------
# STARTUP LOGS
# ------------------------------------------------------------
logging.info("%s started", SERVICE_ID)
logging.info("Logging initialized. Log file: %s", LOG_FILE.resolve())

print(f"{SERVICE_NAME} v{SERVICE_VERSION} starting")
print(f"Config  : {CONFIG_PATH}")
print(f"Logging initialized. Log file: {LOG_FILE.resolve()}")


# ============================================================
# STARTUP HEALTH CHECK
# ============================================================
def startup_health_check() -> None:
    """
    Fail fast on startup if the service cannot reach the database
    and perform the same permission path that previously failed
    during batch finalization.
    """
    print_banner()
    print("Checking PostgreSQL connectivity and permissions...")

    with db_connect() as conn:
        conn.autocommit = False

        with conn.cursor() as cur:
            # --------------------------------------------------
            # Basic connection identity
            # --------------------------------------------------
            cur.execute("SELECT current_database(), current_user, now();")
            dbname, dbuser, dbtime = cur.fetchone()
            print(f"Connected to database: {dbname}")
            print(f"Connected as user   : {dbuser}")
            print(f"Database time       : {dbtime}")

            # --------------------------------------------------
            # Basic read checks
            # --------------------------------------------------
            cur.execute("SELECT COUNT(*) FROM ref.display;")
            display_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM ref.container;")
            container_count = cur.fetchone()[0]

            print(f"ref.display rows    : {display_count}")
            print(f"ref.container rows  : {container_count}")

            if CONTROLLER_POLLING_ENABLED:
                cur.execute("SELECT COUNT(*) FROM ref.controller;")
                controller_count = cur.fetchone()[0]
                print(f"ref.controller rows : {controller_count}")

                cur.execute("""
                    SELECT
                        to_regclass('ops.controller_label_batch'),
                        to_regclass('ops.controller_label_batch_item');
                """)
                (
                    controller_batch_table,
                    controller_item_table,
                ) = cur.fetchone()

                if controller_batch_table is None or controller_item_table is None:
                    raise RuntimeError(
                        "Controller polling is enabled, but the Controller label "
                        "batch tables are not installed."
                    )

                cur.execute("""
                    SELECT
                        has_table_privilege(
                            current_user,
                            'ops.controller_label_batch',
                            'SELECT,INSERT,UPDATE'
                        ),
                        has_table_privilege(
                            current_user,
                            'ops.controller_label_batch_item',
                            'SELECT,INSERT,UPDATE'
                        ),
                        has_column_privilege(
                            current_user,
                            'ref.controller',
                            'print_label',
                            'UPDATE'
                        );
                """)
                (
                    can_write_controller_batch,
                    can_write_controller_items,
                    can_clear_controller_request,
                ) = cur.fetchone()

                if not all((
                    can_write_controller_batch,
                    can_write_controller_items,
                    can_clear_controller_request,
                )):
                    raise RuntimeError(
                        "Controller polling is enabled, but printservice does "
                        "not have the required Controller batch/finalization permissions."
                    )

                print("Controller polling  : ENABLED")
            else:
                print("Controller polling  : DISABLED")

            # --------------------------------------------------
            # Temp write test
            # --------------------------------------------------
            cur.execute("CREATE TEMP TABLE IF NOT EXISTS _label_service_healthcheck (x int);")
            cur.execute("TRUNCATE TABLE _label_service_healthcheck;")
            cur.execute("INSERT INTO _label_service_healthcheck (x) VALUES (1);")
            cur.execute("SELECT COUNT(*) FROM _label_service_healthcheck;")
            temp_count = cur.fetchone()[0]

            print(f"Temp write test     : OK ({temp_count} row)")

            # --------------------------------------------------
            # Actor / person permission path
            # This is the path that failed during finalize last time
            # --------------------------------------------------
            print("Checking ref.person access...")
            cur.execute("""
                SELECT p.person_id, p.preferred_name, p.pg_login_name
                FROM ref.person p
                WHERE p.pg_login_name = current_user
                LIMIT 1;
            """)
            actor_row = cur.fetchone()

            if actor_row is None:
                raise RuntimeError(
                    "Startup check FAILED: no ref.person row matches current_user. "
                    "Service account must exist in ref.person.pg_login_name."
                )

            actor_person_id, actor_name, actor_login = actor_row
            print(f"ref.person match    : person_id={actor_person_id}, "
                  f"name={actor_name}, login={actor_login}")

            # --------------------------------------------------
            # resolve_actor() permission + execute check
            # --------------------------------------------------
            print("Checking ref.resolve_actor()...")
            cur.execute("SELECT person_id, actor_name FROM ref.resolve_actor();")
            resolved = cur.fetchone()

            if resolved is None:
                raise RuntimeError(
                    "Startup check FAILED: ref.resolve_actor() returned no row."
                )

            resolved_person_id, resolved_name = resolved
            print(f"resolve_actor()     : person_id={resolved_person_id}, "
                  f"actor_name={resolved_name}")

        # Roll back temp test work
        conn.rollback()

    print("Startup health check PASSED.")
    print(f"Service READY — polling every {POLL_SECONDS} seconds.")
    print("Press Ctrl+C to stop.")
    print("")

# ============================================================
# v4 selected-workload full preflight
# ============================================================

def pending_display_workload_signature(
    conn,
    label_template_id: int,
) -> str:
    ids = query_value(
        conn,
        """
        SELECT COALESCE(
            string_agg(
                display_id::text
                || ':' || COALESCE(display_name, '')
                || ':' || COALESCE(label_template_id::text, ''),
                E'\n'
                ORDER BY display_id
            ),
            ''
        )
        FROM ref.display
        WHERE print_label = true
          AND label_template_id = %(label_template_id)s;
        """,
        {"label_template_id": label_template_id},
    )
    return f"DISPLAY:{label_template_id}:{ids or ''}"


def pending_container_workload_signature(conn) -> str:
    ids = query_value(
        conn,
        """
        SELECT COALESCE(
            string_agg(
                container_id::text
                || ':' || COALESCE(container_type_id::text, ''),
                E'\n'
                ORDER BY container_id
            ),
            ''
        )
        FROM ref.container
        WHERE print_label = true;
        """,
    )
    return f"CONTAINER:{ids or ''}"


def pending_controller_workload_signature(conn) -> str:
    ids = query_value(
        conn,
        """
        SELECT COALESCE(
            string_agg(
                controller_id::text
                || ':' || COALESCE(label_template_id::text, ''),
                E'\n'
                ORDER BY controller_id
            ),
            ''
        )
        FROM ref.controller
        WHERE print_label = true;
        """,
    )
    return f"CONTROLLER:{ids or ''}"


def pending_display_ids(
    conn,
    label_template_id: int,
) -> list[int]:
    rows = query_rows(
        conn,
        """
        SELECT display_id
        FROM ref.display
        WHERE print_label = true
          AND label_template_id = %(label_template_id)s
        ORDER BY display_id;
        """,
        {"label_template_id": label_template_id},
    )
    return [int(row["display_id"]) for row in rows]


def pending_container_ids(conn) -> list[int]:
    rows = query_rows(
        conn,
        """
        SELECT container_id
        FROM ref.container
        WHERE print_label = true
        ORDER BY container_id;
        """,
    )
    return [int(row["container_id"]) for row in rows]


def pending_controller_ids(conn) -> list[int]:
    rows = query_rows(
        conn,
        """
        SELECT controller_id
        FROM ref.controller
        WHERE print_label = true
        ORDER BY controller_id;
        """,
    )
    return [int(row["controller_id"]) for row in rows]


def run_selected_workload_preflight(
    *,
    workload_name: str,
    family: dict[str, Any],
    template_specs: list[tuple[Path, tuple[str, ...]]],
    sql_filenames: tuple[str, ...],
    csv_paths: tuple[Path, ...],
) -> bool:
    """
    Run the complete deterministic v4 pre-batch gate for one selected
    compatible workload. This function performs no PostgreSQL writes.
    """
    printer = family["printer"]

    def check_once() -> tuple[bool, str]:
        ok, reason = validate_runtime_prerequisites(
            required_dirs=(
                BASE_DIR,
                SQL_DIR,
                CSV_DIR,
                STATE_DIR,
                LOG_DIR,
                BATCH_LOG_DIR,
            ),
            sql_paths=tuple(
                SQL_DIR / filename
                for filename in sql_filenames
            ),
            csv_paths=csv_paths,
        )
        if not ok:
            return False, reason

        if not printer["enabled"]:
            return False, (
                f"Configured printer '{printer['key']}' is disabled "
                f"for {workload_name}."
            )

        if family["printer_key"] != "pt_p950nw":
            return False, (
                f"Production SNMP preflight is not yet approved for "
                f"printer family '{family['printer_key']}'."
            )

        ok, reason = snmp_family_preflight(
            host=printer["host"],
            family_code=family["code"],
            expected_width_mm=int(family["media_width_mm"]),
            expected_media_type=str(family["media_type"]),
            oid=SNMP_OID,
            community=SNMP_COMMUNITY,
            port=SNMP_PORT,
            timeout=SNMP_TIMEOUT_SECONDS,
        )
        if not ok:
            return False, reason

        printer_name = printer["queue_name"]

        for template_path, required_objects in template_specs:
            ok, reason = printer_preflight(
                template_path=template_path,
                printer_name=printer_name,
                required_objects=required_objects,
            )
            if not ok:
                return False, reason

        try:
            queue_jobs = get_print_jobs(printer_name)
        except Exception as exc:
            return False, (
                f"Could not inspect Windows printer queue "
                f"'{printer_name}': {exc}"
            )

        if queue_jobs:
            return False, (
                f"Printer queue '{printer_name}' is not empty: "
                f"{summarize_print_jobs(queue_jobs)}. "
                "Resolve the queue safely, then press Retry."
            )

        return True, (
            f"{workload_name} full preflight passed for "
            f"{family['code']} on '{printer_name}'."
        )

    return run_operator_preflight_loop(
        workload_name=workload_name,
        check_once=check_once,
    )


# ============================================================
# Printer preflight
# ============================================================

BPAC_STATUS_CODES = {
    101: "No media",
    102: "End of media",
    50593795: "Printer offline",
}

def decode_bpac_code(code: int) -> str:
    return BPAC_STATUS_CODES.get(code, f"Unknown code {code} (0x{code:08X})")


def printer_preflight(
    template_path: Path,
    printer_name: str,
    required_objects: tuple[str, ...] = (),
) -> tuple[bool, str]:
    """
    Validate the selected physical template and Windows printer before
    any PostgreSQL execution-batch state is created.

    Brother SNMP status hardening and Retry/Cancel dialogs are added in
    the next v4 preflight checkpoint; this function preserves the
    existing b-PAC media check while making it family/template-specific.
    """
    doc = None

    try:
        if template_path is None:
            return False, "No physical template is configured for this render mode"

        if not template_path.exists():
            return False, f"Template file does not exist: {template_path}"

        doc = create_bpac_document()

        opened = doc.Open(str(template_path))
        if not opened:
            return False, f"Could not open template: {template_path}"

        set_printer_ok = doc.SetPrinter(printer_name, True)
        if not set_printer_ok:
            return False, f"Could not set printer '{printer_name}'"

        for object_name in required_objects:
            if doc.GetObject(object_name) is None:
                return False, (
                    f"Template '{template_path.name}' is missing required "
                    f"object '{object_name}'"
                )

        try:
            template_media = doc.GetMediaName
        except Exception as exc:
            template_media = f"<error reading template media: {exc}>"

        try:
            printer_media = doc.Printer.GetMediaName
        except Exception as exc:
            return False, f"Printer GetMediaName failed: {exc}"

        media_id = None
        media_id_error = None
        try:
            media_id = doc.Printer.GetMediaId
        except Exception as exc:
            media_id_error = str(exc)

        if media_id in (101, 102, 50593795):
            return False, decode_bpac_code(media_id)

        if not printer_media or str(printer_media).strip() == "":
            return False, (
                "Printer not ready "
                "(no media, offline, or driver not responding)"
            )

        if (
            template_media
            and printer_media
            and str(template_media).strip() != str(printer_media).strip()
        ):
            return False, (
                f"Loaded media '{printer_media}' does not match "
                f"template media '{template_media}'"
            )

        if media_id_error:
            return True, (
                f"OK template={template_path.name} "
                f"(GetMediaId warning: {media_id_error})"
            )

        return True, (
            f"OK template={template_path.name} "
            f"template_media={template_media} printer_media={printer_media}"
        )

    except Exception as exc:
        return False, f"Printer preflight exception: {exc}"

    finally:
        if doc is not None:
            try:
                _ = doc.Close()
            except Exception:
                pass


# ============================================================
# LOGGING HELPERS
# ============================================================

def write_batch_log(batch_log_path: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with BATCH_LOG_LOCK:
        with batch_log_path.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {message}\n")


def new_batch_log_path(batch_type: str, batch_id: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return BATCH_LOG_DIR / f"{batch_type}_batch_{batch_id}_{stamp}.log"

# ============================================================
# DATABASE HELPERS
# ============================================================

def pending_display_count(conn) -> int:
    return int(query_value(
        conn,
        "SELECT COUNT(*) FROM ref.display WHERE print_label = true;",
    ) or 0)


def pending_display_families(conn) -> list[dict[str, Any]]:
    """
    Return pending Display physical families and the one-line/two-line
    render modes required by each family.

    Accepted compatibility rule:
      - <= 20 characters: one line
      - > 20 with at least two hyphen-delimited leading segments:
        split after the second segment
      - > 20 without that structure: remain one line
    """
    return query_rows(
        conn,
        """
        SELECT
            d.label_template_id,
            lt.label_template_code,
            COUNT(*)::integer AS pending_count,
            COUNT(*) FILTER (
                WHERE LENGTH(d.display_name) <= 20
                   OR d.display_name !~ '^[^-]+-[^-]+-'
            )::integer AS one_line_count,
            COUNT(*) FILTER (
                WHERE LENGTH(d.display_name) > 20
                  AND d.display_name ~ '^[^-]+-[^-]+-'
            )::integer AS two_line_count
        FROM ref.display d
        JOIN ref.label_template lt
          ON lt.label_template_id = d.label_template_id
        WHERE d.print_label = true
        GROUP BY
            d.label_template_id,
            lt.label_template_code
        ORDER BY d.label_template_id;
        """,
    )


def pending_display_preflight_plan(
    conn,
    label_template_id: int,
) -> dict[str, Any] | None:
    """Return Display render counts + signature from one DB statement."""
    rows = query_rows(
        conn,
        """
        SELECT
            d.label_template_id,
            lt.label_template_code,
            COUNT(*)::integer AS pending_count,
            COUNT(*) FILTER (
                WHERE LENGTH(d.display_name) <= 20
                   OR d.display_name !~ '^[^-]+-[^-]+-'
            )::integer AS one_line_count,
            COUNT(*) FILTER (
                WHERE LENGTH(d.display_name) > 20
                  AND d.display_name ~ '^[^-]+-[^-]+-'
            )::integer AS two_line_count,
            'DISPLAY:' || d.label_template_id::text || ':' ||
            COALESCE(
                string_agg(
                    d.display_id::text
                    || ':' || COALESCE(d.display_name, '')
                    || ':' || COALESCE(d.label_template_id::text, ''),
                    E'\n'
                    ORDER BY d.display_id
                ),
                ''
            ) AS workload_signature
        FROM ref.display d
        JOIN ref.label_template lt
          ON lt.label_template_id = d.label_template_id
        WHERE d.print_label = true
          AND d.label_template_id = %(label_template_id)s
        GROUP BY
            d.label_template_id,
            lt.label_template_code;
        """,
        {"label_template_id": label_template_id},
    )
    return rows[0] if rows else None


def pending_container_preflight_plan(conn) -> dict[str, Any]:
    """Return Container orientation counts + signature from one DB statement."""
    rows = query_rows(
        conn,
        """
        SELECT
            COUNT(*)::integer AS pending_count,
            COUNT(*) FILTER (
                WHERE container_type_id = 1
            )::integer AS vertical_count,
            COUNT(*) FILTER (
                WHERE container_type_id IS DISTINCT FROM 1
            )::integer AS horizontal_count,
            'CONTAINER:' ||
            COALESCE(
                string_agg(
                    container_id::text
                    || ':' || COALESCE(container_type_id::text, ''),
                    E'\n'
                    ORDER BY container_id
                ),
                ''
            ) AS workload_signature
        FROM ref.container
        WHERE print_label = true;
        """,
    )
    return rows[0]


def pending_container_count(conn) -> int:
    return int(query_value(
        conn,
        "SELECT COUNT(*) FROM ref.container WHERE print_label = true;",
    ) or 0)


def pending_controller_count(conn) -> int:
    if not CONTROLLER_POLLING_ENABLED:
        return 0

    return int(query_value(
        conn,
        "SELECT COUNT(*) FROM ref.controller WHERE print_label = true;",
    ) or 0)


def pending_controller_preflight_plan(conn) -> dict[str, Any]:
    """Return Controller family validation + signature in one DB statement."""
    rows = query_rows(
        conn,
        """
        SELECT
            COUNT(*)::integer AS pending_count,
            COUNT(*) FILTER (
                WHERE lt.label_template_code = 'QR_24MM_HORIZONTAL'
            )::integer AS eligible_count,
            COUNT(*) FILTER (
                WHERE lt.label_template_code IS DISTINCT FROM
                    'QR_24MM_HORIZONTAL'
            )::integer AS invalid_family_count,
            MIN(lt.label_template_id) FILTER (
                WHERE lt.label_template_code = 'QR_24MM_HORIZONTAL'
            ) AS label_template_id,
            'CONTROLLER:' ||
            COALESCE(
                string_agg(
                    c.controller_id::text
                    || ':' || COALESCE(c.label_template_id::text, ''),
                    E'\n'
                    ORDER BY c.controller_id
                ),
                ''
            ) AS workload_signature
        FROM ref.controller AS c
        LEFT JOIN ref.label_template AS lt
          ON lt.label_template_id = c.label_template_id
        WHERE c.print_label = true;
        """,
    )
    return rows[0]


def pending_container_orientations(conn) -> list[dict[str, Any]]:
    """Return the orientation groups represented by pending Containers."""
    return query_rows(
        conn,
        """
        SELECT
            CASE
                WHEN container_type_id = 1 THEN 'VERTICAL'
                ELSE 'HORIZONTAL'
            END AS label_orientation,
            COUNT(*)::integer AS pending_count
        FROM ref.container
        WHERE print_label = true
        GROUP BY 1
        ORDER BY 1;
        """,
    )

def db_connect():
    return psycopg2.connect(
        host=CONFIG["database"]["host"],
        port=int(CONFIG["database"]["port"]),
        dbname=CONFIG["database"]["dbname"],
        user=CONFIG["database"]["user"],
        password=CONFIG["database"]["password"],
    )

def load_sql(filename: str) -> str:
    path = SQL_DIR / filename
    return path.read_text(encoding="utf-8")


def query_value(conn, sql: str, params: dict[str, Any] | None = None) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        row = cur.fetchone()
        return row[0] if row else None


def query_rows(conn, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params or {})
        return list(cur.fetchall())


def exec_sql(conn, sql: str, params: dict[str, Any] | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})

def active_display_batch_id(conn) -> int | None:
    batch_id = query_value(
        conn,
        """
        SELECT display_label_batch_id
        FROM ops.display_label_batch
        WHERE status = 'PRINTING'
        ORDER BY display_label_batch_id DESC
        LIMIT 1;
        """,
    )
    return int(batch_id) if batch_id is not None else None


def active_container_batch_id(conn) -> int | None:
    batch_id = query_value(
        conn,
        """
        SELECT container_label_batch_id
        FROM ops.container_label_batch
        WHERE status = 'PRINTING'
        ORDER BY container_label_batch_id DESC
        LIMIT 1;
        """,
    )
    return int(batch_id) if batch_id is not None else None


def active_controller_batch_id(conn) -> int | None:
    if not CONTROLLER_POLLING_ENABLED:
        return None

    batch_id = query_value(
        conn,
        """
        SELECT controller_label_batch_id
        FROM ops.controller_label_batch
        WHERE status = 'PRINTING'
        ORDER BY controller_label_batch_id DESC
        LIMIT 1;
        """,
    )
    return int(batch_id) if batch_id is not None else None

#03/30/26 DISPLAY LABELS
def get_display_batch_actor(
    conn,
    label_template_id: int,
) -> tuple[int | None, str | None]:
    row = query_rows(
        conn,
        """
        SELECT DISTINCT
            updated_by_person_id,
            updated_by
        FROM ref.display
        WHERE print_label = true
          AND label_template_id = %(label_template_id)s
        ORDER BY updated_by_person_id NULLS LAST, updated_by
        """,
        {"label_template_id": label_template_id},
    )

    if not row:
        return None, None

    if len(row) > 1:
        logging.warning(
            "Multiple actors detected for display family label_template_id=%s. "
            "Using first row.",
            label_template_id,
        )

    return row[0]["updated_by_person_id"], row[0]["updated_by"]

#03/30/26 CONTAINER LABELS
def get_container_batch_actor(conn) -> tuple[int | None, str | None]:
    row = query_rows(
        conn,
        """
        SELECT DISTINCT
            updated_by_person_id,
            updated_by
        FROM ref.container
        WHERE print_label = true
        """
    )

    if not row:
        return None, None

    if len(row) > 1:
        logging.warning("Multiple actors detected for container batch. Using first row.")

    return row[0]["updated_by_person_id"], row[0]["updated_by"]

# ============================================================
# LOCK FILE HELPERS
# ============================================================

def lock_exists() -> bool:
    return LOCK_FILE.exists()


def create_lock() -> None:
    LOCK_FILE.write_text(
        json.dumps(
            {
                "pid": str(Path.cwd()),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def clear_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


# ============================================================
# BATCH CREATION
# ============================================================

def create_display_batch(
    conn,
    label_template_id: int,
    expected_signature: str,
) -> int | None:
    display_ids = pending_display_ids(conn, label_template_id)
    if not display_ids:
        return None

    locked_rows = query_rows(
        conn,
        """
        SELECT
            display_id,
            updated_by_person_id,
            updated_by
        FROM ref.display
        WHERE display_id = ANY(%(display_ids)s)
          AND print_label = true
          AND label_template_id = %(label_template_id)s
        ORDER BY display_id
        FOR UPDATE;
        """,
        {
            "display_ids": display_ids,
            "label_template_id": label_template_id,
        },
    )
    locked_ids = [int(row["display_id"]) for row in locked_rows]

    if locked_ids != display_ids:
        logging.warning(
            "Display request set changed while acquiring snapshot locks; "
            "no batch created. expected_ids=%s locked_ids=%s",
            display_ids,
            locked_ids,
        )
        return None

    locked_signature = pending_display_workload_signature(
        conn,
        label_template_id,
    )
    if locked_signature != expected_signature:
        logging.warning(
            "Display request/render state changed before snapshot freeze; "
            "no batch created. expected=%s locked=%s",
            expected_signature,
            locked_signature,
        )
        return None

    actors = {
        (row["updated_by_person_id"], row["updated_by"])
        for row in locked_rows
    }
    if len(actors) > 1:
        logging.warning(
            "Multiple actors detected in frozen Display workload. Using first row."
        )

    first_row = locked_rows[0]
    person_id = first_row["updated_by_person_id"]
    person_text = first_row["updated_by"]

    if person_id is None:
        logging.warning(
            "Display batch actor not found from frozen ref.display rows. "
            "Falling back to service identity."
        )
        person_id = STARTED_BY_PERSON_ID
        person_text = STARTED_BY_TEXT

    sql = """
        INSERT INTO ops.display_label_batch (
            started_by_person_id,
            started_by_text,
            label_template_id,
            status,
            notes
        )
        VALUES (
            %(person_id)s,
            %(person_text)s,
            %(label_template_id)s,
            'PRINTING',
            'Polling service snapshot'
        )
        RETURNING display_label_batch_id;
    """
    batch_id = query_value(
        conn,
        sql,
        {
            "person_id": person_id,
            "person_text": person_text,
            "label_template_id": label_template_id,
        },
    )

    exec_sql(
        conn,
        load_sql("display_snapshot_v4.sql"),
        {
            "batch_id": batch_id,
            "label_template_id": label_template_id,
            "display_ids": display_ids,
        },
    )

    row_count = int(query_value(
        conn,
        "SELECT COUNT(*) FROM ops.display_label_batch_item WHERE display_label_batch_id = %(batch_id)s;",
        {"batch_id": batch_id},
    ) or 0)

    if row_count != len(display_ids):
        raise RuntimeError(
            f"Display snapshot row count mismatch: expected {len(display_ids)}, "
            f"created {row_count}. Transaction must roll back."
        )

    logging.info(
        "Created display batch %s label_template_id=%s rows=%s "
        "started_by_person_id=%s started_by_text=%s",
        batch_id,
        label_template_id,
        len(display_ids),
        person_id,
        person_text,
    )

    return int(batch_id)

def create_container_batch(
    conn,
    expected_signature: str,
) -> int | None:
    container_ids = pending_container_ids(conn)
    if not container_ids:
        return None

    locked_rows = query_rows(
        conn,
        """
        SELECT
            container_id,
            updated_by_person_id,
            updated_by
        FROM ref.container
        WHERE container_id = ANY(%(container_ids)s)
          AND print_label = true
        ORDER BY container_id
        FOR UPDATE;
        """,
        {"container_ids": container_ids},
    )
    locked_ids = [int(row["container_id"]) for row in locked_rows]

    if locked_ids != container_ids:
        logging.warning(
            "Container request set changed while acquiring snapshot locks; "
            "no batch created. expected_ids=%s locked_ids=%s",
            container_ids,
            locked_ids,
        )
        return None

    locked_signature = pending_container_workload_signature(conn)
    if locked_signature != expected_signature:
        logging.warning(
            "Container request/orientation state changed before snapshot freeze; "
            "no batch created. expected=%s locked=%s",
            expected_signature,
            locked_signature,
        )
        return None

    actors = {
        (row["updated_by_person_id"], row["updated_by"])
        for row in locked_rows
    }
    if len(actors) > 1:
        logging.warning(
            "Multiple actors detected in frozen Container workload. Using first row."
        )

    first_row = locked_rows[0]
    person_id = first_row["updated_by_person_id"]
    person_text = first_row["updated_by"]

    if person_id is None:
        logging.warning(
            "Container batch actor not found from frozen ref.container rows. "
            "Falling back to service identity."
        )
        person_id = STARTED_BY_PERSON_ID
        person_text = STARTED_BY_TEXT

    sql = """
        INSERT INTO ops.container_label_batch (
            started_by_person_id,
            started_by_text,
            status,
            notes
        )
        VALUES (%(person_id)s, %(person_text)s, 'PRINTING', 'Polling service snapshot')
        RETURNING container_label_batch_id;
    """
    batch_id = query_value(
        conn,
        sql,
        {
            "person_id": person_id,
            "person_text": person_text,
        },
    )

    exec_sql(
        conn,
        load_sql("container_snapshot_v4.sql"),
        {
            "batch_id": batch_id,
            "container_ids": container_ids,
        },
    )

    row_count = int(query_value(
        conn,
        "SELECT COUNT(*) FROM ops.container_label_batch_item WHERE container_label_batch_id = %(batch_id)s;",
        {"batch_id": batch_id},
    ) or 0)

    if row_count != len(container_ids):
        raise RuntimeError(
            f"Container snapshot row count mismatch: expected {len(container_ids)}, "
            f"created {row_count}. Transaction must roll back."
        )

    logging.info(
        "Created container batch %s rows=%s "
        "started_by_person_id=%s started_by_text=%s",
        batch_id,
        len(container_ids),
        person_id,
        person_text,
    )

    return int(batch_id)


def create_controller_batch(
    conn,
    expected_signature: str,
    label_template_id: int,
) -> int | None:
    controller_ids = pending_controller_ids(conn)
    if not controller_ids:
        return None

    locked_rows = query_rows(
        conn,
        """
        SELECT
            c.controller_id,
            c.updated_by_person_id,
            c.updated_by
        FROM ref.controller AS c
        JOIN ref.label_template AS lt
          ON lt.label_template_id = c.label_template_id
        WHERE c.controller_id = ANY(%(controller_ids)s)
          AND c.print_label = true
          AND c.label_template_id = %(label_template_id)s
          AND lt.label_template_code = 'QR_24MM_HORIZONTAL'
        ORDER BY c.controller_id
        FOR UPDATE OF c;
        """,
        {
            "controller_ids": controller_ids,
            "label_template_id": label_template_id,
        },
    )
    locked_ids = [int(row["controller_id"]) for row in locked_rows]

    if locked_ids != controller_ids:
        logging.warning(
            "Controller request set changed or contains an invalid family "
            "while acquiring snapshot locks; no batch created. "
            "expected_ids=%s locked_ids=%s",
            controller_ids,
            locked_ids,
        )
        return None

    locked_signature = pending_controller_workload_signature(conn)
    if locked_signature != expected_signature:
        logging.warning(
            "Controller request/family state changed before snapshot freeze; "
            "no batch created. expected=%s locked=%s",
            expected_signature,
            locked_signature,
        )
        return None

    actors = {
        (row["updated_by_person_id"], row["updated_by"])
        for row in locked_rows
    }
    if len(actors) > 1:
        logging.warning(
            "Multiple actors detected in frozen Controller workload. "
            "Using first row."
        )

    first_row = locked_rows[0]
    person_id = first_row["updated_by_person_id"]
    person_text = first_row["updated_by"]

    if person_id is None:
        logging.warning(
            "Controller batch actor not found from frozen ref.controller rows. "
            "Falling back to service identity."
        )
        person_id = STARTED_BY_PERSON_ID
        person_text = STARTED_BY_TEXT

    batch_id = query_value(
        conn,
        """
        INSERT INTO ops.controller_label_batch (
            started_by_person_id,
            started_by_text,
            label_template_id,
            status,
            notes
        )
        VALUES (
            %(person_id)s,
            %(person_text)s,
            %(label_template_id)s,
            'PRINTING',
            'Polling service snapshot'
        )
        RETURNING controller_label_batch_id;
        """,
        {
            "person_id": person_id,
            "person_text": person_text,
            "label_template_id": label_template_id,
        },
    )

    exec_sql(
        conn,
        load_sql("controller_snapshot_v4.sql"),
        {
            "batch_id": batch_id,
            "controller_ids": controller_ids,
        },
    )

    row_count = int(query_value(
        conn,
        """
        SELECT COUNT(*)
        FROM ops.controller_label_batch_item
        WHERE controller_label_batch_id = %(batch_id)s;
        """,
        {"batch_id": batch_id},
    ) or 0)

    if row_count != len(controller_ids):
        raise RuntimeError(
            f"Controller snapshot row count mismatch: expected "
            f"{len(controller_ids)}, created {row_count}. "
            "Transaction must roll back."
        )

    logging.info(
        "Created Controller batch %s rows=%s "
        "started_by_person_id=%s started_by_text=%s",
        batch_id,
        len(controller_ids),
        person_id,
        person_text,
    )

    return int(batch_id)

# ============================================================
# CSV EXPORT (kept for audit/debug/fallback)
# ============================================================

def write_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0

    headers = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ============================================================
# b-PAC HELPERS
# ============================================================
def create_bpac_document():
    return win32com.client.Dispatch("bpac.Document")


def get_required_object(doc, object_name: str):
    obj = doc.GetObject(object_name)
    if obj is None:
        raise RuntimeError(
            f"Template object '{object_name}' was not found. "
            f"Check the LBX template object names."
        )
    return obj


def get_optional_object(doc, object_name: str):
    obj = doc.GetObject(object_name)
    return obj


def finish_bpac_document(doc, batch_log_path: Path) -> None:
    """
    b-PAC behaves oddly in Python on this machine:
    EndPrint and Close appear to act like properties instead of clean methods.

    Accessing them without parentheses is the least-bad known behavior right now.
    """
    try:
        end_result = doc.EndPrint
        write_batch_log(batch_log_path, f"EndPrint result: {end_result}")
    except Exception as exc:
        write_batch_log(batch_log_path, f"WARNING EndPrint raised exception: {exc}")

    try:
        close_result = doc.Close
        write_batch_log(batch_log_path, f"Close result: {close_result}")
    except Exception as exc:
        write_batch_log(batch_log_path, f"WARNING Close raised exception: {exc}")

def log_media_status(doc, batch_log_path: Path) -> None:
    """
    Log template media and currently loaded printer media.
    """
    try:
        template_media = doc.GetMediaName
    except Exception as exc:
        template_media = f"<error reading template media: {exc}>"

    try:
        printer_media = doc.Printer.GetMediaName
    except Exception as exc:
        printer_media = f"<error reading printer media: {exc}>"

    write_batch_log(batch_log_path, f"Template media: {template_media}")
    write_batch_log(batch_log_path, f"Printer media : {printer_media}")

# ============================================================
# WINDOWS PRINT QUEUE HELPERS
# ============================================================

def get_print_jobs(printer_name: str) -> list[dict[str, Any]]:
    handle = None
    try:
        handle = win32print.OpenPrinter(printer_name)
        return list(win32print.EnumJobs(handle, 0, 999, 1))
    finally:
        if handle is not None:
            win32print.ClosePrinter(handle)

# 26-03-26 gal
def summarize_print_jobs(jobs: list[dict[str, Any]]) -> str:
    if not jobs:
        return "<empty>"

    parts: list[str] = []
    for job in jobs:
        status = job.get("Status", 0)
        decoded = decode_spooler_status(status)

        parts.append(
            f"JobId={job.get('JobId')} "
            f"Document='{job.get('pDocument')}' "
            f"Status={status} ({decoded})"
        )

    return "; ".join(parts)


def create_spooler_job_observer(
    printer_name: str,
    known_job_ids: set[int],
    expected_document: str,
    batch_log_path: Path,
) -> SpoolerJobObserver:
    """Build the observer that must be started before ``StartPrint``."""
    return SpoolerJobObserver(
        printer_name=printer_name,
        known_job_ids=known_job_ids,
        expected_document=expected_document,
        read_jobs=get_print_jobs,
        log_message=lambda message: write_batch_log(batch_log_path, message),
    )


def create_brother_status_sampler(
    *,
    family: dict[str, Any],
    batch_log_path: Path,
    context: str,
) -> BrotherStatusSampler | None:
    """Build the observation-only PT-P950NW status sampler."""
    if not STATUS_SAMPLER_ENABLED:
        write_batch_log(
            batch_log_path,
            f"BROTHER_STATUS_SAMPLER_DISABLED context='{context}'",
        )
        return None

    if family["printer_key"] != "pt_p950nw":
        write_batch_log(
            batch_log_path,
            "BROTHER_STATUS_SAMPLER_UNSUPPORTED "
            f"context='{context}' printer_key='{family['printer_key']}'",
        )
        return None

    printer = family["printer"]
    return BrotherStatusSampler(
        context=context,
        read_status=lambda: query_brother_snmp_status(
            host=printer["host"],
            oid=SNMP_OID,
            community=SNMP_COMMUNITY,
            port=SNMP_PORT,
            timeout=SNMP_TIMEOUT_SECONDS,
        ),
        log_message=lambda message: write_batch_log(batch_log_path, message),
        poll_interval_seconds=STATUS_SAMPLE_INTERVAL_SECONDS,
        heartbeat_seconds=STATUS_HEARTBEAT_SECONDS,
        startup_timeout_seconds=SNMP_TIMEOUT_SECONDS + 2.0,
        stop_timeout_seconds=SNMP_TIMEOUT_SECONDS + 2.0,
    )


def start_print_observers(
    *,
    family: dict[str, Any],
    printer_name: str,
    known_job_ids: set[int],
    expected_document: str,
    batch_log_path: Path,
    context: str,
) -> tuple[SpoolerJobObserver, BrotherStatusSampler | None]:
    """Start status and spooler observation before b-PAC submission."""
    status_sampler = create_brother_status_sampler(
        family=family,
        batch_log_path=batch_log_path,
        context=context,
    )
    spooler_observer = create_spooler_job_observer(
        printer_name=printer_name,
        known_job_ids=known_job_ids,
        expected_document=expected_document,
        batch_log_path=batch_log_path,
    )

    if status_sampler is not None:
        status_sampler.start()

    try:
        spooler_observer.start()
    except Exception:
        if status_sampler is not None:
            status_sampler.stop()
        raise

    return spooler_observer, status_sampler


def stop_print_observers(
    *,
    spooler_observer: SpoolerJobObserver,
    status_sampler: BrotherStatusSampler | None,
    spooler_completed: bool,
) -> None:
    """Stop both observers while preserving a post-spooler status window."""
    spooler_observer.stop()
    if status_sampler is not None:
        status_sampler.stop(
            post_observation_seconds=(
                STATUS_POST_SPOOLER_SECONDS
                if spooler_completed
                else 0.0
            )
        )

# ============================================================
# DISPLAY PRINTING
# ============================================================


def get_display_batch_family_code(conn, display_batch_id: int) -> str:
    family_code = query_value(
        conn,
        """
        SELECT lt.label_template_code
        FROM ops.display_label_batch b
        JOIN ref.label_template lt
          ON lt.label_template_id = b.label_template_id
        WHERE b.display_label_batch_id = %(batch_id)s;
        """,
        {"batch_id": display_batch_id},
    )

    if not family_code:
        raise RuntimeError(
            f"Display batch {display_batch_id} has no resolvable label family."
        )

    return str(family_code)


def print_display_rows_with_template(
    rows: list[dict[str, Any]],
    family: dict[str, Any],
    template_path: Path,
    batch_log_path: Path,
    variant: str,
) -> None:
    if not rows:
        return

    printer_name = family["printer"]["queue_name"]

    baseline_jobs = get_print_jobs(printer_name)
    baseline_job_ids = {
        int(job.get("JobId"))
        for job in baseline_jobs
    }

    write_batch_log(
        batch_log_path,
        f"Baseline queue before {variant} Display print: "
        f"{summarize_print_jobs(baseline_jobs)}",
    )

    doc = create_bpac_document()

    write_batch_log(
        batch_log_path,
        f"Opening Display template family={family['code']} "
        f"variant={variant}: {template_path}",
    )

    opened = doc.Open(str(template_path))
    write_batch_log(batch_log_path, f"Template opened: {opened}")

    if not opened:
        raise RuntimeError(
            f"b-PAC could not open Display template: {template_path}"
        )

    set_printer_ok = doc.SetPrinter(printer_name, True)
    write_batch_log(
        batch_log_path,
        f"SetPrinter('{printer_name}') = {set_printer_ok}",
    )

    if not set_printer_ok:
        raise RuntimeError(
            f"b-PAC could not set Display printer '{printer_name}'."
        )

    log_media_status(doc, batch_log_path)

    obj_line1 = get_required_object(doc, DISPLAY_OBJ_LINE1)
    obj_qr = get_required_object(doc, DISPLAY_OBJ_QR)

    obj_line2 = None
    if variant == "TWO_LINE":
        obj_line2 = get_required_object(doc, DISPLAY_OBJ_LINE2)

    write_batch_log(
        batch_log_path,
        f"Resolved Display objects family={family['code']} "
        f"variant={variant}: "
        f"line1={DISPLAY_OBJ_LINE1}, "
        f"line2={DISPLAY_OBJ_LINE2 if obj_line2 is not None else 'NOT USED'}, "
        f"qr={DISPLAY_OBJ_QR}",
    )

    spooler_observer, status_sampler = start_print_observers(
        family=family,
        printer_name=printer_name,
        known_job_ids=baseline_job_ids,
        expected_document=template_path.stem,
        batch_log_path=batch_log_path,
        context=(
            f"Display family={family['code']} variant={variant} "
            f"labels={len(rows)}"
        ),
    )
    spooler_completed = False

    try:
        doc.StartPrint("", PRINT_FLAGS)
        write_batch_log(
            batch_log_path,
            f"StartPrint called with flags={hex(PRINT_FLAGS)}",
        )

        for idx, row in enumerate(rows, start=1):
            obj_line1.Text = row.get("line1", "") or ""
            obj_qr.Text = row.get("qr_url", "") or ""

            if obj_line2 is not None:
                obj_line2.Text = row.get("line2", "") or ""

            result = doc.PrintOut(1, 0)

            write_batch_log(
                batch_log_path,
                f"Queued Display label {idx}/{len(rows)} "
                f"family={family['code']} variant={variant} "
                f"display_id={row.get('display_id')} result={result} "
                f"line1={row.get('line1')} line2={row.get('line2')}",
            )

            if not result:
                raise RuntimeError(
                    f"Display PrintOut failed on row {idx} "
                    f"display_id={row.get('display_id')}"
                )

        finish_bpac_document(doc, batch_log_path)
        spooler_observer.wait_for_completion()
        spooler_completed = True
    finally:
        stop_print_observers(
            spooler_observer=spooler_observer,
            status_sampler=status_sampler,
            spooler_completed=spooler_completed,
        )


def print_display_batch(
    rows: list[dict[str, Any]],
    batch_log_path: Path,
    family_code: str,
) -> None:
    """
    Route one homogeneous Display family to its physical one-line and
    two-line LBX templates.
    """
    if not rows:
        write_batch_log(batch_log_path, "No Display rows to print.")
        return

    family = LABEL_FAMILIES.get(family_code)
    if family is None:
        raise RuntimeError(
            f"No LabelPrintService runtime mapping exists for "
            f"Display family '{family_code}'."
        )

    if family_code not in (
        "QR_36MM_HORIZONTAL",
        "QR_24MM_HORIZONTAL",
    ):
        raise RuntimeError(
            f"Label family '{family_code}' is not an accepted "
            f"Display identity-label family."
        )

    one_line_rows = [
        row for row in rows
        if not (row.get("line2") or "").strip()
    ]

    two_line_rows = [
        row for row in rows
        if (row.get("line2") or "").strip()
    ]

    write_batch_log(
        batch_log_path,
        f"Display render plan family={family_code}: "
        f"one_line={len(one_line_rows)} "
        f"two_line={len(two_line_rows)}",
    )

    if one_line_rows:
        template = family["template_1_line"]
        if template is None:
            raise RuntimeError(
                f"Family '{family_code}' has no one-line template."
            )

        print_display_rows_with_template(
            rows=one_line_rows,
            family=family,
            template_path=template,
            batch_log_path=batch_log_path,
            variant="ONE_LINE",
        )

    if two_line_rows:
        template = family["template_2_line"]
        if template is None:
            raise RuntimeError(
                f"Family '{family_code}' has no two-line template."
            )

        print_display_rows_with_template(
            rows=two_line_rows,
            family=family,
            template_path=template,
            batch_log_path=batch_log_path,
            variant="TWO_LINE",
        )


# ============================================================
# CONTAINER PRINTING
# ============================================================

def duplicate_container_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Each selected container needs TWO labels.
    We duplicate the logical row list in memory before printing.
    """
    duplicated: list[dict[str, Any]] = []
    for row in rows:
        duplicated.append(dict(row))
        duplicated.append(dict(row))
    return duplicated

def print_container_batch(
    rows: list[dict[str, Any]],
    template_path: Path,
    batch_log_path: Path,
    orientation: str,
) -> None:
    """
    Print Container labels using the accepted generic QR one-line
    template contract: objLine1 + objQr.
    """
    if not rows:
        write_batch_log(
            batch_log_path,
            f"No {orientation.lower()} Container rows to print.",
        )
        return

    normalized_orientation = orientation.upper()
    if normalized_orientation == "VERTICAL":
        family_code = "QR_36MM_VERTICAL"
    elif normalized_orientation == "HORIZONTAL":
        family_code = "QR_36MM_HORIZONTAL"
    else:
        raise RuntimeError(
            f"Unsupported Container label orientation: {orientation}"
        )

    family = LABEL_FAMILIES[family_code]
    printer_name = family["printer"]["queue_name"]

    rows_to_print = duplicate_container_rows(rows)
    write_batch_log(
        batch_log_path,
        f"{normalized_orientation} Container rows duplicated for quantity 2. "
        f"Original={len(rows)} Effective={len(rows_to_print)}",
    )

    baseline_jobs = get_print_jobs(printer_name)
    baseline_job_ids = {
        int(job.get("JobId"))
        for job in baseline_jobs
    }
    write_batch_log(
        batch_log_path,
        f"Baseline queue before {normalized_orientation.lower()} Container "
        f"print: {summarize_print_jobs(baseline_jobs)}",
    )

    doc = create_bpac_document()

    write_batch_log(
        batch_log_path,
        f"Opening {normalized_orientation.lower()} Container template: "
        f"{template_path}",
    )
    opened = doc.Open(str(template_path))
    write_batch_log(batch_log_path, f"Template opened: {opened}")
    if not opened:
        raise RuntimeError(
            f"b-PAC could not open the {normalized_orientation.lower()} "
            "Container template."
        )

    set_printer_ok = doc.SetPrinter(printer_name, True)
    write_batch_log(
        batch_log_path,
        f"SetPrinter('{printer_name}') = {set_printer_ok}",
    )
    if not set_printer_ok:
        raise RuntimeError(
            f"b-PAC could not set the {normalized_orientation.lower()} "
            "Container printer."
        )

    log_media_status(doc, batch_log_path)

    obj_line1 = get_required_object(doc, CONTAINER_OBJ_LINE1)
    obj_qr = get_required_object(doc, CONTAINER_OBJ_QR)

    write_batch_log(
        batch_log_path,
        f"Resolved Container objects: line1={CONTAINER_OBJ_LINE1}, "
        f"qr={CONTAINER_OBJ_QR}",
    )

    spooler_observer, status_sampler = start_print_observers(
        family=family,
        printer_name=printer_name,
        known_job_ids=baseline_job_ids,
        expected_document=template_path.stem,
        batch_log_path=batch_log_path,
        context=(
            f"Container family={family_code} "
            f"orientation={normalized_orientation} "
            f"labels={len(rows_to_print)}"
        ),
    )
    spooler_completed = False

    try:
        doc.StartPrint("", PRINT_FLAGS)
        write_batch_log(
            batch_log_path,
            f"StartPrint called with flags={hex(PRINT_FLAGS)}",
        )

        for idx, row in enumerate(rows_to_print, start=1):
            obj_line1.Text = row.get("container_label", "") or ""
            obj_qr.Text = row.get("qr_url", "") or ""

            result = doc.PrintOut(1, 0)
            write_batch_log(
                batch_log_path,
                f"Queued {normalized_orientation.lower()} Container label "
                f"{idx}/{len(rows_to_print)} "
                f"container_id={row.get('container_id')} result={result} "
                f"label={row.get('container_label')}",
            )

            if not result:
                raise RuntimeError(
                    f"{normalized_orientation} Container PrintOut failed on "
                    f"row {idx} container_id={row.get('container_id')}"
                )

        finish_bpac_document(doc, batch_log_path)
        spooler_observer.wait_for_completion()
        spooler_completed = True
    finally:
        stop_print_observers(
            spooler_observer=spooler_observer,
            status_sampler=status_sampler,
            spooler_completed=spooler_completed,
        )


# ============================================================
# CONTROLLER PRINTING
# ============================================================

def print_controller_batch(
    rows: list[dict[str, Any]],
    batch_log_path: Path,
) -> None:
    """Print one 24 mm permanent identity label per Controller snapshot row."""
    if not rows:
        write_batch_log(batch_log_path, "No Controller rows to print.")
        return

    family = LABEL_FAMILIES[CONTROLLER_FAMILY_CODE]
    printer_name = family["printer"]["queue_name"]
    template_path = CONTROLLER_TEMPLATE
    if template_path is None:
        raise RuntimeError(
            f"Family '{CONTROLLER_FAMILY_CODE}' has no one-line template."
        )

    baseline_jobs = get_print_jobs(printer_name)
    baseline_job_ids = {
        int(job.get("JobId"))
        for job in baseline_jobs
    }
    write_batch_log(
        batch_log_path,
        "Baseline queue before Controller print: "
        f"{summarize_print_jobs(baseline_jobs)}",
    )

    doc = create_bpac_document()
    write_batch_log(
        batch_log_path,
        f"Opening Controller template: {template_path}",
    )

    opened = doc.Open(str(template_path))
    write_batch_log(batch_log_path, f"Template opened: {opened}")
    if not opened:
        raise RuntimeError(
            f"b-PAC could not open Controller template: {template_path}"
        )

    set_printer_ok = doc.SetPrinter(printer_name, True)
    write_batch_log(
        batch_log_path,
        f"SetPrinter('{printer_name}') = {set_printer_ok}",
    )
    if not set_printer_ok:
        raise RuntimeError(
            f"b-PAC could not set Controller printer '{printer_name}'."
        )

    log_media_status(doc, batch_log_path)

    obj_line1 = get_required_object(doc, CONTROLLER_OBJ_LINE1)
    obj_qr = get_required_object(doc, CONTROLLER_OBJ_QR)
    write_batch_log(
        batch_log_path,
        f"Resolved Controller objects: line1={CONTROLLER_OBJ_LINE1}, "
        f"qr={CONTROLLER_OBJ_QR}",
    )

    spooler_observer, status_sampler = start_print_observers(
        family=family,
        printer_name=printer_name,
        known_job_ids=baseline_job_ids,
        expected_document=template_path.stem,
        batch_log_path=batch_log_path,
        context=f"Controller family={family['code']} labels={len(rows)}",
    )
    spooler_completed = False

    try:
        doc.StartPrint("", PRINT_FLAGS)
        write_batch_log(
            batch_log_path,
            f"StartPrint called with flags={hex(PRINT_FLAGS)}",
        )

        for idx, row in enumerate(rows, start=1):
            obj_line1.Text = row.get("line1", "") or ""
            obj_qr.Text = row.get("qr_url", "") or ""

            result = doc.PrintOut(1, 0)
            write_batch_log(
                batch_log_path,
                f"Queued Controller label {idx}/{len(rows)} "
                f"controller_id={row.get('controller_id')} result={result} "
                f"line1={row.get('line1')}",
            )
            if not result:
                raise RuntimeError(
                    f"Controller PrintOut failed on row {idx} "
                    f"controller_id={row.get('controller_id')}"
                )

        finish_bpac_document(doc, batch_log_path)
        spooler_observer.wait_for_completion()
        spooler_completed = True
    finally:
        stop_print_observers(
            spooler_observer=spooler_observer,
            status_sampler=status_sampler,
            spooler_completed=spooler_completed,
        )


# ============================================================
# FAILURE HANDLING HELPERS
# ============================================================

def mark_display_batch_failed(conn, batch_id: int, reason: str) -> None:
    exec_sql(
        conn,
        """
        UPDATE ops.display_label_batch
        SET status = 'FAILED',
            notes = COALESCE(notes, '') || E'\nFAILED: ' || %(reason)s
        WHERE display_label_batch_id = %(batch_id)s;
        """,
        {"batch_id": batch_id, "reason": reason[:1000]},
    )


def mark_container_batch_failed(conn, batch_id: int, reason: str) -> None:
    exec_sql(
        conn,
        """
        UPDATE ops.container_label_batch
        SET status = 'FAILED',
            notes = COALESCE(notes, '') || E'\nFAILED: ' || %(reason)s
        WHERE container_label_batch_id = %(batch_id)s;
        """,
        {"batch_id": batch_id, "reason": reason[:1000]},
    )


def mark_controller_batch_failed(conn, batch_id: int, reason: str) -> None:
    exec_sql(
        conn,
        """
        UPDATE ops.controller_label_batch
        SET status = 'FAILED',
            notes = COALESCE(notes, '') || E'\nFAILED: ' || %(reason)s
        WHERE controller_label_batch_id = %(batch_id)s;
        """,
        {"batch_id": batch_id, "reason": reason[:1000]},
    )

# 03-26-26 not to duplicate failed batches
def get_failed_display_batch_id(conn):
    with conn.cursor() as cur:
        cur.execute("""
            WITH latest_failed AS (
                SELECT display_label_batch_id
                FROM ops.display_label_batch
                WHERE status = 'FAILED'
                ORDER BY display_label_batch_id DESC
                LIMIT 1
            ),
            latest_completed AS (
                SELECT COALESCE(MAX(display_label_batch_id), 0) AS completed_batch_id
                FROM ops.display_label_batch
                WHERE status = 'COMPLETED'
            )
            SELECT f.display_label_batch_id
            FROM latest_failed f
            CROSS JOIN latest_completed c
            WHERE f.display_label_batch_id > c.completed_batch_id;
        """)
        row = cur.fetchone()
        return row[0] if row else None


def get_failed_container_batch_id(conn):
    with conn.cursor() as cur:
        cur.execute("""
            WITH latest_failed AS (
                SELECT container_label_batch_id
                FROM ops.container_label_batch
                WHERE status = 'FAILED'
                ORDER BY container_label_batch_id DESC
                LIMIT 1
            ),
            latest_completed AS (
                SELECT COALESCE(MAX(container_label_batch_id), 0) AS completed_batch_id
                FROM ops.container_label_batch
                WHERE status = 'COMPLETED'
            )
            SELECT f.container_label_batch_id
            FROM latest_failed f
            CROSS JOIN latest_completed c
            WHERE f.container_label_batch_id > c.completed_batch_id;
        """)
        row = cur.fetchone()
        return row[0] if row else None


def get_failed_controller_batch_id(conn):
    if not CONTROLLER_POLLING_ENABLED:
        return None

    with conn.cursor() as cur:
        cur.execute("""
            WITH latest_failed AS (
                SELECT controller_label_batch_id
                FROM ops.controller_label_batch
                WHERE status = 'FAILED'
                ORDER BY controller_label_batch_id DESC
                LIMIT 1
            ),
            latest_completed AS (
                SELECT COALESCE(MAX(controller_label_batch_id), 0)
                    AS completed_batch_id
                FROM ops.controller_label_batch
                WHERE status = 'COMPLETED'
            )
            SELECT f.controller_label_batch_id
            FROM latest_failed AS f
            CROSS JOIN latest_completed AS c
            WHERE f.controller_label_batch_id > c.completed_batch_id;
        """)
        row = cur.fetchone()
        return row[0] if row else None
# ============================================================
# MAIN BATCH PROCESSING
# ============================================================

def process_display(conn, display_batch_id: int) -> None:
    rows = query_rows(
        conn,
        load_sql("display_export.sql"),
        {"batch_id": display_batch_id},
    )
    write_csv(DISPLAY_CSV, rows)

    family_code = get_display_batch_family_code(
        conn,
        display_batch_id,
    )

    batch_log_path = new_batch_log_path("display", display_batch_id)
    write_batch_log(
        batch_log_path,
        f"Display batch {display_batch_id} created.",
    )
    write_batch_log(
        batch_log_path,
        f"Display family: {family_code}",
    )
    write_batch_log(
        batch_log_path,
        f"Display CSV written: {DISPLAY_CSV}",
    )
    write_batch_log(
        batch_log_path,
        f"Display row count: {len(rows)}",
    )

    print_display_batch(
        rows,
        batch_log_path,
        family_code,
    )

    exec_sql(
        conn,
        load_sql("display_finalized.sql"),
        {"batch_id": display_batch_id},
    )
    write_batch_log(
        batch_log_path,
        "Display batch finalized successfully.",
    )
    logging.info(
        "Display batch %s completed successfully.",
        display_batch_id,
    )


def process_container(conn, container_batch_id: int) -> None:
    vert_rows = query_rows(conn, load_sql("container_export_vertical.sql"), {"batch_id": container_batch_id})
    horz_rows = query_rows(conn, load_sql("container_export_horizontal.sql"), {"batch_id": container_batch_id})

    write_csv(CONTAINER_VERTICAL_CSV, vert_rows)
    write_csv(CONTAINER_HORIZONTAL_CSV, horz_rows)

    batch_log_path = new_batch_log_path("container", container_batch_id)
    write_batch_log(batch_log_path, f"Container batch {container_batch_id} created.")
    write_batch_log(batch_log_path, f"Vertical container CSV written: {CONTAINER_VERTICAL_CSV}")
    write_batch_log(batch_log_path, f"Horizontal container CSV written: {CONTAINER_HORIZONTAL_CSV}")
    write_batch_log(batch_log_path, f"Vertical row count: {len(vert_rows)}")
    write_batch_log(batch_log_path, f"Horizontal row count: {len(horz_rows)}")

    if vert_rows:
        print_container_batch(
            rows=vert_rows,
            template_path=CONTAINER_VERTICAL_TEMPLATE,
            batch_log_path=batch_log_path,
            orientation="VERTICAL",
        )

    if horz_rows:
        print_container_batch(
            rows=horz_rows,
            template_path=CONTAINER_HORIZONTAL_TEMPLATE,
            batch_log_path=batch_log_path,
            orientation="HORIZONTAL",
        )

    exec_sql(conn, load_sql("container_finalized.sql"), {"batch_id": container_batch_id})
    write_batch_log(batch_log_path, "Container batch finalized successfully.")
    logging.info("Container batch %s completed successfully.", container_batch_id)


def process_controller(conn, controller_batch_id: int) -> None:
    rows = query_rows(
        conn,
        load_sql("controller_export.sql"),
        {"batch_id": controller_batch_id},
    )
    write_csv(CONTROLLER_CSV, rows)

    batch_log_path = new_batch_log_path("controller", controller_batch_id)
    write_batch_log(
        batch_log_path,
        f"Controller batch {controller_batch_id} created.",
    )
    write_batch_log(
        batch_log_path,
        f"Controller CSV written: {CONTROLLER_CSV}",
    )
    write_batch_log(
        batch_log_path,
        f"Controller row count: {len(rows)}",
    )

    print_controller_batch(rows, batch_log_path)

    exec_sql(
        conn,
        load_sql("controller_finalized.sql"),
        {"batch_id": controller_batch_id},
    )
    write_batch_log(
        batch_log_path,
        "Controller batch finalized successfully.",
    )
    logging.info(
        "Controller batch %s completed successfully.",
        controller_batch_id,
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main() -> None:
    print_banner()

    startup_health_check()

    # Cancel suppresses repeated dialogs for the exact same pending
    # request set until the set changes or the service restarts.
    cancelled_preflight_signature: str | None = None

    while True:
        try:
            logging.info("Poll tick - checking for pending labels.")
            if lock_exists():
                time.sleep(POLL_SECONDS)
                continue

            create_lock()

            with db_connect() as conn:
                conn.autocommit = False

                # --------------------------------------------------
                # Step 1: Check whether there is any work pending
                # --------------------------------------------------
                display_families = pending_display_families(conn)
                display_pending = sum(
                    int(row["pending_count"])
                    for row in display_families
                )
                container_pending = pending_container_count(conn)
                controller_pending = pending_controller_count(conn)

                logging.info(
                    "Pending labels - displays=%s containers=%s controllers=%s "
                    "display_families=%s controller_polling_enabled=%s",
                    display_pending,
                    container_pending,
                    controller_pending,
                    [
                        (
                            row["label_template_id"],
                            row["label_template_code"],
                            row["pending_count"],
                        )
                        for row in display_families
                    ],
                    CONTROLLER_POLLING_ENABLED,
                )

                if len(display_families) > 1:
                    family_msg = (
                        "Multiple pending Display label families detected. "
                        "No Display batch will be created until v4 family routing "
                        "selects one compatible workload: "
                        + ", ".join(
                            f'{row["label_template_code"]}={row["pending_count"]}'
                            for row in display_families
                        )
                    )
                    logging.error(family_msg)
                    print(family_msg)
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                selected_display_family = (
                    display_families[0]
                    if display_families
                    else None
                )

                if (
                    display_pending == 0
                    and container_pending == 0
                    and controller_pending == 0
                ):
                    cancelled_preflight_signature = None
                    logging.info("No pending labels. Service idle.")
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                # --------------------------------------------------
                # Step 1a: Harden the main loop against storms and stuck queue
                # --------------------------------------------------
                existing_display_batch_id = active_display_batch_id(conn)
                existing_container_batch_id = active_container_batch_id(conn)
                existing_controller_batch_id = active_controller_batch_id(conn)

                if (
                    existing_display_batch_id
                    or existing_container_batch_id
                    or existing_controller_batch_id
                ):
                    logging.warning(
                        "Active PRINTING batch already exists. "
                        "display_batch_id=%s container_batch_id=%s "
                        "controller_batch_id=%s",
                        existing_display_batch_id,
                        existing_container_batch_id,
                        existing_controller_batch_id,
                    )
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                # --------------------------------------------------
                # Step 1b: Block retry if FAILED batch exists
                # --------------------------------------------------
                failed_display_batch_id = get_failed_display_batch_id(conn)
                failed_container_batch_id = get_failed_container_batch_id(conn)
                failed_controller_batch_id = get_failed_controller_batch_id(conn)

                if (
                    failed_display_batch_id
                    or failed_container_batch_id
                    or failed_controller_batch_id
                ):
                    logging.error(
                        "FAILED batch exists - blocking retry. "
                        "display_batch_id=%s container_batch_id=%s "
                        "controller_batch_id=%s",
                        failed_display_batch_id,
                        failed_container_batch_id,
                        failed_controller_batch_id,
                    )
                    print(
                        f"FAILED batch exists - manual intervention required. "
                        f"display_batch_id={failed_display_batch_id} "
                        f"container_batch_id={failed_container_batch_id} "
                        f"controller_batch_id={failed_controller_batch_id}"
                    )
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                # --------------------------------------------------
                # Step 2: Resolve exact physical workload BEFORE batch creation
                # --------------------------------------------------
                selected_family_config = None
                selected_printer_name = None
                required_display_templates: list[
                    tuple[Path, tuple[str, ...]]
                ] = []

                if display_pending > 0:
                    display_plan = pending_display_preflight_plan(
                        conn,
                        int(selected_display_family["label_template_id"]),
                    )
                    if display_plan is None:
                        logging.warning(
                            "Selected Display workload disappeared before "
                            "preflight planning; restarting poll."
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    family_code = str(
                        display_plan["label_template_code"]
                    )

                    if family_code not in (
                        "QR_36MM_HORIZONTAL",
                        "QR_24MM_HORIZONTAL",
                    ):
                        family_msg = (
                            f"Pending Display family '{family_code}' is not "
                            "an accepted Display identity-label family."
                        )
                        logging.error(family_msg)
                        print(family_msg)
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    selected_family_config = LABEL_FAMILIES.get(
                        family_code
                    )

                    if selected_family_config is None:
                        family_msg = (
                            f"No LabelPrintService runtime mapping exists "
                            f"for Display family '{family_code}'."
                        )
                        logging.error(family_msg)
                        print(family_msg)
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    selected_printer_name = (
                        selected_family_config["printer"]["queue_name"]
                    )

                    if int(
                        display_plan["one_line_count"]
                    ) > 0:
                        template = selected_family_config[
                            "template_1_line"
                        ]
                        if template is None:
                            raise RuntimeError(
                                f"Family '{family_code}' has pending "
                                "one-line Displays but no one-line template."
                            )

                        required_display_templates.append(
                            (
                                template,
                                (
                                    DISPLAY_OBJ_LINE1,
                                    DISPLAY_OBJ_QR,
                                ),
                            )
                        )

                    if int(
                        display_plan["two_line_count"]
                    ) > 0:
                        template = selected_family_config[
                            "template_2_line"
                        ]
                        if template is None:
                            raise RuntimeError(
                                f"Family '{family_code}' has pending "
                                "two-line Displays but no two-line template."
                            )

                        required_display_templates.append(
                            (
                                template,
                                (
                                    DISPLAY_OBJ_LINE1,
                                    DISPLAY_OBJ_LINE2,
                                    DISPLAY_OBJ_QR,
                                ),
                            )
                        )

                    display_preflight_signature = str(
                        display_plan["workload_signature"]
                    )

                    if (
                        cancelled_preflight_signature
                        == display_preflight_signature
                    ):
                        logging.info(
                            "Preflight remains cancelled for unchanged "
                            "Display request set; waiting for request change "
                            "or service restart. signature=%s",
                            display_preflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    display_preflight_passed = (
                        run_selected_workload_preflight(
                            workload_name=(
                                f"Display labels ({family_code})"
                            ),
                            family=selected_family_config,
                            template_specs=required_display_templates,
                            sql_filenames=(
                                "display_snapshot_v4.sql",
                                "display_export.sql",
                                "display_finalized.sql",
                            ),
                            csv_paths=(DISPLAY_CSV,),
                        )
                    )

                    if not display_preflight_passed:
                        cancelled_preflight_signature = (
                            display_preflight_signature
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    display_postflight_signature = (
                        pending_display_workload_signature(
                            conn,
                            int(
                                selected_display_family[
                                    "label_template_id"
                                ]
                            ),
                        )
                    )
                    if (
                        display_postflight_signature
                        != display_preflight_signature
                    ):
                        logging.warning(
                            "Display pending workload changed during preflight; "
                            "no batch will be created. before=%s after=%s",
                            display_preflight_signature,
                            display_postflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    cancelled_preflight_signature = None

                    if container_pending > 0:
                        logging.warning(
                            "Container labels are also pending. This checkpoint "
                            "will process the Display batch only and leave "
                            "Container requests untouched."
                        )

                elif container_pending > 0:
                    container_plan = pending_container_preflight_plan(conn)
                    if int(container_plan["pending_count"]) == 0:
                        logging.warning(
                            "Pending Container workload disappeared before "
                            "preflight planning; restarting poll."
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    container_orientations: list[dict[str, Any]] = []
                    if int(container_plan["vertical_count"]) > 0:
                        container_orientations.append(
                            {
                                "label_orientation": "VERTICAL",
                                "pending_count": int(
                                    container_plan["vertical_count"]
                                ),
                            }
                        )
                    if int(container_plan["horizontal_count"]) > 0:
                        container_orientations.append(
                            {
                                "label_orientation": "HORIZONTAL",
                                "pending_count": int(
                                    container_plan["horizontal_count"]
                                ),
                            }
                        )

                    container_printer_name = None
                    required_container_templates: list[
                        tuple[Path, tuple[str, ...]]
                    ] = []

                    for orientation_row in container_orientations:
                        orientation = str(
                            orientation_row["label_orientation"]
                        ).upper()

                        if orientation == "VERTICAL":
                            container_family_code = "QR_36MM_VERTICAL"
                        elif orientation == "HORIZONTAL":
                            container_family_code = "QR_36MM_HORIZONTAL"
                        else:
                            raise RuntimeError(
                                f"Unsupported pending Container orientation: "
                                f"{orientation}"
                            )

                        container_family = LABEL_FAMILIES[
                            container_family_code
                        ]
                        template = container_family["template_1_line"]
                        if template is None:
                            raise RuntimeError(
                                f"Container family '{container_family_code}' "
                                "has no one-line template."
                            )

                        queue_name = container_family["printer"][
                            "queue_name"
                        ]
                        if container_printer_name is None:
                            container_printer_name = queue_name
                        elif container_printer_name != queue_name:
                            raise RuntimeError(
                                "Pending Container orientations resolve to "
                                "different printer queues; refusing to create "
                                "one execution batch."
                            )

                        required_container_templates.append(
                            (
                                template,
                                (
                                    CONTAINER_OBJ_LINE1,
                                    CONTAINER_OBJ_QR,
                                ),
                            )
                        )

                    container_preflight_signature = str(
                        container_plan["workload_signature"]
                    )

                    if (
                        cancelled_preflight_signature
                        == container_preflight_signature
                    ):
                        logging.info(
                            "Preflight remains cancelled for unchanged "
                            "Container request set; waiting for request change "
                            "or service restart. signature=%s",
                            container_preflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    container_preflight_passed = (
                        run_selected_workload_preflight(
                            workload_name="Container labels (36 mm)",
                            family=LABEL_FAMILIES[
                                "QR_36MM_HORIZONTAL"
                            ],
                            template_specs=required_container_templates,
                            sql_filenames=(
                                "container_snapshot_v4.sql",
                                "container_export_vertical.sql",
                                "container_export_horizontal.sql",
                                "container_finalized.sql",
                            ),
                            csv_paths=(
                                CONTAINER_VERTICAL_CSV,
                                CONTAINER_HORIZONTAL_CSV,
                            ),
                        )
                    )

                    if not container_preflight_passed:
                        cancelled_preflight_signature = (
                            container_preflight_signature
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    container_postflight_signature = (
                        pending_container_workload_signature(conn)
                    )
                    if (
                        container_postflight_signature
                        != container_preflight_signature
                    ):
                        logging.warning(
                            "Container pending workload changed during preflight; "
                            "no batch will be created. before=%s after=%s",
                            container_preflight_signature,
                            container_postflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    cancelled_preflight_signature = None

                elif controller_pending > 0:
                    controller_plan = pending_controller_preflight_plan(conn)
                    if int(controller_plan["pending_count"]) == 0:
                        logging.warning(
                            "Pending Controller workload disappeared before "
                            "preflight planning; restarting poll."
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    invalid_family_count = int(
                        controller_plan["invalid_family_count"]
                    )
                    if invalid_family_count > 0:
                        logging.error(
                            "Pending Controller requests include %s row(s) "
                            "without the required QR_24MM_HORIZONTAL family. "
                            "No Controller batch will be created.",
                            invalid_family_count,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    if int(controller_plan["eligible_count"]) != int(
                        controller_plan["pending_count"]
                    ):
                        raise RuntimeError(
                            "Controller preflight plan did not account for every "
                            "pending request."
                        )

                    controller_label_template_id = int(
                        controller_plan["label_template_id"]
                    )
                    controller_family = LABEL_FAMILIES[
                        CONTROLLER_FAMILY_CODE
                    ]
                    if CONTROLLER_TEMPLATE is None:
                        raise RuntimeError(
                            f"Family '{CONTROLLER_FAMILY_CODE}' has no "
                            "one-line template."
                        )

                    controller_preflight_signature = str(
                        controller_plan["workload_signature"]
                    )

                    if (
                        cancelled_preflight_signature
                        == controller_preflight_signature
                    ):
                        logging.info(
                            "Preflight remains cancelled for unchanged "
                            "Controller request set; waiting for request change "
                            "or service restart. signature=%s",
                            controller_preflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    controller_preflight_passed = (
                        run_selected_workload_preflight(
                            workload_name="Controller labels (24 mm)",
                            family=controller_family,
                            template_specs=[
                                (
                                    CONTROLLER_TEMPLATE,
                                    (
                                        CONTROLLER_OBJ_LINE1,
                                        CONTROLLER_OBJ_QR,
                                    ),
                                )
                            ],
                            sql_filenames=(
                                "controller_snapshot_v4.sql",
                                "controller_export.sql",
                                "controller_finalized.sql",
                            ),
                            csv_paths=(CONTROLLER_CSV,),
                        )
                    )

                    if not controller_preflight_passed:
                        cancelled_preflight_signature = (
                            controller_preflight_signature
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    controller_postflight_signature = (
                        pending_controller_workload_signature(conn)
                    )
                    if (
                        controller_postflight_signature
                        != controller_preflight_signature
                    ):
                        logging.warning(
                            "Controller pending workload changed during "
                            "preflight; no batch will be created. "
                            "before=%s after=%s",
                            controller_preflight_signature,
                            controller_postflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    cancelled_preflight_signature = None

                # --------------------------------------------------
                # Step 3: Only create batches AFTER printer passes Updated 04/16/26 for warning and loop
                # --------------------------------------------------
                display_batch_id = None
                container_batch_id = None
                controller_batch_id = None

                if display_pending > 0:
                    display_batch_id = create_display_batch(
                        conn,
                        int(selected_display_family["label_template_id"]),
                        display_postflight_signature,
                    )
                elif container_pending > 0:
                    container_batch_id = create_container_batch(
                        conn,
                        container_postflight_signature,
                    )
                elif controller_pending > 0:
                    controller_batch_id = create_controller_batch(
                        conn,
                        controller_postflight_signature,
                        controller_label_template_id,
                    )

                logging.info(
                    "Batch creation results - display_batch_id=%s "
                    "container_batch_id=%s controller_batch_id=%s",
                    display_batch_id,
                    container_batch_id,
                    controller_batch_id,
                )

                if (
                    not display_batch_id
                    and not container_batch_id
                    and not controller_batch_id
                ):
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                # --------------------------------------------------
                # Commit batch header + items BEFORE physical printing
                # so failed batches remain in the database and can be
                # marked FAILED instead of being rolled back away.
                # --------------------------------------------------
                conn.commit()
                logging.info(
                    "Batch rows committed before printing. display_batch_id=%s "
                    "container_batch_id=%s controller_batch_id=%s",
                    display_batch_id,
                    container_batch_id,
                    controller_batch_id,
                )

                try:
                    conn.autocommit = False

                    if display_batch_id:
                        process_display(conn, display_batch_id)

                    if container_batch_id:
                        process_container(conn, container_batch_id)

                    if controller_batch_id:
                        process_controller(conn, controller_batch_id)

                    conn.commit()
                    logging.info(
                        "Batch cycle committed successfully. display_batch_id=%s "
                        "container_batch_id=%s controller_batch_id=%s",
                        display_batch_id,
                        container_batch_id,
                        controller_batch_id,
                    )

                except Exception as batch_exc:
                    conn.rollback()

                    # Re-open a transaction so we can mark failure cleanly
                    conn.autocommit = False

                    if display_batch_id:
                        mark_display_batch_failed(conn, display_batch_id, str(batch_exc))

                    if container_batch_id:
                        mark_container_batch_failed(conn, container_batch_id, str(batch_exc))

                    if controller_batch_id:
                        mark_controller_batch_failed(
                            conn,
                            controller_batch_id,
                            str(batch_exc),
                        )

                    conn.commit()

                    logging.exception(
                        "Batch cycle failed. display_batch_id=%s "
                        "container_batch_id=%s controller_batch_id=%s error=%s",
                        display_batch_id,
                        container_batch_id,
                        controller_batch_id,
                        batch_exc,
                    )

        except Exception as exc:
            logging.exception("Polling cycle failed: %s", exc)

        finally:
            clear_lock()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
