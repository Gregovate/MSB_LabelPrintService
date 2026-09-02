from __future__ import annotations

import argparse
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

PROBE_VALUES = {
    "objChannel": "09",
    "objLine1": "FOLDOVER-PROBE-A",
    "objLine2": "FOLDOVER-PROBE-B",
}


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
    return parser.parse_args()


def close_document(document: object) -> None:
    """Use the property-style close behavior proven on PRINT-SERVER."""
    try:
        _ = document.Close
    except Exception as exc:
        print(f"WARNING: b-PAC Close raised: {exc}")


def main() -> int:
    args = parse_args()
    template = args.template.resolve()

    if not template.is_file():
        raise FileNotFoundError(f"Template does not exist: {template}")

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
        for object_name, value in PROBE_VALUES.items():
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
    print()
    print("Acceptance check:")
    print("  Both halves must show Channel 09.")
    print("  Both halves must show FOLDOVER-PROBE-A.")
    print("  Both halves must show FOLDOVER-PROBE-B.")
    print("Do not activate Wiring runtime printing if either half is stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
