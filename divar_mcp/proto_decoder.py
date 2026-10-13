"""Lightweight pure-python Protobuf decoder for Divar gRPC and Wire messages.

Decodes wire-format protobuf binary streams without requiring protoc or external packages.
"""

from __future__ import annotations
from typing import Any


def decode_protobuf(data: bytes) -> dict[int, Any]:
    """Decode raw protobuf bytes into a nested dictionary keyed by field numbers."""
    idx = 0
    fields: dict[int, Any] = {}
    while idx < len(data):
        # Read varint key (field_number << 3 | wire_type)
        key = 0
        shift = 0
        while idx < len(data):
            b = data[idx]
            idx += 1
            key |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        if key == 0:
            break
        field_num = key >> 3
        wire_type = key & 0x07

        if wire_type == 0:  # Varint
            val = 0
            shift = 0
            while idx < len(data):
                b = data[idx]
                idx += 1
                val |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
        elif wire_type == 1:  # 64-bit fixed
            val = data[idx:idx + 8]
            idx += 8
        elif wire_type == 2:  # Length-delimited (string, bytes, or sub-message)
            length = 0
            shift = 0
            while idx < len(data):
                b = data[idx]
                idx += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            raw_bytes = data[idx:idx + length]
            idx += length
            try:
                s = raw_bytes.decode("utf-8")
                # Accept as string if mostly printable text
                if all(ord(c) >= 32 or c in "\n\r\t" for c in s) and len(s) > 0:
                    val = s
                else:
                    nested = decode_protobuf(raw_bytes)
                    val = nested if nested else raw_bytes
            except Exception:
                try:
                    nested = decode_protobuf(raw_bytes)
                    val = nested if nested else raw_bytes
                except Exception:
                    val = raw_bytes
        elif wire_type == 5:  # 32-bit fixed
            val = data[idx:idx + 4]
            idx += 4
        else:
            break

        if field_num not in fields:
            fields[field_num] = val
        elif isinstance(fields[field_num], list):
            fields[field_num].append(val)
        else:
            fields[field_num] = [fields[field_num], val]

    return fields
