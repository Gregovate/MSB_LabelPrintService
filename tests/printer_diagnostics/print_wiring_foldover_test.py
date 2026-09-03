from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

import win32com.client


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from v4_preflight_runtime import snmp_family_preflight  # noqa: E402


DEFAULT_TEMPLATE = Path(
    r"C:\MSB_LabelService\templates\pt_p950nw"
    r"\wiring_label_2_line_horz_12mm_double_sided.lbx"
)
DEFAULT_EVIDENCE_DIR = Path(
    r"C:\MSB_LabelService\tests\printer_diagnostics\evidence"
)
DEFAULT_PRINTER = "Brother PT-P950NW"
DEFAULT_HOST = "192.168.5.12"
DEFAULT_OID = "1.3.6.1.4.1.2435.3.3.9.1.6.1.0"
DEFAULT_FIXTURE_CSV = (
    REPO_ROOT
    / "templates"
    / "pt_p950nw"
    / "csv"
    / "wiring_label_12mm_real_fieldlead_test.csv"
)

REQUIRED_WIDTH_MM = 12
PRINT_FLAGS = 0x200 | 0x400 | 0x04000000

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print exactly one 12 mm Wiring fold-over test label after a "
            "mandatory live PT-P950NW cassette/status preflight."
        )
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--printer", default=DEFAULT_PRINTER)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--oid", default=DEFAULT_OID)
    parser.add_argument("--community", default="public")
    parser.add_argument("--port", type=int, default=161)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--fixture-csv",
        type=Path,
        default=DEFAULT_FIXTURE_CSV,
        help="Tracked CSV containing real FieldWiring label fixtures.",
    )
    parser.add_argument(
        "--fixture-row",
        type=int,
        default=1,
        help="One-based data-row number from the fixture CSV. Default: 1.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=DEFAULT_EVIDENCE_DIR,
    )
    return parser.parse_args()


def load_fixture(path: Path, row_number: int) -> dict[str, str]:
    if row_number < 1:
        raise ValueError("--fixture-row must be at least 1")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if row_number > len(rows):
        raise ValueError(
            f"Fixture row {row_number} does not exist; CSV has {len(rows)} rows"
        )

    row = rows[row_number - 1]
    channel = (row.get("output_plug") or "").strip()
    line1 = (row.get("line1") or "").strip()
    line2 = (row.get("line2") or "").strip()

    if not channel or not line1:
        raise ValueError(
            f"Fixture row {row_number} requires output_plug and line1"
        )

    if channel.isdigit():
        channel = channel.zfill(2)

    return {
        "objChannel": channel,
        "objLine1": line1,
        "objLine2": line2,
        "objChannel_right": channel,
        "objLine1_right": line1,
        "objLine2_right": line2,
    }


def close_document(document: object, print_started: bool) -> list[str]:
    results: list[str] = []

    if print_started:
        try:
            end_result = document.EndPrint
            results.append(f"EndPrint result={end_result}")
        except Exception as exc:
            results.append(f"WARNING EndPrint raised: {exc}")

    try:
        close_result = document.Close
        results.append(f"Close result={close_result}")
    except Exception as exc:
        results.append(f"WARNING Close raised: {exc}")

    return results


def main() -> int:
    args = parse_args()
    template = args.template.resolve()
    fixture_csv = args.fixture_csv.resolve()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if not template.is_file():
        raise FileNotFoundError(f"Template does not exist: {template}")
    if not fixture_csv.is_file():
        raise FileNotFoundError(f"Fixture CSV does not exist: {fixture_csv}")

    test_values = load_fixture(fixture_csv, args.fixture_row)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_lines = [
        "MSB 12 mm Wiring fold-over physical print test",
        f"timestamp={timestamp}",
        f"template={template}",
        f"printer={args.printer}",
        f"host={args.host}",
        f"fixture={fixture_csv}",
        f"fixture_row={args.fixture_row}",
    ]

    print("Checking the PT-P950NW before any b-PAC print operation...")
    preflight_ok, preflight_message = snmp_family_preflight(
        host=args.host,
        family_code="WIRING_12MM_HORIZONTAL",
        expected_width_mm=REQUIRED_WIDTH_MM,
        expected_media_type="LAMINATED_TAPE",
        oid=args.oid,
        community=args.community,
        port=args.port,
        timeout=args.timeout,
    )
    print(preflight_message)
    if not preflight_ok:
        raise RuntimeError(
            "12 mm Wiring preflight FAILED; nothing was printed. "
            + preflight_message
        )
    evidence_lines.append(f"preflight_detail={preflight_message}")
    evidence_lines.append("preflight=PASS")
    print("PREFLIGHT PASS — 12 mm laminated tape is loaded and ready.")

    document = win32com.client.Dispatch("bpac.Document")
    opened = document.Open(str(template))
    if not opened:
        raise RuntimeError(f"b-PAC could not open template: {template}")

    print_started = False
    try:
        objects: dict[str, object] = {}
        for object_name, value in test_values.items():
            obj = document.GetObject(object_name)
            if obj is None:
                raise RuntimeError(
                    f"Template object not found: {object_name}; nothing was printed"
                )
            objects[object_name] = obj

        for object_name, value in test_values.items():
            objects[object_name].Text = value
            evidence_lines.append(f"{object_name}={value}")
            print(f"Assigned {object_name}={value!r}")

        set_printer_ok = document.SetPrinter(args.printer, True)
        evidence_lines.append(f"SetPrinter={set_printer_ok}")
        if not set_printer_ok:
            raise RuntimeError(
                f"b-PAC could not set printer {args.printer!r}; nothing was printed"
            )

        start_result = document.StartPrint("", PRINT_FLAGS)
        print_started = True
        evidence_lines.append(
            f"StartPrint flags=0x{PRINT_FLAGS:08X} result={start_result}"
        )

        print_result = document.PrintOut(1, 0)
        evidence_lines.append(f"PrintOut copies=1 result={print_result}")
        if not print_result:
            raise RuntimeError("b-PAC PrintOut returned failure")
    finally:
        cleanup_lines = close_document(document, print_started)
        evidence_lines.extend(cleanup_lines)
        for line in cleanup_lines:
            print(line)

    evidence_lines.append("submission=PASS")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = (
        args.evidence_dir
        / f"wiring_foldover_physical_{timestamp}.txt"
    )
    evidence_path.write_text("\n".join(evidence_lines) + "\n", encoding="utf-8")

    print()
    print("ONE 12 MM WIRING FOLD-OVER LABEL WAS SUBMITTED")
    print(f"Evidence: {evidence_path}")
    print()
    print("Physical acceptance check:")
    print(f"  Both halves show Channel {test_values['objChannel']}.")
    print(f"  Both halves show {test_values['objLine1']}.")
    print(f"  Both halves show {test_values['objLine2']}.")
    print("  Text orientation is correct after folding around a wire.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
