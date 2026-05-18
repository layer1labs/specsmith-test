"""specsmith governance CLI integration tests (REQ-008..REQ-010).

Exercises the specsmith tool chain directly: preflight, validate,
sync, audit, session-show, REQ/TEST coverage, and file existence
assertions.  Requires specsmith to be installed in the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Root of this project
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SPECSMITH = [sys.executable, "-m", "specsmith"]
_ENV = {**os.environ, "SPECSMITH_NO_AUTO_UPDATE": "1", "SPECSMITH_PYPI_CHECKED": "1"}


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*SPECSMITH, *args, "--project-dir", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        env=_ENV,
        check=check,
    )


# ---------------------------------------------------------------------------
# Critical governance files exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relpath",
    [
        "docs/SPECSMITH.yml",
        "docs/REQUIREMENTS.md",
        "docs/TESTS.md",
        "docs/ARCHITECTURE.md",
        "AGENTS.md",
        "LEDGER.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "docs/requirements/gateway.yml",
        "docs/tests/gateway.yml",
        ".specsmith/governance-mode",
        ".specsmith/requirements.json",
        ".specsmith/testcases.json",
    ],
)
def test_governance_file_exists(relpath: str):
    assert (PROJECT_ROOT / relpath).exists(), f"Missing: {relpath}"


# ---------------------------------------------------------------------------
# YAML-first mode (REQ-009)
# ---------------------------------------------------------------------------


def test_governance_mode_is_yaml():
    mode = (PROJECT_ROOT / ".specsmith" / "governance-mode").read_text().strip()
    assert mode == "yaml", f"Expected 'yaml', got '{mode}'"


# ---------------------------------------------------------------------------
# specsmith validate --strict (TEST-013 / REQ-010)
# ---------------------------------------------------------------------------


def test_validate_strict_exits_0():
    """specsmith validate --strict exits 0 (REQ-010)."""
    result = _run("validate", "--strict", "--json")
    assert result.returncode == 0, f"validate --strict failed:\n{result.stdout}\n{result.stderr}"


def test_validate_strict_zero_errors():
    """specsmith validate --strict reports 0 strict_errors."""
    result = _run("validate", "--strict", "--json")
    data = json.loads(result.stdout)
    assert data.get("strict_errors", 1) == 0, f"strict_errors: {data}"


def test_validate_strict_ok_true():
    """specsmith validate --strict reports ok: true."""
    result = _run("validate", "--strict", "--json")
    data = json.loads(result.stdout)
    assert data.get("ok") is True, f"ok is not True: {data}"


# ---------------------------------------------------------------------------
# specsmith sync --check (TEST-012 / REQ-009)
# ---------------------------------------------------------------------------


def test_sync_check_exits_0():
    """specsmith sync --check exits 0 (REQ-009)."""
    result = _run("sync", "--check")
    assert result.returncode == 0, f"sync --check failed:\n{result.stdout}\n{result.stderr}"


def test_sync_check_reports_in_sync():
    """Machine state matches YAML governance sources."""
    result = _run("sync", "--check")
    combined = (result.stdout + result.stderr).lower()
    assert "sync" in combined or "in sync" in combined or "already" in combined


# ---------------------------------------------------------------------------
# specsmith audit (TEST-011 / REQ-008)
# ---------------------------------------------------------------------------


def test_audit_exits_0():
    """specsmith audit exits 0 (REQ-008)."""
    result = _run("audit")
    assert result.returncode == 0, f"audit failed:\n{result.stdout}\n{result.stderr}"


def test_audit_reports_healthy():
    """specsmith audit output contains 'Healthy' or 'passed'."""
    result = _run("audit")
    combined = result.stdout + result.stderr
    assert "healthy" in combined.lower() or "passed" in combined.lower()


def test_audit_check_count_nonzero():
    """At least 1 check is reported by the auditor."""
    result = _run("audit")
    combined = result.stdout + result.stderr
    # Look for a number followed by 'check'
    import re

    matches = re.findall(r"(\d+)\s+checks?\s+passed", combined, re.IGNORECASE)
    assert matches, f"Could not find check count in: {combined[:500]}"
    assert int(matches[0]) > 0


# ---------------------------------------------------------------------------
# specsmith preflight (REQ-008 via governance gate)
# ---------------------------------------------------------------------------


def test_preflight_accepted_for_read_only():
    """A read-only query is accepted by the preflight classifier."""
    result = _run("preflight", "what is the current CAN frame parse latency?", "--json")
    data = json.loads(result.stdout)
    assert data["decision"] in ("accepted", "needs_clarification")
    assert data["intent"] in ("read_only_ask", "change", "needs_clarification")


def test_preflight_json_has_required_fields():
    """preflight --json output includes all contract fields."""
    result = _run("preflight", "add CRC retry logic for corrupted frames", "--json", check=False)
    data = json.loads(result.stdout)
    for field in ("decision", "intent", "confidence_target", "ai_disclosure"):
        assert field in data, f"Missing field '{field}' in preflight output"


def test_preflight_ai_disclosure_present():
    """Every preflight output includes AI disclosure metadata (REG-009)."""
    result = _run("preflight", "refactor ADC buffer size", "--json", check=False)
    data = json.loads(result.stdout)
    disclosure = data.get("ai_disclosure", {})
    assert disclosure.get("governed_by") == "specsmith"
    assert disclosure.get("governance_gated") is True


# ---------------------------------------------------------------------------
# REQ / TEST coverage assertions
# ---------------------------------------------------------------------------


def test_requirements_json_has_10_reqs():
    """Machine state records exactly 10 requirements (REQ-001..010)."""
    reqs_path = PROJECT_ROOT / ".specsmith" / "requirements.json"
    data = json.loads(reqs_path.read_text(encoding="utf-8"))
    assert len(data) == 10, f"Expected 10 reqs, found {len(data)}"


def test_testcases_json_has_13_tests():
    """Machine state records exactly 13 test cases (TEST-001..013)."""
    tests_path = PROJECT_ROOT / ".specsmith" / "testcases.json"
    data = json.loads(tests_path.read_text(encoding="utf-8"))
    assert len(data) == 13, f"Expected 13 tests, found {len(data)}"


def test_all_req_ids_sequential():
    """REQ IDs are REQ-001 through REQ-010 with no gaps."""
    reqs_path = PROJECT_ROOT / ".specsmith" / "requirements.json"
    data = json.loads(reqs_path.read_text(encoding="utf-8"))
    ids = {r["id"] for r in data}
    expected = {f"REQ-{i:03d}" for i in range(1, 11)}
    assert ids == expected, f"REQ ID mismatch: {ids ^ expected}"


def test_all_test_ids_sequential():
    """TEST IDs are TEST-001 through TEST-013 with no gaps."""
    tests_path = PROJECT_ROOT / ".specsmith" / "testcases.json"
    data = json.loads(tests_path.read_text(encoding="utf-8"))
    ids = {t["id"] for t in data}
    expected = {f"TEST-{i:03d}" for i in range(1, 14)}
    assert ids == expected, f"TEST ID mismatch: {ids ^ expected}"


def test_every_test_has_requirement_id():
    """Every test case in testcases.json references a requirement."""
    tests_path = PROJECT_ROOT / ".specsmith" / "testcases.json"
    data = json.loads(tests_path.read_text(encoding="utf-8"))
    for test in data:
        req_id = test.get("requirement_id") or test.get("req_id")
        assert req_id, f"Test {test.get('id')} has no requirement_id"
        assert req_id.startswith("REQ-"), f"Invalid requirement_id: {req_id}"


def test_req_coverage_no_gaps():
    """Every requirement appears in at least one test case."""
    reqs_path = PROJECT_ROOT / ".specsmith" / "requirements.json"
    tests_path = PROJECT_ROOT / ".specsmith" / "testcases.json"
    reqs = {r["id"] for r in json.loads(reqs_path.read_text(encoding="utf-8"))}
    tests = json.loads(tests_path.read_text(encoding="utf-8"))
    covered = {t.get("requirement_id") or t.get("req_id") for t in tests}
    uncovered = reqs - covered
    assert not uncovered, f"Uncovered requirements: {sorted(uncovered)}"


# ---------------------------------------------------------------------------
# LEDGER continuity
# ---------------------------------------------------------------------------


def test_ledger_has_entries():
    """LEDGER.md contains at least one governance entry."""
    ledger = (PROJECT_ROOT / "LEDGER.md").read_text(encoding="utf-8")
    sections = [ln for ln in ledger.splitlines() if ln.startswith("## ")]
    assert sections, "LEDGER.md has no ## entries"


def test_ledger_mentions_specsmith():
    """LEDGER.md references specsmith (bootstrapped by the tool)."""
    ledger = (PROJECT_ROOT / "LEDGER.md").read_text(encoding="utf-8")
    assert "specsmith" in ledger.lower()


# ---------------------------------------------------------------------------
# specsmith session-show (context seed / REQ-307)
# ---------------------------------------------------------------------------


def test_session_show_exits_0():
    """specsmith session-show exits 0 regardless of prior session state."""
    result = _run("session-show", "--json")
    assert result.returncode == 0, f"session-show failed:\n{result.stderr}"


def test_session_show_json_is_list():
    """specsmith session-show --json returns a JSON array (possibly empty)."""
    result = _run("session-show", "--json")
    data = json.loads(result.stdout)
    assert isinstance(data, list), f"Expected list, got {type(data).__name__}"


# ---------------------------------------------------------------------------
# Architecture document quality
# ---------------------------------------------------------------------------


def test_architecture_has_sections():
    """ARCHITECTURE.md contains at least 3 ## sections."""
    arch = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    sections = [ln for ln in arch.splitlines() if ln.startswith("## ")]
    assert len(sections) >= 3, f"ARCHITECTURE.md only has {len(sections)} sections"


def test_architecture_mentions_all_layers():
    """ARCHITECTURE.md references all 4 technology layers."""
    arch = (PROJECT_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8").lower()
    for layer in ("firmware", "rust", "python", "wayland"):
        assert layer in arch, f"ARCHITECTURE.md does not mention '{layer}'"
