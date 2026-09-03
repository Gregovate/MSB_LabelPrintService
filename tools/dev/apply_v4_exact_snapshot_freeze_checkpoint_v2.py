from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "label_poll_service_v4.py"
DISPLAY_SQL = ROOT / "sql" / "display_snapshot_v4.sql"
CONTAINER_SQL = ROOT / "sql" / "container_snapshot_v4.sql"
ARCH = ROOT / "docs" / "01_Engineering" / "Label_Service_v4_Architecture_and_Acceptance.md"


def fail(message: str) -> None:
    raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"{label}: expected text not found")
    return text.replace(old, new, 1)


def replace_function_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    try:
        start = text.index(start_marker)
        end = text.index(end_marker, start)
    except ValueError as exc:
        fail(f"{label}: function boundary not found ({exc})")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def main() -> None:
    text = V4.read_text(encoding="utf-8")

    # The earlier checkpoint accidentally referenced doc.Close without invoking it.
    if "_ = doc.Close()" not in text:
        text = replace_once(
            text,
            "_ = doc.Close\n",
            "_ = doc.Close()\n",
            "b-PAC preflight Close call",
        )

    # Add helpers immediately before the selected-workload preflight function.
    helper_marker = "def run_selected_workload_preflight(\n"
    if "def pending_display_ids(" not in text:
        try:
            helper_pos = text.index(helper_marker)
        except ValueError:
            fail("pending-ID helper insertion marker not found")

        helpers = '''def pending_display_ids(
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


'''
        text = text[:helper_pos] + helpers + text[helper_pos:]

    display_block = '''def create_display_batch(
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
'''
    text = replace_function_block(
        text,
        "def create_display_batch(\n",
        "def create_container_batch(",
        display_block,
        "Display exact snapshot batch function",
    )

    container_block = '''def create_container_batch(
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
'''
    text = replace_function_block(
        text,
        "def create_container_batch(",
        "# ============================================================\n# CSV EXPORT",
        container_block,
        "Container exact snapshot batch function",
    )

    old_display_call = '''                    display_batch_id = create_display_batch(
                        conn,
                        int(selected_display_family["label_template_id"]),
                    )
'''
    new_display_call = '''                    display_batch_id = create_display_batch(
                        conn,
                        int(selected_display_family["label_template_id"]),
                        display_postflight_signature,
                    )
'''
    if new_display_call not in text:
        text = replace_once(
            text,
            old_display_call,
            new_display_call,
            "Display create call signature",
        )

    old_container_call = '''                    container_batch_id = create_container_batch(conn)
'''
    new_container_call = '''                    container_batch_id = create_container_batch(
                        conn,
                        container_postflight_signature,
                    )
'''
    if new_container_call not in text:
        text = replace_once(
            text,
            old_container_call,
            new_container_call,
            "Container create call signature",
        )

    V4.write_text(text, encoding="utf-8", newline="\n")

    display_sql = DISPLAY_SQL.read_text(encoding="utf-8")
    if "ANY(%(display_ids)s)" not in display_sql:
        display_sql = replace_once(
            display_sql,
            "     %(label_template_id)s\n",
            "     %(label_template_id)s\n     %(display_ids)s\n",
            "Display snapshot parameter comment",
        )
        display_sql = replace_once(
            display_sql,
            "WHERE d.print_label = true\n  AND d.label_template_id = %(label_template_id)s\n",
            "WHERE d.print_label = true\n  AND d.label_template_id = %(label_template_id)s\n  AND d.display_id = ANY(%(display_ids)s)\n",
            "Display exact-ID snapshot filter",
        )
        DISPLAY_SQL.write_text(display_sql, encoding="utf-8", newline="\n")

    container_sql = CONTAINER_SQL.read_text(encoding="utf-8")
    if "ANY(%(container_ids)s)" not in container_sql:
        container_sql = replace_once(
            container_sql,
            "     %(batch_id)s\n",
            "     %(batch_id)s\n     %(container_ids)s\n",
            "Container snapshot parameter comment",
        )
        container_sql = replace_once(
            container_sql,
            "FROM ref.container c\nWHERE c.print_label = true\n",
            "FROM ref.container c\nWHERE c.print_label = true\n  AND c.container_id = ANY(%(container_ids)s)\n",
            "Container exact-ID snapshot filter",
        )
        CONTAINER_SQL.write_text(container_sql, encoding="utf-8", newline="\n")

    arch = ARCH.read_text(encoding="utf-8")
    if "Immediately before the batch header is inserted, v4 freezes the exact pending" not in arch:
        marker = '''operator dialog/preflight loop was active, v4 creates no batch and returns to a
fresh poll so the new workload is rebuilt and preflighted before any snapshot
state is written.
'''
        addition = marker + '''
Immediately before the batch header is inserted, v4 freezes the exact pending
asset IDs, acquires row locks on those selected source rows, and rechecks the
validated workload signature again. The v4 snapshot SQL is restricted to those
exact IDs. The frozen rows also supply batch requester attribution. This closes
the final race between preflight and snapshot creation: a newly requested asset
cannot be swept into a batch that was not preflighted, and a selected row cannot
change its render-affecting source fields after the freeze until the snapshot
transaction completes.
'''
        arch = replace_once(
            arch,
            marker,
            addition,
            "Architecture exact snapshot freeze",
        )
        ARCH.write_text(arch, encoding="utf-8", newline="\n")

    print("v4 exact preflight-to-snapshot freeze checkpoint v2 applied.")


if __name__ == "__main__":
    main()
