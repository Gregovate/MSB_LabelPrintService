from __future__ import annotations

import configparser
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import pythoncom
import psycopg2
from psycopg2.extras import RealDictCursor
import win32com.client


# ============================================================
# MSB Label Polling Service
#
# Purpose:
#   Poll ref.display / ref.container for print_label = true,
#   snapshot selected rows into batch tables, generate fixed CSV files,
#   print labels through Brother b-PAC, write history, and clear only
#   the snapshot rows that were part of the completed batch.
#
# IMPORTANT:
#   This service no longer opens P-touch Editor templates for manual
#   printing. It uses b-PAC directly.
#
# Current assumptions:
#   - Display template object names:
#       objLine1
#       objLine2
#       objQr
#
#   - Container template object names:
#       objContainerLabel
#       objQr
#
#   - Display labels print one label per row.
#   - Container labels print TWO labels per selected container.
#     This is handled by duplicating rows in memory before printing.
#
# Media-out handling:
#   - Not fully characterized yet.
#   - If b-PAC throws an exception, the batch is marked FAILED and
#     the print_label flags remain set.
#   - If the printer accepts the batch and later runs out of stock,
#     that real-world behavior will be captured in the batch log.
#
# Author: Greg Liebig / Engineering Innovations, LLC
# Date: 2026-03-21
# ============================================================

# ============================================================
# CHANGE LOG
# ============================================================
# 2026-03-21  — Greg Liebig
#
# v0.3  — Printer-safe batch creation
#   • Added pending label checks before batch creation
#   • Added printer preflight check BEFORE creating batches
#   • Prevents endless batch creation when printer is empty,
#     offline, paused, or otherwise not ready
#   • Service now idles safely until printer becomes available
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

SERVICE_VERSION = "0.3"




# ============================================================
# CONFIG LOADING
# ============================================================

def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(Path(__file__).with_name("config.local.ini"))
    return config


CONFIG = load_config()

BASE_DIR = Path(CONFIG["paths"]["base_dir"])
SQL_DIR = Path(CONFIG["paths"]["sql_dir"])
CSV_DIR = Path(CONFIG["paths"]["csv_dir"])
TEMPLATE_DIR = Path(CONFIG["paths"]["template_dir"])
STATE_DIR = Path(CONFIG["paths"]["state_dir"])
LOG_DIR = Path(CONFIG["paths"]["log_dir"])
BATCH_LOG_DIR = LOG_DIR / "batches"

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
BATCH_LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

LOCK_FILE = STATE_DIR / "print_service.lock"
LOG_FILE = LOG_DIR / "label_service.log"

POLL_SECONDS = int(CONFIG["service"]["poll_seconds"])
STARTED_BY_PERSON_ID = int(CONFIG["service"]["started_by_person_id"])
STARTED_BY_TEXT = CONFIG["service"]["started_by_text"]

DISPLAY_TEMPLATE = Path(CONFIG["templates"]["display"])
CONTAINER_VERTICAL_TEMPLATE = Path(CONFIG["templates"]["container_vertical"])
CONTAINER_HORIZONTAL_TEMPLATE = Path(CONFIG["templates"]["container_horizontal"])

DISPLAY_CSV = Path(CONFIG["csv_files"]["display"])
CONTAINER_VERTICAL_CSV = Path(CONFIG["csv_files"]["container_vertical"])
CONTAINER_HORIZONTAL_CSV = Path(CONFIG["csv_files"]["container_horizontal"])

# Printer name used by b-PAC SetPrinter()
# Add this to config.local.ini under [printer]:
# name = Brother PT-P950NW
PRINTER_NAME = CONFIG.get("printer", "name", fallback="Brother PT-P950NW")

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
# Template object names
# ------------------------------------------------------------
DISPLAY_OBJ_LINE1 = "objLine1"
DISPLAY_OBJ_LINE2 = "objLine2"
DISPLAY_OBJ_QR = "objQr"

CONTAINER_OBJ_LABEL = "objContainerLabel"
CONTAINER_OBJ_QR = "objQr"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True,
)
logging.info("MSB Label Polling Service v%s started.", SERVICE_VERSION)
print(f"MSB Label Polling Service v{SERVICE_VERSION} started.")
logging.info("Logging initialized. Log file: %s", LOG_FILE)
print(f"Logging initialized. Log file: {LOG_FILE}")


# ============================================================
# STARTUP HEALTH CHECK
# ============================================================
def startup_health_check() -> None:
    """
    Fail fast on startup if the service cannot reach the database
    and perform the same permission path that previously failed
    during batch finalization.
    """
    print("==================================================")
    print("MSB Label Service v2 starting")
    print("==================================================")
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
# Printer preflight
# ============================================================

BPAC_STATUS_CODES = {
    101: "No media",
    102: "End of media",
    50593795: "Printer offline",
}

def decode_bpac_code(code: int) -> str:
    return BPAC_STATUS_CODES.get(code, f"Unknown code {code} (0x{code:08X})")


def printer_preflight(template_path: Path) -> tuple[bool, str]:
    """
    Check whether the printer appears ready before creating a batch.

    Returns:
      (True, "OK")
      (False, "reason")
    """
    try:
        doc = create_bpac_document()

        opened = doc.Open(str(template_path))
        if not opened:
            return False, f"Could not open template: {template_path}"

        set_printer_ok = doc.SetPrinter(PRINTER_NAME, True)
        if not set_printer_ok:
            return False, f"Could not set printer '{PRINTER_NAME}'"

        # Template media from LBX
        try:
            template_media = doc.GetMediaName()
        except Exception as exc:
            template_media = f"<error reading template media: {exc}>"

        # Printer media from printer object
        try:
            printer_media = doc.Printer.GetMediaName()
        except Exception as exc:
            return False, f"Printer GetMediaName failed: {exc}"

        # Media ID / error path
        media_id = None
        media_id_error = None
        try:
            media_id = doc.Printer.GetMediaId()
        except Exception as exc:
            media_id_error = str(exc)

        # Close doc as best we can
        try:
            _ = doc.Close
        except Exception:
            pass

        # Known failure cases
        if media_id in (101, 102, 50593795):
            return False, decode_bpac_code(media_id)

        if not printer_media or str(printer_media).strip() == "":
            return False, "Printer reports no media loaded"

        # Optional media mismatch warning
        # Do not hard-fail on mismatch yet unless you want to enforce it
        if template_media and printer_media and str(template_media).strip() != str(printer_media).strip():
            return False, f"Loaded media '{printer_media}' does not match template media '{template_media}'"

        if media_id_error:
            # If GetMediaId threw something but media name exists, log it as warning-level text
            return True, f"OK (GetMediaId warning: {media_id_error})"

        return True, f"OK (template_media={template_media}, printer_media={printer_media})"

    except Exception as exc:
        return False, f"Printer preflight exception: {exc}"
    
# ============================================================
# LOGGING HELPERS
# ============================================================

def write_batch_log(batch_log_path: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with batch_log_path.open("a", encoding="utf-8") as f:
        f.write(f"{timestamp} | {message}\n")


def new_batch_log_path(batch_type: str, batch_id: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return BATCH_LOG_DIR / f"{batch_type}_batch_{batch_id}_{stamp}.log"

# ============================================================
# b-PAC printed callback / status handling
# ============================================================

BPAC_ERROR_CODES = {
    0: "Printed successfully",
    101: "No media",
    102: "End of media",
    50593795: "Printer offline",
}

def decode_bpac_status(code: int) -> str:
    return BPAC_ERROR_CODES.get(code, f"Unknown b-PAC status {code} (0x{code:08X})")


class BpacPrintEvents:
    """
    Event sink for Brother b-PAC Printed callback.

    Brother docs show:
      Printed(status, value)

    pywin32 event naming can vary by typelib, so we provide both
    OnPrinted and Printed handlers.
    """
    def __init__(self):
        self.printed_called = False
        self.status = None
        self.value = None

    def OnPrinted(self, status, value):
        self.printed_called = True
        self.status = int(status)
        self.value = value

    def Printed(self, status, value):
        self.printed_called = True
        self.status = int(status)
        self.value = value


def wait_for_bpac_result(event_sink: BpacPrintEvents, timeout_seconds: int = 120) -> tuple[int, object]:
    """
    Wait for the Brother b-PAC Printed callback.
    Returns:
      (status, value)

    Raises:
      TimeoutError if no callback is received.
    """
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        pythoncom.PumpWaitingMessages()

        if event_sink.printed_called:
            return event_sink.status, event_sink.value

        time.sleep(0.1)

    raise TimeoutError("Timed out waiting for b-PAC Printed callback.")

# ============================================================
# DATABASE HELPERS
# ============================================================

def pending_display_count(conn) -> int:
    return int(query_value(
        conn,
        "SELECT COUNT(*) FROM ref.display WHERE print_label = true;",
    ) or 0)


def pending_container_count(conn) -> int:
    return int(query_value(
        conn,
        "SELECT COUNT(*) FROM ref.container WHERE print_label = true;",
    ) or 0)

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

def create_display_batch(conn) -> int | None:
    sql = """
        INSERT INTO ops.display_label_batch (
            started_by_person_id,
            started_by_text,
            status,
            notes
        )
        VALUES (%(person_id)s, %(person_text)s, 'PRINTING', 'Polling service snapshot')
        RETURNING display_label_batch_id;
    """
    batch_id = query_value(
        conn,
        sql,
        {
            "person_id": STARTED_BY_PERSON_ID,
            "person_text": STARTED_BY_TEXT,
        },
    )

    exec_sql(conn, load_sql("display_snapshot.sql"), {"batch_id": batch_id})

    row_count = query_value(
        conn,
        "SELECT COUNT(*) FROM ops.display_label_batch_item WHERE display_label_batch_id = %(batch_id)s;",
        {"batch_id": batch_id},
    )

    if row_count == 0:
        exec_sql(
            conn,
            "DELETE FROM ops.display_label_batch WHERE display_label_batch_id = %(batch_id)s;",
            {"batch_id": batch_id},
        )
        return None

    return int(batch_id)


def create_container_batch(conn) -> int | None:
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
            "person_id": STARTED_BY_PERSON_ID,
            "person_text": STARTED_BY_TEXT,
        },
    )

    exec_sql(conn, load_sql("container_snapshot.sql"), {"batch_id": batch_id})

    row_count = query_value(
        conn,
        "SELECT COUNT(*) FROM ops.container_label_batch_item WHERE container_label_batch_id = %(batch_id)s;",
        {"batch_id": batch_id},
    )

    if row_count == 0:
        exec_sql(
            conn,
            "DELETE FROM ops.container_label_batch WHERE container_label_batch_id = %(batch_id)s;",
            {"batch_id": batch_id},
        )
        return None

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

def create_bpac_document_with_events():
    """
    Return:
      (doc, event_sink)
    """
    event_sink = BpacPrintEvents()
    doc = win32com.client.DispatchWithEvents("bpac.Document", BpacPrintEvents)
    return doc, doc


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
        template_media = doc.GetMediaName()
    except Exception as exc:
        template_media = f"<error reading template media: {exc}>"

    try:
        printer_media = doc.Printer.GetMediaName()
    except Exception as exc:
        printer_media = f"<error reading printer media: {exc}>"

    write_batch_log(batch_log_path, f"Template media: {template_media}")
    write_batch_log(batch_log_path, f"Printer media : {printer_media}")

# ============================================================
# DISPLAY PRINTING
# ============================================================

def print_display_batch(rows: list[dict[str, Any]], batch_log_path: Path) -> None:
    """
    Print display labels through b-PAC and wait for true printer result.
    """
    if not rows:
        write_batch_log(batch_log_path, "No display rows to print.")
        return

    doc, event_sink = create_bpac_document_with_events()

    write_batch_log(batch_log_path, f"Opening display template: {DISPLAY_TEMPLATE}")
    opened = doc.Open(str(DISPLAY_TEMPLATE))
    write_batch_log(batch_log_path, f"Template opened: {opened}")
    if not opened:
        raise RuntimeError("b-PAC could not open the display template.")

    set_printer_ok = doc.SetPrinter(PRINTER_NAME, True)
    write_batch_log(batch_log_path, f"SetPrinter('{PRINTER_NAME}') = {set_printer_ok}")
    if not set_printer_ok:
        raise RuntimeError("b-PAC could not set the display printer.")

    log_media_status(doc, batch_log_path)

    obj_line1 = get_required_object(doc, DISPLAY_OBJ_LINE1)
    obj_qr = get_required_object(doc, DISPLAY_OBJ_QR)
    obj_line2 = get_optional_object(doc, DISPLAY_OBJ_LINE2)

    write_batch_log(
        batch_log_path,
        f"Resolved display objects: line1={DISPLAY_OBJ_LINE1}, "
        f"line2={DISPLAY_OBJ_LINE2 if obj_line2 is not None else 'MISSING'}, "
        f"qr={DISPLAY_OBJ_QR}",
    )

    doc.StartPrint("", PRINT_FLAGS)
    write_batch_log(batch_log_path, f"StartPrint called with flags={hex(PRINT_FLAGS)}")

    for idx, row in enumerate(rows, start=1):
        obj_line1.Text = row.get("line1", "") or ""
        obj_qr.Text = row.get("qr_url", "") or ""

        if obj_line2 is not None:
            obj_line2.Text = row.get("line2", "") or ""

        result = doc.PrintOut(1, 0)
        write_batch_log(
            batch_log_path,
            f"Queued display label {idx}/{len(rows)} "
            f"display_id={row.get('display_id')} result={result} "
            f"line1={row.get('line1')} line2={row.get('line2')}",
        )

        if not result:
            raise RuntimeError(
                f"Display PrintOut failed on row {idx} display_id={row.get('display_id')}"
            )

    end_result = doc.EndPrint
    write_batch_log(batch_log_path, f"EndPrint result: {end_result}")

    status, value = wait_for_bpac_result(event_sink, timeout_seconds=120)
    write_batch_log(
        batch_log_path,
        f"Printed callback received: status={status} value={value} "
        f"message='{decode_bpac_status(status)}'"
    )

    close_result = doc.Close
    write_batch_log(batch_log_path, f"Close result: {close_result}")

    if status != 0:
        raise RuntimeError(
            f"Display batch printer reported failure: status={status} "
            f"message='{decode_bpac_status(status)}' value={value}"
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
    Print container labels through b-PAC and wait for true printer result.
    """
    if not rows:
        write_batch_log(batch_log_path, f"No {orientation.lower()} container rows to print.")
        return

    rows_to_print = duplicate_container_rows(rows)
    write_batch_log(
        batch_log_path,
        f"{orientation} container rows duplicated for quantity 2. "
        f"Original={len(rows)} Effective={len(rows_to_print)}"
    )

    doc, event_sink = create_bpac_document_with_events()

    write_batch_log(batch_log_path, f"Opening {orientation.lower()} template: {template_path}")
    opened = doc.Open(str(template_path))
    write_batch_log(batch_log_path, f"Template opened: {opened}")
    if not opened:
        raise RuntimeError(f"b-PAC could not open the {orientation.lower()} container template.")

    set_printer_ok = doc.SetPrinter(PRINTER_NAME, True)
    write_batch_log(batch_log_path, f"SetPrinter('{PRINTER_NAME}') = {set_printer_ok}")
    if not set_printer_ok:
        raise RuntimeError(f"b-PAC could not set the {orientation.lower()} container printer.")

    log_media_status(doc, batch_log_path)

    obj_label = get_required_object(doc, CONTAINER_OBJ_LABEL)
    obj_qr = get_required_object(doc, CONTAINER_OBJ_QR)

    write_batch_log(
        batch_log_path,
        f"Resolved container objects: label={CONTAINER_OBJ_LABEL}, qr={CONTAINER_OBJ_QR}",
    )

    doc.StartPrint("", PRINT_FLAGS)
    write_batch_log(batch_log_path, f"StartPrint called with flags={hex(PRINT_FLAGS)}")

    for idx, row in enumerate(rows_to_print, start=1):
        obj_label.Text = row.get("container_label", "") or ""
        obj_qr.Text = row.get("qr_url", "") or ""

        result = doc.PrintOut(1, 0)
        write_batch_log(
            batch_log_path,
            f"Queued {orientation.lower()} container label {idx}/{len(rows_to_print)} "
            f"container_id={row.get('container_id')} result={result} "
            f"label={row.get('container_label')}",
        )

        if not result:
            raise RuntimeError(
                f"{orientation} container PrintOut failed on row {idx} "
                f"container_id={row.get('container_id')}"
            )

    end_result = doc.EndPrint
    write_batch_log(batch_log_path, f"EndPrint result: {end_result}")

    status, value = wait_for_bpac_result(event_sink, timeout_seconds=120)
    write_batch_log(
        batch_log_path,
        f"Printed callback received: status={status} value={value} "
        f"message='{decode_bpac_status(status)}'"
    )

    close_result = doc.Close
    write_batch_log(batch_log_path, f"Close result: {close_result}")

    if status != 0:
        raise RuntimeError(
            f"{orientation} container batch printer reported failure: status={status} "
            f"message='{decode_bpac_status(status)}' value={value}"
        )


# ============================================================
# FAILURE HANDLING
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


# ============================================================
# MAIN BATCH PROCESSING
# ============================================================

def process_display(conn, display_batch_id: int) -> None:
    rows = query_rows(conn, load_sql("display_export.sql"), {"batch_id": display_batch_id})
    write_csv(DISPLAY_CSV, rows)

    batch_log_path = new_batch_log_path("display", display_batch_id)
    write_batch_log(batch_log_path, f"Display batch {display_batch_id} created.")
    write_batch_log(batch_log_path, f"Display CSV written: {DISPLAY_CSV}")
    write_batch_log(batch_log_path, f"Display row count: {len(rows)}")

    print_display_batch(rows, batch_log_path)

    exec_sql(conn, load_sql("display_finalized.sql"), {"batch_id": display_batch_id})
    write_batch_log(batch_log_path, "Display batch finalized successfully.")
    logging.info("Display batch %s completed successfully.", display_batch_id)


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


# ============================================================
# MAIN LOOP
# ============================================================

def main() -> None:
    logging.info("MSB label polling service started.")

    startup_health_check()

    while True:
        try:
            logging.info("Poll tick — checking for pending labels.")
            if lock_exists():
                time.sleep(POLL_SECONDS)
                continue

            create_lock()

            with db_connect() as conn:
                conn.autocommit = False

                # --------------------------------------------------
                # Step 1: Check whether there is any work pending
                # --------------------------------------------------
                display_pending = pending_display_count(conn)
                container_pending = pending_container_count(conn)
                logging.info(
                    "Pending labels — displays=%s containers=%s",
                    display_pending,
                    container_pending,
                )

                if display_pending == 0 and container_pending == 0:
                    logging.info("No pending labels. Service idle.")
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                # --------------------------------------------------
                # Step 2: Preflight printer BEFORE creating any batch
                # This prevents endless batch creation when printer is
                # empty, offline, paused, or otherwise not ready.
                # --------------------------------------------------
                preflight_template = (
                    DISPLAY_TEMPLATE
                    if display_pending > 0
                    else CONTAINER_VERTICAL_TEMPLATE
                )

                preflight_ok, preflight_msg = printer_preflight(preflight_template)

                if not preflight_ok:
                    logging.error("Printer preflight failed: %s", preflight_msg)
                    print(f"Printer preflight failed: {preflight_msg}")
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                logging.info("Printer preflight passed: %s", preflight_msg)
                print(f"Printer preflight passed: {preflight_msg}")

                # --------------------------------------------------
                # Step 3: Only create batches AFTER printer passes
                # --------------------------------------------------
                display_batch_id = create_display_batch(conn)
                container_batch_id = create_container_batch(conn)
                logging.info(
                    "Batch creation results — display_batch_id=%s container_batch_id=%s",
                    display_batch_id,
                    container_batch_id,
                )

                if not display_batch_id and not container_batch_id:
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                try:
                    if display_batch_id:
                        process_display(conn, display_batch_id)

                    if container_batch_id:
                        process_container(conn, container_batch_id)

                    conn.commit()
                    logging.info(
                        "Batch cycle committed successfully. display_batch_id=%s container_batch_id=%s",
                        display_batch_id,
                        container_batch_id,
                    )

                except Exception as batch_exc:
                    conn.rollback()

                    # Re-open a transaction so we can mark failure cleanly
                    conn.autocommit = False

                    if display_batch_id:
                        mark_display_batch_failed(conn, display_batch_id, str(batch_exc))

                    if container_batch_id:
                        mark_container_batch_failed(conn, container_batch_id, str(batch_exc))

                    conn.commit()

                    logging.exception(
                        "Batch cycle failed. display_batch_id=%s container_batch_id=%s error=%s",
                        display_batch_id,
                        container_batch_id,
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