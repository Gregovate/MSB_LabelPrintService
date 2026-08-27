#!/usr/bin/env python3
"""MSB PT-P950NW network status diagnostic using Brother's documented SNMP OID.

DIAGNOSTIC ONLY:
- Does not connect to PostgreSQL.
- Does not import or control the production Label Print Service.
- Does not use b-PAC.
- Does not submit, feed, cut, or print labels.
- Performs one SNMP GET for Brother's documented network status OID.

Brother documents OID 1.3.6.1.4.1.2435.3.3.9.1.6.1.0 for PT-P950NW network
status and states that its returned value is the same status information as the
ESC/P status request response.
"""

from __future__ import annotations

import argparse
import socket
import sys
from dataclasses import dataclass

DEFAULT_HOST = "192.168.5.12"
DEFAULT_COMMUNITY = "public"
DEFAULT_PORT = 161
DEFAULT_TIMEOUT = 3.0
STATUS_OID = "1.3.6.1.4.1.2435.3.3.9.1.6.1.0"


@dataclass
class BerValue:
    tag: int
    value: bytes


def ber_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + ber_length(len(value)) + value


def ber_integer(value: int) -> bytes:
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw
    return tlv(0x02, raw)


def encode_oid(oid: str) -> bytes:
    parts = [int(p) for p in oid.split(".")]
    if len(parts) < 2:
        raise ValueError("OID must contain at least two arcs")
    body = bytearray([40 * parts[0] + parts[1]])
    for arc in parts[2:]:
        if arc < 0:
            raise ValueError("OID arcs must be non-negative")
        stack = [arc & 0x7F]
        arc >>= 7
        while arc:
            stack.append(0x80 | (arc & 0x7F))
            arc >>= 7
        body.extend(reversed(stack))
    return tlv(0x06, bytes(body))


def build_snmp_get(community: str, request_id: int = 1) -> bytes:
    varbind = tlv(0x30, encode_oid(STATUS_OID) + tlv(0x05, b""))
    varbind_list = tlv(0x30, varbind)
    pdu = tlv(0xA0, ber_integer(request_id) + ber_integer(0) + ber_integer(0) + varbind_list)
    return tlv(0x30, ber_integer(0) + tlv(0x04, community.encode("ascii")) + pdu)


def read_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    if count == 0 or offset + count > len(data):
        raise ValueError("Invalid BER length")
    length = int.from_bytes(data[offset:offset + count], "big")
    return length, offset + count


def read_tlv(data: bytes, offset: int) -> tuple[BerValue, int]:
    if offset >= len(data):
        raise ValueError("Unexpected end of BER data")
    tag = data[offset]
    length, value_offset = read_length(data, offset + 1)
    end = value_offset + length
    if end > len(data):
        raise ValueError("Truncated BER value")
    return BerValue(tag, data[value_offset:end]), end


def extract_status_value(packet: bytes) -> bytes:
    outer, _ = read_tlv(packet, 0)
    if outer.tag != 0x30:
        raise ValueError("SNMP response is not a sequence")
    pos = 0
    _, pos = read_tlv(outer.value, pos)  # version
    _, pos = read_tlv(outer.value, pos)  # community
    pdu, pos = read_tlv(outer.value, pos)
    if pdu.tag != 0xA2:
        raise ValueError(f"Expected GetResponse PDU (A2), got {pdu.tag:02X}")
    p = 0
    _, p = read_tlv(pdu.value, p)  # request id
    error_status, p = read_tlv(pdu.value, p)
    error_index, p = read_tlv(pdu.value, p)
    if int.from_bytes(error_status.value, "big") != 0:
        raise ValueError(
            f"SNMP error status={int.from_bytes(error_status.value, 'big')} "
            f"index={int.from_bytes(error_index.value, 'big')}"
        )
    varbind_list, p = read_tlv(pdu.value, p)
    vb, _ = read_tlv(varbind_list.value, 0)
    q = 0
    _, q = read_tlv(vb.value, q)  # OID
    value, q = read_tlv(vb.value, q)
    return value.value


def printable_ascii(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def main() -> int:
    parser = argparse.ArgumentParser(description="PT-P950NW SNMP status-only diagnostic")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"printer IP (default {DEFAULT_HOST})")
    parser.add_argument("--community", default=DEFAULT_COMMUNITY, help="SNMP v1 community (default public)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="SNMP UDP port (default 161)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="timeout seconds")
    args = parser.parse_args()

    request = build_snmp_get(args.community)
    print("STATUS-ONLY MODE: Brother documented SNMP network status query.")
    print(f"Target: {args.host}:{args.port}/UDP")
    print(f"OID: {STATUS_OID}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)
    try:
        sock.sendto(request, (args.host, args.port))
        packet, peer = sock.recvfrom(4096)
    except socket.timeout:
        print("ERROR: SNMP query timed out", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        sock.close()

    print(f"Reply from: {peer[0]}:{peer[1]}")
    print(f"SNMP packet bytes: {len(packet)}")
    print(f"SNMP packet hex: {packet.hex(' ').upper()}")

    try:
        value = extract_status_value(packet)
    except ValueError as exc:
        print(f"ERROR decoding SNMP response: {exc}", file=sys.stderr)
        return 3

    print(f"Status value bytes: {len(value)}")
    print(f"Status value hex: {value.hex(' ').upper()}")
    print(f"Status value ASCII: {printable_ascii(value)}")
    print("NOTE: Preserve this raw value for comparison across cassette/no-tape/end-of-tape tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
