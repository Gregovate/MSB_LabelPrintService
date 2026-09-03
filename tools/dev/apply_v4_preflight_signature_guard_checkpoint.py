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

    text = replace_once(
        text,
        '''        SELECT COALESCE(
            string_agg(display_id::text, ',' ORDER BY display_id),
            ''
        )
        FROM ref.display
        WHERE print_label = true
          AND label_template_id = %(label_template_id)s;
''',
        '''        SELECT COALESCE(
            string_agg(
                display_id::text
                || ':' || COALESCE(display_name, '')
                || ':' || COALESCE(label_template_id::text, ''),
                E'\\n'
                ORDER BY display_id
            ),
            ''
        )
        FROM ref.display
        WHERE print_label = true
          AND label_template_id = %(label_template_id)s;
''',
        "Display workload signature fields",
    )

    text = replace_once(
        text,
        '''        SELECT COALESCE(
            string_agg(container_id::text, ',' ORDER BY container_id),
            ''
        )
        FROM ref.container
        WHERE print_label = true;
''',
        '''        SELECT COALESCE(
            string_agg(
                container_id::text
                || ':' || COALESCE(container_type_id::text, ''),
                E'\\n'
                ORDER BY container_id
            ),
            ''
        )
        FROM ref.container
        WHERE print_label = true;
''',
        "Container workload signature fields",
    )

    display_old = '''                    cancelled_preflight_signature = None

                    if container_pending > 0:
'''
    display_new = '''                    display_postflight_signature = (
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
                        display_postflight_signature
                        != display_preflight_signature
                    ):
                        logging.warning(
                            "Display pending workload changed during preflight; "
                            "no batch will be created. before=%s after=%s",
                            display_preflight_signature,
                            display_postflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    cancelled_preflight_signature = None

                    if container_pending > 0:
'''
    text = replace_once(
        text,
        display_old,
        display_new,
        "Display post-preflight signature guard",
    )

    container_old = '''                    cancelled_preflight_signature = None

                # --------------------------------------------------
                # Step 3: Only create batches AFTER printer passes Updated 04/16/26 for warning and loop
'''
    container_new = '''                    container_postflight_signature = (
                        pending_container_workload_signature(conn)
                    )
                    if (
                        container_postflight_signature
                        != container_preflight_signature
                    ):
                        logging.warning(
                            "Container pending workload changed during preflight; "
                            "no batch will be created. before=%s after=%s",
                            container_preflight_signature,
                            container_postflight_signature,
                        )
                        conn.rollback()
                        clear_lock()
                        time.sleep(POLL_SECONDS)
                        continue

                    cancelled_preflight_signature = None

                # --------------------------------------------------
                # Step 3: Only create batches AFTER printer passes Updated 04/16/26 for warning and loop
'''
    text = replace_once(
        text,
        container_old,
        container_new,
        "Container post-preflight signature guard",
    )

    V4.write_text(text, encoding="utf-8", newline="\n")

    arch = ARCH.read_text(encoding="utf-8")
    arch = replace_once(
        arch,
        '''Cancel leaves pending source requests untouched and creates no execution
batch. To prevent a 15-second popup storm, v4 suppresses another dialog for the
exact same pending request set until that set changes or the service restarts.
The suppression is in-memory runtime state only and does not mutate
PostgreSQL.
''',
        '''Cancel leaves pending source requests untouched and creates no execution
batch. To prevent a 15-second popup storm, v4 suppresses another dialog for the
exact same pending request set until that set changes or the service restarts.
The suppression is in-memory runtime state only and does not mutate
PostgreSQL.

After a Retry path finally passes full preflight, v4 re-reads a workload
signature before batch creation. Display signatures include `display_id`,
`display_name`, and `label_template_id`; Container signatures include
`container_id` and `container_type_id`. If that signature changed while the
operator dialog/preflight loop was active, v4 creates no batch and returns to a
fresh poll so the new workload is rebuilt and preflighted before any snapshot
state is written.
''',
        "Architecture request-change guard",
    )
    ARCH.write_text(arch, encoding="utf-8", newline="\n")

    print("v4 post-preflight workload-signature guard applied.")


if __name__ == "__main__":
    main()
