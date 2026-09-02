from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import win32com.client


DEFAULT_TEMPLATE = Path(
    r"C:\MSB_LabelService\templates\pt_p950nw"
    r"\wiring_label_2_line_horz_12mm_double_sided.lbx"
)
DEFAULT_OUTPUT_DIR = Path(
    r"C:\MSB_LabelService\tests\printer_diagnostics\evidence"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE_CSV = (
    REPO_ROOT
    / "templates"
    / "pt_p950nw"
    / "csv"
    / "wiring_label_12mm_real_fieldlead_test.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assign one Wiring record through b-PAC and export a bitmap. "
            "This probe does not call SetPrinter, StartPrint, or PrintOut."
        )
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="Path to the double-sided Wiring LBX template.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the timestamped BMP evidence file.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=180,
        help="Bitmap export resolution. Default: 180 dpi.",
    )
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


def close_document(document: object) -> None:
    """Use the property-style close behavior proven on PRINT-SERVER."""
    try:
        _ = document.Close
    except Exception as exc:
        print(f"WARNING: b-PAC Close raised: {exc}")


def main() -> int:
    args = parse_args()
    template = args.template.resolve()
    fixture_csv = args.fixture_csv.resolve()

    if not template.is_file():
        raise FileNotFoundError(f"Template does not exist: {template}")
    if not fixture_csv.is_file():
        raise FileNotFoundError(f"Fixture CSV does not exist: {fixture_csv}")

    probe_values = load_fixture(fixture_csv, args.fixture_row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = (
        args.output_dir
        / f"wiring_foldover_direct_assignment_{timestamp}.bmp"
    ).resolve()

    document = win32com.client.Dispatch("bpac.Document")
    opened = document.Open(str(template))
    if not opened:
        raise RuntimeError(f"b-PAC could not open template: {template}")

    try:
        for object_name, value in probe_values.items():
            obj = document.GetObject(object_name)
            if obj is None:
                raise RuntimeError(
                    f"Template object not found: {object_name}"
                )
            obj.Text = value
            print(f"Assigned {object_name}={value!r}")

        exported = document.Export(4, str(output), args.dpi)
        if not exported:
            raise RuntimeError(
                f"b-PAC Export returned failure for: {output}"
            )
    finally:
        close_document(document)

    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Export did not create a usable BMP: {output}")

    print()
    print("EXPORT-ONLY PROBE COMPLETE — NOTHING WAS PRINTED")
    print(f"Bitmap: {output}")
    print(f"Bytes: {output.stat().st_size}")
    print(f"Fixture: {fixture_csv} row {args.fixture_row}")
    print()
    print("Acceptance check:")
    print(f"  Both halves must show Channel {probe_values['objChannel']}.")
    print(f"  Both halves must show {probe_values['objLine1']}.")
    print(f"  Both halves must show {probe_values['objLine2']}.")
    print("Do not activate Wiring runtime printing if either half is stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
