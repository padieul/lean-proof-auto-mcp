"""Tests for verify tool evaluation.

This module tests the verify tool across fixture files in the evaluation
repository. Tests are organized into tiers (smoke, quick, normal) using
domain-based fixture selection for deterministic, cross-platform behavior.

The verify tool validates Lean 4 files by checking syntax and type correctness.
It operates at the file level and returns a VerifyResult with status, diagnostics,
timing, and evidence.

Tier Selection (domain-based, not index-based):
- Smoke: Totient fixtures only (~2 min)
- Quick: Data + GroupTheory/Group fixtures (~10 min)
- Normal: All 23 fixture files (~30 min)
"""

import time

import pytest
from eval_logger import EvalLogger
from mcp_client import MCPClient
from result_collector import ResultCollector

from fixtures import ALL_FIXTURE_FILES, QUICK_FIXTURES, SMOKE_FIXTURES, FixtureFile

pytestmark = [pytest.mark.eval_normal]


def _skip_if_no_fixtures(fixture_list: list[FixtureFile], tier: str) -> None:
    """Skip test if fixture list is empty."""
    if not fixture_list:
        pytest.skip(f"No fixture files available for {tier} tier")


def _run_verify_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
) -> dict:
    """Run verify tool on a fixture file, record result, log details, return response.

    Uses the correct MCP parameter name 'file' (not 'file_path').
    Records the outcome in result_collector regardless of success or failure.
    When a logger is provided, writes detailed per-fixture output to the log.

    Returns:
        The parsed tool response dict.
    """
    file_size = fixture_file.path.stat().st_size if fixture_file.path.exists() else 0
    if logger:
        logger.log_fixture_start(fixture_file.relative_path, file_size, index, total)

    start = time.perf_counter()

    try:
        response = mcp_client.call_tool(
            "verify",
            {"file": str(fixture_file.path), "budget_s": 120.0},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Determine status from verify tool's response schema
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
        tool="verify",
        file_path=str(fixture_file.path),
        status=status,
        elapsed_ms=elapsed_ms,
        raw_response=response,
        domain=fixture_file.domain,
        subdomain=fixture_file.subdomain,
    )

    # Log the result details (assertion check without raising)
    if logger and status not in ("timeout", "error"):
        passed, failures = _check_verify_response_structure(response)
        logger.log_fixture_result(response, elapsed_ms / 1000, passed, failures)

    return response


def _check_verify_response_structure(response: dict) -> tuple[bool, list[str]]:
    """Check verify response structure without raising.

    Mirrors _assert_verify_response_structure but returns (passed, failures)
    instead of raising AssertionError. Used by the logger to record outcomes.
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
        for key in ("api_version", "run_id", "file", "diagnostics", "diagnostic_summary", "timing"):
            if key not in response:
                failures.append(f"Missing '{key}'")
        if "diagnostics" in response and not isinstance(response["diagnostics"], list):
            failures.append("diagnostics must be a list")

    if status == "success":
        summary = response.get("diagnostic_summary", {})
        if summary.get("error_count", 0) != 0:
            failures.append(f"Success status but error_count={summary.get('error_count')}")

    return len(failures) == 0, failures


def _assert_verify_response_structure(response: dict) -> None:
    """Assert the verify tool response conforms to the VerifyResult schema.

    Validates fields defined in core/verify_domain.py VerifyResult:
    api_version, status, run_id, file, diagnostics, diagnostic_summary, timing.
    """
    # Must have the core status field
    assert "status" in response, f"Response missing 'status' field. Keys: {list(response.keys())}"
    assert response["status"] in ("success", "fail", "timeout", "error"), (
        f"Invalid status: {response['status']}"
    )

    # For non-error responses, validate the full schema
    if response["status"] != "error":
        assert "api_version" in response, "Missing 'api_version'"
        assert "run_id" in response, "Missing 'run_id'"
        assert "file" in response, "Missing 'file'"
        assert "diagnostics" in response, "Missing 'diagnostics'"
        assert isinstance(response["diagnostics"], list), "diagnostics must be a list"
        assert "diagnostic_summary" in response, "Missing 'diagnostic_summary'"
        assert "timing" in response, "Missing 'timing'"

    # For successful verification, diagnostics should have no errors
    if response["status"] == "success":
        summary = response.get("diagnostic_summary", {})
        assert summary.get("error_count", 0) == 0, (
            f"Success status but error_count={summary.get('error_count')}"
        )


class TestVerifySmoke:
    """Smoke tier: Totient fixtures only. Should complete in < 2 minutes."""

    @pytest.mark.eval_smoke
    @pytest.mark.parametrize("fixture_file", SMOKE_FIXTURES, ids=lambda f: f.relative_path)
    def test_verify_smoke(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        _skip_if_no_fixtures(SMOKE_FIXTURES, "smoke")
        idx = SMOKE_FIXTURES.index(fixture_file)
        response = _run_verify_and_record(
            mcp_client,
            fixture_file,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=len(SMOKE_FIXTURES),
        )
        _assert_verify_response_structure(response)


class TestVerifyQuick:
    """Quick tier: Data + Group domain fixtures. Should complete in < 10 minutes."""

    @pytest.mark.eval_quick
    @pytest.mark.parametrize("fixture_file", QUICK_FIXTURES, ids=lambda f: f.relative_path)
    def test_verify_quick(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        _skip_if_no_fixtures(QUICK_FIXTURES, "quick")
        idx = QUICK_FIXTURES.index(fixture_file)
        response = _run_verify_and_record(
            mcp_client,
            fixture_file,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=len(QUICK_FIXTURES),
        )
        _assert_verify_response_structure(response)


class TestVerifyNormal:
    """Normal tier: All 23 fixture files. Should complete in < 30 minutes."""

    @pytest.mark.eval_normal
    @pytest.mark.parametrize("fixture_file", ALL_FIXTURE_FILES, ids=lambda f: f.relative_path)
    def test_verify_normal(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        _skip_if_no_fixtures(ALL_FIXTURE_FILES, "normal")
        idx = ALL_FIXTURE_FILES.index(fixture_file)
        response = _run_verify_and_record(
            mcp_client,
            fixture_file,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=len(ALL_FIXTURE_FILES),
        )
        _assert_verify_response_structure(response)
