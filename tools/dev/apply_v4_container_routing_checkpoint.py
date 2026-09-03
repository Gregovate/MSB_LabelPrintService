from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY_PATH = ROOT / "label_poll_service_v4.py"
DOC_PATH = ROOT / "docs" / "01_Engineering" / "Label_Service_v4_Architecture_and_Acceptance.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected block not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PY_PATH.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 1. Generic Container template object contract
    # ------------------------------------------------------------
    text = replace_once(
        text,
        'CONTAINER_OBJ_LABEL = "objContainerLabel"\nCONTAINER_OBJ_QR = "objQr"',
        'CONTAINER_OBJ_LINE1 = "objLine1"\nCONTAINER_OBJ_QR = "objQr"',
        "Container object constants",
    )

    text = replace_once(
        text,
        '# Temporary v4 bridge aliases.\n# These keep the inherited v3 print functions runnable while they are\n# converted to use LABEL_FAMILIES directly.\nPRINTER_NAME = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["printer"]["queue_name"]\n\nCONTAINER_HORIZONTAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["template_1_line"]\nCONTAINER_VERTICAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_VERTICAL"]["template_1_line"]',
        '# Accepted v4 Container physical templates.\n# Containers remain 36 mm, with orientation determined by the existing\n# database rule. Both use the generic QR one-line object contract.\nCONTAINER_HORIZONTAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["template_1_line"]\nCONTAINER_VERTICAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_VERTICAL"]["template_1_line"]',
        "v4 bridge aliases",
    )

    # ------------------------------------------------------------
    # 2. Pending Container orientation discovery
    # ------------------------------------------------------------
    old = '''def pending_container_count(conn) -> int:\n    return int(query_value(\n        conn,\n        "SELECT COUNT(*) FROM ref.container WHERE print_label = true;",\n    ) or 0)\n'''

    new = '''def pending_container_count(conn) -> int:\n    return int(query_value(\n        conn,\n        "SELECT COUNT(*) FROM ref.container WHERE print_label = true;",\n    ) or 0)\n\n\ndef pending_container_orientations(conn) -> list[dict[str, Any]]:\n    """Return the orientation groups represented by pending Containers."""\n    return query_rows(\n        conn,\n        """\n        SELECT\n            CASE\n                WHEN container_type_id = 1 THEN 'VERTICAL'\n                ELSE 'HORIZONTAL'\n            END AS label_orientation,\n            COUNT(*)::integer AS pending_count\n        FROM ref.container\n        WHERE print_label = true\n        GROUP BY 1\n        ORDER BY 1;\n        """,\n    )\n'''

    text = replace_once(text, old, new, "pending Container helpers")

    # ------------------------------------------------------------
    # 3. Replace inherited Container renderer with generic QR renderer
    # ------------------------------------------------------------
    start = text.index("def print_container_batch(")
    end = text.index(
        "# ============================================================\n# FAILURE HANDLING HELPERS",
        start,
    )

    new_container_renderer = '''def print_container_batch(\n    rows: list[dict[str, Any]],\n    template_path: Path,\n    batch_log_path: Path,\n    orientation: str,\n) -> None:\n    """\n    Print Container labels using the accepted generic QR one-line\n    template contract: objLine1 + objQr.\n    """\n    if not rows:\n        write_batch_log(\n            batch_log_path,\n            f"No {orientation.lower()} Container rows to print.",\n        )\n        return\n\n    normalized_orientation = orientation.upper()\n    if normalized_orientation == "VERTICAL":\n        family_code = "QR_36MM_VERTICAL"\n    elif normalized_orientation == "HORIZONTAL":\n        family_code = "QR_36MM_HORIZONTAL"\n    else:\n        raise RuntimeError(\n            f"Unsupported Container label orientation: {orientation}"\n        )\n\n    family = LABEL_FAMILIES[family_code]\n    printer_name = family["printer"]["queue_name"]\n\n    rows_to_print = duplicate_container_rows(rows)\n    write_batch_log(\n        batch_log_path,\n        f"{normalized_orientation} Container rows duplicated for quantity 2. "\n        f"Original={len(rows)} Effective={len(rows_to_print)}",\n    )\n\n    baseline_jobs = get_print_jobs(printer_name)\n    baseline_job_ids = {\n        int(job.get("JobId"))\n        for job in baseline_jobs\n    }\n    write_batch_log(\n        batch_log_path,\n        f"Baseline queue before {normalized_orientation.lower()} Container "\n        f"print: {summarize_print_jobs(baseline_jobs)}",\n    )\n\n    doc = create_bpac_document()\n\n    write_batch_log(\n        batch_log_path,\n        f"Opening {normalized_orientation.lower()} Container template: "\n        f"{template_path}",\n    )\n    opened = doc.Open(str(template_path))\n    write_batch_log(batch_log_path, f"Template opened: {opened}")\n    if not opened:\n        raise RuntimeError(\n            f"b-PAC could not open the {normalized_orientation.lower()} "\n            "Container template."\n        )\n\n    set_printer_ok = doc.SetPrinter(printer_name, True)\n    write_batch_log(\n        batch_log_path,\n        f"SetPrinter('{printer_name}') = {set_printer_ok}",\n    )\n    if not set_printer_ok:\n        raise RuntimeError(\n            f"b-PAC could not set the {normalized_orientation.lower()} "\n            "Container printer."\n        )\n\n    log_media_status(doc, batch_log_path)\n\n    obj_line1 = get_required_object(doc, CONTAINER_OBJ_LINE1)\n    obj_qr = get_required_object(doc, CONTAINER_OBJ_QR)\n\n    write_batch_log(\n        batch_log_path,\n        f"Resolved Container objects: line1={CONTAINER_OBJ_LINE1}, "\n        f"qr={CONTAINER_OBJ_QR}",\n    )\n\n    doc.StartPrint("", PRINT_FLAGS)\n    write_batch_log(\n        batch_log_path,\n        f"StartPrint called with flags={hex(PRINT_FLAGS)}",\n    )\n\n    for idx, row in enumerate(rows_to_print, start=1):\n        obj_line1.Text = row.get("container_label", "") or ""\n        obj_qr.Text = row.get("qr_url", "") or ""\n\n        result = doc.PrintOut(1, 0)\n        write_batch_log(\n            batch_log_path,\n            f"Queued {normalized_orientation.lower()} Container label "\n            f"{idx}/{len(rows_to_print)} "\n            f"container_id={row.get('container_id')} result={result} "\n            f"label={row.get('container_label')}",\n        )\n\n        if not result:\n            raise RuntimeError(\n                f"{normalized_orientation} Container PrintOut failed on "\n                f"row {idx} container_id={row.get('container_id')}"\n            )\n\n    finish_bpac_document(doc, batch_log_path)\n\n    wait_for_spooler_job_to_clear(\n        printer_name=printer_name,\n        known_job_ids=baseline_job_ids,\n        expected_document=template_path.stem,\n        batch_log_path=batch_log_path,\n    )\n\n\n'''

    text = text[:start] + new_container_renderer + text[end:]

    # ------------------------------------------------------------
    # 4. Remove Container-only safety block now that rendering exists
    # ------------------------------------------------------------
    old = '''                if container_pending > 0 and display_pending == 0:\n                    container_msg = (\n                        "Container labels are pending, but Container rendering "\n                        "is not yet enabled in this v4 checkpoint. "\n                        "No batch was created and requests remain pending."\n                    )\n                    logging.warning(container_msg)\n                    print(container_msg)\n                    conn.rollback()\n                    clear_lock()\n                    time.sleep(POLL_SECONDS)\n                    continue\n\n'''
    text = replace_once(text, old, "", "Container-only safety block")

    # ------------------------------------------------------------
    # 5. Add Container preflight when no Display batch is selected
    # ------------------------------------------------------------
    anchor = '''                    if container_pending > 0:\n                        logging.warning(\n                            "Container labels are also pending. This checkpoint "\n                            "will process the Display batch only and leave "\n                            "Container requests untouched."\n                        )\n\n'''

    container_preflight = anchor + '''                elif container_pending > 0:\n                    container_orientations = pending_container_orientations(conn)\n                    container_printer_name = None\n                    required_container_templates: list[\n                        tuple[Path, tuple[str, ...]]\n                    ] = []\n\n                    for orientation_row in container_orientations:\n                        orientation = str(\n                            orientation_row["label_orientation"]\n                        ).upper()\n\n                        if orientation == "VERTICAL":\n                            container_family_code = "QR_36MM_VERTICAL"\n                        elif orientation == "HORIZONTAL":\n                            container_family_code = "QR_36MM_HORIZONTAL"\n                        else:\n                            raise RuntimeError(\n                                f"Unsupported pending Container orientation: "\n                                f"{orientation}"\n                            )\n\n                        container_family = LABEL_FAMILIES[\n                            container_family_code\n                        ]\n                        template = container_family["template_1_line"]\n                        if template is None:\n                            raise RuntimeError(\n                                f"Container family '{container_family_code}' "\n                                "has no one-line template."\n                            )\n\n                        queue_name = container_family["printer"][\n                            "queue_name"\n                        ]\n                        if container_printer_name is None:\n                            container_printer_name = queue_name\n                        elif container_printer_name != queue_name:\n                            raise RuntimeError(\n                                "Pending Container orientations resolve to "\n                                "different printer queues; refusing to create "\n                                "one execution batch."\n                            )\n\n                        required_container_templates.append(\n                            (\n                                template,\n                                (\n                                    CONTAINER_OBJ_LINE1,\n                                    CONTAINER_OBJ_QR,\n                                ),\n                            )\n                        )\n\n                    container_preflight_failed = False\n                    for template_path, required_objects in (\n                        required_container_templates\n                    ):\n                        preflight_ok, preflight_msg = printer_preflight(\n                            template_path=template_path,\n                            printer_name=container_printer_name,\n                            required_objects=required_objects,\n                        )\n\n                        if not preflight_ok:\n                            logging.error(\n                                "Container preflight failed: %s",\n                                preflight_msg,\n                            )\n                            print(\n                                f"Container preflight failed: "\n                                f"{preflight_msg}"\n                            )\n                            container_preflight_failed = True\n                            break\n\n                        logging.info(\n                            "Container preflight passed: %s",\n                            preflight_msg,\n                        )\n                        print(\n                            f"Container preflight passed: "\n                            f"{preflight_msg}"\n                        )\n\n                    if container_preflight_failed:\n                        conn.rollback()\n                        clear_lock()\n                        time.sleep(POLL_SECONDS)\n                        continue\n\n                    queue_jobs = get_print_jobs(\n                        container_printer_name\n                    )\n                    if queue_jobs:\n                        queue_msg = (\n                            f"Printer queue is not empty: "\n                            f"{summarize_print_jobs(queue_jobs)}"\n                        )\n                        logging.error(queue_msg)\n                        print(queue_msg)\n                        conn.rollback()\n                        clear_lock()\n                        time.sleep(POLL_SECONDS)\n                        continue\n\n'''

    text = replace_once(
        text,
        anchor,
        container_preflight,
        "Container preflight insertion point",
    )

    # ------------------------------------------------------------
    # 6. Create a Container batch only when no Display batch is selected
    # ------------------------------------------------------------
    old = '''                if display_pending > 0:\n                    display_batch_id = create_display_batch(\n                        conn,\n                        int(selected_display_family["label_template_id"]),\n                    )\n\n                if container_pending > 0:\n                    logging.info(\n                        "Container batch creation deferred in this v4 checkpoint; "\n                        "pending Container requests remain untouched."\n                    )\n'''

    new = '''                if display_pending > 0:\n                    display_batch_id = create_display_batch(\n                        conn,\n                        int(selected_display_family["label_template_id"]),\n                    )\n                elif container_pending > 0:\n                    container_batch_id = create_container_batch(conn)\n'''

    text = replace_once(text, old, new, "Container batch creation")

    # ------------------------------------------------------------
    # 7. Update inherited header comments where they describe v3 objects
    # ------------------------------------------------------------
    text = text.replace(
        '''#   - Container template object names:\n#       objContainerLabel\n#       objQr''',
        '''#   - v4 Container generic QR template object names:\n#       objLine1\n#       objQr''',
        1,
    )

    PY_PATH.write_text(text, encoding="utf-8", newline="\n")

    # ------------------------------------------------------------
    # 8. Keep the durable architecture contract synchronized
    # ------------------------------------------------------------
    doc = DOC_PATH.read_text(encoding="utf-8")

    old = '''The existing database-driven `label_orientation` rule remains. v4 replaces the old Container-specific LBX filenames with the generic physical templates; it does not collapse all Containers to one orientation.\n\nCurrent Container quantity behavior remains two physical labels per selected Container unless separately changed and accepted.\n'''

    new = '''The existing database-driven `label_orientation` rule remains. v4 replaces the old Container-specific LBX filenames with the generic physical templates; it does not collapse all Containers to one orientation.\n\nThe generic Container QR template object contract is:\n\n```text\nobjLine1 = existing human-readable Container label, such as C216\nobjQr    = Container QR payload\n```\n\nThe old Container-specific `objContainerLabel` object is a v3 template dependency and is not part of the accepted v4 generic template contract.\n\nCurrent Container quantity behavior remains two physical labels per selected Container unless separately changed and accepted.\n\nDuring the current polling transition, if both Display and Container requests are pending, v4 processes the selected Display workload first and leaves Container requests untouched for a later poll. This is a deterministic safety rule that avoids mixing 24 mm Display work with 36 mm Container work in one execution cycle.\n'''

    doc = replace_once(doc, old, new, "Container architecture contract")
    DOC_PATH.write_text(doc, encoding="utf-8", newline="\n")

    print("v4 Container routing checkpoint applied.")


if __name__ == "__main__":
    main()
