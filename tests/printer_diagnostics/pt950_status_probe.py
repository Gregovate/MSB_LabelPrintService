"""MSB PT-P950NW status-only diagnostic.

Safety boundary:
- No PostgreSQL access.
- No b-PAC access.
- No Windows spooler control.
- No print, feed, cut, Raster-data, ESC/P-data, or P-touch Template commands.
- The only bytes transmitted are Brother's documented status request: ESC i S.

Reference:
Brother PT-P900/P900W/P950NW Raster Command Reference v1.02,
"ESC i S Status information request" and associated 32-byte status tables.
"""

from __future__ import annotations

import argparse
import json
import socket
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


STATUS_REQUEST = bytes((0x1B, 0x69, 0x53))  # ESC i S
EXPECTED_STATUS_BYTES = 32
DEFAULT_PORT = 9100
DEFAULT_TIMEOUT_SECONDS = 3.0


MEDIA_TYPE = {
    0x00: "No media",
    0x01: "Laminated tape",
    0x03: "Non-laminated tape",
    0x04: "Fabric tape",
    0x11: "Heat-shrink tube (HS 2:1)",
    0x13: "FLe tape",
    0x14: "Flexible ID tape",
    0x15: "Satin tape",
    0x17: "Heat-shrink tube (HS 3:1)",
    0xFF: "Incompatible tape",
}

STATUS_TYPE = {
    0x00: "Reply to status request",
    0x01: "Printing completed",
    0x02: "Error occurred",
    0x03: "Exit IF mode / not used",
    0x04: "Turned off",
    0x05: "Notification",
    0x06: "Phase change",
}

PHASE_TYPE = {
    0x00: "Editing / reception possible",
    0x01: "Printing",
}

NOTIFICATION = {
    0x00: "Not available",
    0x01: "Cover open",
    0x02: "Cover closed",
    0x03: "Cooling started",
    0x04: "Cooling finished",
}

TAPE_COLOR = {
    0x01: "White",
    0x02: "Other",
    0x03: "Clear",
    0x04: "Red",
    0x05: "Blue",
    0x06: "Yellow",
    0x07: "Green",
    0x08: "Black",
    0x09: "Clear (white text)",
    0x20: "Matte White",
    0x21: "Matte Clear",
    0x22: "Matte Silver",
    0x23: "Satin Gold",
    0x24: "Satin Silver",
    0x30: "Blue (D)",
    0x31: "Red (D)",
    0x40: "Fluorescent Orange",
    0x41: "Fluorescent Yellow",
    0x50: "Berry Pink (S)",
    0x51: "Light Gray (S)",
    0x52: "Lime Green (S)",
    0x60: "Yellow (F)",
    0x61: "Pink (F)",
    0x62: "Blue (F)",
    0x70: "White (heat-shrink tube)",
    0x90: "White (Flexible ID)",
    0x91: "Yellow (Flexible ID)",
    0xF0: "Cleaning",
    0xF1: "Stencil",
    0xFF: "Incompatible",
}

TEXT_COLOR = {
    0x01: "White",
    0x02: "Other",
    0x04: "Red",
    0x05: "Blue",
    0x08: "Black",
    0x0A: "Gold",
    0x62: "Blue (F)",
    0xF0: "Cleaning",
    0xF1: "Stencil",
    0xFF: "Incompatible",
}

BATTERY_LEVEL = {
    0x00: "Full",
    0x01: "Half",
    0x02: "Low",
    0x03: "Needs charge",
    0x04: "AC adapter",
    0xFF: "Unknown",
}

EXTENDED_ERROR = {
    0x00: "None",
    0x10: "FLe tape end",
    0x1D: "High-resolution/draft printing error",
    0x1E: "Adapter pull/insert error",
    0x21: "Incompatible media error",
}

ERROR_INFO_1 = (
    (0x01, "No media"),
    (0x02, "End of media"),
    (0x04, "Cutter jam"),
    (0x08, "Weak batteries"),
    (0x10, "Printer in use (bit documented but unsupported for PT-P950NW)"),
    (0x20, "Reserved/not used"),
    (0x40, "High-voltage adapter"),
    (0x80, "Reserved/not used"),
)

ERROR_INFO_2 = (
    (0x01, "Replace media / wrong media"),
    (0x02, "Expansion buffer full"),
    (0x04, "Communication error"),
    (0x08, "Communication buffer full"),
    (0x10, "Cover open"),
    (0x20, "Overheating"),
    (0x40, "Black marking not detected"),
    (0x80, "System error"),
)

MODEL_CODE = {
    0x70: "PT-P950NW",  # 'p'
    0x71: "PT-P900",    # 'q'
    0x69: "PT-P900W",   # manual's Raster status table value
}


@dataclass(frozen=True)
class DecodedStatus:
    raw_hex: str
    model_code_hex: str
    model: str
    battery: str
    extended_error_code: str
    extended_error: str
    error_info_1_hex: str
    error_info_2_hex: str
    errors: list[str]
    media_width_mm: int
    media_length_mm: int
    media_type_code: str
    media_type: str
    status_type_code: str
    status_type: str
    phase_type_code: str
    phase_type: str
    phase_number: int
    notification_code: str
    notification: str
    tape_color_code: str
    tape_color: str
    text_color_code: str
    text_color: str


def _hex(value: int) -> str:
    return f"0x{value:02X}"


def _lookup(mapping: dict[int, str], value: int, prefix: str = "Unknown") -> str:
    return mapping.get(value, f"{prefix} ({_hex(value)})")


def _decode_flags(value: int, definitions: Iterable[tuple[int, str]]) -> list[str]:
    return [label for mask, label in definitions if value & mask]


def decode_status(data: bytes) -> DecodedStatus:
    """Decode one Brother 32-byte PT-P950NW status packet."""
    if len(data) != EXPECTED_STATUS_BYTES:
        raise ValueError(
            f"Expected {EXPECTED_STATUS_BYTES} status bytes, received {len(data)}"
        )

    # Fixed header documented by Brother for this status structure.
    if data[0] != 0x80 or data[1] != 0x20 or data[2] != 0x42 or data[3] != 0x30:
        raise ValueError(
            "Response does not match the documented Brother 32-byte status header: "
            f"{data[:4].hex(' ')}"
        )

    error_1 = data[8]
    error_2 = data[9]
    errors = _decode_flags(error_1, ERROR_INFO_1)
    errors.extend(_decode_flags(error_2, ERROR_INFO_2))

    extended_error = data[7]
    if extended_error:
        errors.append(f"Extended: {_lookup(EXTENDED_ERROR, extended_error)}")

    phase_number = (data[20] << 8) | data[21]

    return DecodedStatus(
        raw_hex=data.hex(" ").upper(),
        model_code_hex=_hex(data[4]),
        model=_lookup(MODEL_CODE, data[4], "Unknown Brother model code"),
        battery=_lookup(BATTERY_LEVEL, data[6]),
        extended_error_code=_hex(extended_error),
        extended_error=_lookup(EXTENDED_ERROR, extended_error),
        error_info_1_hex=_hex(error_1),
        error_info_2_hex=_hex(error_2),
        errors=errors,
        media_width_mm=data[10],
        media_length_mm=data[17],
        media_type_code=_hex(data[11]),
        media_type=_lookup(MEDIA_TYPE, data[11]),
        status_type_code=_hex(data[18]),
        status_type=_lookup(STATUS_TYPE, data[18]),
        phase_type_code=_hex(data[19]),
        phase_type=_lookup(PHASE_TYPE, data[19]),
        phase_number=phase_number,
        notification_code=_hex(data[22]),
        notification=_lookup(NOTIFICATION, data[22]),
        tape_color_code=_hex(data[24]),
        tape_color=_lookup(TAPE_COLOR, data[24]),
        text_color_code=_hex(data[25]),
        text_color=_lookup(TEXT_COLOR, data[25]),
    )


def receive_exact_status(sock: socket.socket) -> bytes:
    """Receive exactly one 32-byte status packet or fail clearly."""
    chunks: list[bytes] = []
    remaining = EXPECTED_STATUS_BYTES

    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)

    data = b"".join(chunks)
    if len(data) != EXPECTED_STATUS_BYTES:
        raise RuntimeError(
            f"Printer returned {len(data)} bytes; expected {EXPECTED_STATUS_BYTES}. "
            f"Partial raw response: {data.hex(' ').upper() or '<empty>'}"
        )
    return data


def request_status(host: str, port: int, timeout: float) -> bytes:
    """Send only ESC i S and return the 32-byte response."""
    if STATUS_REQUEST != b"\x1b\x69\x53":
        raise RuntimeError("STATUS_REQUEST safety assertion failed")

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(STATUS_REQUEST)
        return receive_exact_status(sock)


def format_report(host: str, port: int, status: DecodedStatus) -> str:
    lines = [
        "MSB PT-P950NW STATUS-ONLY DIAGNOSTIC",
        f"Timestamp: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Target: {host}:{port}",
        "Command sent: 1B 69 53 (ESC i S) only",
        "",
        f"RAW 32 BYTES: {status.raw_hex}",
        "",
        f"Model: {status.model} ({status.model_code_hex})",
        f"Battery/power: {status.battery}",
        f"Media width: {status.media_width_mm} mm",
        f"Media length: {status.media_length_mm} mm",
        f"Media type: {status.media_type} ({status.media_type_code})",
        f"Tape color: {status.tape_color} ({status.tape_color_code})",
        f"Text/ribbon color: {status.text_color} ({status.text_color_code})",
        f"Status type: {status.status_type} ({status.status_type_code})",
        f"Phase: {status.phase_type} ({status.phase_type_code}), number={status.phase_number}",
        f"Notification: {status.notification} ({status.notification_code})",
        f"Error byte 1: {status.error_info_1_hex}",
        f"Error byte 2: {status.error_info_2_hex}",
        f"Extended error: {status.extended_error} ({status.extended_error_code})",
        "Errors:",
    ]

    if status.errors:
        lines.extend(f"  - {item}" for item in status.errors)
    else:
        lines.append("  - None decoded")

    return "\n".join(lines)


def write_result(report: str, result_dir: Path) -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    path = result_dir / f"pt950_status_{stamp}.txt"
    path.write_text(report + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read and decode one Brother PT-P950NW 32-byte status response. "
            "This diagnostic sends no print commands."
        )
    )
    parser.add_argument("--host", required=True, help="Printer IP address or hostname")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Raw TCP printer port (default: {DEFAULT_PORT}; override if configured differently)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Socket timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also print decoded status as JSON",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not write a timestamped result file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("STATUS-ONLY MODE: sends only Brother ESC i S (1B 69 53).")
    print(f"Connecting to {args.host}:{args.port} ...")

    try:
        raw = request_status(args.host, args.port, args.timeout)
        decoded = decode_status(raw)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    report = format_report(args.host, args.port, decoded)
    print()
    print(report)

    if args.json:
        print()
        print(json.dumps(asdict(decoded), indent=2))

    if not args.no_log:
        result_dir = Path(__file__).resolve().parent / "results"
        result_path = write_result(report, result_dir)
        print()
        print(f"Result saved: {result_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
