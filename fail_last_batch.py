from __future__ import annotations

import configparser
import json
from pathlib import Path

import psycopg2


# ============================================================
# Fail Last Batch
# Purpose:
#   Mark the currently active batch as FAILED and release the lock
#   without clearing any print_label flags.
#
# Use when:
#   - print was cancelled
#   - wrong labels were loaded
#   - media issue requires retry later
# ============================================================


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(Path(__file__).with_name("config.ini"))
    return config


CONFIG = load_config()

BASE_DIR = Path(CONFIG["paths"]["base_dir"])
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


def main() -> None:
    if not ACTIVE_BATCH_FILE.exists():
        print("No active batch file found.")
        return

    payload = json.loads(ACTIVE_BATCH_FILE.read_text(encoding="utf-8"))
    display_batch_id = payload.get("display_batch_id")
    container_batch_id = payload.get("container_batch_id")

    with db_connect() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            if display_batch_id:
                cur.execute(
                    """
                    UPDATE ops.display_label_batch
                    SET status = 'FAILED'
                    WHERE display_label_batch_id = %s;
                    """,
                    (display_batch_id,),
                )

            if container_batch_id:
                cur.execute(
                    """
                    UPDATE ops.container_label_batch
                    SET status = 'FAILED'
                    WHERE container_label_batch_id = %s;
                    """,
                    (container_batch_id,),
                )

        conn.commit()

    ACTIVE_BATCH_FILE.unlink(missing_ok=True)
    LOCK_FILE.unlink(missing_ok=True)

    print("Batch marked FAILED. Selection flags remain set for retry.")


if __name__ == "__main__":
    main()