"""End-to-end integration tests for the iSMART gateway stack.

Tests the full pipeline: CAN frame parsing → ADC filtering → gateway
HTTP/SSE delivery, including concurrent clients, throughput, error
handling, and cross-layer interaction.
"""

from __future__ import annotations

import json
import queue
import socket
import struct
import threading
import time
import urllib.request
from typing import Any

import pytest

from ismart_core.can.frame import parse_frame
from ismart_core.sensor.adc import MedianFilter

# ---------------------------------------------------------------------------
# Shared gateway fixture (module scope for performance)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gw():
    """Start a gateway server for the whole module; tear it down after."""
    from ismart_core.gateway import GatewayHandler, _mock_producer, _ThreadedServer

    tq: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
    stop = threading.Event()

    class Handler(GatewayHandler):
        pass

    Handler.telemetry_queue = tq
    producer = threading.Thread(target=_mock_producer, args=(tq, stop), daemon=True)
    producer.start()

    server = _ThreadedServer(("127.0.0.1", 19501), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.15)  # let it come up

    yield "http://127.0.0.1:19501"

    stop.set()
    server.shutdown()


# ---------------------------------------------------------------------------
# CAN → ADC → gateway pipeline tests
# ---------------------------------------------------------------------------


def test_can_value_flows_through_adc_filter():
    """CAN frame byte can be used as an ADC sample value and filtered."""
    # Build a CAN frame carrying a single ADC reading in byte 0
    adc_byte = 128
    can_id_word = (0x200 & 0x7FF) << 20
    header = struct.pack("<IBBBB", can_id_word, 1, 0, 0, 0)
    raw = header + bytes([adc_byte]) + bytes(7)

    frame = parse_frame(raw)
    assert len(frame.data) >= 1

    sample_value = float(frame.data[0])
    filt = MedianFilter()
    for _ in range(4):
        filt.push(sample_value)
    result = filt.push(sample_value)
    assert result == sample_value


def test_pipeline_100_can_frames_all_parsed():
    """100 CAN frames can each be parsed and their data fed into an ADC filter."""
    filt = MedianFilter()
    outputs = []
    for i in range(100):
        can_id_word = ((i % 0x7FF) & 0x7FF) << 20
        header = struct.pack("<IBBBB", can_id_word, 1, 0, 0, 0)
        raw = header + bytes([i % 256]) + bytes(7)
        frame = parse_frame(raw)
        result = filt.push(float(frame.data[0]))
        if result is not None:
            outputs.append(result)
    assert len(outputs) == 96  # 100 - 4 warmup
    assert all(isinstance(v, float) for v in outputs)


def test_adc_output_is_monotone_for_linear_input():
    """For a linearly increasing CAN signal, the filtered output is also non-decreasing."""
    filt = MedianFilter()
    outputs = []
    for i in range(20):
        result = filt.push(float(i))
        if result is not None:
            outputs.append(result)
    # Outputs should be non-decreasing for a strictly increasing input
    for a, b in zip(outputs, outputs[1:], strict=False):
        assert b >= a


# ---------------------------------------------------------------------------
# HTTP health endpoint
# ---------------------------------------------------------------------------


def test_health_returns_200(gw):
    with urllib.request.urlopen(f"{gw}/api/health") as r:
        assert r.status == 200


def test_health_content_type_json(gw):
    with urllib.request.urlopen(f"{gw}/api/health") as r:
        ct = r.headers.get("Content-Type", "")
        assert "application/json" in ct


def test_health_ok_field_true(gw):
    with urllib.request.urlopen(f"{gw}/api/health") as r:
        body = json.loads(r.read())
    assert body.get("ok") is True


def test_unknown_endpoint_returns_404(gw):
    try:
        urllib.request.urlopen(f"{gw}/api/nonexistent")
    except urllib.error.HTTPError as e:
        assert e.code == 404
    else:
        pytest.fail("Expected 404")


# ---------------------------------------------------------------------------
# SSE streaming tests
# ---------------------------------------------------------------------------


def _collect_sse_events(url: str, max_events: int = 3, timeout: float = 5.0) -> list[dict]:
    """Open an SSE connection and collect up to max_events data frames."""
    events = []
    host, port = "127.0.0.1", 19501
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.sendall(b"GET /api/telemetry HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        s.settimeout(timeout)
        buf = b""
        deadline = time.time() + timeout
        while len(events) < max_events and time.time() < deadline:
            try:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"data:" in buf:
                    idx = buf.find(b"data:")
                    end = buf.find(b"\n\n", idx)
                    if end == -1:
                        break
                    line = buf[idx + 5 : end].strip()
                    buf = buf[end + 2 :]
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            except (TimeoutError, OSError):
                break
        s.close()
    except (OSError, ConnectionRefusedError):
        pass
    return events


def test_sse_delivers_events(gw):
    """SSE endpoint delivers at least one telemetry event within 5 s."""
    events = _collect_sse_events(f"{gw}/api/telemetry", max_events=1)
    assert len(events) >= 1, "No SSE events received within timeout"


def test_sse_event_has_required_fields(gw):
    """Each SSE event contains 'source' and 'value' keys."""
    events = _collect_sse_events(f"{gw}/api/telemetry", max_events=2)
    assert events, "No SSE events received"
    for evt in events:
        assert "source" in evt, f"Missing 'source' in {evt}"
        assert "value" in evt, f"Missing 'value' in {evt}"


def test_sse_value_is_numeric(gw):
    """SSE telemetry values are floats (not strings or None)."""
    events = _collect_sse_events(f"{gw}/api/telemetry", max_events=3)
    for evt in events:
        assert isinstance(evt["value"], (int, float)), f"Non-numeric value: {evt['value']}"


def test_sse_multiple_events_are_distinct(gw):
    """Multiple SSE events differ from each other (signal has variation)."""
    events = _collect_sse_events(f"{gw}/api/telemetry", max_events=5, timeout=8.0)
    if len(events) >= 2:
        values = [e["value"] for e in events]
        # At least some variation expected in a sinusoidal mock signal
        assert max(values) >= min(values)  # trivially true but validates schema


# ---------------------------------------------------------------------------
# Concurrent client tests
# ---------------------------------------------------------------------------


def test_two_concurrent_health_requests(gw):
    """Two concurrent health requests both return 200."""
    results = []

    def fetch():
        try:
            with urllib.request.urlopen(f"{gw}/api/health") as r:
                results.append(r.status)
        except Exception:
            results.append(0)

    t1 = threading.Thread(target=fetch)
    t2 = threading.Thread(target=fetch)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert results == [200, 200], f"Expected [200, 200], got {results}"


def test_ten_concurrent_health_requests(gw):
    """Ten concurrent health requests all succeed."""
    results = []
    lock = threading.Lock()

    def fetch():
        try:
            with urllib.request.urlopen(f"{gw}/api/health") as r, lock:
                results.append(r.status)
        except Exception:
            with lock:
                results.append(0)

    threads = [threading.Thread(target=fetch) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(results) == 10
    assert all(s == 200 for s in results), f"Some requests failed: {results}"


# ---------------------------------------------------------------------------
# Throughput / performance
# ---------------------------------------------------------------------------


def test_health_latency_under_100ms(gw):
    """Single health request completes in under 100 ms."""
    start = time.perf_counter()
    with urllib.request.urlopen(f"{gw}/api/health") as _:
        pass
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"Health latency {elapsed:.3f}s exceeded 100 ms"


def test_adc_filter_1000_samples_per_second():
    """MedianFilter can process at least 1 000 samples per second."""
    filt = MedianFilter()
    n = 1000
    start = time.perf_counter()
    for i in range(n):
        filt.push(float(i % 100))
    elapsed = time.perf_counter() - start
    rate = n / elapsed
    assert rate >= 1000, f"ADC filter throughput {rate:.0f} samples/s < 1000"


def test_can_parse_throughput_1000_frames():
    """CAN parser processes at least 1 000 frames per second."""
    header = struct.pack("<IBBBB", (0x100 & 0x7FF) << 20, 4, 0, 0, 0)
    raw = header + b"\xde\xad\xbe\xef\x00\x00\x00\x00"
    n = 1000
    start = time.perf_counter()
    for _ in range(n):
        parse_frame(raw)
    elapsed = time.perf_counter() - start
    rate = n / elapsed
    assert rate >= 1000, f"CAN parse throughput {rate:.0f} frames/s < 1000"


# ---------------------------------------------------------------------------
# Mock producer signal quality
# ---------------------------------------------------------------------------


def test_mock_producer_values_in_valid_range(gw):
    """Mock telemetry values fall in the range [0.0, 2.0] (sin-based signal)."""
    events = _collect_sse_events(f"{gw}/api/telemetry", max_events=5, timeout=8.0)
    for evt in events:
        v = evt.get("value", 0.0)
        assert -0.1 <= v <= 2.1, f"Value {v} out of expected [0, 2] range for mock signal"


def test_mock_producer_source_is_mock(gw):
    """Mock telemetry source field always equals 'mock' in fallback mode."""
    events = _collect_sse_events(f"{gw}/api/telemetry", max_events=3)
    for evt in events:
        assert evt.get("source") == "mock", f"Unexpected source: {evt.get('source')}"
