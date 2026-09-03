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


def main() -> None:
    text = V4.read_text(encoding="utf-8")

    # b-PAC preflight documents must actually close.
    text = replace_once(
        text,
        "                _ = doc.Close\n",
        "                _ = doc.Close()\n",
        "b-PAC preflight Close call",
    )

    # Add exact pending-ID helpers next to the workload signatures.
    anchor = '''def pending_container_workload_signature(conn) -> str:\n    ids = query_value(\n        conn,\n        """\n        SELECT COALESCE(\n            string_agg(\n                container_id::text\n                || ':' || COALESCE(container_type_id::text, ''),\n                E'\\\\n'\n                ORDER BY container_id\n            ),\n            ''\n        )\n        FROM ref.container\n        WHERE print_label = true;\n        """,\n    )\n    return f"CONTAINER:{ids or ''}"\n\n\n'''

    helpers = anchor + '''def pending_display_ids(\n    conn,\n    label_template_id: int,\n) -> list[int]:\n    rows = query_rows(\n        conn,\n        """\n        SELECT display_id\n        FROM ref.display\n        WHERE print_label = true\n          AND label_template_id = %(label_template_id)s\n        ORDER BY display_id;\n        """,\n        {"label_template_id": label_template_id},\n    )\n    return [int(row["display_id"]) for row in rows]\n\n\ndef pending_container_ids(conn) -> list[int]:\n    rows = query_rows(\n        conn,\n        """\n        SELECT container_id\n        FROM ref.container\n        WHERE print_label = true\n        ORDER BY container_id;\n        """,\n    )\n    return [int(row["container_id"]) for row in rows]\n\n\n'''
    text = replace_once(
        text,
        anchor,
        helpers,
        "exact pending-ID helpers",
    )

    # Replace Display batch creation with exact-ID freeze + row lock + signature recheck.
    display_start = text.index("def create_display_batch(\n")
    display_end = text.index("\n\ndef create_container_batch", display_start)
    display_block = '''def create_display_batch(\n    conn,\n    label_template_id: int,\n    expected_signature: str,\n) -> int | None:\n    display_ids = pending_display_ids(conn, label_template_id)\n    if not display_ids:\n        return None\n\n    locked_rows = query_rows(\n        conn,\n        """\n        SELECT display_id\n        FROM ref.display\n        WHERE display_id = ANY(%(display_ids)s)\n          AND print_label = true\n          AND label_template_id = %(label_template_id)s\n        ORDER BY display_id\n        FOR UPDATE;\n        """,\n        {\n            "display_ids": display_ids,\n            "label_template_id": label_template_id,\n        },\n    )\n    locked_ids = [int(row["display_id"]) for row in locked_rows]\n\n    if locked_ids != display_ids:\n        logging.warning(\n            "Display request set changed while acquiring snapshot locks; "\n            "no batch created. expected_ids=%s locked_ids=%s",\n            display_ids,\n            locked_ids,\n        )\n        return None\n\n    locked_signature = pending_display_workload_signature(\n        conn,\n        label_template_id,\n    )\n    if locked_signature != expected_signature:\n        logging.warning(\n            "Display request/render state changed before snapshot freeze; "\n            "no batch created. expected=%s locked=%s",\n            expected_signature,\n            locked_signature,\n        )\n        return None\n\n    person_id, person_text = get_display_batch_actor(\n        conn,\n        label_template_id,\n    )\n\n    if person_id is None:\n        logging.warning(\n            "Display batch actor not found from ref.display audit fields. "\n            "Falling back to service identity."\n        )\n        person_id = STARTED_BY_PERSON_ID\n        person_text = STARTED_BY_TEXT\n\n    sql = """\n        INSERT INTO ops.display_label_batch (\n            started_by_person_id,\n            started_by_text,\n            label_template_id,\n            status,\n            notes\n        )\n        VALUES (\n            %(person_id)s,\n            %(person_text)s,\n            %(label_template_id)s,\n            'PRINTING',\n            'Polling service snapshot'\n        )\n        RETURNING display_label_batch_id;\n    """\n    batch_id = query_value(\n        conn,\n        sql,\n        {\n            "person_id": person_id,\n            "person_text": person_text,\n            "label_template_id": label_template_id,\n        },\n    )\n\n    exec_sql(\n        conn,\n        load_sql("display_snapshot_v4.sql"),\n        {\n            "batch_id": batch_id,\n            "label_template_id": label_template_id,\n            "display_ids": display_ids,\n        },\n    )\n\n    row_count = query_value(\n        conn,\n        "SELECT COUNT(*) FROM ops.display_label_batch_item WHERE display_label_batch_id = %(batch_id)s;",\n        {"batch_id": batch_id},\n    )\n\n    if row_count != len(display_ids):\n        raise RuntimeError(\n            f"Display snapshot row count mismatch: expected {len(display_ids)}, "\n            f"created {row_count}. Transaction must roll back."\n        )\n\n    logging.info(\n        "Created display batch %s label_template_id=%s rows=%s "\n        "started_by_person_id=%s started_by_text=%s",\n        batch_id,\n        label_template_id,\n        len(display_ids),\n        person_id,\n        person_text,\n    )\n\n    return int(batch_id)\n'''
    text = text[:display_start] + display_block + text[display_end:]

    # Replace Container batch creation with exact-ID freeze + row lock + signature recheck.
    container_start = text.index("def create_container_batch(")
    container_end = text.index(
        "\n\n# ============================================================\n# CSV EXPORT",
        container_start,
    )
    container_block = '''def create_container_batch(\n    conn,\n    expected_signature: str,\n) -> int | None:\n    container_ids = pending_container_ids(conn)\n    if not container_ids:\n        return None\n\n    locked_rows = query_rows(\n        conn,\n        """\n        SELECT container_id\n        FROM ref.container\n        WHERE container_id = ANY(%(container_ids)s)\n          AND print_label = true\n        ORDER BY container_id\n        FOR UPDATE;\n        """,\n        {"container_ids": container_ids},\n    )\n    locked_ids = [int(row["container_id"]) for row in locked_rows]\n\n    if locked_ids != container_ids:\n        logging.warning(\n            "Container request set changed while acquiring snapshot locks; "\n            "no batch created. expected_ids=%s locked_ids=%s",\n            container_ids,\n            locked_ids,\n        )\n        return None\n\n    locked_signature = pending_container_workload_signature(conn)\n    if locked_signature != expected_signature:\n        logging.warning(\n            "Container request/orientation state changed before snapshot freeze; "\n            "no batch created. expected=%s locked=%s",\n            expected_signature,\n            locked_signature,\n        )\n        return None\n\n    person_id, person_text = get_container_batch_actor(conn)\n\n    if person_id is None:\n        logging.warning(\n            "Container batch actor not found from ref.container audit fields. "\n            "Falling back to service identity."\n        )\n        person_id = STARTED_BY_PERSON_ID\n        person_text = STARTED_BY_TEXT\n\n    sql = """\n        INSERT INTO ops.container_label_batch (\n            started_by_person_id,\n            started_by_text,\n            status,\n            notes\n        )\n        VALUES (%(person_id)s, %(person_text)s, 'PRINTING', 'Polling service snapshot')\n        RETURNING container_label_batch_id;\n    """\n    batch_id = query_value(\n        conn,\n        sql,\n        {\n            "person_id": person_id,\n            "person_text": person_text,\n        },\n    )\n\n    exec_sql(\n        conn,\n        load_sql("container_snapshot_v4.sql"),\n        {\n            "batch_id": batch_id,\n            "container_ids": container_ids,\n        },\n    )\n\n    row_count = query_value(\n        conn,\n        "SELECT COUNT(*) FROM ops.container_label_batch_item WHERE container_label_batch_id = %(batch_id)s;",\n        {"batch_id": batch_id},\n    )\n\n    if row_count != len(container_ids):\n        raise RuntimeError(\n            f"Container snapshot row count mismatch: expected {len(container_ids)}, "\n            f"created {row_count}. Transaction must roll back."\n        )\n\n    logging.info(\n        "Created container batch %s rows=%s "\n        "started_by_person_id=%s started_by_text=%s",\n        batch_id,\n        len(container_ids),\n        person_id,\n        person_text,\n    )\n\n    return int(batch_id)\n'''
    text = text[:container_start] + container_block + text[container_end:]

    # Pass the already validated post-preflight signature into the final freeze.
    text = replace_once(
        text,
        '''                    display_batch_id = create_display_batch(\n                        conn,\n                        int(selected_display_family["label_template_id"]),\n                    )\n''',
        '''                    display_batch_id = create_display_batch(\n                        conn,\n                        int(selected_display_family["label_template_id"]),\n                        display_postflight_signature,\n                    )\n''',
        "Display create call signature",
    )

    text = replace_once(
        text,
        '''                    container_batch_id = create_container_batch(conn)\n''',
        '''                    container_batch_id = create_container_batch(\n                        conn,\n                        container_postflight_signature,\n                    )\n''',
        "Container create call signature",
    )

    V4.write_text(text, encoding="utf-8", newline="\n")

    display_sql = DISPLAY_SQL.read_text(encoding="utf-8")
    display_sql = replace_once(
        display_sql,
        "     %(label_template_id)s\n",
        "     %(label_template_id)s\n     %(display_ids)s\n",
        "Display snapshot parameter comment",
    )
    display_sql = replace_once(
        display_sql,
        '''WHERE d.print_label = true\n  AND d.label_template_id = %(label_template_id)s\n''',
        '''WHERE d.print_label = true\n  AND d.label_template_id = %(label_template_id)s\n  AND d.display_id = ANY(%(display_ids)s)\n''',
        "Display exact-ID snapshot filter",
    )
    DISPLAY_SQL.write_text(display_sql, encoding="utf-8", newline="\n")

    container_sql = CONTAINER_SQL.read_text(encoding="utf-8")
    container_sql = replace_once(
        container_sql,
        "     %(batch_id)s\n",
        "     %(batch_id)s\n     %(container_ids)s\n",
        "Container snapshot parameter comment",
    )
    container_sql = replace_once(
        container_sql,
        '''FROM ref.container c\nWHERE c.print_label = true\n''',
        '''FROM ref.container c\nWHERE c.print_label = true\n  AND c.container_id = ANY(%(container_ids)s)\n''',
        "Container exact-ID snapshot filter",
    )
    CONTAINER_SQL.write_text(container_sql, encoding="utf-8", newline="\n")

    arch = ARCH.read_text(encoding="utf-8")
    old = '''After a Retry path finally passes full preflight, v4 re-reads a workload\nsignature before batch creation. Display signatures include `display_id`,\n`display_name`, and `label_template_id`; Container signatures include\n`container_id` and `container_type_id`. If that signature changed while the\noperator dialog/preflight loop was active, v4 creates no batch and returns to a\nfresh poll so the new workload is rebuilt and preflighted before any snapshot\nstate is written.\n'''
    new = old + '''\nImmediately before the batch header is inserted, v4 freezes the exact pending\nasset IDs, acquires row locks on those selected source rows, and rechecks the\nvalidated workload signature again. The v4 snapshot SQL is restricted to those\nexact IDs. This closes the final race between preflight and snapshot creation:\na newly requested asset cannot be swept into a batch that was not preflighted,\nand a selected row cannot change its render-affecting source fields after the\nfreeze until the snapshot transaction completes.\n'''
    arch = replace_once(
        arch,
        old,
        new,
        "Architecture exact snapshot freeze",
    )
    ARCH.write_text(arch, encoding="utf-8", newline="\n")

    print("v4 exact preflight-to-snapshot freeze checkpoint applied.")


if __name__ == "__main__":
    main()
