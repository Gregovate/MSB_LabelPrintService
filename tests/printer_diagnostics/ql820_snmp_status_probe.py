#!/usr/bin/env python3
"""
MSB Label Print Service - Brother QL-820NWB SNMP status diagnostic.

STATUS-ONLY TEST HARNESS

This script:
- does NOT connect to PostgreSQL
- does NOT use b-PAC
- does NOT import the production label service
- does NOT submit print jobs
- does NOT alter the Windows print spooler
- sends only an SNMP GET for Brother's documented printer-status OID

Default target:
    Brother QL-820NWB at 192.168.5.11

Brother documented network-status OID:
    1.3.6.1.4.1.2435.3.3.9.1.6.1.0

The returned OCTET STRING is expected to contain the same 32-byte Brother
status structure used by the ESC/P status request. This diagnostic preserves
both the raw SNMP response and the extracted status value so bench tests can
compare loaded media, no-roll, end-of-roll, cover-open, and other conditions.
"""

from __future__ import annotations

import argparse
import socket
import sys
from typing import Tuple

DEFAULT_HOST = "192.168.5.11"
DEFAULT_PORT = 161
DEFAULT_COMMUNITY = "public"
DEFAULT_TIMEOUT = 3.0
OID = "1.3.6.1.4.1.2435.3.3.9.1.6.1.0"


def ber_len(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def ber_tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + ber_len(len(value)) + value


def encode_base128(value: int) -> bytes:
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(parts))


def encode_oid(oid: str) -> bytes:
    parts = [int(x) for x in oid.split(".")]
    if len(parts) < 2:
        raise ValueError("OID must contain at least two arcs")
    body = bytes([40 * parts[0] + parts[1]])
    for arc in parts[2:]:
        body += encode_base128(arc)
    return ber_tlv(0x06, body)


def build_snmp_get(community: str) -> bytes:
    request_id = ber_tlv(0x02, b"\x01")
    error_status = ber_tlv(0x02, b"\x00")
    error_index = ber_tlv(0x02, b"\x00")
    varbind = ber_tlv(0x30, encode_oid(OID) + ber_tlv(0x05, b""))
    varbind_list = ber_tlv(0x30, varbind)
    pdu = ber_tlv(0xA0, request_id + error_status + error_index + varbind_list)
    version = ber_tlv(0x02, b"\x00")  # SNMP v1
    community_tlv = ber_tlv(0x04, community.encode("ascii"))
    return ber_tlv(0x30, version + community_tlv + pdu)


def read_len(data: bytes, offset: int) -> Tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    if count == 0 or offset + count > len(data):
        raise ValueError("Invalid BER length")
    length = int.from_bytes(data[offset:offset + count], "big")
    return length, offset + count


def read_tlv(data: bytes, offset: int) -> Tuple[int, bytes, int]:
    if offset >= len(data):
        raise ValueError("Unexpected end of BER data")
    tag = data[offset]
    length, value_offset = read_len(data, offset + 1)
    end = value_offset + length
    if end > len(data):
        raise ValueError("BER value exceeds packet length")
    return tag, data[value_offset:end], end


def extract_status_value(packet: bytes) -> bytes:
    # Walk BER recursively and collect OCTET STRING values. The final 32-byte
    # OCTET STRING is Brother's printer status value.
    values: list[bytes] = []

    def walk(data: bytes) -> None:
        offset = 0
        while offset < len(data):
            tag, value, offset = read_tlv(data, offset)
            if tag == 0x04:
                values.append(value)
            if tag & 0x20 or tag in (0x30, 0xA0, 0xA2):
                try:
                    walk(value)
                except ValueError:
                    pass

    walk(packet)
    for value in reversed(values):
        if len(value) == 32 and value[:1] == b"\x80":
            return value
    raise ValueError("No 32-byte Brother status OCTET STRING found in SNMP reply")


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def ascii_preview(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Brother QL-820NWB SNMP status-only probe")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Printer IP/host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"SNMP UDP port (default: {DEFAULT_PORT})")
    parser.add_argument("--community", default=DEFAULT_COMMUNITY, help=f"SNMP community (default: {DEFAULT_COMMUNITY})")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"Timeout seconds (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    request = build_snmp_get(args.community)

    print("STATUS-ONLY MODE: Brother documented SNMP network status query.")
    print(f"Target: {args.host}:{args.port}/UDP")
    print(f"OID: {OID}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)
    try:
        sock.sendto(request, (args.host, args.port))
        packet, addr = sock.recvfrom(4096)
    except socket.timeout:
        print("ERROR: timed out waiting for SNMP reply", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        sock.close()

    print(f"Reply from: {addr[0]}:{addr[1]}")
    print(f"SNMP packet bytes: {len(packet)}")
    print(f"SNMP packet hex: {hex_bytes(packet)}")

    try:
        status = extract_status_value(packet)
    except ValueError as exc:
        print(f"ERROR decoding SNMP response: {exc}", file=sys.stderr)
        return 3

    print(f"Status value bytes: {len(status)}")
    print(f"Status value hex: {hex_bytes(status)}")
    print(f"Status value ASCII: {ascii_preview(status)}")
    print("NOTE: Preserve this raw value for comparison across roll/no-media/end-of-media tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
