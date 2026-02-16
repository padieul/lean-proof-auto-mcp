"""Tests for probe_file tool evaluation.

This module tests the probe_file tool across fixture files in the evaluation
repository. Tests are organized into tiers (smoke, quick, normal) using
domain-based fixture selection for deterministic, cross-platform behavior.

The probe_file tool analyzes entire Lean 4 files to discover all theorems
and test them with automation modes (aesop, grind, aesop?). It returns a
ProbeFileResult with file path, summary statistics, per-theorem results, and metadata.

Tier Selection (domain-based, not index-based):
- Smoke: 2 files in one mode (~2 min)
- Quick: 5 files in all three modes (~10 min)
- Normal: All 23 files in all three modes (~30 min)
"""

import time
from typing import Any

import pytest
from eval_logger import EvalLogger
from mcp_client import MCPClient
from result_collector import ResultCollector

from fixtures import ALL_FIXTURE_FILES, QUICK_FIXTURES, SMOKE_FIXTURES, FixtureFile

pytestmark = [pytest.mark.eval_normal]


# Probe modes to test
PROBE_MODES = ["aesop", "grind", "aesop?"]

# Tier-specific fixture slices (computed once, reused everywhere)
_SMOKE_SLICE = SMOKE_FIXTURES[:2]
_QUICK_SLICE = QUICK_FIXTURES[:5]


def _skip_if_no_fixtures(fixture_list: list[FixtureFile], tier: str) -> None:
    """Skip test if fixture list is empty."""
    if not fixture_list:
        pytest.skip(f"No fixture files available for {tier} tier")


def _check_probe_file_response_structure(response: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check probe_file response structure without raising.

    Validates against the actual ProbeFileResult schema:
    api_version, status, file, summary, results, metadata.

    Returns (passed, failures) for logging purposes.
    """
    failures: list[str] = []

    if "status" not in response:
        failures.append(f"Response missing 'status' field. Keys: {list(response.keys())}")
        return False, failures

    status = response["status"]
    if status not in ("success", "partial", "error"):
        failures.append(f"Invalid status: {status}")
        return False, failures

    # All responses (including error) should have these top-level fields
    for key in ("api_version", "file", "summary", "results", "metadata"):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate summary structure
    if "summary" in response:
        summary = response["summary"]
        if not isinstance(summary, dict):
            failures.append("summary must be a dict")
        else:
            for key in ("total", "closed", "promising", "failed", "timed_out"):
                if key not in summary:
                    failures.append(f"summary missing '{key}'")

    # Validate results is a list
    if "results" in response:
        if not isinstance(response["results"], list):
            failures.append("results must be a list")

    # Validate metadata is a dict
    if "metadata" in response:
        if not isinstance(response["metadata"], dict):
            failures.append("metadata must be a dict")

    return len(failures) == 0, failures


def _assert_probe_file_response_structure(response: dict[str, Any]) -> None:
    """Assert the probe_file tool response conforms to the ProbeFileResult schema.

    Delegates to _check_probe_file_response_structure and raises on failure,
    keeping validation logic in one place.
    """
    passed, failures = _check_probe_file_response_structure(response)
    if not passed:
        raise AssertionError(f"probe_file response structure invalid: {'; '.join(failures)}")


def _log_probe_file_details(logger: EvalLogger, response: dict[str, Any]) -> None:
    """Log probe_file-specific response details.

    Extracted from the test helper to keep _run_probe_file_and_record focused
    on orchestration. Logs summary stats, first few per-theorem results,
    and metadata including error details.
    """
    logger.log_info(f"response_keys={list(response.keys())}")
    logger.log_info(f"status={response.get('status', 'N/A')}")

    # Summary stats
    summary = response.get("summary", {})
    if isinstance(summary, dict):
        logger.log_info(
            f"summary: total={summary.get('total', '?')}, "
            f"closed={summary.get('closed', '?')}, "
            f"promising={summary.get('promising', '?')}, "
            f"failed={summary.get('failed', '?')}, "
            f"timed_out={summary.get('timed_out', '?')}"
        )

    # Per-theorem results (first 3)
    results_list = response.get("results", [])
    if isinstance(results_list, list):
        logger.log_info(f"results_count={len(results_list)}")
        for i, tr in enumerate(results_list[:3]):
            if isinstance(tr, dict):
                tid = tr.get("theorem_id", tr.get("name", "?"))
                toutcome = tr.get("outcome", tr.get("status", "?"))
                logger.log_info(f"  result[{i}]: {tid} -> {toutcome}")

    # Metadata
    metadata = response.get("metadata", {})
    if not isinstance(metadata, dict):
        return

    elapsed = metadata.get("elapsed_ms", "?")
    logger.log_info(f"metadata: elapsed_ms={elapsed}")

    # Error fields
    error = metadata.get("error")
    if error:
        logger.log_info(f"metadata.error={str(error)[:200]}")
    error_code = metadata.get("error_code")
    if error_code:
        logger.log_info(f"metadata.error_code={error_code}")

    # Per-theorem error list
    errors_list = metadata.get("errors")
    if isinstance(errors_list, list):
        logger.log_info(f"metadata.errors_count={len(errors_list)}")
        for i, err in enumerate(errors_list[:5]):
            if isinstance(err, dict):
                tid = err.get("theorem_id", "?")
                emsg = str(err.get("error", ""))[:150]
                logger.log_info(f"  err[{i}]: {tid} -> {emsg}")

    # Aggregate counters
    for key in ("total_theorems", "successful_probes", "failed_probes"):
        val = metadata.get(key)
        if val is not None:
            logger.log_info(f"metadata.{key}={val}")


def _run_probe_file_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    mode: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run probe_file tool on a fixture file, record result, log details, return response.

    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file to probe
        mode: Probe mode (aesop, grind, aesop?)
        result_collector: Result collector for recording outcomes
        logger: Optional logger for detailed output
        index: Current test index (for logging)
        total: Total number of tests (for logging)
        limit: Maximum theorems to probe (optional)

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
        tool_args: dict[str, Any] = {
            "file": str(fixture_file.path),
            "mode": mode,
            "budget_s_per": 30.0,
        }
        if limit is not None:
            tool_args["limit"] = limit

        response = mcp_client.call_tool("probe_file", tool_args)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Determine status from probe_file tool's response schema
        # Valid statuses: "success", "partial", "error"
        tool_status = response.get("status", "")
        if tool_status in ("success", "partial"):
            status = tool_status
        elif tool_status == "error" or "error" in response:
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

    # Log structure check and tool-specific details
    if logger and status != "timeout":
        passed, failures = _check_probe_file_response_structure(response)
        logger.log_fixture_result(response, elapsed_ms / 1000, passed, failures)
        _log_probe_file_details(logger, response)

    return response


class TestProbeFileSmoke:
    """Smoke tier: 2 files in one mode. Should complete in < 2 minutes."""

    @pytest.mark.eval_smoke
    @pytest.mark.parametrize("fixture_file", _SMOKE_SLICE, ids=lambda f: f.relative_path)
    def test_probe_file_smoke(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe_file tool on smoke tier fixtures with one mode."""
        _skip_if_no_fixtures(_SMOKE_SLICE, "smoke")

        mode = "aesop"  # Single mode for smoke tier
        idx = _SMOKE_SLICE.index(fixture_file)

        response = _run_probe_file_and_record(
            mcp_client,
            fixture_file,
            mode,
            result_collector,
            logger=eval_logger,
            index=idx + 1,
            total=len(_SMOKE_SLICE),
            limit=5,  # Smoke tier: limit theorems for fast feedback
        )

        _assert_probe_file_response_structure(response)


class TestProbeFileQuick:
    """Quick tier: 5 files in all three modes. Should complete in < 10 minutes."""

    @pytest.mark.eval_quick
    @pytest.mark.parametrize("mode", PROBE_MODES)
    @pytest.mark.parametrize("fixture_file", _QUICK_SLICE, ids=lambda f: f.relative_path)
    def test_probe_file_quick(
        self,
        mcp_client: MCPClient,
        fixture_file: FixtureFile,
        mode: str,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test probe_file tool on quick tier fixtures with all modes."""
        _skip_if_no_fixtures(_QUICK_SLICE, "quick")

        fixture_idx = _QUICK_SLICE.index(fixture_file)
        mode_idx = PROBE_MODES.index(mode)
        idx = fixture_idx * len(PROBE_MODES) + mode_idx
        total = len(_QUICK_SLICE) * len(PROBE_MODES)

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


class TestProbeFileNormal:
    """Normal tier: All 23 files in all three modes. Should complete in < 30 minutes."""

    @pytest.mark.eval_normal
    @pytest.mark.parametrize("mode", PROBE_MODES)
    @pytest.mark.parametrize("fixture_file", ALL_FIXTURE_FILES, ids=lambda f: f.relative_path)
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

        # Verify result counts match expected ranges for successful probes
        if response.get("status") == "success":
            results_list = response.get("results", [])
            assert isinstance(results_list, list), "results must be a list"
            result_count = len(results_list)
            assert 0 <= result_count <= 1000, (
                f"Unexpected result count: {result_count}. Expected 0-1000."
            )
