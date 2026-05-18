# AGENTS.md — iSMART Gateway Simulator

This project is governed by **specsmith** (AEE spec 0.11.3).
All changes must pass governance preflight before execution.

## Sister repos
- [specsmith](https://github.com/layer1labs/specsmith) — AEE governance engine
- [kairos](https://github.com/layer1labs/kairos) — specsmith desktop companion

## Governance contract

- REQUIREMENTS.md and TESTS.md are **derived** — edit YAML sources in `docs/requirements/` and `docs/tests/`
- Run `specsmith sync` after any YAML governance change
- Run `specsmith validate --strict` before committing
- Every change must be logged in LEDGER.md via `specsmith ledger add`

## Language-specific conventions

### Python (`src/ismart_core/`)
- `ruff` for lint and format (line-length 100)
- `pytest` for all tests — no unittest
- Type annotations required on all public functions

### Rust (`firmware/rust/`)
- `cargo clippy -- -D warnings` must pass
- `cargo fmt --all -- --check` must pass
- All public items must have doc comments

### C (`firmware/c/`)
- MISRA-C advisory subset; warnings as errors
- No dynamic memory allocation in real-time paths

## Test IDs
- TEST-001..003 → Python unit (CAN parse, ADC filter)
- TEST-004..006 → Rust unit (CRC, ring buffer)
- TEST-007..009 → Python integration (REST, SSE, SocketCAN)
- TEST-010 → Manual (Wayland headless)
- TEST-011..013 → specsmith CLI assertions (audit, sync, validate)
