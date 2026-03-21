from __future__ import annotations

import configparser
import csv
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


# ============================================================
# MSB Label Polling Service
# Purpose:
#   Poll ref.display / ref.container for print_label = true,
#   snapshot selected rows into batch tables, generate fixed CSV files,
#   and launch the Brother templates.
#
# IMPORTANT:
#   This service DOES NOT auto-finalize a batch.
#   After the operator confirms that printing completed successfully,
#   run confirm_last_batch.py.
#
# Why manual confirmation?
#   Brother/PT Editor does not provide a clean, trustworthy success
#   callback, and media-out conditions can pause jobs unpredictably.
#
# Author: Greg Liebig / Engineering Innovations, LLC
# Date: 2026-03-20
# ============================================================


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(Path(__file__).with_name("config.ini"))
    return config


CONFIG = load_config()

BASE_DIR = Path(CONFIG["paths"]["base_dir"])
SQL_DIR = Path(CONFIG["paths"]["sql_dir"])
CSV_DIR = Path(CONFIG["paths"]["csv_dir"])
TEMPLATE_DIR = Path(CONFIG["paths"]["template_dir"])
STATE_DIR = Path(CONFIG["paths"]["state_dir"])
LOG_DIR = Path(CONFIG["paths"]["log_dir"])

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

LOCK_FILE = STATE_DIR / "print_service.lock"
ACTIVE_BATCH_FILE = STATE_DIR / "active_batch.json"
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

PRINT_MODE = CONFIG["printing"]["mode"].strip()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        # Truncate to headerless empty file only if you really want it blank.
        # Safer for PT binding: keep headers if possible.
        path.write_text("", encoding="utf-8")
        return 0

    headers = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def launch_template(template_path: Path, command_template: str) -> None:
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    if PRINT_MODE == "open_template":
        os.startfile(str(template_path))
        return

    if PRINT_MODE == "command":
        if not command_template.strip():
            raise RuntimeError(f"No print command configured for template {template_path}")
        cmd = command_template.format(template=str(template_path))
        subprocess.run(cmd, shell=True, check=True)
        return

    raise RuntimeError(f"Unknown print mode: {PRINT_MODE}")


def export_and_launch(conn, display_batch_id: int | None, container_batch_id: int | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "display_batch_id": display_batch_id,
        "container_batch_id": container_batch_id,
        "display_count": 0,
        "container_vertical_count": 0,
        "container_horizontal_count": 0,
    }

    if display_batch_id:
        rows = query_rows(conn, load_sql("display_export.sql"), {"batch_id": display_batch_id})
        result["display_count"] = write_csv(DISPLAY_CSV, rows)
        if rows:
            launch_template(DISPLAY_TEMPLATE, CONFIG["printing"]["display_command"])
            logging.info("Launched display template for batch %s", display_batch_id)

    if container_batch_id:
        vert_rows = query_rows(conn, load_sql("container_export_vertical.sql"), {"batch_id": container_batch_id})
        horz_rows = query_rows(conn, load_sql("container_export_horizontal.sql"), {"batch_id": container_batch_id})

        result["container_vertical_count"] = write_csv(CONTAINER_VERTICAL_CSV, vert_rows)
        result["container_horizontal_count"] = write_csv(CONTAINER_HORIZONTAL_CSV, horz_rows)

        if vert_rows:
            launch_template(
                CONTAINER_VERTICAL_TEMPLATE,
                CONFIG["printing"]["container_vertical_command"],
            )
            logging.info("Launched vertical container template for batch %s", container_batch_id)

        if horz_rows:
            launch_template(
                CONTAINER_HORIZONTAL_TEMPLATE,
                CONFIG["printing"]["container_horizontal_command"],
            )
            logging.info("Launched horizontal container template for batch %s", container_batch_id)

    return result


def write_active_batch_state(payload: dict[str, Any]) -> None:
    ACTIVE_BATCH_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOCK_FILE.write_text("LOCKED\n", encoding="utf-8")


def active_batch_exists() -> bool:
    return ACTIVE_BATCH_FILE.exists() or LOCK_FILE.exists()


def main() -> None:
    logging.info("MSB label polling service started.")

    while True:
        try:
            if active_batch_exists():
                time.sleep(POLL_SECONDS)
                continue

            with db_connect() as conn:
                conn.autocommit = False

                display_batch_id = create_display_batch(conn)
                container_batch_id = create_container_batch(conn)

                if not display_batch_id and not container_batch_id:
                    conn.rollback()
                    time.sleep(POLL_SECONDS)
                    continue

                export_result = export_and_launch(conn, display_batch_id, container_batch_id)

                # Snapshot is now committed and locked. Finalize happens only after operator confirmation.
                conn.commit()

                write_active_batch_state(
                    {
                        "display_batch_id": display_batch_id,
                        "container_batch_id": container_batch_id,
                        "display_count": export_result["display_count"],
                        "container_vertical_count": export_result["container_vertical_count"],
                        "container_horizontal_count": export_result["container_horizontal_count"],
                        "started_by_person_id": STARTED_BY_PERSON_ID,
                        "started_by_text": STARTED_BY_TEXT,
                    }
                )

                logging.info("Active batch created: %s", export_result)

        except Exception as exc:
            logging.exception("Polling cycle failed: %s", exc)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)