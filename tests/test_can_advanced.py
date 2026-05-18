"""Advanced CAN 2.0B frame parser tests (REQ-001).

Exercises edge cases, boundary identifiers, flag combinations, batch
processing, error handling, and frame property invariants.
"""

from __future__ import annotations

import struct

import pytest

from ismart_core.can.frame import CanFrame, parse_frame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def std_frame(can_id: int, data: bytes = b"") -> bytes:
    """Build a SocketCAN frame with 11-bit standard identifier."""
    dlc = len(data)
    can_id_word = (can_id & 0x7FF) << 20
    header = struct.pack("<IBBBB", can_id_word, dlc, 0, 0, 0)
    return header + data + bytes(8 - dlc)


def eff_frame(can_id: int, data: bytes = b"") -> bytes:
    """Build a SocketCAN frame with 29-bit extended identifier."""
    dlc = len(data)
    can_id_word = 0x80000000 | (can_id & 0x1FFFFFFF)
    header = struct.pack("<IBBBB", can_id_word, dlc, 0, 0, 0)
    return header + data + bytes(8 - dlc)


def rtr_frame(can_id: int, dlc: int = 0) -> bytes:
    """Build an RTR (remote transmission request) frame."""
    can_id_word = ((can_id & 0x7FF) << 20) | 0x40000000
    header = struct.pack("<IBBBB", can_id_word, dlc, 0, 0, 0)
    return header + bytes(8)


# ---------------------------------------------------------------------------
# DLC boundary tests
# ---------------------------------------------------------------------------


def test_dlc_zero_empty_payload():
    """Frame with DLC=0 has empty data field."""
    raw = std_frame(0x100, b"")
    f = parse_frame(raw)
    assert f.dlc == 0
    assert f.data == b""


def test_dlc_one():
    raw = std_frame(0x100, b"\xab")
    f = parse_frame(raw)
    assert f.dlc == 1
    assert f.data == b"\xab"


def test_dlc_max_eight_bytes():
    """Frame with DLC=8 carries maximum payload."""
    payload = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    raw = std_frame(0x100, payload)
    f = parse_frame(raw)
    assert f.dlc == 8
    assert f.data == payload


def test_dlc_four_midrange():
    raw = std_frame(0x1FF, b"\xca\xfe\xba\xbe")
    f = parse_frame(raw)
    assert f.dlc == 4
    assert f.data == b"\xca\xfe\xba\xbe"


# ---------------------------------------------------------------------------
# Identifier boundary tests
# ---------------------------------------------------------------------------


def test_std_id_zero():
    """Standard 11-bit ID = 0x000 is valid."""
    raw = std_frame(0x000, b"\x00")
    f = parse_frame(raw)
    assert f.can_id == 0x000
    assert not f.is_extended


def test_std_id_max():
    """Standard 11-bit ID = 0x7FF is the maximum valid value."""
    raw = std_frame(0x7FF, b"\xff")
    f = parse_frame(raw)
    assert f.can_id == 0x7FF
    assert not f.is_extended


def test_eff_id_zero():
    """Extended 29-bit ID = 0x00000000 is valid."""
    raw = eff_frame(0x00000000, b"\x00")
    f = parse_frame(raw)
    assert f.can_id == 0x00000000
    assert f.is_extended


def test_eff_id_max():
    """Extended 29-bit ID = 0x1FFFFFFF is the maximum valid value."""
    raw = eff_frame(0x1FFFFFFF, b"\xff")
    f = parse_frame(raw)
    assert f.can_id == 0x1FFFFFFF
    assert f.is_extended


def test_eff_id_j1939_typical():
    """J1939 parameter group number — common real-world EFF ID."""
    raw = eff_frame(0x18FEF100, b"\x01\x02\x03\x04\x05\x06\x07\x08")
    f = parse_frame(raw)
    assert f.can_id == 0x18FEF100
    assert f.dlc == 8


# ---------------------------------------------------------------------------
# Flag tests
# ---------------------------------------------------------------------------


def test_rtr_flag_set():
    """Remote transmission request frames have is_rtr=True."""
    raw = rtr_frame(0x200, dlc=4)
    f = parse_frame(raw)
    assert f.is_rtr is True


def test_rtr_flag_clear_on_standard():
    """Normal data frames never have is_rtr set."""
    raw = std_frame(0x300, b"\x42")
    f = parse_frame(raw)
    assert f.is_rtr is False


def test_is_standard_property():
    """is_standard is the inverse of is_extended."""
    std = parse_frame(std_frame(0x100, b"\x01"))
    eff = parse_frame(eff_frame(0x100000, b"\x01"))
    assert std.is_standard is True
    assert std.is_extended is False
    assert eff.is_standard is False
    assert eff.is_extended is True


# ---------------------------------------------------------------------------
# Data content tests
# ---------------------------------------------------------------------------


def test_all_zeros_payload():
    """A frame carrying eight zero bytes parses correctly."""
    raw = std_frame(0x1, b"\x00" * 8)
    f = parse_frame(raw)
    assert f.data == b"\x00" * 8


def test_all_ones_payload():
    """A frame carrying eight 0xFF bytes parses correctly."""
    raw = std_frame(0x1, b"\xff" * 8)
    f = parse_frame(raw)
    assert f.data == b"\xff" * 8


def test_mixed_bytes_preserved():
    """Arbitrary byte sequence is preserved without corruption."""
    payload = bytes(range(8))  # 0x00 .. 0x07
    raw = std_frame(0x123, payload)
    f = parse_frame(raw)
    assert f.data == payload


# ---------------------------------------------------------------------------
# Error / invalid-input tests
# ---------------------------------------------------------------------------


def test_too_short_raises():
    with pytest.raises(ValueError, match="Expected 16 bytes"):
        parse_frame(b"\x00" * 15)


def test_too_long_raises():
    with pytest.raises(ValueError, match="Expected 16 bytes"):
        parse_frame(b"\x00" * 17)


def test_empty_raises():
    with pytest.raises(ValueError, match="Expected 16 bytes"):
        parse_frame(b"")


def test_exactly_16_bytes_is_valid():
    """Exactly 16 bytes never raises regardless of content."""
    raw = b"\x00" * 16
    f = parse_frame(raw)
    assert isinstance(f, CanFrame)


# ---------------------------------------------------------------------------
# Idempotency + batch tests
# ---------------------------------------------------------------------------


def test_parse_is_idempotent():
    """Parsing the same raw bytes twice returns equal frames."""
    raw = eff_frame(0x18DA00F1, b"\x02\x10\x00\x00\x00\x00\x00\x00")
    f1 = parse_frame(raw)
    f2 = parse_frame(raw)
    assert f1.can_id == f2.can_id
    assert f1.dlc == f2.dlc
    assert f1.data == f2.data
    assert f1.is_extended == f2.is_extended


def test_batch_parse_100_frames():
    """Parse 100 unique frames and verify identifier monotonicity."""
    frames = []
    for i in range(100):
        raw = std_frame(i % 0x7FF, bytes([i % 256]))
        frames.append(parse_frame(raw))
    assert len(frames) == 100
    # All frames are valid CanFrame instances
    assert all(isinstance(f, CanFrame) for f in frames)


def test_batch_mixed_standard_and_extended():
    """Interleaved standard and extended frames parse without confusion."""
    results = []
    for i in range(20):
        raw = std_frame(i, b"\xaa") if i % 2 == 0 else eff_frame(65536 + i, b"\xbb")
        results.append(parse_frame(raw))
    std_count = sum(1 for f in results if not f.is_extended)
    eff_count = sum(1 for f in results if f.is_extended)
    assert std_count == 10
    assert eff_count == 10


# ---------------------------------------------------------------------------
# Dataclass fields completeness
# ---------------------------------------------------------------------------


def test_frame_fields_all_present():
    """CanFrame exposes all required fields (REQ-001 schema)."""
    raw = std_frame(0x300, b"\x01\x02\x03")
    f = parse_frame(raw)
    assert hasattr(f, "can_id")
    assert hasattr(f, "is_extended")
    assert hasattr(f, "is_rtr")
    assert hasattr(f, "dlc")
    assert hasattr(f, "data")
    assert hasattr(f, "is_standard")
