from __future__ import annotations

import socket
from dataclasses import dataclass

EXPECTED_STATUS_BYTES = 32

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

ERROR_INFO_1 = (
    (0x01, "No media"),
    (0x02, "End of media"),
    (0x04, "Cutter jam"),
    (0x08, "Weak batteries"),
    (0x10, "Printer in use"),
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


@dataclass(frozen=True)
class BrotherStatus:
    raw_hex: str
    error_info_1: int
    error_info_2: int
    errors: tuple[str, ...]
    media_width_mm: int
    media_type_code: int
    media_type: str
    status_type_code: int
    phase_type_code: int
    notification_code: int


@dataclass(frozen=True)
class BerValue:
    tag: int
    value: bytes


def _decode_flags(value: int, definitions: tuple[tuple[int, str], ...]) -> list[str]:
    return [label for mask, label in definitions if value & mask]


def decode_brother_status(data: bytes) -> BrotherStatus:
    """Decode the documented Brother 32-byte PT-P950NW status payload."""
    if len(data) != EXPECTED_STATUS_BYTES:
        raise ValueError(
            f"Expected {EXPECTED_STATUS_BYTES} Brother status bytes, "
            f"received {len(data)}"
        )

    if data[:4] != bytes((0x80, 0x20, 0x42, 0x30)):
        raise ValueError(
            "Response does not match the documented Brother 32-byte "
            f"status header: {data[:4].hex(' ')}"
        )

    error_1 = data[8]
    error_2 = data[9]
    errors = _decode_flags(error_1, ERROR_INFO_1)
    errors.extend(_decode_flags(error_2, ERROR_INFO_2))

    media_type_code = data[11]

    return BrotherStatus(
        raw_hex=data.hex(" ").upper(),
        error_info_1=error_1,
        error_info_2=error_2,
        errors=tuple(errors),
        media_width_mm=data[10],
        media_type_code=media_type_code,
        media_type=MEDIA_TYPE.get(
            media_type_code,
            f"Unknown media type (0x{media_type_code:02X})",
        ),
        status_type_code=data[18],
        phase_type_code=data[19],
        notification_code=data[22],
    )


def _ber_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _ber_length(len(value)) + value


def _ber_integer(value: int) -> bytes:
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw
    return _tlv(0x02, raw)


def _encode_oid(oid: str) -> bytes:
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

    return _tlv(0x06, bytes(body))


def _build_snmp_get(oid: str, community: str, request_id: int = 1) -> bytes:
    varbind = _tlv(0x30, _encode_oid(oid) + _tlv(0x05, b""))
    varbind_list = _tlv(0x30, varbind)
    pdu = _tlv(
        0xA0,
        _ber_integer(request_id)
        + _ber_integer(0)
        + _ber_integer(0)
        + varbind_list,
    )
    return _tlv(
        0x30,
        _ber_integer(0)
        + _tlv(0x04, community.encode("ascii"))
        + pdu,
    )


def _read_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1

    if first < 0x80:
        return first, offset

    count = first & 0x7F
    if count == 0 or offset + count > len(data):
        raise ValueError("Invalid BER length")

    length = int.from_bytes(data[offset : offset + count], "big")
    return length, offset + count


def _read_tlv(data: bytes, offset: int) -> tuple[BerValue, int]:
    if offset >= len(data):
        raise ValueError("Unexpected end of BER data")

    tag = data[offset]
    length, value_offset = _read_length(data, offset + 1)
    end = value_offset + length

    if end > len(data):
        raise ValueError("Truncated BER value")

    return BerValue(tag, data[value_offset:end]), end


def _extract_status_value(packet: bytes) -> bytes:
    outer, _ = _read_tlv(packet, 0)
    if outer.tag != 0x30:
        raise ValueError("SNMP response is not a sequence")

    pos = 0
    _, pos = _read_tlv(outer.value, pos)
    _, pos = _read_tlv(outer.value, pos)
    pdu, pos = _read_tlv(outer.value, pos)

    if pdu.tag != 0xA2:
        raise ValueError(
            f"Expected SNMP GetResponse PDU (A2), got {pdu.tag:02X}"
        )

    p = 0
    _, p = _read_tlv(pdu.value, p)
    error_status, p = _read_tlv(pdu.value, p)
    error_index, p = _read_tlv(pdu.value, p)

    if int.from_bytes(error_status.value, "big") != 0:
        raise ValueError(
            f"SNMP error status="
            f"{int.from_bytes(error_status.value, 'big')} "
            f"index={int.from_bytes(error_index.value, 'big')}"
        )

    varbind_list, p = _read_tlv(pdu.value, p)
    varbind, _ = _read_tlv(varbind_list.value, 0)

    q = 0
    _, q = _read_tlv(varbind.value, q)
    value, q = _read_tlv(varbind.value, q)

    return value.value


def query_brother_snmp_status(
    host: str,
    oid: str,
    *,
    community: str = "public",
    port: int = 161,
    timeout: float = 3.0,
) -> BrotherStatus:
    """Perform one SNMP v1 GET and decode Brother's 32-byte status payload."""
    request = _build_snmp_get(
        oid=oid,
        community=community,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
        sock.sendto(request, (host, port))
        packet, _peer = sock.recvfrom(4096)
    finally:
        sock.close()

    return decode_brother_status(
        _extract_status_value(packet)
    )
