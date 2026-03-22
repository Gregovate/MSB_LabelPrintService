# ============================================================
# MSB Label Polling Service Test Print
# File: bpac_print_test2.py
#
# Purpose:
#   Read the generated display label CSV file, open the Brother
#   b-PAC label template, and print the full batch through the
#   PT-P950NW using the b-PAC SDK.
#
# IMPORTANT:
#   This is a TEST file only.
#
#   It does NOT:
#     - poll the database
#     - create batches
#     - write history
#     - clear print flags
#
#   It ONLY tests whether the printer can print a system-generated
#   batch file correctly through b-PAC.
#
# Current CSV source:
#   C:\MSB_LabelService\csv\display_labels.csv
#
# Assumptions:
#   1. The template contains named objects that b-PAC can access.
#   2. Those object names are defined below.
#   3. The PT-P950NW driver is installed and working.
#
# Author: Greg Liebig / Engineering Innovations, LLC
# Date: 2026-03-21
# Updated to find callback messages
# v0.1  — Initial standalone print test
#   • Direct LBX + CSV print test
#   • Plain b-PAC printing path
# ============================================================


from __future__ import annotations

import csv
from pathlib import Path
import sys

import win32com.client


SCRIPT_NAME = Path(__file__).name
SCRIPT_VERSION = "0.3"
SCRIPT_DATE = "2026-03-21"
SCRIPT_DESC = "Brother b-PAC Standalone Print Test"

# ============================================================
# CONFIGURATION
# ============================================================

TEMPLATE_PATH = Path(r"C:\MSB_LabelService\templates\QR_display_labels_2_line.lbx")
CSV_PATH = Path(r"C:\MSB_LabelService\csv\display_labels.csv")
PRINTER_NAME = "Brother PT-P950NW"

# Template object names inside the LBX file
OBJ_LINE1 = "objLine1"
OBJ_LINE2 = "objLine2"      #Optional
OBJ_QR = "objQr"

# b-PAC flags
# bpoHalfCut   = 0x200
# bpoChainPrint= 0x400
PRINT_FLAGS = 0x200 | 0x400


# ============================================================
# HELPERS
# ============================================================

def load_rows_from_csv(csv_path: Path) -> list[dict[str, str]]:
    """Load rows from the generated CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows: list[dict[str, str]] = []

    with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        required = {"line1", "line2", "qr_url"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(
                f"CSV file is missing required columns: {sorted(missing)}"
            )

        for row in reader:
            rows.append(
                {
                    "line1": row.get("line1", "") or "",
                    "line2": row.get("line2", "") or "",
                    "qr_url": row.get("qr_url", "") or "",
                }
            )

    return rows


def create_bpac_document():
    """Create the Brother b-PAC COM document object."""
    return win32com.client.Dispatch("bpac.Document")


def get_required_object(doc, object_name: str):
    """Get a required template object."""
    obj = doc.GetObject(object_name)
    if obj is None:
        raise RuntimeError(
            f"Template object '{object_name}' was not found.\n"
            f"Open the LBX template and make sure the object is named exactly '{object_name}'."
        )
    return obj


def get_optional_object(doc, object_name: str):
    """Get an optional template object."""
    obj = doc.GetObject(object_name)
    if obj is None:
        print(f"WARNING: Optional template object '{object_name}' was not found.")
    return obj

def log_printer_status(doc, label: str) -> None:
    print(f"--- {label} ---")

    try:
        template_media = doc.GetMediaName
    except Exception as exc:
        template_media = f"<template media read failed: {exc}>"

    try:
        printer_media = doc.Printer.GetMediaName
    except Exception as exc:
        printer_media = f"<printer media read failed: {exc}>"

    try:
        error_code = doc.Printer.ErrorCode
    except Exception as exc:
        error_code = f"<error code read failed: {exc}>"

    try:
        error_string = doc.Printer.ErrorString
    except Exception as exc:
        error_string = f"<error string read failed: {exc}>"

    print(f"Template media : {template_media}")
    print(f"Printer media  : {printer_media}")
    print(f"ErrorCode      : {error_code}")
    print(f"ErrorString    : {error_string}")
    print("")


# ============================================================
# MAIN PRINT FUNCTION
# ============================================================

def main() -> None:
    print("=" * 60)
    print(f"{SCRIPT_NAME}  v{SCRIPT_VERSION}  ({SCRIPT_DATE})")
    print(SCRIPT_DESC)
    print("=" * 60)
    print(f"Template: {TEMPLATE_PATH}")
    print(f"CSV File: {CSV_PATH}")
    print(f"Printer : {PRINTER_NAME}")
    print("")

    rows = load_rows_from_csv(CSV_PATH)
    print(f"Loaded {len(rows)} row(s) from CSV.")

    if not rows:
        print("CSV contains no rows. Nothing to print.")
        return

    print("Creating b-PAC document...")
    doc = create_bpac_document()

    print(f"Opening template: {TEMPLATE_PATH}")
    opened = doc.Open(str(TEMPLATE_PATH))
    print(f"Template opened: {opened}")

    if not opened:
        raise RuntimeError("b-PAC could not open the template.")

    print(f"Setting printer: {PRINTER_NAME}")
    set_printer_ok = doc.SetPrinter(PRINTER_NAME, True)
    print(f"SetPrinter result: {set_printer_ok}")
    log_printer_status(doc, "AFTER SetPrinter")

    if not set_printer_ok:
        raise RuntimeError("b-PAC could not set the printer.")

    print("Resolving template objects...")
    obj_line1 = get_required_object(doc, OBJ_LINE1)
    obj_qr = get_required_object(doc, OBJ_QR)
    obj_line2 = get_optional_object(doc, OBJ_LINE2)
    print("Template object check complete.")

    print("Starting print job...")
    log_printer_status(doc, "BEFORE StartPrint")
    doc.StartPrint("", PRINT_FLAGS)

    for i, row in enumerate(rows, start=1):
        print(f"Queueing label {i} of {len(rows)}")

        # Required objects
        obj_line1.Text = row["line1"]
        obj_qr.Text = row["qr_url"]

        # Optional second line
        if obj_line2 is not None:
            obj_line2.Text = row["line2"] or ""

        result = doc.PrintOut(1, 0)
        print(f"  PrintOut result: {result}")
        log_printer_status(doc, f"AFTER PrintOut row {i}")

        if not result:
            raise RuntimeError(f"PrintOut failed on row {i}")

    print("Ending print job and sending batch to printer...")
    try:
        print("Ending print job and sending batch to printer...")
        try:
            end_result = doc.EndPrint
            print(f"EndPrint result: {end_result}")
        except Exception as exc:
            print(f"WARNING: EndPrint call raised exception: {exc}")

        log_printer_status(doc, "AFTER EndPrint")

    print("Closing template...")
    try:
        close_result = doc.Close
        print(f"Close result: {close_result}")
    except Exception as exc:
        print(f"WARNING: Close call raised exception: {exc}")

    print("")
    print("Batch print test complete.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("")
        print("ERROR:")
        print(exc)
        sys.exit(1)