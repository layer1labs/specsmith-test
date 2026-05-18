# Architecture — iSMART Gateway Simulator

## 1. Overview

The iSMART Gateway Simulator is a multi-language IoT gateway that:
- Parses CAN-bus telemetry from a SocketCAN interface (C firmware + Python)
- Validates telemetry integrity using CRC-32C (Rust embedded crate)
- Buffers samples in a lock-free SPSC ring buffer (Rust)
- Exposes processed telemetry over HTTP/SSE (Python REST API)
- Renders a minimal Wayland dashboard (Python + PySide6, headless-capable)

## 2. Governance

This project is governed by specsmith (AEE spec 0.11.3) in YAML-first mode.
All requirements and tests are canonical in `docs/requirements/` and `docs/tests/`.
REQUIREMENTS.md and TESTS.md are derived artifacts — do not edit them directly.

## 3. Firmware Layer (C)

The `firmware/c/` directory contains a bare-metal CAN frame parser targeting
embedded Linux (SocketCAN). It handles:
- Standard 11-bit CAN 2.0A identifiers
- Extended 29-bit CAN 2.0B identifiers
- DLC validation and frame timestamp

No dynamic memory allocation is used in the real-time CAN path.

## 4. Embedded RT Layer (Rust)

The `firmware/rust/` crate provides:
- `TelemetryRecord` with CRC-32C integrity (REQ-003)
- `RingBuffer<T, N>` lock-free SPSC with overflow-drop semantics (REQ-004)

The Rust crate is `no_std` compatible and compiled to a static library
that the Python layer links via ctypes (future work).

## 5. API Layer (Python)

`src/ismart_core/` implements:
- `can/frame.py` — SocketCAN frame parser (REQ-001)
- `sensor/adc.py` — ADC median filter (REQ-002)
- `gateway.py` — HTTP/SSE REST server (REQ-005, REQ-006)

The gateway gracefully falls back to synthetic mock data when vcan0 is absent.

## 6. Display Layer (Python)

`src/ismart_core/display/` (planned): a PySide6/Wayland EGL stub that renders
a minimal telemetry dashboard. Headless mode activates automatically when
DISPLAY and WAYLAND_DISPLAY environment variables are unset (REQ-007).

## 7. Test Strategy

- Unit tests: pytest (Python) + cargo test (Rust), run on every push
- Integration tests: pytest with live gateway server fixture
- CLI tests: specsmith audit/sync/validate assertions in CI
- Manual tests: Wayland headless mode (TEST-010)
