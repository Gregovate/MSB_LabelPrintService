from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = ROOT / "label_poll_service_v4.py"
DOC_PATH = (
    ROOT
    / "docs"
    / "01_Engineering"
    / "Label_Service_v4_Architecture_and_Acceptance.md"
)
V3_SQL_PATH = ROOT / "sql" / "container_snapshot.sql"
V4_SQL_PATH = ROOT / "sql" / "container_snapshot_v4.sql"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} match; found {count}. "
            "Refusing to guess."
        )
    return text.replace(old, new, 1)


def main() -> None:
    # Keep v3 rollback on the deployed full-URL Container payload.
    v3_sql = V3_SQL_PATH.read_text(encoding="utf-8")
    full_url_expression = (
        "'https://db.sheboyganlights.org/scan/CONT/' || "
        "c.container_id AS qr_url"
    )
    if full_url_expression not in v3_sql:
        raise RuntimeError(
            "Shared v3 Container snapshot no longer contains the expected "
            "full-URL payload. Refusing to modify anything."
        )

    # v4 intentionally migrates newly printed/replacement Containers first
    # to the compact canonical payload for fast Zebra HID scanning.
    v4_sql = v3_sql.replace(
        full_url_expression,
        "'CONT:' || c.container_id::text AS qr_url",
        1,
    )
    v4_sql = v4_sql.replace(
        "Snapshot selected containers into a batch.",
        "Snapshot selected Containers into a v4 batch.\n"
        "   v4 machine payload: CONT:<container_id>.\n"
        "   Existing deployed full-URL labels remain supported by Scan.",
        1,
    )
    V4_SQL_PATH.write_text(v4_sql, encoding="utf-8", newline="\n")

    service = SERVICE_PATH.read_text(encoding="utf-8")
    service = replace_once(
        service,
        'load_sql("container_snapshot.sql")',
        'load_sql("container_snapshot_v4.sql")',
        "v4 Container snapshot SQL reference",
    )
    SERVICE_PATH.write_text(service, encoding="utf-8", newline="\n")

    doc = DOC_PATH.read_text(encoding="utf-8")

    old_payload_section = '''## QR Payload Compatibility

Existing deployed Display and Container labels contain full scan URLs and remain supported. There is no mass relabel requirement solely to change payload format.

The scan platform also accepts compact canonical payloads such as:

```text
DISP:323
CONT:216
LOC:<location_code>
```

Compact payloads are preferred candidates for newly printed/replacement labels because Bluetooth HID entry of full URLs is slow. Final acceptance of compact payload printing must preserve backward compatibility with already-deployed full-URL labels.
'''

    new_payload_section = '''## QR Payload Compatibility and Container-First Migration

Existing deployed Display and Container labels contain full scan URLs and remain supported indefinitely. There is no mass relabel requirement solely to change payload format.

The scan platform accepts both full URLs and compact canonical payloads such as:

```text
DISP:323
CONT:216
LOC:<location_code>
```

The operational tradeoff is different by scanning device:

```text
phone camera
    full https://db.sheboyganlights.org/... QR
    -> convenient direct browser opening

Zebra Bluetooth HID scanner
    full URL
    -> slow because the scanner types every URL character

Zebra Bluetooth HID scanner
    CONT:216
    -> much shorter/faster keyboard input
```

### Accepted migration order

Containers migrate first because Container labels are expected to be the highest-volume Setup scanning workflow.

For LabelPrintService v4:

```text
new/replacement Container QR payload
    -> CONT:<container_id>

new/replacement Display QR payload
    -> keep full https://db.sheboyganlights.org/scan/DISP/<id> URL for now
```

Existing deployed Container full-URL labels continue to resolve normally. v3.4 rollback also retains its original full-URL Container snapshot behavior. Only the v4 Container snapshot path uses the compact payload.

The database column/batch field remains named `qr_url` for backward-compatible schema reasons during this Setup-critical migration, but for v4 Container rows its value is the actual machine-readable payload and therefore may be `CONT:<id>` rather than a literal URL. Do not add a second schema merely to rename this field during the Setup-critical v4 work.

Display compact-payload migration remains a separate later decision because full URLs are convenient when a phone camera is used directly.
'''

    doc = replace_once(
        doc,
        old_payload_section,
        new_payload_section,
        "QR payload compatibility section",
    )

    old_container_contract = '''Current Container quantity behavior remains two physical labels per selected Container unless separately changed and accepted.
'''
    new_container_contract = '''Current Container quantity behavior remains two physical labels per selected Container unless separately changed and accepted.

For v4, newly printed/replacement Container labels use the compact canonical machine payload `CONT:<container_id>`. This is intentionally isolated in `sql/container_snapshot_v4.sql`; the shared v3 `sql/container_snapshot.sql` remains full-URL for rollback compatibility.
'''
    doc = replace_once(
        doc,
        old_container_contract,
        new_container_contract,
        "Container compact-payload contract",
    )

    old_acceptance = '''### Compact QR payload

If compact `DISP:` / `CONT:` payload printing is enabled in v4, prove scan compatibility while retaining support for existing full-URL physical labels.
'''
    new_acceptance = '''### Compact QR payload

Container compact payload printing is enabled first in v4. Acceptance must prove at minimum:

- a newly printed/replacement Container QR encodes exactly `CONT:<container_id>`;
- Zebra HID scanning reaches the same Container scan workflow as the existing full URL;
- already-deployed full-URL Container labels continue to resolve;
- v3.4 rollback still snapshots/prints the original full Container URL;
- Display v4 QR payload remains the full URL until a separate Display migration is accepted.
'''
    doc = replace_once(
        doc,
        old_acceptance,
        new_acceptance,
        "compact payload acceptance section",
    )

    DOC_PATH.write_text(doc, encoding="utf-8", newline="\n")

    print("v4 Container-first compact QR payload checkpoint applied.")
    print("v3 shared Container snapshot left unchanged.")
    print("v4 Container snapshot uses CONT:<container_id>.")
    print("v4 Display snapshot remains full URL.")


if __name__ == "__main__":
    main()
