"""Tests for probe tool evaluation.

This module tests the probe tool across fixture files and theorems in the
evaluation repository. Tests are organized into tiers (smoke, quick, normal)
using domain-based fixture selection and theorem sampling.

The probe tool tests individual theorems with automation modes (aesop, grind,
aesop?) and returns a ProbeResult with outcome classification, suggested script,
timing, and diagnostics.

Tier Selection:
- Smoke: 2 files, first 5 theorems each, one mode (~2 min)
- Quick: 5 files, first 10 theorems each, all modes (~10 min)
- Normal: All 23 files, first 5 theorems each, all modes (~30 min)

Theorem Discovery:
- Uses scan_file (lightweight regex scan) to discover theorem IDs
- Filters to theorem/lemma kinds only (no instances/examples)
- Falls back gracefully if scan_file returns no theorems
"""

import pytest
import time
from typing import Any

from fixtures import FixtureFile, ALL_FIXTURE_FILES, SMOKE_FIXTURES, QUICK_FIXTURES
from mcp_client import MCPClient
from result_collector import ResultCollector
from eval_logger import EvalLogger


pytestmark = [pytest.mark.eval_normal]


# Probe modes to test (must match probe tool's accepted values)
PROBE_MODES = ["aesop", "grind", "aesop?"]

# Tier-specific fixture slices
_SMOKE_SLICE = SMOKE_FIXTURES[:2]
_QUICK_SLICE = QUICK_FIXTURES[:5]

# Non-probeable declaration kinds (instances/examples can't have proofs replaced)
_NON_PROBEABLE_KINDS = {"instance", "example"}


def _skip_if_no_fixtures(fixture_list: list[FixtureFile], tier: str) -> None:
    """Skip test if fixture list is empty."""
    if not fixture_list:
        pytest.skip(f"No fixture files available for {tier} tier")


def _discover_theorems(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    max_theorems: int | None = None,
) -> list[str]:
    """Discover probeable theorems in a fixture file using scan_file.

    Uses scan_file (lightweight regex scan) rather than probe_file to avoid
    paying the Lean REPL cost just for discovery. Filters out instance and
    example declarations since those can't have proofs replaced with aesop/grind.

    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file to scan
        max_theorems: Maximum number of theorem IDs to return

    Returns:
        List of theorem IDs discovered in the file
    """
    try:
        response = mcp_client.call_tool(
            "scan_file",
            {"file": str(fixture_file.path)},
        )

        if response.get("status") != "success":
            return []

        theorems = response.get("theorems", [])
        # Filter to probeable kinds only
        theorem_ids = [
            t["theorem_id"]
            for t in theorems
            if t.get("theorem_id") and t.get("kind") not in _NON_PROBEABLE_KINDS
        ]

        if max_theorems is not None:
            return theorem_ids[:max_theorems]
        return theorem_ids
    except Exception:
        return []



def _check_probe_response_structure(response: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check probe response structure without raising.

    Validates against the ProbeResult schema:
    api_version, status, run_id, probe_result, diagnostics, timing.

    Returns (passed, failures) for logging purposes.
    """
    failures: list[str] = []

    if "status" not in response:
        failures.append(f"Response missing 'status' field. Keys: {list(response.keys())}")
        return False, failures

    status = response["status"]
    if status not in ("success", "fail", "timeout", "error"):
        failures.append(f"Invalid status: {status}")
        return False, failures

    if status != "error":
        for key in ("api_version", "run_id", "probe_result", "diagnostics", "timing"):
            if key not in response:
                failures.append(f"Missing '{key}'")

        if "probe_result" in response:
            probe_result = response["probe_result"]
            if not isinstance(probe_result, dict):
                failures.append("probe_result must be a dict")
            else:
                for key in ("mode", "outcome", "classification"):
                    if key not in probe_result:
                        failures.append(f"probe_result missing '{key}'")

    return len(failures) == 0, failures


def _assert_probe_response_structure(response: dict[str, Any]) -> None:
    """Assert the probe tool response conforms to the ProbeResult schema.

    Delegates to _check_probe_response_structure and raises on failure.
    """
    passed, failures = _check_probe_response_structure(response)
    if not passed:
        raise AssertionError(
            f"probe response structure invalid: {'; '.join(failures)}"
        )


def _log_probe_details(logger: EvalLogger, response: dict[str, Any]) -> None:
    """Log probe-specific response details.

    Extracted to keep _run_probe_and_record focused on orchestration.
    """
    logger.log_info(f"response_keys={list(response.keys())}")
    logger.log_info(f"status={response.get('status', 'N/A')}")

    probe_result = response.get("probe_result", {})
    if isinstance(probe_result, dict):
        outcome = probe_result.get("outcome", "N/A")
        classification = probe_result.get("classification", "N/A")
        probe_mode = probe_result.get("mode", "N/A")
        logger.log_info(f"mode={probe_mode}, outcome={outcome}, classification={classification}")
        suggested_script = probe_result.get("suggested_script")
        if suggested_script:
            logger.log_info(f"suggested_script={suggested_script[:150]}")

    diagnostics = response.get("diagnostics", [])
    if isinstance(diagnostics, list):
        logger.log_info(f"diagnostics_count={len(diagnostics)}")
        for i, d in enumerate(diagnostics[:3]):
            if isinstance(d, dict):
                sev = d.get("severity", "?")
                msg = d.get("message", "")[:120]
                logger.log_info(f"  diag[{i}]: {sev}: {msg}")

    timing = response.get("timing", {})
    if isinstance(timing, dict):
        logger.log_info(f"timing: elapsed_ms={timing.get('elapsed_ms', '?')}, budget_s={timing.get('budget_s', '?')}")

    error = response.get("error")
    if error:
        logger.log_info(f"error={str(error)[:200]}")

    metadata = response.get("metadata", {})
    if isinstance(metadata, dict):
        error_code = metadata.get("error_code")
        if error_code:
            logger.log_info(f"metadata.error_code={error_code}")


def _run_probe_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    theorem_id: str,
    mode: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
) -> dict[str, Any]:
    """Run probe tool on a theorem, record result, log details, return response.

    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file containing the theorem
        theorem_id: Theorem identifier to probe
        mode: Probe mode (aesop, grind, aesop?)
        result_collector: Result collector for recording outcomes
        logger: Optional logger for detailed output
        index: Current test index (for logging)
        total: Total number of tests (for logging)

    Returns:
        The parsed tool response dict
    """
    file_size = fixture_file.path.stat().st_size if fixture_file.path.exists() else 0
    if logger:
        logger.log_fixture_start(
            f"{fixture_file.relative_path}::{theorem_id} (mode={mode})",
            file_size,
            index,
            total,
        )

    start = time.perf_counter()

    try:
        response = mcp_client.call_tool(
            "probe",
            {
                "file": str(fixture_file.path),
                "theorem_id": theorem_id,
                "mode": mode,
                "budget_s": 30.0,
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        tool_status = response.get("status", "")
        if tool_status in ("success", "fail", "timeout"):
            status = tool_status if tool_status != "fail" else "failure"
        elif "error" in response:
            status = "error"
        else:
            status = "failure"

    except TimeoutError:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "timeout"
        response = {"error": "timeout", "status": "timeout"}
        if logger:
            logger.log_error(elapsed_ms / 1000, "timeout")
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "error"
        response = {"error": str(e), "status": "error"}
        if logger:
            logger.log_error(elapsed_ms / 1000, str(e))

    result_collector.record(
        tool="probe",
        file_path=str(fixture_file.path),
        status=status,
        elapsed_ms=elapsed_ms,
        raw_response=response,
        domain=fixture_file.domain,
        subdomain=fixture_file.subdomain,
        theorem_id=theorem_id,
        mode=mode,
    )

    if logger and status != "timeout":
        passed, failures = _check_probe_response_structure(response)
        logger.log_fixture_result(response, elapsed_ms / 1000, passed, failures)
        _log_probe_details(logger, response)

    return response



class TestProbeSmoke:
    """Smoke tier: 2 files, first 5 theorems each, one mode."""

    @pytest.mark.eval_smoke
    def test_probe_smoke(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe tool on smoke tier fixtures with limited theorems."""
        _skip_if_no_fixtures(_SMOKE_SLICE, "smoke")

        mode = "aesop"
        test_cases: list[tuple[FixtureFile, str]] = []
        for fixture in _SMOKE_SLICE:
            theorems = _discover_theorems(mcp_client, fixture, max_theorems=5)
            for theorem_id in theorems:
                test_cases.append((fixture, theorem_id))

        if not test_cases:
            pytest.skip("No theorems discovered in smoke fixtures")

        for idx, (fixture, theorem_id) in enumerate(test_cases):
            response = _run_probe_and_record(
                mcp_client,
                fixture,
                theorem_id,
                mode,
                result_collector,
                logger=eval_logger,
                index=idx + 1,
                total=len(test_cases),
            )
            _assert_probe_response_structure(response)


class TestProbeQuick:
    """Quick tier: 5 files, first 10 theorems each, all modes."""

    @pytest.mark.eval_quick
    @pytest.mark.parametrize("mode", PROBE_MODES)
    def test_probe_quick(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
        mode: str,
    ):
        """Test probe tool on quick tier fixtures with multiple theorems and modes."""
        _skip_if_no_fixtures(_QUICK_SLICE, "quick")

        test_cases: list[tuple[FixtureFile, str]] = []
        for fixture in _QUICK_SLICE:
            theorems = _discover_theorems(mcp_client, fixture, max_theorems=10)
            for theorem_id in theorems:
                test_cases.append((fixture, theorem_id))

        if not test_cases:
            pytest.skip(f"No theorems discovered in quick fixtures for mode={mode}")

        for idx, (fixture, theorem_id) in enumerate(test_cases):
            response = _run_probe_and_record(
                mcp_client,
                fixture,
                theorem_id,
                mode,
                result_collector,
                logger=eval_logger,
                index=idx + 1,
                total=len(test_cases),
            )
            _assert_probe_response_structure(response)


class TestProbeNormal:
    """Normal tier: All files, first 5 theorems each, all modes."""

    @pytest.mark.eval_normal
    @pytest.mark.parametrize("mode", PROBE_MODES)
    def test_probe_normal(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
        mode: str,
    ):
        """Test probe tool on all fixtures with selected theorems and all modes."""
        _skip_if_no_fixtures(ALL_FIXTURE_FILES, "normal")

        test_cases: list[tuple[FixtureFile, str]] = []
        for fixture in ALL_FIXTURE_FILES:
            theorems = _discover_theorems(mcp_client, fixture, max_theorems=5)
            for theorem_id in theorems:
                test_cases.append((fixture, theorem_id))

        if not test_cases:
            pytest.skip(f"No theorems discovered in fixtures for mode={mode}")

        for idx, (fixture, theorem_id) in enumerate(test_cases):
            response = _run_probe_and_record(
                mcp_client,
                fixture,
                theorem_id,
                mode,
                result_collector,
                logger=eval_logger,
                index=idx + 1,
                total=len(test_cases),
            )
            _assert_probe_response_structure(response)
