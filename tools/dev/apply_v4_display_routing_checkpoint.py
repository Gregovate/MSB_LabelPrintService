from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V4_PATH = ROOT / "label_poll_service_v4.py"
DOC_PATH = (
    ROOT
    / "docs"
    / "01_Engineering"
    / "Label_Service_v4_Architecture_and_Acceptance.md"
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected block not found: {label}")
    return text.replace(old, new, 1)


def patch_v4() -> None:
    text = V4_PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''def pending_display_families(conn) -> list[dict[str, Any]]:
    """
    Return the physical label families represented by pending Display
    requests. One Display execution batch may contain only one family.
    """
    return query_rows(
        conn,
        """
        SELECT
            d.label_template_id,
            lt.label_template_code,
            COUNT(*)::integer AS pending_count
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
''',
        '''def pending_display_families(conn) -> list[dict[str, Any]]:
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
''',
        "pending_display_families",
    )

    text = replace_once(
        text,
        '''DISPLAY_TEMPLATE = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["template_2_line"]
CONTAINER_HORIZONTAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["template_1_line"]
''',
        '''CONTAINER_HORIZONTAL_TEMPLATE = LABEL_FAMILIES["QR_36MM_HORIZONTAL"]["template_1_line"]
''',
        "remove DISPLAY_TEMPLATE bridge",
    )

    start = text.index("def printer_preflight(")
    end = text.index(
        "# ============================================================\n# LOGGING HELPERS",
        start,
    )

    new_preflight = '''def printer_preflight(
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
                _ = doc.Close
            except Exception:
                pass


'''
    text = text[:start] + new_preflight + text[end:]

    start = text.index(
        "# ============================================================\n# DISPLAY PRINTING"
    )
    end = text.index(
        "# ============================================================\n# CONTAINER PRINTING",
        start,
    )

    new_display_printing = '''# ============================================================
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

    wait_for_spooler_job_to_clear(
        printer_name=printer_name,
        known_job_ids=baseline_job_ids,
        expected_document=template_path.stem,
        batch_log_path=batch_log_path,
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


'''
    text = text[:start] + new_display_printing + text[end:]

    text = replace_once(
        text,
        '''def process_display(conn, display_batch_id: int) -> None:
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
''',
        '''def process_display(conn, display_batch_id: int) -> None:
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
''',
        "process_display",
    )

    text = replace_once(
        text,
        '''                # Temporary safety gate for this checkpoint.
                # Family-specific physical printer/template routing is the
                # next v4 change. Never allow a 24 mm request to fall through
                # the inherited fixed 36 mm print path.
                if (
                    selected_display_family is not None
                    and selected_display_family["label_template_code"]
                    != "QR_36MM_HORIZONTAL"
                ):
                    family_msg = (
                        "Pending Display family "
                        f'{selected_display_family["label_template_code"]} '
                        "is not yet enabled for physical printing in this "
                        "v4 checkpoint. Request remains pending."
                    )
                    logging.warning(family_msg)
                    print(family_msg)
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

''',
        "",
        "temporary 24 mm gate",
    )

    start = text.index(
        "                # --------------------------------------------------\n"
        "                # Step 2: Preflight printer BEFORE creating any batch"
    )
    end = text.index(
        "                # --------------------------------------------------\n"
        "                # Step 3: Only create batches AFTER printer passes",
        start,
    )

    new_main_preflight = '''                # --------------------------------------------------
                # Step 2: Resolve exact physical workload BEFORE batch creation
                # --------------------------------------------------
                if container_pending > 0 and display_pending == 0:
                    container_msg = (
                        "Container labels are pending, but Container rendering "
                        "is not yet enabled in this v4 checkpoint. "
                        "No batch was created and requests remain pending."
                    )
                    logging.warning(container_msg)
                    print(container_msg)
                    conn.rollback()
                    clear_lock()
                    time.sleep(POLL_SECONDS)
                    continue

                selected_family_config = None
                selected_printer_name = None
                required_display_templates: list[
                    tuple[Path, tuple[str, ...]]
                ] = []

                if display_pending > 0:
                    family_code = str(
                        selected_display_family["label_template_code"]
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
                        selected_display_family["one_line_count"]
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
                        selected_display_family["two_line_count"]
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

                    display_preflight_failed = False
                    for template_path, required_objects in (
                        required_display_templates
                    ):
                        preflight_ok, preflight_msg = printer_preflight(
                            template_path=template_path,
                            printer_name=selected_printer_name,
                            required_objects=required_objects,
                        )

                        if not preflight_ok:
                            logging.error(
                                "Display preflight failed: %s",
                                preflight_msg,
                            )
                            print(
                                f"Display preflight failed: "
                                f"{preflight_msg}"
                            )
                            display_preflight_failed = True
                            break

                        logging.info(
                            "Display preflight passed: %s",
                            preflight_msg,
                        )
                        print(
                            f"Display preflight passed: "
                            f"{preflight_msg}"
                        )

                    if display_preflight_failed:
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    queue_jobs = get_print_jobs(
                        selected_printer_name
                    )

                    if queue_jobs:
                        queue_msg = (
                            f"Printer queue is not empty: "
                            f"{summarize_print_jobs(queue_jobs)}"
                        )
                        logging.error(queue_msg)
                        print(queue_msg)
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    if container_pending > 0:
                        logging.warning(
                            "Container labels are also pending. This checkpoint "
                            "will process the Display batch only and leave "
                            "Container requests untouched."
                        )

'''
    text = text[:start] + new_main_preflight + text[end:]

    text = replace_once(
        text,
        '''                if container_pending > 0:
                    container_batch_id = create_container_batch(conn)
''',
        '''                if container_pending > 0:
                    logging.info(
                        "Container batch creation deferred in this v4 checkpoint; "
                        "pending Container requests remain untouched."
                    )
''',
        "defer Container batch creation",
    )

    V4_PATH.write_text(text, encoding="utf-8", newline="\n")


def patch_doc() -> None:
    doc = DOC_PATH.read_text(encoding="utf-8")

    doc = replace_once(
        doc,
        '''The exact one-line thresholds are to be established by physical template testing. Do not freeze arbitrary thresholds merely to finish code.

### Safe split behavior

- prefer a meaningful safe break, especially existing hyphen-delimited segments;
- do not silently rewrite the identity text to make it fit;
- snapshot the final `line1`/`line2` values used for the batch;
- once the batch is created, the frozen render intent must not be silently recomputed from later source edits.
''',
        '''For the current Display label population, the accepted v4 compatibility rule preserves the established production split behavior:

```text
display_name length <= 20
    -> one-line template

display_name length > 20
AND the name contains at least two leading hyphen-delimited segments
    -> split after the second segment
    -> two-line template

display_name length > 20
AND that two-hyphen structure is absent
    -> keep the complete name on the one-line template
```

The 2026-08-31 profile found 107 Display names over 20 characters. 103 follow the established two-hyphen split structure. Three confirmed valid long names intentionally remain one-line:

```text
CL-LollipopTrailerNetLights
MI-ProgramTrailerPallets
PB-SlidingPenguinsString
```

`display_id 650` (`SecurityLight-FoodTruck`) was identified during this review as incorrect upstream/master data that does not follow the naming standard and does not represent a real Food Truck Display. It must be corrected upstream and re-parsed; v4 must not add a renderer special case for that bad row.

The purpose of the one-line/two-line selection is to avoid printing hundreds of otherwise compact labels as wasteful single-line tape while preserving exact Display identity text.

### Safe split behavior

- preserve the exact Display name content;
- use the established second-hyphen split where the naming structure supports it;
- allow the confirmed valid long exceptions above to remain one-line;
- snapshot the final `line1`/`line2` values used for the batch;
- once the batch is created, the frozen render intent must not be silently recomputed from later source edits.
''',
        "Display rendering contract",
    )

    replacements = (
        (
            '''`objLine1` / `objLine2` are the installer-facing descriptive wiring text. They should contain the field plug identifier and useful connection metadata supplied by the structured FieldWiring system.''',
            '''`objLine1` / `objLine2` are the installer-facing descriptive wiring text. They contain only the useful descriptive connection metadata supplied by the structured FieldWiring system. Field plug identifiers such as `P1` are not printed.''',
            "Wiring descriptive text",
        ),
        (
            '''objLine1/objLine2 = field plug P1 + useful Caroler/Mouth Open 2 metadata''',
            '''objLine1/objLine2 = Caroler / Mouth Open 2''',
            "Wiring example",
        ),
        (
            '''Only the supplied plug/metadata text is eligible for safe splitting between `objLine1` and `objLine2`.''',
            '''Only the supplied descriptive metadata is eligible for safe splitting between `objLine1` and `objLine2`.''',
            "Wiring split rule",
        ),
        (
            '''showing the physical controller output/channel number prominently while retaining the field plug and useful connection metadata for confirmation.''',
            '''showing the physical controller output/channel number prominently while retaining only useful descriptive connection metadata for confirmation.''',
            "Wiring visual goal",
        ),
        (
            '''structured channel/output, plug, and printable metadata fields unambiguously.''',
            '''structured channel/output and printable metadata fields unambiguously.''',
            "Wiring source mapping",
        ),
        (
            '''full FieldWiring print-request UI and structured channel/plug/metadata source mapping;''',
            '''full FieldWiring print-request UI and structured channel/printable-metadata source mapping;''',
            "Deferred Wiring mapping",
        ),
    )

    for old, new, label in replacements:
        doc = replace_once(doc, old, new, label)

    DOC_PATH.write_text(doc, encoding="utf-8", newline="\n")


def main() -> None:
    patch_v4()
    patch_doc()
    print("Applied v4 Display family/template routing checkpoint.")
    print("Modified:")
    print(f"  {V4_PATH.relative_to(ROOT)}")
    print(f"  {DOC_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
