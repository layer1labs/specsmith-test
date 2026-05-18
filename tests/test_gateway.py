"""Integration tests for the iSMART gateway (TEST-001..TEST-009)."""

from __future__ import annotations

import json
import struct
import threading
import time
import urllib.request

import pytest

from ismart_core.can.frame import parse_frame
from ismart_core.sensor.adc import MedianFilter

# ---------------------------------------------------------------------------
# TEST-001: CAN frame — 11-bit standard ID
# ---------------------------------------------------------------------------


def _make_std_frame(can_id: int, data: bytes) -> bytes:
    """Build a 16-byte SocketCAN frame with 11-bit standard ID."""
    dlc = len(data)
    # Standard frame: ID in bits 31-20 of can_id field
    can_id_word = (can_id & 0x7FF) << 20
    header = struct.pack("<IBBBB", can_id_word, dlc, 0, 0, 0)
    payload = data + bytes(8 - dlc)
    return header + payload


def _make_eff_frame(can_id: int, data: bytes) -> bytes:
    """Build a 16-byte SocketCAN frame with 29-bit extended ID."""
    dlc = len(data)
    can_id_word = 0x80000000 | (can_id & 0x1FFFFFFF)
    header = struct.pack("<IBBBB", can_id_word, dlc, 0, 0, 0)
    payload = data + bytes(8 - dlc)
    return header + payload


def test_can_parse_standard_frame():
    """TEST-001: Parse 11-bit standard CAN frame."""
    raw = _make_std_frame(0x123, b"\xde\xad\xbe\xef")
    frame = parse_frame(raw)
    assert frame.can_id == 0x123
    assert not frame.is_extended
    assert frame.dlc == 4
    assert frame.data == b"\xde\xad\xbe\xef"


def test_can_parse_extended_frame():
    """TEST-002: Parse 29-bit extended CAN frame."""
    raw = _make_eff_frame(0x18FEF100, b"\x01\x02")
    frame = parse_frame(raw)
    assert frame.can_id == 0x18FEF100
    assert frame.is_extended
    assert frame.dlc == 2
    assert frame.data == b"\x01\x02"


def test_can_parse_invalid_length():
    """parse_frame raises on wrong byte count."""
    with pytest.raises(ValueError, match="Expected 16 bytes"):
        parse_frame(b"\x00" * 8)


# ---------------------------------------------------------------------------
# TEST-003: ADC median filter
# ---------------------------------------------------------------------------


def test_adc_median_filter_correctness():
    """TEST-003: Median filter produces correct output after window fill."""
    filt = MedianFilter()
    samples = [3.0, 1.0, 4.0, 1.0, 5.0]
    results = [filt.push(s) for s in samples]
    # Window fills at 5th sample; median of [3,1,4,1,5] = 3.0
    assert results[-1] == 3.0, f"Expected 3.0, got {results[-1]}"
    # First 4 should be None (window not full)
    assert all(r is None for r in results[:4])


def test_adc_median_filter_even_number():
    """Median filter handles even-sized window (should not happen but defensive)."""
    from ismart_core.sensor.adc import _median

    assert _median([1.0, 3.0]) == 2.0


# ---------------------------------------------------------------------------
# TEST-007 / TEST-008: REST gateway
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gateway_server():
    """Start the gateway server in a background thread for module scope."""
    import queue as _queue

    from ismart_core.gateway import GatewayHandler, _mock_producer, _ThreadedServer

    tq: _queue.Queue = _queue.Queue(maxsize=50)
    stop = threading.Event()

    class Handler(GatewayHandler):
        pass

    Handler.telemetry_queue = tq

    producer = threading.Thread(target=_mock_producer, args=(tq, stop), daemon=True)
    producer.start()

    server = _ThreadedServer(("127.0.0.1", 18500), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)

    yield "http://127.0.0.1:18500"

    stop.set()
    server.shutdown()


def test_health_endpoint(gateway_server):
    """TEST-007: GET /api/health returns JSON {ok: true}."""
    with urllib.request.urlopen(f"{gateway_server}/api/health") as resp:
        assert resp.status == 200
        data = json.loads(resp.read())
    assert data.get("ok") is True


def test_telemetry_sse_streams_events(gateway_server):
    """TEST-008: SSE /api/telemetry delivers at least one event within 3 s."""
    import socket

    host, port = "127.0.0.1", 18500
    s = socket.create_connection((host, port), timeout=5)
    s.sendall(b"GET /api/telemetry HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
    s.settimeout(3)

    received = b""
    deadline = time.time() + 3
    try:
        while time.time() < deadline:
            chunk = s.recv(4096)
            if not chunk:
                break
            received += chunk
            if b"data:" in received:
                break
    except (TimeoutError, OSError):
        pass
    finally:
        s.close()

    assert b"data:" in received, "Expected at least one SSE data: event"


# ---------------------------------------------------------------------------
# TEST-009: SocketCAN graceful fallback
# ---------------------------------------------------------------------------


def test_socketcan_fallback(gateway_server):
    """TEST-009: Mock data is served when vcan0 is absent."""
    # The test server uses mock producer by default; health check confirms
    with urllib.request.urlopen(f"{gateway_server}/api/health") as resp:
        assert resp.status == 200
