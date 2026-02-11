"""Tests for try_automated_proof tool evaluation.

This module tests the try_automated_proof tool on selected theorems from
each mathematical domain in the evaluation repository. Tests are organized
into the normal tier.

The try_automated_proof tool validates whether a given proof script successfully
proves a theorem. It returns a TryAutomatedProofResult with validation success/failure,
timing, and diagnostics.

Tier Selection:
- Normal: Validation cases from all 6 domains (~30 min)

Theorem Selection Strategy:
- Choose theorems for try_automated_proof validation
- Ensure coverage across all 6 mathematical domains
- Focus on theorems with known proof tactics that can be validated
"""

import pytest
import time
from typing import Any

from fixtures import FixtureFile, ALL_FIXTURE_FILES
from mcp_client import MCPClient
from result_collector import ResultCollector
from eval_logger import EvalLogger


pytestmark = [pytest.mark.eval_normal]


# Validation theorems selected from each domain for try_automated_proof testing
# Format: (relative_path, theorem_id, proof_script)
#
# Every theorem_id is verified against actual declarations extracted by
# LeanInteract (cross-referenced with get_proof_context eval results).
# Proof scripts are simple tactics — they may fail (the test validates
# response structure, not proof correctness).
TRY_AUTOMATED_PROOF_CASES: list[tuple[str, str, str]] = [
    # Algebra domain (7 files)
    (r"Algebra\Group\Defs.lean", "mul_left_cancel", "simp"),
    (r"Algebra\Module\Defs.lean", "add_smul", "simp"),
    (r"Algebra\Polynomial\Basic.lean", "Polynomial.coeff_zero", "simp"),

    # Analysis domain (2 files)
    (r"Analysis\Calculus\Deriv\Basic.lean", "deriv_const", "simp"),
    (r"Analysis\Calculus\Deriv\MeanValue.lean", "exists_hasDerivAt_eq_slope", "simp"),

    # Data domain (2 files)
    (r"Data\Int\GCD.lean", "Int.gcd_def", "rfl"),
    (r"Data\Nat\Totient.lean", "Nat.totient_one", "rfl"),

    # GroupTheory domain (4 files)
    (r"GroupTheory\GroupAction\Basic.lean", "MulAction.orbit_eq_univ", "simp"),
    (r"GroupTheory\QuotientGroup\Defs.lean", "QuotientGroup.coe_mk'", "rfl"),

    # LinearAlgebra domain (4 files)
    (r"LinearAlgebra\LinearIndependent\Defs.lean", "linearIndependent_iff_injective_finsuppLinearCombination", "rfl"),
    (r"LinearAlgebra\Matrix\Determinant\Basic.lean", "Matrix.det_apply", "simp"),

    # RingTheory domain (3 files)
    (r"RingTheory\Ideal\Defs.lean", "Ideal.mul_mem_left", "simp"),
    (r"RingTheory\Ideal\Quotient\Operations.lean", "RingHom.kerLift_mk", "simp"),
]


def _skip_if_no_cases() -> None:
    """Skip test if no validation cases are selected."""
    if not TRY_AUTOMATED_PROOF_CASES:
        pytest.skip("No validation cases selected for try_automated_proof testing")


def _check_try_automated_proof_response_structure(
    response: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Check try_automated_proof response structure without raising.

    Validates the flat response schema from the target architecture:
    api_version, status, run_id, file, theorem_id, validation_status,
    error_message, error_location, proof_state, suggestions, metadata, timing.

    Returns (passed, failures) for logging purposes.
    """
    failures: list[str] = []

    if "status" not in response:
        failures.append(f"Response missing 'status' field. Keys: {list(response.keys())}")
        return False, failures

    status = response["status"]
    if status not in ("success", "error", "incomplete", "timeout"):
        failures.append(f"Invalid status: {status}")
        return False, failures

    # All responses (including error) should have these envelope fields
    for key in ("api_version", "run_id", "file", "theorem_id"):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate flat result fields (no try_result wrapper)
    for key in ("validation_status", "error_message", "error_location",
                "proof_state", "suggestions", "metadata", "timing"):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate suggestions is a list
    if "suggestions" in response and not isinstance(response["suggestions"], list):
        failures.append("suggestions must be a list")

    return len(failures) == 0, failures


def _assert_try_automated_proof_response_structure(response: dict[str, Any]) -> None:
    """Assert the try_automated_proof tool response conforms to the target flat schema.

    Delegates to _check_try_automated_proof_response_structure and raises on failure.
    """
    passed, failures = _check_try_automated_proof_response_structure(response)
    if not passed:
        raise AssertionError(
            f"try_automated_proof response structure invalid: {'; '.join(failures)}"
        )


def _log_try_automated_proof_details(logger: EvalLogger, response: dict[str, Any]) -> None:
    """Log try_automated_proof-specific response details.

    Extracted to keep _run_try_automated_proof_and_record focused on orchestration.
    Logs validation status, error info, proof state, suggestions, and metadata.
    """
    logger.log_info(f"response_keys={list(response.keys())}")
    logger.log_info(f"status={response.get('status', 'N/A')}")

    validation_status = response.get("validation_status", "N/A")
    logger.log_info(f"validation_status={validation_status}")

    error_msg = response.get("error_message")
    if error_msg:
        logger.log_info(f"error_message={str(error_msg)[:200]}")

    error_loc = response.get("error_location")
    if error_loc:
        logger.log_info(f"error_location={error_loc}")

    proof_state = response.get("proof_state")
    if isinstance(proof_state, dict):
        goal = proof_state.get("goal", "N/A")
        remaining = proof_state.get("goals_remaining", "?")
        hyps = proof_state.get("hypotheses", [])
        logger.log_info(
            f"proof_state: goal={str(goal)[:120]}, "
            f"goals_remaining={remaining}, hypotheses={len(hyps)}"
        )

    suggestions = response.get("suggestions", [])
    if suggestions:
        logger.log_info(f"suggestions ({len(suggestions)}): {suggestions[:3]}")

    timing = response.get("timing", {})
    if isinstance(timing, dict):
        logger.log_info(f"timing={timing}")

    metadata = response.get("metadata", {})
    if isinstance(metadata, dict) and metadata:
        logger.log_info(f"metadata={metadata}")


def _run_try_automated_proof_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    theorem_id: str,
    proof_script: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
) -> dict[str, Any]:
    """Run try_automated_proof tool on a theorem with proof script, record result, return response.

    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file containing the theorem
        theorem_id: Theorem identifier to validate proof for
        proof_script: Proof script to validate
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
            0,  # File size not relevant for try_automated_proof
            index,
            total,
        )

    start = time.perf_counter()

    try:
        response = mcp_client.call_tool(
            "try_automated_proof",
            {
                "file": str(fixture_file.path),
                "theorem_id": theorem_id,
                "proof_attempt": proof_script,
                "timeout_s": 30.0,
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Determine status from try_automated_proof tool's target response schema
        # Target statuses: success, error, incomplete, timeout
        tool_status = response.get("status", "")
        if tool_status in ("success", "error", "incomplete", "timeout"):
            status = tool_status
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
        tool="try_automated_proof",
        file_path=str(fixture_file.path),
        status=status,
        elapsed_ms=elapsed_ms,
        raw_response=response,
        domain=fixture_file.domain,
        subdomain=fixture_file.subdomain,
        theorem_id=theorem_id,
        mode=None,  # try_automated_proof doesn't use mode
    )

    # Log structure check and tool-specific details (matches probe/probe_file pattern)
    if logger and status != "timeout":
        passed, failures = _check_try_automated_proof_response_structure(response)
        logger.log_fixture_result(response, elapsed_ms / 1000, passed, failures)
        _log_try_automated_proof_details(logger, response)

    return response


class TestTryAutomatedProofNormal:
    """Normal tier: Validation cases from all 6 domains. Should complete in < 30 minutes."""

    @pytest.mark.eval_normal
    def test_try_automated_proof_normal(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test try_automated_proof tool on validation cases from each domain."""
        _skip_if_no_cases()

        # Build test cases from validation cases
        test_cases = []
        for relative_path, theorem_id, proof_script in TRY_AUTOMATED_PROOF_CASES:
            fixture = next(
                (f for f in ALL_FIXTURE_FILES if f.relative_path == relative_path),
                None
            )
            if fixture:
                test_cases.append((fixture, theorem_id, proof_script))

        if not test_cases:
            pytest.skip("No valid fixture files found for validation cases")

        for idx, (fixture, theorem_id, proof_script) in enumerate(test_cases):
            response = _run_try_automated_proof_and_record(
                mcp_client,
                fixture,
                theorem_id,
                proof_script,
                result_collector,
                logger=eval_logger,
                index=idx + 1,
                total=len(test_cases),
            )
            _assert_try_automated_proof_response_structure(response)
