from pathlib import Path
import win32com.client

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

    print(f"Setting printer: {PRINTER_NAME}")
    set_printer_ok = doc.SetPrinter(PRINTER_NAME, True)
    print(f"SetPrinter result: {set_printer_ok}")
    if not set_printer_ok:
        raise RuntimeError("b-PAC could not set printer.")

    print("Starting print job...")
    doc.StartPrint("", 0)

    print("Printing one label...")
    result = doc.PrintOut(1, 0)
    print(f"PrintOut result: {result}")

    print("Done.")

if __name__ == "__main__":
    main()