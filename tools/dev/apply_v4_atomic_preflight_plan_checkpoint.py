from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "label_poll_service_v4.py"
ARCH = ROOT / "docs" / "01_Engineering" / "Label_Service_v4_Architecture_and_Acceptance.md"


def fail(message: str) -> None:
    raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"{label}: expected text not found")
    return text.replace(old, new, 1)


def main() -> None:
    text = V4.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # Atomic plan helpers: the physical-template requirements and
    # workload signature come from the same PostgreSQL statement.
    # ------------------------------------------------------------
    anchor = '''def pending_container_count(conn) -> int:\n'''
    if anchor not in text:
        fail("pending_container_count anchor not found")

    helpers = '''def pending_display_preflight_plan(\n    conn,\n    label_template_id: int,\n) -> dict[str, Any] | None:\n    \"\"\"Return Display render counts + signature from one DB statement.\"\"\"\n    rows = query_rows(\n        conn,\n        \"\"\"\n        SELECT\n            d.label_template_id,\n            lt.label_template_code,\n            COUNT(*)::integer AS pending_count,\n            COUNT(*) FILTER (\n                WHERE LENGTH(d.display_name) <= 20\n                   OR d.display_name !~ '^[^-]+-[^-]+-'\n            )::integer AS one_line_count,\n            COUNT(*) FILTER (\n                WHERE LENGTH(d.display_name) > 20\n                  AND d.display_name ~ '^[^-]+-[^-]+-'\n            )::integer AS two_line_count,\n            'DISPLAY:' || d.label_template_id::text || ':' ||\n            COALESCE(\n                string_agg(\n                    d.display_id::text\n                    || ':' || COALESCE(d.display_name, '')\n                    || ':' || COALESCE(d.label_template_id::text, ''),\n                    E'\\n'\n                    ORDER BY d.display_id\n                ),\n                ''\n            ) AS workload_signature\n        FROM ref.display d\n        JOIN ref.label_template lt\n          ON lt.label_template_id = d.label_template_id\n        WHERE d.print_label = true\n          AND d.label_template_id = %(label_template_id)s\n        GROUP BY\n            d.label_template_id,\n            lt.label_template_code;\n        \"\"\",\n        {\"label_template_id\": label_template_id},\n    )\n    return rows[0] if rows else None\n\n\ndef pending_container_preflight_plan(conn) -> dict[str, Any]:\n    \"\"\"Return Container orientation counts + signature from one DB statement.\"\"\"\n    rows = query_rows(\n        conn,\n        \"\"\"\n        SELECT\n            COUNT(*)::integer AS pending_count,\n            COUNT(*) FILTER (\n                WHERE container_type_id = 1\n            )::integer AS vertical_count,\n            COUNT(*) FILTER (\n                WHERE container_type_id IS DISTINCT FROM 1\n            )::integer AS horizontal_count,\n            'CONTAINER:' ||\n            COALESCE(\n                string_agg(\n                    container_id::text\n                    || ':' || COALESCE(container_type_id::text, ''),\n                    E'\\n'\n                    ORDER BY container_id\n                ),\n                ''\n            ) AS workload_signature\n        FROM ref.container\n        WHERE print_label = true;\n        \"\"\",\n    )\n    return rows[0]\n\n\n'''

    if "def pending_display_preflight_plan(" not in text:
        text = text.replace(anchor, helpers + anchor, 1)

    # ------------------------------------------------------------
    # Display: use the atomic plan rather than stale counts from the
    # earlier multi-family discovery query.
    # ------------------------------------------------------------
    old = '''                if display_pending > 0:\n                    family_code = str(\n                        selected_display_family[\"label_template_code\"]\n                    )\n'''
    new = '''                if display_pending > 0:\n                    display_plan = pending_display_preflight_plan(\n                        conn,\n                        int(selected_display_family[\"label_template_id\"]),\n                    )\n                    if display_plan is None:\n                        logging.warning(\n                            \"Selected Display workload disappeared before \"\n                            \"preflight planning; restarting poll.\"\n                        )\n                        conn.rollback()\n                        clear_lock()\n                        time.sleep(POLL_SECONDS)\n                        continue\n\n                    family_code = str(\n                        display_plan[\"label_template_code\"]\n                    )\n'''
    text = replace_once(text, old, new, "Display atomic plan start")

    text = text.replace(
        'selected_display_family["one_line_count"]',
        'display_plan["one_line_count"]',
    )
    text = text.replace(
        'selected_display_family["two_line_count"]',
        'display_plan["two_line_count"]',
    )

    old = '''                    display_preflight_signature = (\n                        pending_display_workload_signature(\n                            conn,\n                            int(\n                                selected_display_family[\n                                    \"label_template_id\"\n                                ]\n                            ),\n                        )\n                    )\n'''
    new = '''                    display_preflight_signature = str(\n                        display_plan[\"workload_signature\"]\n                    )\n'''
    text = replace_once(
        text,
        old,
        new,
        "Display atomic plan signature",
    )

    # ------------------------------------------------------------
    # Container: derive the required orientation templates from the
    # same statement that produced the signature.
    # ------------------------------------------------------------
    old = '''                elif container_pending > 0:\n                    container_orientations = pending_container_orientations(conn)\n                    container_printer_name = None\n'''
    new = '''                elif container_pending > 0:\n                    container_plan = pending_container_preflight_plan(conn)\n                    if int(container_plan[\"pending_count\"]) == 0:\n                        logging.warning(\n                            \"Pending Container workload disappeared before \"\n                            \"preflight planning; restarting poll.\"\n                        )\n                        conn.rollback()\n                        clear_lock()\n                        time.sleep(POLL_SECONDS)\n                        continue\n\n                    container_orientations: list[dict[str, Any]] = []\n                    if int(container_plan[\"vertical_count\"]) > 0:\n                        container_orientations.append(\n                            {\n                                \"label_orientation\": \"VERTICAL\",\n                                \"pending_count\": int(\n                                    container_plan[\"vertical_count\"]\n                                ),\n                            }\n                        )\n                    if int(container_plan[\"horizontal_count\"]) > 0:\n                        container_orientations.append(\n                            {\n                                \"label_orientation\": \"HORIZONTAL\",\n                                \"pending_count\": int(\n                                    container_plan[\"horizontal_count\"]\n                                ),\n                            }\n                        )\n\n                    container_printer_name = None\n'''
    text = replace_once(text, old, new, "Container atomic plan start")

    old = '''                    container_preflight_signature = (\n                        pending_container_workload_signature(conn)\n                    )\n'''
    new = '''                    container_preflight_signature = str(\n                        container_plan[\"workload_signature\"]\n                    )\n'''
    text = replace_once(
        text,
        old,
        new,
        "Container atomic plan signature",
    )

    V4.write_text(text, encoding="utf-8", newline="\n")

    # ------------------------------------------------------------
    # Durable architecture note.
    # ------------------------------------------------------------
    arch = ARCH.read_text(encoding="utf-8")
    marker = '''Immediately before the batch header is inserted, v4 freezes the exact pending\nasset IDs, acquires row locks on those selected source rows, and rechecks the\nvalidated workload signature again. The v4 snapshot SQL is restricted to those\nexact IDs. The frozen rows also supply batch requester attribution. This closes\nthe final race between preflight and snapshot creation: a newly requested asset\ncannot be swept into a batch that was not preflighted, and a selected row cannot\nchange its render-affecting source fields after the freeze until the snapshot\ntransaction completes.\n'''
    addition = marker + '''\nThe physical preflight plan itself is also atomic with its initial workload\nsignature. For Displays, one PostgreSQL statement returns the selected family,\none-line count, two-line count, and signature. For Containers, one statement\nreturns horizontal count, vertical count, and signature. This prevents a request\narriving between template-plan discovery and signature capture from introducing\nan unpreflighted physical template into the later exact-ID snapshot.\n'''

    if "The physical preflight plan itself is also atomic" not in arch:
        arch = replace_once(
            arch,
            marker,
            addition,
            "Architecture atomic preflight plan",
        )
        ARCH.write_text(arch, encoding="utf-8", newline="\n")

    print("v4 atomic preflight-plan checkpoint applied.")


if __name__ == "__main__":
    main()
