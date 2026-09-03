from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V4 = ROOT / "label_poll_service_v4.py"
CONFIG_EXAMPLE = ROOT / "config.v4.example.ini"
ARCH = ROOT / "docs" / "01_Engineering" / "Label_Service_v4_Architecture_and_Acceptance.md"
SOP = ROOT / "docs" / "02_Operational_SOPs" / "Label_Service_v4_Printer_Recovery.md"


def fail(message: str) -> None:
    raise RuntimeError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"{label}: expected text not found")
    return text.replace(old, new, 1)


def main() -> None:
    text = V4.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import socket\nimport os\n",
        "import socket\nimport os\n\n"
        "from v4_preflight_runtime import (\n"
        "    run_operator_preflight_loop,\n"
        "    snmp_family_preflight,\n"
        "    validate_runtime_prerequisites,\n"
        ")\n",
        "v4 preflight-runtime import",
    )

    text = replace_once(
        text,
        'STARTED_BY_TEXT = CONFIG["service"]["started_by_text"]\n\n'
        'DISPLAY_CSV = Path(CONFIG["csv_files"]["display"])\n',
        'STARTED_BY_TEXT = CONFIG["service"]["started_by_text"]\n\n'
        'SNMP_OID = CONFIG.get(\n'
        '    "printing",\n'
        '    "snmp_oid",\n'
        '    fallback="1.3.6.1.4.1.2435.3.3.9.1.6.1.0",\n'
        ')\n'
        'SNMP_COMMUNITY = CONFIG.get(\n'
        '    "printing",\n'
        '    "snmp_community",\n'
        '    fallback="public",\n'
        ')\n'
        'SNMP_PORT = CONFIG.getint(\n'
        '    "printing",\n'
        '    "snmp_port",\n'
        '    fallback=161,\n'
        ')\n'
        'SNMP_TIMEOUT_SECONDS = CONFIG.getfloat(\n'
        '    "printing",\n'
        '    "snmp_timeout_seconds",\n'
        '    fallback=3.0,\n'
        ')\n\n'
        'DISPLAY_CSV = Path(CONFIG["csv_files"]["display"])\n',
        "SNMP configuration",
    )

    helper_anchor = (
        "# ============================================================\n"
        "# Printer preflight\n"
        "# ============================================================\n"
    )
    if helper_anchor not in text:
        fail("Printer preflight anchor not found")

    helper = r'''# ============================================================
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
            string_agg(display_id::text, ',' ORDER BY display_id),
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
            string_agg(container_id::text, ',' ORDER BY container_id),
            ''
        )
        FROM ref.container
        WHERE print_label = true;
        """,
    )
    return f"CONTAINER:{ids or ''}"


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


'''
    text = text.replace(helper_anchor, helper + helper_anchor, 1)

    main_anchor = (
        "def main() -> None:\n"
        "    print_banner()\n\n"
        "    startup_health_check()\n\n"
        "    while True:\n"
    )
    text = replace_once(
        text,
        main_anchor,
        "def main() -> None:\n"
        "    print_banner()\n\n"
        "    startup_health_check()\n\n"
        "    # Cancel suppresses repeated dialogs for the exact same pending\n"
        "    # request set until the set changes or the service restarts.\n"
        "    cancelled_preflight_signature: str | None = None\n\n"
        "    while True:\n",
        "main preflight cancel state",
    )

    text = replace_once(
        text,
        '''                if display_pending == 0 and container_pending == 0:
                    logging.info("No pending labels. Service idle.")
                    conn.rollback()
''',
        '''                if display_pending == 0 and container_pending == 0:
                    cancelled_preflight_signature = None
                    logging.info("No pending labels. Service idle.")
                    conn.rollback()
''',
        "idle cancel reset",
    )

    display_start = text.index(
        "                    display_preflight_failed = False"
    )
    display_end = text.index(
        "                    if container_pending > 0:",
        display_start,
    )

    display_gate = r'''                    display_preflight_signature = (
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

                    cancelled_preflight_signature = None

'''
    text = text[:display_start] + display_gate + text[display_end:]

    container_start = text.index(
        "                    container_preflight_failed = False"
    )
    container_end = text.index(
        "                # --------------------------------------------------\n"
        "                # Step 3: Only create batches AFTER printer passes",
        container_start,
    )

    container_gate = r'''                    container_preflight_signature = (
                        pending_container_workload_signature(conn)
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

                    cancelled_preflight_signature = None

'''
    text = text[:container_start] + container_gate + text[container_end:]

    V4.write_text(text, encoding="utf-8", newline="\n")

    config = CONFIG_EXAMPLE.read_text(encoding="utf-8")
    config = replace_once(
        config,
        "snmp_oid = 1.3.6.1.4.1.2435.3.3.9.1.6.1.0\n",
        "snmp_oid = 1.3.6.1.4.1.2435.3.3.9.1.6.1.0\n"
        "snmp_community = public\n"
        "snmp_port = 161\n"
        "snmp_timeout_seconds = 3.0\n",
        "config SNMP settings",
    )
    CONFIG_EXAMPLE.write_text(config, encoding="utf-8", newline="\n")

    arch = ARCH.read_text(encoding="utf-8")
    marker = "## Deferred / Future Work"
    if marker not in arch:
        fail("Architecture deferred-work marker not found")

    arch_section = r'''## v4 Full Preflight and Operator Retry/Cancel Gate

The v4 branch implementation uses Brother SNMP status as the physical
printer/media authority for PT-P950NW preflight. The decoder uses the same
documented 32-byte Brother status structure and field offsets already proven
by the repository diagnostic tools.

For the selected compatible Display or Container workload, the pre-batch gate
checks:

```text
required runtime directories exist and are writable
required SQL files exist and are UTF-8 readable
target CSV/output paths are writable
configured printer is enabled
Brother SNMP status responds
required tape width is loaded
required tape type is laminated tape
cover is closed / media is present / end-of-media is not active
every required LBX exists and opens in b-PAC
every required LBX contains the expected named objects
Windows printer queue can be inspected
Windows printer queue is empty/safe
```

Active/FAILED PostgreSQL batch guards remain before this gate.

If any gate fails, v4 shows one blocking Windows **Retry / Cancel** dialog in
the interactive PRINT-SERVER session. Retry reruns the entire gate. No
execution batch header/item or source `print_label` mutation is allowed before
the gate passes.

Cancel leaves pending source requests untouched and creates no execution
batch. To prevent a 15-second popup storm, v4 suppresses another dialog for the
exact same pending request set until that set changes or the service restarts.
The suppression is in-memory runtime state only and does not mutate
PostgreSQL.

Controlled acceptance must deliberately prove wrong 24/36 mm media, no
cassette, cover open, unavailable printer, unsafe queue, missing runtime
file/path, Retry recovery, Cancel suppression, and zero PostgreSQL execution
state change on every failed preflight.

'''
    arch = arch.replace(marker, arch_section + marker, 1)
    ARCH.write_text(arch, encoding="utf-8", newline="\n")

    sop = SOP.read_text(encoding="utf-8")
    sop = replace_once(
        sop,
        '''Cancel must:

- stop the current preflight attempt;
- return the service safely to idle;
- leave source `print_label` requests untouched;
- create no batch header/items;
- require no PostgreSQL cleanup.
''',
        '''Cancel must:

- stop the current preflight attempt;
- return the service safely to idle;
- leave source `print_label` requests untouched;
- create no batch header/items;
- require no PostgreSQL cleanup.

To prevent a 15-second popup storm, v4 suppresses another preflight dialog for
that exact unchanged pending request set. The same requests can be reconsidered
after the pending selection changes or the service is restarted. This
suppression is in-memory only and does not alter PostgreSQL request state.
''',
        "SOP Cancel behavior",
    )
    SOP.write_text(sop, encoding="utf-8", newline="\n")

    print("v4 SNMP + Retry/Cancel full-preflight checkpoint applied.")


if __name__ == "__main__":
    main()
