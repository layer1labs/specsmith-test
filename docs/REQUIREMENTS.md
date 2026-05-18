# Requirements

## REQ-001. CAN-bus Frame Parsing
- **ID:** REQ-001
- **Title:** CAN-bus Frame Parsing
- **Description:** The firmware C module SHALL parse CAN 2.0B frames (11-bit and 29-bit identifiers) from the SocketCAN interface within 1 ms latency.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §3
- **Test_Ids:** ['TEST-001', 'TEST-002']

## REQ-002. Sensor ADC Median Filter
- **ID:** REQ-002
- **Title:** Sensor ADC Median Filter
- **Description:** The firmware SHALL sample the ADC at 100 Hz and apply a 5-sample sliding window median filter before publishing to the telemetry bus.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §3
- **Test_Ids:** ['TEST-003']

## REQ-003. Telemetry CRC-32C Validation
- **ID:** REQ-003
- **Title:** Telemetry CRC-32C Validation
- **Description:** The Rust embedded crate SHALL validate every telemetry record with a CRC-32C checksum and reject frames where CRC does not match.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §4
- **Test_Ids:** ['TEST-004', 'TEST-005']

## REQ-004. Ring Buffer SPSC Overflow Protection
- **ID:** REQ-004
- **Title:** Ring Buffer SPSC Overflow Protection
- **Description:** The Rust ring buffer SHALL use a lock-free SPSC design and drop the oldest sample (not block) when the buffer is full.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §4
- **Test_Ids:** ['TEST-006']

## REQ-005. Python REST Telemetry Gateway
- **ID:** REQ-005
- **Title:** Python REST Telemetry Gateway
- **Description:** The Python API SHALL expose telemetry over HTTP/SSE at /api/telemetry with JSON payloads, supporting up to 10 concurrent SSE subscribers.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §5
- **Test_Ids:** ['TEST-007', 'TEST-008']

## REQ-006. SocketCAN Graceful Fallback
- **ID:** REQ-006
- **Title:** SocketCAN Graceful Fallback
- **Description:** The Python layer SHALL bind to the SocketCAN virtual interface (vcan0) and gracefully degrade to mock data when the interface is unavailable.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §5
- **Test_Ids:** ['TEST-009']

## REQ-007. Wayland Display Stub
- **ID:** REQ-007
- **Title:** Wayland Display Stub
- **Description:** A Wayland EGL stub SHALL render a minimal telemetry dashboard using PySide6, falling back to headless mode when no display is available.
- **Status:** partial
- **Source:** ARCHITECTURE.md §6
- **Test_Ids:** ['TEST-010']

## REQ-008. Governance Audit Health
- **ID:** REQ-008
- **Title:** Governance Audit Health
- **Description:** The project SHALL maintain specsmith audit health at all times. CI MUST fail if specsmith audit returns a non-zero exit code.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §2
- **Test_Ids:** ['TEST-011']

## REQ-009. Drift-Free Machine State
- **ID:** REQ-009
- **Title:** Drift-Free Machine State
- **Description:** specsmith sync --check SHALL exit 0 on every push, confirming the YAML governance sources and .specsmith/ machine state are in sync.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §2
- **Test_Ids:** ['TEST-012']

## REQ-010. Strict Schema Validation
- **ID:** REQ-010
- **Title:** Strict Schema Validation
- **Description:** specsmith validate --strict SHALL exit 0 with zero errors on every push, verifying no duplicate IDs, orphaned tests, or missing fields.
- **Status:** implemented
- **Source:** ARCHITECTURE.md §2
- **Test_Ids:** ['TEST-013']

