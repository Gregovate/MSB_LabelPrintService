from pathlib import Path

import win32com.client


# ============================================================
# MSB b-PAC smoke test
# Purpose:
#   Verify Python can control Brother b-PAC directly.
# ============================================================

TEMPLATE = Path(r"C:\MSB_LabelService\templates\QR_display_labels_2_line.lbx")
PRINTER_NAME = "Brother PT-P950NW"

def main() -> None:
    print("Creating b-PAC document...")
    doc = win32com.client.Dispatch("bpac.Document")

    print(f"Opening template: {TEMPLATE}")
    opened = doc.Open(str(TEMPLATE))
    print(f"Template opened: {opened}")

    if not opened:
        raise RuntimeError("b-PAC could not open template.")

    print("Setting printer...")
    # second arg True = local settings? keep simple for test
    set_printer_ok = doc.SetPrinter(PRINTER_NAME, True)
    print(f"SetPrinter result: {set_printer_ok}")

    # Try to inspect objects in template
    for name in ["line1", "line2", "qr_url"]:
        try:
            obj = doc.GetObject(name)
            print(f"Object '{name}': {obj}")
        except Exception as exc:
            print(f"Object '{name}' lookup failed: {exc}")

    print("Done. Closing template.")
    doc.Close()

if __name__ == "__main__":
    main()