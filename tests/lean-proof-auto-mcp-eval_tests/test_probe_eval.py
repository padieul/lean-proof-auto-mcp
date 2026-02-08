"""Tests for probe tool evaluation.

This module tests the probe tool across fixture files and theorems in the
evaluation repository. Tests are organized into tiers (smoke, quick, normal)
using domain-based fixture selection and theorem sampling.

The probe tool tests individual theorems with automation modes (aesop, grind, both)
and returns a ProbeResult with outcome classification, suggested script, timing,
and diagnostics.

Tier Selection:
- Smoke: 2 files with 5 theorems each in one mode (~2 min)
- Quick: 5 files with 10 theorems each in all modes (~10 min)
- Normal: All 23 files with selected theorems in all modes (~30 min)

Theorem Selection Strategy:
- Use probe_file to discover available theorems in each fixture
- Select representative theorems from each file for testing
- Test each theorem-mode combination independently
"""

import pytest
import time
from typing import Any

from fixtures import FixtureFile, ALL_FIXTURE_FILES, SMOKE_FIXTURES, QUICK_FIXTURES
from mcp_client import MCPClient
from result_collector import ResultCollector
from eval_logger import EvalLogger


pytestmark = [pytest.mark.eval_normal]


# Probe modes to test
PROBE_MODES = ["aesop", "grind", "both"]


def _skip_if_no_fixtures(fixture_list: list[FixtureFile], tier: str) -> None:
    """Skip test if fixture list is empty."""
    if not fixture_list:
        pytest.skip(f"No fixture files available for {tier} tier")


def _discover_theorems(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    mode: str = "aesop",
    max_theorems: int | None = None,
) -> list[str]:
    """Discover theorems in a fixture file using probe_file tool.
    
    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file to probe
        mode: Probe mode to use for discovery
        max_theorems: Maximum number of theorems to return (None = all)
        
    Returns:
        List of theorem IDs discovered in the file
    """
    try:
        response = mcp_client.call_tool(
            "probe_file",
            {"file": str(fixture_file.path), "mode": mode, "budget_s": 60.0},
        )
        
        # Extract theorem list from probe_file response
        if response.get("status") == "success":
            probe_file_result = response.get("probe_file_result", {})
            theorem_results = probe_file_result.get("theorem_results", [])
            theorem_ids = [tr.get("theorem_id") for tr in theorem_results if tr.get("theorem_id")]
            
            if max_theorems is not None:
                return theorem_ids[:max_theorems]
            return theorem_ids
        
        return []
    except Exception:
        # If probe_file fails, return empty list
        return []


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
        mode: Probe mode (aesop, grind, both)
        result_collector: Result collector for recording outcomes
        logger: Optional logger for detailed output
        index: Current test index (for logging)
        total: Total number of tests (for logging)
        
    Returns:
        The parsed tool response dict
    """
    if logger:
        logger.log_fixture_start(
            f"{fixture_file.relative_path}::{theorem_id} (mode={mode})",
            0,  # File size not relevant for probe
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
        
        # Determine status from probe tool's response schema
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
    
    # Log the result details — always log structure check and tool-specific info
    if logger:
        elapsed_s = elapsed_ms / 1000
        
        if status == "timeout":
            # Already logged via log_error above
            pass
        else:
            # Always run structure check and log result
            passed, failures = _check_probe_response_structure(response)
            logger.log_fixture_result(response, elapsed_s, passed, failures)
        
        # Log tool-specific response details for ALL non-timeout responses
        if status != "timeout":
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
            else:
                logger.log_info(f"probe_result missing or not dict: {type(probe_result)}")
            
            diagnostics = response.get("diagnostics", [])
            if isinstance(diagnostics, list):
                logger.log_info(f"diagnostics_count={len(diagnostics)}")
                for i, d in enumerate(diagnostics[:3]):
                    sev = d.get("severity", "?") if isinstance(d, dict) else "?"
                    msg = d.get("message", "")[:120] if isinstance(d, dict) else str(d)[:120]
                    logger.log_info(f"  diag[{i}]: {sev}: {msg}")
            
            # Log error details if present
            error = response.get("error")
            if error:
                logger.log_info(f"error={str(error)[:200]}")
    
    return response


def _check_probe_response_structure(response: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check probe response structure without raising.
    
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
            for key in ("mode", "outcome", "classification"):
                if key not in probe_result:
                    failures.append(f"probe_result missing '{key}'")
    
    return len(failures) == 0, failures


def _assert_probe_response_structure(response: dict[str, Any]) -> None:
    """Assert the probe tool response conforms to the ProbeResult schema.
    
    Validates fields defined in core/probe_domain.py ProbeResult:
    api_version, status, run_id, probe_result, diagnostics, timing.
    """
    assert "status" in response, (
        f"Response missing 'status' field. Keys: {list(response.keys())}"
    )
    assert response["status"] in ("success", "fail", "timeout", "error"), (
        f"Invalid status: {response['status']}"
    )
    
    # For non-error responses, validate the full schema
    if response["status"] != "error":
        assert "api_version" in response, "Missing 'api_version'"
        assert "run_id" in response, "Missing 'run_id'"
        assert "probe_result" in response, "Missing 'probe_result'"
        assert "diagnostics" in response, "Missing 'diagnostics'"
        assert isinstance(response["diagnostics"], list), "diagnostics must be a list"
        assert "timing" in response, "Missing 'timing'"
        
        # Validate probe_result structure
        probe_result = response["probe_result"]
        assert "mode" in probe_result, "probe_result missing 'mode'"
        assert "outcome" in probe_result, "probe_result missing 'outcome'"
        assert "classification" in probe_result, "probe_result missing 'classification'"


class TestProbeSmoke:
    """Smoke tier: 2 files with 5 theorems each in one mode. Should complete in < 2 minutes."""
    
    @pytest.mark.eval_smoke
    def test_probe_smoke(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe tool on smoke tier fixtures with limited theorems."""
        _skip_if_no_fixtures(SMOKE_FIXTURES, "smoke")
        
        # Select first 2 files from smoke fixtures
        test_fixtures = SMOKE_FIXTURES[:2]
        mode = "aesop"  # Use single mode for smoke tier
        
        test_cases = []
        for fixture in test_fixtures:
            theorems = _discover_theorems(mcp_client, fixture, mode, max_theorems=5)
            for theorem_id in theorems:
                test_cases.append((fixture, theorem_id, mode))
        
        if not test_cases:
            pytest.skip("No theorems discovered in smoke fixtures")
        
        # Run probe on each test case
        for idx, (fixture, theorem_id, mode) in enumerate(test_cases):
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
    """Quick tier: 5 files with 10 theorems each in all modes. Should complete in < 10 minutes."""
    
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
        _skip_if_no_fixtures(QUICK_FIXTURES, "quick")
        
        # Select first 5 files from quick fixtures
        test_fixtures = QUICK_FIXTURES[:5]
        
        test_cases = []
        for fixture in test_fixtures:
            theorems = _discover_theorems(mcp_client, fixture, mode, max_theorems=10)
            for theorem_id in theorems:
                test_cases.append((fixture, theorem_id))
        
        if not test_cases:
            pytest.skip(f"No theorems discovered in quick fixtures for mode={mode}")
        
        # Run probe on each test case
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
    """Normal tier: All 23 files with selected theorems in all modes. Should complete in < 30 minutes."""
    
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
        
        test_cases = []
        for fixture in ALL_FIXTURE_FILES:
            # Discover up to 5 theorems per file for normal tier
            theorems = _discover_theorems(mcp_client, fixture, mode, max_theorems=5)
            for theorem_id in theorems:
                test_cases.append((fixture, theorem_id))
        
        if not test_cases:
            pytest.skip(f"No theorems discovered in fixtures for mode={mode}")
        
        # Run probe on each test case
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
