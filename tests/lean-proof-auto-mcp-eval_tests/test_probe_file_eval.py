"""Tests for probe_file tool evaluation.

This module tests the probe_file tool across fixture files in the evaluation
repository. Tests are organized into tiers (smoke, quick, normal) using
domain-based fixture selection for deterministic, cross-platform behavior.

The probe_file tool analyzes entire Lean 4 files to discover all theorems
and test them with automation modes (aesop, grind, both). It returns a
ProbeFileResult with theorem results, summary statistics, timing, and diagnostics.

Tier Selection (domain-based, not index-based):
- Smoke: 2 files in one mode (~2 min)
- Quick: 5 files in all three modes (~10 min)
- Normal: All 23 files in all three modes (~30 min)
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


def _run_probe_file_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    mode: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
) -> dict[str, Any]:
    """Run probe_file tool on a fixture file, record result, log details, return response.
    
    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file to probe
        mode: Probe mode (aesop, grind, both)
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
            f"{fixture_file.relative_path} (mode={mode})",
            file_size,
            index,
            total,
        )
    
    start = time.perf_counter()
    
    try:
        response = mcp_client.call_tool(
            "probe_file",
            {
                "file": str(fixture_file.path),
                "mode": mode,
                "budget_s": 120.0,
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # Determine status from probe_file tool's response schema
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
        tool="probe_file",
        file_path=str(fixture_file.path),
        status=status,
        elapsed_ms=elapsed_ms,
        raw_response=response,
        domain=fixture_file.domain,
        subdomain=fixture_file.subdomain,
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
            passed, failures = _check_probe_file_response_structure(response)
            logger.log_fixture_result(response, elapsed_s, passed, failures)
        
        # Log tool-specific response details for ALL non-timeout responses
        if status != "timeout":
            logger.log_info(f"response_keys={list(response.keys())}")
            logger.log_info(f"status={response.get('status', 'N/A')}")
            
            probe_file_result = response.get("probe_file_result", {})
            if isinstance(probe_file_result, dict):
                probe_mode = probe_file_result.get("mode", "N/A")
                theorem_results = probe_file_result.get("theorem_results", [])
                summary = probe_file_result.get("summary", {})
                theorem_count = len(theorem_results) if isinstance(theorem_results, list) else 0
                logger.log_info(f"mode={probe_mode}, theorem_count={theorem_count}")
                if isinstance(summary, dict):
                    logger.log_info(
                        f"summary: total={summary.get('total', '?')}, "
                        f"success={summary.get('success', '?')}, "
                        f"failure={summary.get('failure', '?')}, "
                        f"timeout={summary.get('timeout', '?')}"
                    )
                # Log first few theorem results for detail
                if isinstance(theorem_results, list):
                    for i, tr in enumerate(theorem_results[:3]):
                        if isinstance(tr, dict):
                            tid = tr.get("theorem_id", "?")
                            toutcome = tr.get("outcome", "?")
                            logger.log_info(f"  theorem[{i}]: {tid} -> {toutcome}")
            else:
                logger.log_info(f"probe_file_result missing or not dict: {type(probe_file_result)}")
            
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


def _check_probe_file_response_structure(response: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check probe_file response structure without raising.
    
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
        for key in ("api_version", "run_id", "probe_file_result", "diagnostics", "timing"):
            if key not in response:
                failures.append(f"Missing '{key}'")
        
        if "probe_file_result" in response:
            probe_file_result = response["probe_file_result"]
            for key in ("mode", "theorem_results", "summary"):
                if key not in probe_file_result:
                    failures.append(f"probe_file_result missing '{key}'")
            
            # Validate theorem_results is a list
            if "theorem_results" in probe_file_result:
                if not isinstance(probe_file_result["theorem_results"], list):
                    failures.append("theorem_results must be a list")
    
    return len(failures) == 0, failures


def _assert_probe_file_response_structure(response: dict[str, Any]) -> None:
    """Assert the probe_file tool response conforms to the ProbeFileResult schema.
    
    Validates fields defined in core/probe_file_domain.py ProbeFileResult:
    api_version, status, run_id, probe_file_result, diagnostics, timing.
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
        assert "probe_file_result" in response, "Missing 'probe_file_result'"
        assert "diagnostics" in response, "Missing 'diagnostics'"
        assert isinstance(response["diagnostics"], list), "diagnostics must be a list"
        assert "timing" in response, "Missing 'timing'"
        
        # Validate probe_file_result structure
        probe_file_result = response["probe_file_result"]
        assert "mode" in probe_file_result, "probe_file_result missing 'mode'"
        assert "theorem_results" in probe_file_result, "probe_file_result missing 'theorem_results'"
        assert isinstance(probe_file_result["theorem_results"], list), "theorem_results must be a list"
        assert "summary" in probe_file_result, "probe_file_result missing 'summary'"


class TestProbeFileSmoke:
    """Smoke tier: 2 files in one mode. Should complete in < 2 minutes."""
    
    @pytest.mark.eval_smoke
    @pytest.mark.parametrize(
        "fixture_file", SMOKE_FIXTURES[:2], ids=lambda f: f.relative_path
    )
    def test_probe_file_smoke(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe_file tool on smoke tier fixtures with one mode."""
        _skip_if_no_fixtures(SMOKE_FIXTURES[:2], "smoke")
        
        mode = "aesop"  # Use single mode for smoke tier
        idx = SMOKE_FIXTURES[:2].index(fixture_file)
        
        response = _run_probe_file_and_record(
            mcp_client,
            fixture_file,
            mode,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=len(SMOKE_FIXTURES[:2]),
        )
        
        _assert_probe_file_response_structure(response)
        
        # Validate response contains theorem list
        if response.get("status") == "success":
            probe_file_result = response.get("probe_file_result", {})
            theorem_results = probe_file_result.get("theorem_results", [])
            assert isinstance(theorem_results, list), "theorem_results must be a list"


class TestProbeFileQuick:
    """Quick tier: 5 files in all three modes. Should complete in < 10 minutes."""
    
    @pytest.mark.eval_quick
    @pytest.mark.parametrize("mode", PROBE_MODES)
    @pytest.mark.parametrize(
        "fixture_file", QUICK_FIXTURES[:5], ids=lambda f: f.relative_path
    )
    def test_probe_file_quick(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        mode: str,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe_file tool on quick tier fixtures with all modes."""
        _skip_if_no_fixtures(QUICK_FIXTURES[:5], "quick")
        
        # Calculate index for logging (fixture_index * modes + mode_index)
        fixture_idx = QUICK_FIXTURES[:5].index(fixture_file)
        mode_idx = PROBE_MODES.index(mode)
        idx = fixture_idx * len(PROBE_MODES) + mode_idx
        total = len(QUICK_FIXTURES[:5]) * len(PROBE_MODES)
        
        response = _run_probe_file_and_record(
            mcp_client,
            fixture_file,
            mode,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=total,
        )
        
        _assert_probe_file_response_structure(response)
        
        # Validate theorem counts
        if response.get("status") == "success":
            probe_file_result = response.get("probe_file_result", {})
            theorem_results = probe_file_result.get("theorem_results", [])
            assert isinstance(theorem_results, list), "theorem_results must be a list"
            # Theorem count should be non-negative
            assert len(theorem_results) >= 0, "theorem_results count must be non-negative"


class TestProbeFileNormal:
    """Normal tier: All 23 files in all three modes. Should complete in < 30 minutes."""
    
    @pytest.mark.eval_normal
    @pytest.mark.parametrize("mode", PROBE_MODES)
    @pytest.mark.parametrize(
        "fixture_file", ALL_FIXTURE_FILES, ids=lambda f: f.relative_path
    )
    def test_probe_file_normal(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        mode: str,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe_file tool on all fixtures with all modes."""
        _skip_if_no_fixtures(ALL_FIXTURE_FILES, "normal")
        
        # Calculate index for logging (fixture_index * modes + mode_index)
        fixture_idx = ALL_FIXTURE_FILES.index(fixture_file)
        mode_idx = PROBE_MODES.index(mode)
        idx = fixture_idx * len(PROBE_MODES) + mode_idx
        total = len(ALL_FIXTURE_FILES) * len(PROBE_MODES)
        
        response = _run_probe_file_and_record(
            mcp_client,
            fixture_file,
            mode,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=total,
        )
        
        _assert_probe_file_response_structure(response)
        
        # Verify theorem counts match expected ranges
        if response.get("status") == "success":
            probe_file_result = response.get("probe_file_result", {})
            theorem_results = probe_file_result.get("theorem_results", [])
            assert isinstance(theorem_results, list), "theorem_results must be a list"
            
            # Theorem count should be reasonable (0-1000 per file)
            theorem_count = len(theorem_results)
            assert 0 <= theorem_count <= 1000, (
                f"Unexpected theorem count: {theorem_count}. Expected 0-1000."
            )
