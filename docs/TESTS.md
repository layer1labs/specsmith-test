# Test Specification

## TEST-001. CAN frame parse — standard 11-bit ID
- **ID:** TEST-001
- **Title:** CAN frame parse — standard 11-bit ID
- **Description:** Parse a known-good 11-bit CAN frame and assert field values.
- **Requirement ID:** REQ-001
- **Type:** unit
- **Verification Method:** pytest
- **Confidence:** 1.0

## TEST-002. CAN frame parse — extended 29-bit ID
- **ID:** TEST-002
- **Title:** CAN frame parse — extended 29-bit ID
- **Description:** Parse a 29-bit extended CAN frame and verify identifier masking.
- **Requirement ID:** REQ-001
- **Type:** unit
- **Verification Method:** pytest
- **Confidence:** 1.0

## TEST-003. ADC median filter correctness
- **ID:** TEST-003
- **Title:** ADC median filter correctness
- **Description:** Feed 5 samples with a known median and assert filtered output.
- **Requirement ID:** REQ-002
- **Type:** unit
- **Verification Method:** pytest
- **Confidence:** 1.0

## TEST-004. CRC-32C accept valid frame
- **ID:** TEST-004
- **Title:** CRC-32C accept valid frame
- **Description:** A frame with correct CRC-32C passes validation without error.
- **Requirement ID:** REQ-003
- **Type:** unit
- **Verification Method:** cargo test
- **Confidence:** 1.0

## TEST-005. CRC-32C reject corrupted frame
- **ID:** TEST-005
- **Title:** CRC-32C reject corrupted frame
- **Description:** Flipping one byte in the payload causes the CRC check to fail.
- **Requirement ID:** REQ-003
- **Type:** unit
- **Verification Method:** cargo test
- **Confidence:** 1.0

## TEST-006. Ring buffer SPSC overflow drops oldest
- **ID:** TEST-006
- **Title:** Ring buffer SPSC overflow drops oldest
- **Description:** Fill the ring buffer beyond capacity; assert the oldest entry is dropped.
- **Requirement ID:** REQ-004
- **Type:** unit
- **Verification Method:** cargo test
- **Confidence:** 1.0

## TEST-007. REST /api/health returns JSON
- **ID:** TEST-007
- **Title:** REST /api/health returns JSON
- **Description:** HTTP GET /api/health returns 200 with Content-Type application/json.
- **Requirement ID:** REQ-005
- **Type:** integration
- **Verification Method:** pytest
- **Confidence:** 1.0

## TEST-008. SSE /api/telemetry streams events
- **ID:** TEST-008
- **Title:** SSE /api/telemetry streams events
- **Description:** Open an SSE connection; assert at least one event is received within 3 s.
- **Requirement ID:** REQ-005
- **Type:** integration
- **Verification Method:** pytest
- **Confidence:** 1.0

## TEST-009. SocketCAN graceful fallback
- **ID:** TEST-009
- **Title:** SocketCAN graceful fallback
- **Description:** With vcan0 absent, the gateway returns mock telemetry rather than raising.
- **Requirement ID:** REQ-006
- **Type:** integration
- **Verification Method:** pytest
- **Confidence:** 1.0

## TEST-010. Wayland headless mode
- **ID:** TEST-010
- **Title:** Wayland headless mode
- **Description:** When DISPLAY and WAYLAND_DISPLAY are unset, the display stub runs headless.
- **Requirement ID:** REQ-007
- **Type:** manual
- **Verification Method:** manual
- **Confidence:** 1.0

## TEST-011. specsmith audit exits 0
- **ID:** TEST-011
- **Title:** specsmith audit exits 0
- **Description:** Run specsmith audit --project-dir . and assert exit code 0.
- **Requirement ID:** REQ-008
- **Type:** cli
- **Verification Method:** bash
- **Confidence:** 1.0

## TEST-012. specsmith sync --check exits 0
- **ID:** TEST-012
- **Title:** specsmith sync --check exits 0
- **Description:** Run specsmith sync --check --project-dir . and assert exit code 0.
- **Requirement ID:** REQ-009
- **Type:** cli
- **Verification Method:** bash
- **Confidence:** 1.0

## TEST-013. specsmith validate --strict exits 0
- **ID:** TEST-013
- **Title:** specsmith validate --strict exits 0
- **Description:** Run specsmith validate --strict --json --project-dir . and assert exit 0.
- **Requirement ID:** REQ-010
- **Type:** cli
- **Verification Method:** bash
- **Confidence:** 1.0

