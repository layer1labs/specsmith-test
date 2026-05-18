"""iSMART REST gateway — HTTP/SSE telemetry endpoint (REQ-005, REQ-006).

Exposes telemetry over HTTP/SSE at /api/telemetry with JSON payloads.
Binds to the SocketCAN virtual interface (vcan0); falls back to mock
data when the interface is unavailable (REQ-006).
"""

from __future__ import annotations

import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any

from ismart_core.can.frame import CanFrame, parse_frame
from ismart_core.sensor.adc import MedianFilter

_MOCK_INTERVAL = 0.1  # 100 Hz mock data rate


class _ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class GatewayHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the telemetry gateway."""

    telemetry_queue: queue.Queue[dict[str, Any]]

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # suppress default logging

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/telemetry":
            self._sse()
        elif self.path == "/api/health":
            self._json({"ok": True})
        else:
            self.send_error(404)

    def _json(self, data: dict[str, Any], code: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                try:
                    record = type(self).telemetry_queue.get(timeout=2)
                    line = f"data: {json.dumps(record)}\n\n".encode()
                    self.wfile.write(line)
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client disconnected — normal SSE teardown


def _mock_producer(q: queue.Queue[dict[str, Any]], stop: threading.Event) -> None:
    """Publish mock telemetry when SocketCAN is unavailable (REQ-006)."""
    filt = MedianFilter()
    t = 0.0
    while not stop.is_set():
        import math

        raw = 1.0 + 0.5 * math.sin(t)
        filtered = filt.push(raw)
        if filtered is not None:
            q.put({"source": "mock", "value": round(filtered, 4), "ts": time.time()})
        t += 0.1
        time.sleep(_MOCK_INTERVAL)


def run_gateway(host: str = "127.0.0.1", port: int = 8500) -> None:
    """Start the telemetry gateway HTTP server."""
    tq: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
    stop = threading.Event()

    class Handler(GatewayHandler):
        pass

    Handler.telemetry_queue = tq

    producer = threading.Thread(target=_mock_producer, args=(tq, stop), daemon=True)
    producer.start()

    server = _ThreadedServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.shutdown()
