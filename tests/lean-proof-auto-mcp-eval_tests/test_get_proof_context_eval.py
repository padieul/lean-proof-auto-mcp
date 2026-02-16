"""Tests for get_proof_context tool evaluation.

This module tests the get_proof_context tool on selected theorems from
each mathematical domain in the evaluation repository. Tests are organized
into the normal tier.

The get_proof_context tool extracts relevant context for a theorem, including
imports, definitions, and related theorems. It returns a GetProofContextResult
with context information, timing, and diagnostics.

Tier Selection:
- Normal: One theorem per fixture file across all 7 domains (~30 min)

Theorem Selection Strategy:
- One theorem per fixture file (22 files, 22 theorems)
- Every theorem_id verified against actual declarations in the Lean source
- Coverage spans all 7 mathematical domains in the fixture set
"""

import time
from typing import Any

import pytest
from eval_logger import EvalLogger
from mcp_client import MCPClient
from result_collector import ResultCollector

from fixtures import ALL_FIXTURE_FILES, FixtureFile

pytestmark = [pytest.mark.eval_normal]


# Representative theorems selected from each domain for context extraction testing.
# Format: (relative_path, theorem_id)
#
# Selection criteria:
# - Every entry maps to an actual fixture file under fixtures/mathlib/Fixtures/
# - theorem_id matches a real theorem/lemma declaration in that file
# - Coverage spans all 7 mathematical domains present in the fixture set
CONTEXT_THEOREMS: list[tuple[str, str]] = [
    # Algebra domain (6 files)
    (r"Algebra\Group\Defs.lean", "mul_left_cancel"),
    (r"Algebra\Group\Subgroup\Basic.lean", "Subgroup.div_mem_comm_iff"),
    (r"Algebra\Module\Defs.lean", "add_smul"),
    (r"Algebra\Module\LinearMap\Defs.lean", "LinearMap.map_zero"),
    (r"Algebra\Polynomial\Basic.lean", "Polynomial.coeff_zero"),
    (r"Algebra\Polynomial\Derivative.lean", "Polynomial.derivative_zero"),
    (
        r"Algebra\Polynomial\FieldDivision.lean",
        "Polynomial.isRoot_iterate_derivative_of_lt_rootMultiplicity",
    ),
    # Analysis domain (2 files)
    (r"Analysis\Calculus\Deriv\Basic.lean", "deriv_const"),
    (r"Analysis\Calculus\Deriv\MeanValue.lean", "exists_hasDerivAt_eq_slope"),
    # Data domain (2 files)
    (r"Data\Int\GCD.lean", "Int.gcd_def"),
    (r"Data\Nat\Totient.lean", "Nat.totient_one"),
    # GroupTheory domain (4 files)
    (r"GroupTheory\GroupAction\Basic.lean", "MulAction.orbit_eq_univ"),
    (r"GroupTheory\GroupAction\Quotient.lean", "Quotient.smul_mk"),
    (r"GroupTheory\QuotientGroup\Basic.lean", "QuotientGroup.sound"),
    (r"GroupTheory\QuotientGroup\Defs.lean", "QuotientGroup.coe_mk'"),
    # LinearAlgebra domain (4 files)
    (r"LinearAlgebra\Basis\Defs.lean", "Basis.repr_self"),
    (
        r"LinearAlgebra\LinearIndependent\Defs.lean",
        "linearIndependent_iff_injective_finsuppLinearCombination",
    ),
    (r"LinearAlgebra\Matrix\Defs.lean", "Matrix.ext_iff"),
    (r"LinearAlgebra\Matrix\Determinant\Basic.lean", "Matrix.det_apply"),
    # RingTheory domain (3 files)
    (r"RingTheory\Ideal\Defs.lean", "Ideal.mul_mem_left"),
    (
        r"RingTheory\Ideal\Quotient\ChineseRemainder.lean",
        "Ideal.pi_tensorProductMk_quotient_surjective",
    ),
    (r"RingTheory\Ideal\Quotient\Operations.lean", "RingHom.kerLift_mk"),
]


def _skip_if_no_theorems() -> None:
    """Skip test if no theorems are selected."""
    if not CONTEXT_THEOREMS:
        pytest.skip("No theorems selected for context extraction testing")


def _check_get_proof_context_response_structure(response: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check get_proof_context response structure without raising.

    Validates the flat response schema from the target architecture:
    api_version, status, run_id, file, theorem_id, theorem_statement,
    original_proof, hypotheses, in_scope, namespace, similar_proofs,
    metadata, timing.

    Returns (passed, failures) for logging purposes.
    """
    failures: list[str] = []

    if "status" not in response:
        failures.append(f"Response missing 'status' field. Keys: {list(response.keys())}")
        return False, failures

    status = response["status"]
    if status not in ("success", "fail", "error"):
        failures.append(f"Invalid status: {status}")
        return False, failures

    # All responses should have envelope fields
    for key in ("api_version", "run_id", "file", "theorem_id"):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate flat context fields (no context wrapper dict)
    for key in (
        "theorem_statement",
        "original_proof",
        "hypotheses",
        "in_scope",
        "namespace",
        "similar_proofs",
        "metadata",
        "timing",
    ):
        if key not in response:
            failures.append(f"Missing '{key}'")

    # Validate list fields
    if "hypotheses" in response and not isinstance(response["hypotheses"], list):
        failures.append("hypotheses must be a list")
    if "in_scope" in response and not isinstance(response["in_scope"], list):
        failures.append("in_scope must be a list")
    if "similar_proofs" in response and not isinstance(response["similar_proofs"], list):
        failures.append("similar_proofs must be a list")

    # For successful extraction, validate content completeness
    if status == "success":
        completeness = _validate_context_completeness(response)
        if not any(completeness.values()):
            failures.append(
                "context should include at least one of: theorem_statement, "
                "original_proof, hypotheses, in_scope, or similar_proofs"
            )

    return len(failures) == 0, failures


def _validate_context_completeness(response: dict[str, Any]) -> dict[str, bool]:
    """Validate that the flat response includes theorem context fields.

    Args:
        response: The flat response dict from get_proof_context

    Returns:
        Dictionary with completeness metrics for each context field.
    """
    metrics = {
        "has_theorem_statement": False,
        "has_original_proof": False,
        "has_hypotheses": False,
        "has_in_scope": False,
        "has_similar_proofs": False,
    }

    theorem_stmt = response.get("theorem_statement")
    if isinstance(theorem_stmt, str) and theorem_stmt.strip():
        metrics["has_theorem_statement"] = True

    original_proof = response.get("original_proof")
    if isinstance(original_proof, str) and original_proof.strip():
        metrics["has_original_proof"] = True

    hypotheses = response.get("hypotheses")
    if isinstance(hypotheses, list) and hypotheses:
        metrics["has_hypotheses"] = True

    in_scope = response.get("in_scope")
    if isinstance(in_scope, list) and in_scope:
        metrics["has_in_scope"] = True

    similar_proofs = response.get("similar_proofs")
    if isinstance(similar_proofs, list) and similar_proofs:
        metrics["has_similar_proofs"] = True

    return metrics


def _assert_get_proof_context_response_structure(response: dict[str, Any]) -> None:
    """Assert the get_proof_context tool response conforms to the target flat schema.

    Delegates to _check_get_proof_context_response_structure and raises on failure.
    """
    passed, failures = _check_get_proof_context_response_structure(response)
    if not passed:
        raise AssertionError(f"get_proof_context response structure invalid: {'; '.join(failures)}")


def _log_get_proof_context_details(logger: EvalLogger, response: dict[str, Any]) -> None:
    """Log get_proof_context-specific response details.

    Extracted to keep _run_get_proof_context_and_record focused on orchestration.
    Logs context fields, completeness metrics, and metadata.
    """
    logger.log_info(f"response_keys={list(response.keys())}")
    logger.log_info(f"status={response.get('status', 'N/A')}")

    namespace = response.get("namespace", "")
    logger.log_info(f"namespace={namespace!r}")

    theorem_stmt = response.get("theorem_statement", "")
    if theorem_stmt:
        logger.log_info(f"theorem_statement={theorem_stmt[:150]}")
    else:
        logger.log_info("theorem_statement=(empty)")

    original_proof = response.get("original_proof", "")
    if original_proof:
        logger.log_info(f"original_proof present ({len(original_proof)} chars)")
    else:
        logger.log_info("original_proof=(empty)")

    hypotheses = response.get("hypotheses", [])
    if isinstance(hypotheses, list):
        logger.log_info(f"hypotheses count={len(hypotheses)}")
        for i, h in enumerate(hypotheses[:3]):
            logger.log_info(f"  hypothesis[{i}]={str(h)[:120]}")

    in_scope = response.get("in_scope", [])
    if isinstance(in_scope, list):
        logger.log_info(f"in_scope count={len(in_scope)}")
        for i, d in enumerate(in_scope[:3]):
            logger.log_info(f"  in_scope[{i}]={str(d)[:120]}")

    similar = response.get("similar_proofs", [])
    if isinstance(similar, list) and similar:
        sim_ids = [s.get("theorem_id", "?") if isinstance(s, dict) else str(s) for s in similar[:5]]
        logger.log_info(f"similar_proofs ({len(similar)}): {sim_ids}")
    else:
        logger.log_info(
            f"similar_proofs count={len(similar) if isinstance(similar, list) else 'N/A'}"
        )

    # Context quality summary (for successful responses)
    if response.get("status") == "success":
        completeness = _validate_context_completeness(response)
        hyp_count = len(hypotheses) if isinstance(hypotheses, list) else 0
        scope_count = len(in_scope) if isinstance(in_scope, list) else 0
        similar_count = len(similar) if isinstance(similar, list) else 0
        logger.log_info(
            f"context quality: theorem_stmt={completeness['has_theorem_statement']}, "
            f"original_proof={completeness['has_original_proof']}, "
            f"hypotheses={hyp_count}, in_scope={scope_count}, "
            f"similar_proofs={similar_count}"
        )

    timing = response.get("timing", {})
    if isinstance(timing, dict):
        logger.log_info(f"timing={timing}")

    metadata = response.get("metadata", {})
    if isinstance(metadata, dict) and metadata:
        logger.log_info(f"metadata={metadata}")


def _is_transient_lean_crash(response: dict[str, Any]) -> bool:
    """Detect transient Lean server crashes that are recoverable via retry.

    The Lean REPL can crash unexpectedly due to OOM or corrupted cache.
    These failures are transient and typically succeed on a second attempt
    after the MCP server restarts its internal REPL.
    """
    if response.get("status") != "error":
        return False
    metadata = response.get("metadata", {})
    if not isinstance(metadata, dict):
        return False
    error_msg = metadata.get("error_message", "")
    return "Lean server closed unexpectedly" in error_msg


def _call_get_proof_context(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    theorem_id: str,
) -> tuple[dict[str, Any], float, str]:
    """Execute a single get_proof_context call, returning (response, elapsed_ms, status).

    Pure orchestration: no logging, no recording, no side effects beyond the MCP call.
    """
    start = time.perf_counter()

    try:
        response = mcp_client.call_tool(
            "get_proof_context",
            {
                "file": str(fixture_file.path),
                "theorem_id": theorem_id,
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        tool_status = response.get("status", "")
        if tool_status in ("success", "fail", "error"):
            status = tool_status
        else:
            status = "error"

    except TimeoutError:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "timeout"
        response = {"error": "timeout", "status": "timeout"}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = "error"
        response = {"error": str(e), "status": "error"}

    return response, elapsed_ms, status


def _run_get_proof_context_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    theorem_id: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
    max_retries: int = 1,
) -> dict[str, Any]:
    """Run get_proof_context tool on a theorem, record result, return response.

    On transient Lean server crashes (OOM / corrupted REPL cache), restarts
    the MCP client and retries up to max_retries times before recording failure.

    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file containing the theorem
        theorem_id: Theorem identifier to extract context for
        result_collector: Result collector for recording outcomes
        logger: Optional logger for detailed output
        index: Current test index (for logging)
        total: Total number of tests (for logging)
        max_retries: Maximum retry attempts for transient Lean crashes

    Returns:
        The parsed tool response dict
    """
    if logger:
        logger.log_fixture_start(
            f"{fixture_file.relative_path}::{theorem_id}",
            0,  # File size not relevant for get_proof_context
            index,
            total,
        )

    response, elapsed_ms, status = _call_get_proof_context(
        mcp_client,
        fixture_file,
        theorem_id,
    )

    # Retry on transient Lean server crashes (OOM / corrupted REPL)
    for attempt in range(1, max_retries + 1):
        if not _is_transient_lean_crash(response):
            break
        if logger:
            logger.log_info(
                f"Transient Lean crash detected, restarting MCP client "
                f"(retry {attempt}/{max_retries})"
            )
        try:
            mcp_client.restart()
        except Exception as restart_err:
            if logger:
                logger.log_error(0, f"MCP restart failed: {restart_err}")
            break
        response, retry_ms, status = _call_get_proof_context(
            mcp_client,
            fixture_file,
            theorem_id,
        )
        elapsed_ms += retry_ms

    if status == "timeout" and logger:
        logger.log_error(elapsed_ms / 1000, "timeout")
    elif status == "error" and "error" in response and logger:
        error_val = response["error"]
        if isinstance(error_val, str):
            logger.log_error(elapsed_ms / 1000, error_val)

    result_collector.record(
        tool="get_proof_context",
        file_path=str(fixture_file.path),
        status=status,
        elapsed_ms=elapsed_ms,
        raw_response=response,
        domain=fixture_file.domain,
        subdomain=fixture_file.subdomain,
        theorem_id=theorem_id,
        mode=None,  # get_proof_context doesn't use mode
    )

    # Log structure check and tool-specific details (matches probe/probe_file pattern)
    if logger and status != "timeout":
        passed, failures = _check_get_proof_context_response_structure(response)
        logger.log_fixture_result(response, elapsed_ms / 1000, passed, failures)
        _log_get_proof_context_details(logger, response)

    return response


class TestGetProofContextNormal:
    """Normal tier: Selected theorems from all 7 domains. Should complete in < 30 minutes."""

    @pytest.mark.eval_normal
    def test_get_proof_context_normal(
        self,
        mcp_client: MCPClient,
        result_collector: ResultCollector,
        eval_logger: EvalLogger,
    ):
        """Test get_proof_context tool on selected theorems from each domain."""
        _skip_if_no_theorems()

        # Build test cases from selected theorems
        test_cases = []
        for relative_path, theorem_id in CONTEXT_THEOREMS:
            fixture = next((f for f in ALL_FIXTURE_FILES if f.relative_path == relative_path), None)
            if fixture:
                test_cases.append((fixture, theorem_id))

        if not test_cases:
            pytest.skip("No valid fixture files found for selected theorems")

        for idx, (fixture, theorem_id) in enumerate(test_cases):
            response = _run_get_proof_context_and_record(
                mcp_client,
                fixture,
                theorem_id,
                result_collector,
                logger=eval_logger,
                index=idx + 1,
                total=len(test_cases),
            )
            _assert_get_proof_context_response_structure(response)
