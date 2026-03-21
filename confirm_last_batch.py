# confirm_last_batch.py

from __future__ import annotations

import configparser
import json
from pathlib import Path

import psycopg2


# ============================================================
# Confirm Last Batch
# Purpose:
#   Finalize the currently active label batch after the operator confirms
#   that printing completed successfully.
#
# Effects:
#   - writes history
#   - clears print_label only for snapshot rows
#   - marks batch completed
#   - releases service lock
# ============================================================


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(Path(__file__).with_name("config.ini"))
    return config


CONFIG = load_config()

BASE_DIR = Path(CONFIG["paths"]["base_dir"])
SQL_DIR = Path(CONFIG["paths"]["sql_dir"])
STATE_DIR = Path(CONFIG["paths"]["state_dir"])

ACTIVE_BATCH_FILE = STATE_DIR / "active_batch.json"
LOCK_FILE = STATE_DIR / "print_service.lock"


def db_connect():
    return psycopg2.connect(
        host=CONFIG["database"]["host"],
        port=int(CONFIG["database"]["port"]),
        dbname=CONFIG["database"]["dbname"],
        user=CONFIG["database"]["user"],
        password=CONFIG["database"]["password"],
    )


def load_sql(filename: str) -> str:
    return (SQL_DIR / filename).read_text(encoding="utf-8")


def exec_sql(conn, sql: str, params: dict | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})


def main() -> None:
    if not ACTIVE_BATCH_FILE.exists():
        print("No active batch file found.")
        return

    payload = json.loads(ACTIVE_BATCH_FILE.read_text(encoding="utf-8"))
    display_batch_id = payload.get("display_batch_id")
    container_batch_id = payload.get("container_batch_id")

    with db_connect() as conn:
        conn.autocommit = False

        if display_batch_id:
            exec_sql(conn, load_sql("display_finalize.sql"), {"batch_id": display_batch_id})

        if container_batch_id:
            exec_sql(conn, load_sql("container_finalize.sql"), {"batch_id": container_batch_id})

        conn.commit()

    ACTIVE_BATCH_FILE.unlink(missing_ok=True)
    LOCK_FILE.unlink(missing_ok=True)

    print("Batch finalized successfully.")


if __name__ == "__main__":
    main()