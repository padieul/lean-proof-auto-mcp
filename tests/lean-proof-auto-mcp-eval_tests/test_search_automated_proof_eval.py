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
    (r"Algebra\Group\Defs.lean", "Group.mul_left_cancel"),
    (r"Algebra\Module\Defs.lean", "Module.zero_smul"),
    (r"Algebra\Polynomial\Basic.lean", "Polynomial.coeff_zero"),
    
    # Analysis domain (2 files)
    (r"Analysis\Calculus\Deriv\Basic.lean", "deriv_const"),
    (r"Analysis\Calculus\Deriv\MeanValue.lean", "exists_hasDerivAt_eq_slope"),
    
    # Data domain (2 files)
    (r"Data\Int\GCD.lean", "Int.gcd_comm"),
    (r"Data\Nat\Totient.lean", "Nat.totient_one"),
    
    # GroupTheory domain (4 files)
    (r"GroupTheory\GroupAction\Basic.lean", "MulAction.one_smul"),
    (r"GroupTheory\QuotientGroup\Defs.lean", "QuotientGroup.mk_one"),
    
    # LinearAlgebra domain (4 files)
    (r"LinearAlgebra\Basis\Defs.lean", "Basis.repr_self"),
    (r"LinearAlgebra\Matrix\Defs.lean", "Matrix.zero_apply"),
    
    # RingTheory domain (3 files)
    (r"RingTheory\Ideal\Defs.lean", "Ideal.zero_mem"),
    (r"RingTheory\Ideal\Quotient\Operations.lean", "Ideal.Quotient.mk_zero"),
]


def _skip_if_no_theorems() -> None:
    """Skip test if no theorems are selected."""
    if not AUTOMATED_PROOF_THEOREMS:
        pytest.skip("No theorems selected for automated proof testing")


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
    
    # Extract best hint set if found (flat field, no search_result wrapper)
    best_hint_set = None
    if status == "success":
        best_hint_set = response.get("best_hint_set")
    
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
    
    # Log the result details — always log structure check and tool-specific info
    if logger:
        elapsed_s = elapsed_ms / 1000
        
        if status == "timeout":
            # Already logged via log_error above
            pass
        else:
            # Always run structure check and log result
            passed, failures = _check_search_automated_proof_response_structure(response)
            logger.log_fixture_result(response, elapsed_s, passed, failures)
        
        # Log tool-specific response details for ALL non-timeout responses
        if status != "timeout":
            logger.log_info(f"response_keys={list(response.keys())}")
            logger.log_info(f"status={response.get('status', 'N/A')}")
            
            outcome = response.get("outcome", "N/A")
            attempts = response.get("attempts", "N/A")
            explored = response.get("explored_sets", "N/A")
            logger.log_info(f"outcome={outcome}, attempts={attempts}, explored_sets={explored}")
            
            if best_hint_set and isinstance(best_hint_set, list):
                hint_names = [h.get("name", "?") for h in best_hint_set]
                logger.log_info(f"best_hint_set ({len(hint_names)} hints): {hint_names[:5]}")
            elif best_hint_set is None:
                logger.log_info("best_hint_set=None")
            
            feedback = response.get("feedback", {})
            if isinstance(feedback, dict):
                fb_status = feedback.get("status", "N/A")
                hints_found = feedback.get("hints_found", [])
                suggestions = feedback.get("suggestions", [])
                partial = feedback.get("partial_progress", None)
                current_goal = feedback.get("current_goal", None)
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
            
            metadata = response.get("metadata", {})
            if isinstance(metadata, dict) and metadata:
                logger.log_info(f"metadata={metadata}")
    
    return response


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
    
    Target architecture returns flat fields (no search_result wrapper):
    api_version, status, run_id, file, theorem_id, outcome, best_hint_set,
    attempts, explored_sets, feedback, metadata, search_trace, timing.
    """
    assert "status" in response, (
        f"Response missing 'status' field. Keys: {list(response.keys())}"
    )
    assert response["status"] in ("success", "partial", "fail", "error"), (
        f"Invalid status: {response['status']}"
    )
    
    # All responses should have envelope fields
    assert "api_version" in response, "Missing 'api_version'"
    assert "run_id" in response, "Missing 'run_id'"
    assert "file" in response, "Missing 'file'"
    assert "theorem_id" in response, "Missing 'theorem_id'"
    
    # Flat result fields (no search_result wrapper)
    assert "outcome" in response, "Missing 'outcome'"
    assert response["outcome"] in ("closed", "partial", "failed"), (
        f"Invalid outcome: {response['outcome']}"
    )
    assert "best_hint_set" in response, "Missing 'best_hint_set'"
    assert "attempts" in response, "Missing 'attempts'"
    assert "explored_sets" in response, "Missing 'explored_sets'"
    assert "feedback" in response, "Missing 'feedback'"
    assert isinstance(response["feedback"], dict), "feedback must be a dict"
    assert "metadata" in response, "Missing 'metadata'"
    assert "search_trace" in response, "Missing 'search_trace'"
    assert "timing" in response, "Missing 'timing'"


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
            # Find the fixture file matching this relative path
            fixture = next(
                (f for f in ALL_FIXTURE_FILES if f.relative_path == relative_path),
                None
            )
            if fixture:
                test_cases.append((fixture, theorem_id))
        
        if not test_cases:
            pytest.skip("No valid fixture files found for selected theorems")
        
        # Run search_automated_proof on each test case
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
