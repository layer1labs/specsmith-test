# specsmith-test

Integration test harness for **specsmith** + **Kairos** — exercises the full
AEE (Applied Epistemic Engineering) lifecycle against a realistic multi-language
project.

## Project: iSMART Gateway Simulator

A simulated IoT gateway that:
- Reads CAN-bus sensor data (C firmware module)
- Processes and validates telemetry (Rust embedded crate)
- Exposes a Python REST API + Wayland display stub
- Governed end-to-end by specsmith with full YAML-first AEE traceability

## Two test paths

### Staging (ephemeral) — `staging.yml`
Runs on every push.  Creates a **fresh governed project from scratch** each time:

1. `specsmith import` — detect and scaffold governance overlay
2. `specsmith preflight` — classify a representative utterance
3. `specsmith validate --strict` — schema + traceability checks
4. `specsmith audit` — governance health
5. `specsmith sync --check` — machine state drift detection
6. `specsmith dispatch run --no-dag` — smoke-test the dispatch CLI

Proves the **bootstrap → governed → audited → dispatched** lifecycle is
repeatable from a clean slate on Python 3.10, 3.12, 3.13 across Ubuntu,
Windows, and macOS.

### Persistent (long-running) — `persistent.yml`
Runs weekly and on push to `main`.  The **repo itself evolves**:

- Requirements and tests accumulate over time
- LEDGER.md records every governance event
- Drift metrics, orphan tests, REQ coverage are tracked across commits
- Long-term CI failures surface epistemic debt before it compounds

## Languages & disciplines

| Layer | Language | Purpose |
|-------|----------|---------|
| Firmware | C (bare-metal) | CAN-bus frame parser + sensor ADC |
| Embedded RT | Rust | Telemetry validation, CRC, ring buffer |
| API | Python | REST gateway, Wayland display, SocketCAN |
| Governance | YAML | AEE requirements, tests, architecture |

## Sister repos

- [specsmith](https://github.com/layer1labs/specsmith) — AEE governance engine
- [kairos](https://github.com/layer1labs/kairos) — specsmith companion UI
