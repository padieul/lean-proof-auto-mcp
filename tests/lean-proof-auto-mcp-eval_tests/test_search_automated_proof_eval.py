"""Tests for search_automated_proof tool evaluation.

This module tests the search_automated_proof tool on selected theorems from
each mathematical domain in the evaluation repository. Tests are organized
into the normal tier.

The search_automated_proof tool attempts to find automated proofs for theorems
using various tactics and strategies. It returns a SearchAutomatedProofResult
with proof success/failure, suggested tactics, timing, and diagnostics.

Tier Selection:
- Normal: Selected theorems from all 7 domains (~30 min)

Theorem Selection Strategy:
- Choose theorems that are good candidates for automated proof
- Ensure coverage across all 7 mathematical domains
- Focus on theorems with moderate complexity (not trivial, not too complex)
"""

import pytest
import time
from typing import Any

from fixtures import FixtureFile, ALL_FIXTURE_FILES
from mcp_client import MCPClient
from result_collector import ResultCollector
from eval_logger import EvalLogger


pytestmark = [pytest.mark.eval_normal]


# Representative theorems selected from each domain for automated proof testing
# Format: (relative_path, theorem_id)
# These theorems are selected to be good candidates for automated proof:
# - Not trivial (require some reasoning)
# - Not too complex (within automated proof capabilities)
# - Representative of each mathematical domain
AUTOMATED_PROOF_THEOREMS: list[tuple[str, str]] = [
    # Algebra domain (7 files)
    # Note: theorem_ids must match what the regex indexer produces.
    # Class fields (e.g. Module.zero_smul) are not indexed — use standalone theorems.
    (r"Algebra\Group\Defs.lean", "mul_left_cancel"),
    (r"Algebra\Module\Defs.lean", "add_smul"),
    (r"Algebra\Polynomial\Basic.lean", "Polynomial.coeff_zero"),

    # Analysis domain (2 files)
    (r"Analysis\Calculus\Deriv\Basic.lean", "deriv_const"),
    (r"Analysis\Calculus\Deriv\MeanValue.lean", "exists_hasDerivAt_eq_slope"),

    # Data domain (2 files)
    (r"Data\Int\GCD.lean", "Nat.gcd_eq_gcd_ab"),
    (r"Data\Nat\Totient.lean", "Nat.totient_one"),

    # GroupTheory domain (4 files)
    (r"GroupTheory\GroupAction\Basic.lean", "MulAction.orbit_eq_univ"),
    (r"GroupTheory\QuotientGroup\Defs.lean", "QuotientGroup.mk_one"),

    # LinearAlgebra domain (4 files)
    (r"LinearAlgebra\Basis\Defs.lean", "Basis.repr_self"),
    (r"LinearAlgebra\Matrix\Defs.lean", "Matrix.zero_apply"),

    # RingTheory domain (3 files)
    (r"RingTheory\Ideal\Defs.lean", "Ideal.zero_mem"),
    (r"RingTheory\Ideal\Quotient\Operations.lean", "Ideal.map_quotient_self"),
]


def _skip_if_no_theorems() -> None:
    """Skip test if no theorems are selected."""
    if not AUTOMATED_PROOF_THEOREMS:
        pytest.skip("No theorems selected for automated proof testing")


def _check_search_automated_proof_response_structure(
    response: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Check search_automated_proof response structure without raising.

    Validates the flat response schema from the target architecture:
    api_version, status, run_id, file, theorem_id, outcome, best_hint_set,
    attempts, explored_sets, feedback, metadata, search_trace, timing.

    Returns (passed, failures) for logging purposes.
    """
    failures: list[str] = []

    if "status" not in response:
        failures.append(f"Response missing 'status' field. Keys: {list(response.keys())}")
        return False, failures

    status = response["status"]
    if status not in ("success", "partial", "fail", "error"):
        failures.append(f"Invalid status: {status}")
        return False, failures

    # All responses should have envelope fields
    for key in ("api_version", "run_id", "file", "theorem_id"):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate flat result fields (no search_result wrapper)
    for key in ("outcome", "best_hint_set", "attempts", "explored_sets",
                "feedback", "metadata", "search_trace", "timing"):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate outcome values
    if "outcome" in response:
        outcome = response["outcome"]
        if outcome not in ("closed", "partial", "failed"):
            failures.append(f"Invalid outcome: {outcome}")

    # Validate feedback is a dict
    if "feedback" in response and not isinstance(response["feedback"], dict):
        failures.append("feedback must be a dict")

    return len(failures) == 0, failures


def _assert_search_automated_proof_response_structure(response: dict[str, Any]) -> None:
    """Assert the search_automated_proof tool response conforms to the target flat schema.

    Delegates to _check_search_automated_proof_response_structure and raises on failure.
    """
    passed, failures = _check_search_automated_proof_response_structure(response)
    if not passed:
        raise AssertionError(
            f"search_automated_proof response structure invalid: {'; '.join(failures)}"
        )


def _log_search_automated_proof_details(logger: EvalLogger, response: dict[str, Any]) -> None:
    """Log search_automated_proof-specific response details.

    Extracted to keep _run_search_automated_proof_and_record focused on orchestration.
    Logs outcome, hint sets, feedback, search trace, and metadata.
    """
    logger.log_info(f"response_keys={list(response.keys())}")
    logger.log_info(f"status={response.get('status', 'N/A')}")

    outcome = response.get("outcome", "N/A")
    attempts = response.get("attempts", "N/A")
    explored = response.get("explored_sets", "N/A")
    logger.log_info(f"outcome={outcome}, attempts={attempts}, explored_sets={explored}")

    best_hint_set = response.get("best_hint_set")
    if isinstance(best_hint_set, list) and best_hint_set:
        hint_names = [h.get("name", "?") if isinstance(h, dict) else str(h) for h in best_hint_set]
        logger.log_info(f"best_hint_set ({len(hint_names)} hints): {hint_names[:5]}")
    else:
        logger.log_info(f"best_hint_set={best_hint_set}")

    feedback = response.get("feedback", {})
    if isinstance(feedback, dict):
        fb_status = feedback.get("status", "N/A")
        hints_found = feedback.get("hints_found", [])
        suggestions = feedback.get("suggestions", [])
        partial = feedback.get("partial_progress")
        current_goal = feedback.get("current_goal")
        logger.log_info(
            f"feedback: status={fb_status}, hints_found={len(hints_found)}, "
            f"suggestions={len(suggestions)}"
        )
        if suggestions:
            logger.log_info(f"feedback.suggestions: {suggestions[:3]}")
        if current_goal:
            logger.log_info(f"feedback.current_goal={str(current_goal)[:120]}")
        if partial:
            logger.log_info(f"feedback.partial_progress={str(partial)[:200]}")

    search_trace = response.get("search_trace")
    if search_trace:
        logger.log_info(f"search_trace present ({type(search_trace).__name__})")

    timing = response.get("timing", {})
    if isinstance(timing, dict):
        logger.log_info(f"timing={timing}")

    metadata = response.get("metadata", {})
    if isinstance(metadata, dict) and metadata:
        logger.log_info(f"metadata={metadata}")


def _run_search_automated_proof_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    theorem_id: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
) -> dict[str, Any]:
    """Run search_automated_proof tool on a theorem, record result, return response.

    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file containing the theorem
        theorem_id: Theorem identifier to search proof for
        result_collector: Result collector for recording outcomes
        logger: Optional logger for detailed output
        index: Current test index (for logging)
        total: Total number of tests (for logging)

    Returns:
        The parsed tool response dict
    """
    if logger:
        logger.log_fixture_start(
            f"{fixture_file.relative_path}::{theorem_id}",
            0,  # File size not relevant for search_automated_proof
            index,
            total,
        )

    start = time.perf_counter()

    try:
        response = mcp_client.call_tool(
            "search_automated_proof",
            {
                "file": str(fixture_file.path),
                "theorem_id": theorem_id,
                "search_depth": "quick",
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Determine status from search_automated_proof tool's target response schema
        # Target statuses: success, partial, fail, error
        tool_status = response.get("status", "")
        if tool_status in ("success", "partial", "fail", "error"):
            status = tool_status if tool_status != "fail" else "failure"
        else:
            status = "error"

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
        tool="search_automated_proof",
        file_path=str(fixture_file.path),
        status=status,
        elapsed_ms=elapsed_ms,
        raw_response=response,
        domain=fixture_file.domain,
        subdomain=fixture_file.subdomain,
        theorem_id=theorem_id,
        mode=None,  # search_automated_proof doesn't use mode
    )

    # Log structure check and tool-specific details (matches probe/probe_file pattern)
    if logger and status != "timeout":
        passed, failures = _check_search_automated_proof_response_structure(response)
        logger.log_fixture_result(response, elapsed_ms / 1000, passed, failures)
        _log_search_automated_proof_details(logger, response)

    return response


class TestSearchAutomatedProofNormal:
    """Normal tier: Selected theorems from all 7 domains. Should complete in < 30 minutes."""

    @pytest.mark.eval_normal
    def test_search_automated_proof_normal(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test search_automated_proof tool on selected theorems from each domain."""
        _skip_if_no_theorems()

        # Build test cases from selected theorems
        test_cases = []
        for relative_path, theorem_id in AUTOMATED_PROOF_THEOREMS:
            fixture = next(
                (f for f in ALL_FIXTURE_FILES if f.relative_path == relative_path),
                None
            )
            if fixture:
                test_cases.append((fixture, theorem_id))

        if not test_cases:
            pytest.skip("No valid fixture files found for selected theorems")

        for idx, (fixture, theorem_id) in enumerate(test_cases):
            response = _run_search_automated_proof_and_record(
                mcp_client,
                fixture,
                theorem_id,
                result_collector,
                logger=eval_logger,
                index=idx + 1,
                total=len(test_cases),
            )
            _assert_search_automated_proof_response_structure(response)
