"""Tests for get_proof_context tool evaluation.

This module tests the get_proof_context tool on selected theorems from
each mathematical domain in the evaluation repository. Tests are organized
into the normal tier.

The get_proof_context tool extracts relevant context for a theorem, including
imports, definitions, and related theorems. It returns a GetProofContextResult
with context information, timing, and diagnostics.

Tier Selection:
- Normal: Selected theorems from all 7 domains (~30 min)

Theorem Selection Strategy:
- Choose theorems that require context extraction
- Ensure coverage across all 7 mathematical domains
- Focus on theorems with dependencies on imports and definitions
"""

import pytest
import time
from typing import Any

from fixtures import FixtureFile, ALL_FIXTURE_FILES
from mcp_client import MCPClient
from result_collector import ResultCollector
from eval_logger import EvalLogger


pytestmark = [pytest.mark.eval_normal]


# Representative theorems selected from each domain for context extraction testing
# Format: (relative_path, theorem_id)
# These theorems are selected to require meaningful context:
# - Have dependencies on imports
# - Reference definitions or other theorems
# - Representative of each mathematical domain
CONTEXT_THEOREMS: list[tuple[str, str]] = [
    # Algebra domain (7 files)
    (r"Algebra\Group\Defs.lean", "mul_left_cancel"),
    (r"Algebra\Group\Subgroup\Basic.lean", "Subgroup.mem_carrier"),
    (r"Algebra\Module\Defs.lean", "zero_smul"),
    (r"Algebra\Module\LinearMap\Defs.lean", "LinearMap.map_zero"),
    (r"Algebra\Polynomial\Basic.lean", "Polynomial.coeff_zero"),
    (r"Algebra\Ring\Defs.lean", "mul_add"),
    (r"Algebra\Ring\Hom\Defs.lean", "RingHom.map_zero"),
    
    # Analysis domain (2 files)
    (r"Analysis\Calculus\Deriv\Basic.lean", "deriv_const"),
    (r"Analysis\Calculus\Deriv\MeanValue.lean", "exists_hasDerivAt_eq_slope"),
    
    # Data domain (2 files)
    (r"Data\Int\GCD.lean", "Int.gcd_comm"),
    (r"Data\Nat\Totient.lean", "Nat.totient_one"),
    
    # GroupTheory domain (4 files)
    (r"GroupTheory\GroupAction\Basic.lean", "MulAction.one_smul"),
    (r"GroupTheory\GroupAction\Defs.lean", "SMul.smul"),
    (r"GroupTheory\QuotientGroup\Defs.lean", "QuotientGroup.mk_one"),
    (r"GroupTheory\Subgroup\Basic.lean", "Subgroup.one_mem"),
    
    # LinearAlgebra domain (4 files)
    (r"LinearAlgebra\Basis\Defs.lean", "Basis.repr_self"),
    (r"LinearAlgebra\Matrix\Defs.lean", "Matrix.zero_apply"),
    (r"LinearAlgebra\Span.lean", "Submodule.mem_span"),
    (r"LinearAlgebra\StdBasis.lean", "LinearMap.stdBasis_apply"),
    
    # RingTheory domain (3 files)
    (r"RingTheory\Ideal\Defs.lean", "Ideal.zero_mem"),
    (r"RingTheory\Ideal\Quotient\Defs.lean", "Ideal.Quotient.mk_zero"),
    (r"RingTheory\Ideal\Quotient\Operations.lean", "Ideal.Quotient.mk_add"),
    
    # Topology domain (1 file)
    (r"Topology\Basic.lean", "isOpen_univ"),
]


def _skip_if_no_theorems() -> None:
    """Skip test if no theorems are selected."""
    if not CONTEXT_THEOREMS:
        pytest.skip("No theorems selected for context extraction testing")


def _run_get_proof_context_and_record(
    mcp_client: MCPClient,
    fixture_file: FixtureFile,
    theorem_id: str,
    result_collector: ResultCollector,
    logger: EvalLogger | None = None,
    index: int = 0,
    total: int = 0,
) -> dict[str, Any]:
    """Run get_proof_context tool on a theorem, record result, return response.
    
    Args:
        mcp_client: MCP client instance
        fixture_file: Fixture file containing the theorem
        theorem_id: Theorem identifier to extract context for
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
            0,  # File size not relevant for get_proof_context
            index,
            total,
        )
    
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
        
        # Determine status from get_proof_context tool's target response schema
        # Target statuses: success, error
        tool_status = response.get("status", "")
        if tool_status in ("success", "error"):
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
    
    # Extract context quality metrics from flat response fields
    context_metrics: dict[str, Any] = {}
    if status == "success":
        completeness = _validate_context_completeness(response)
        
        context_metrics["has_theorem_statement"] = completeness["has_theorem_statement"]
        context_metrics["has_original_proof"] = completeness["has_original_proof"]
        context_metrics["has_hypotheses"] = completeness["has_hypotheses"]
        context_metrics["has_in_scope"] = completeness["has_in_scope"]
        context_metrics["has_similar_proofs"] = completeness["has_similar_proofs"]
        
        # Log quality metrics
        if logger:
            hypotheses = response.get("hypotheses", [])
            in_scope = response.get("in_scope", [])
            similar = response.get("similar_proofs", [])
            hyp_count = len(hypotheses) if isinstance(hypotheses, list) else 0
            scope_count = len(in_scope) if isinstance(in_scope, list) else 0
            similar_count = len(similar) if isinstance(similar, list) else 0
            logger.log_info(
                f"Context quality: theorem_stmt={completeness['has_theorem_statement']}, "
                f"original_proof={completeness['has_original_proof']}, "
                f"hypotheses={hyp_count}, in_scope={scope_count}, "
                f"similar_proofs={similar_count}"
            )
    
    # Add metrics to raw response for result collection
    if context_metrics:
        response["_context_metrics"] = context_metrics
    
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
    
    # Log the result details — always log structure check and tool-specific info
    if logger:
        elapsed_s = elapsed_ms / 1000
        
        if status == "timeout":
            # Already logged via log_error above
            pass
        else:
            # Always run structure check and log result
            passed, failures = _check_get_proof_context_response_structure(response)
            logger.log_fixture_result(response, elapsed_s, passed, failures)
        
        # Log tool-specific response details for ALL non-timeout responses
        if status != "timeout":
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
                sim_ids = [s.get("theorem_id", "?") for s in similar[:5]]
                logger.log_info(f"similar_proofs ({len(similar)}): {sim_ids}")
            else:
                logger.log_info(f"similar_proofs count={len(similar) if isinstance(similar, list) else 'N/A'}")
            
            metadata = response.get("metadata", {})
            if isinstance(metadata, dict) and metadata:
                logger.log_info(f"metadata={metadata}")
    
    return response


def _check_get_proof_context_response_structure(
    response: dict[str, Any]
) -> tuple[bool, list[str]]:
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
    if status not in ("success", "error"):
        failures.append(f"Invalid status: {status}")
        return False, failures
    
    # All responses should have envelope fields
    for key in ("api_version", "run_id", "file", "theorem_id"):
        if key not in response:
            failures.append(f"Missing '{key}'")
    
    # Validate flat context fields (no context wrapper dict)
    for key in ("theorem_statement", "original_proof", "hypotheses",
                "in_scope", "namespace", "similar_proofs", "metadata", "timing"):
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
    
    # Check theorem_statement
    theorem_stmt = response.get("theorem_statement")
    if isinstance(theorem_stmt, str) and theorem_stmt.strip():
        metrics["has_theorem_statement"] = True
    
    # Check original_proof
    original_proof = response.get("original_proof")
    if isinstance(original_proof, str) and original_proof.strip():
        metrics["has_original_proof"] = True
    
    # Check hypotheses
    hypotheses = response.get("hypotheses")
    if isinstance(hypotheses, list) and hypotheses:
        metrics["has_hypotheses"] = True
    
    # Check in_scope declarations
    in_scope = response.get("in_scope")
    if isinstance(in_scope, list) and in_scope:
        metrics["has_in_scope"] = True
    
    # Check similar_proofs
    similar_proofs = response.get("similar_proofs")
    if isinstance(similar_proofs, list) and similar_proofs:
        metrics["has_similar_proofs"] = True
    
    return metrics


def _assert_get_proof_context_response_structure(response: dict[str, Any]) -> None:
    """Assert the get_proof_context tool response conforms to the target flat schema.
    
    Target architecture returns flat fields (no context wrapper dict):
    api_version, status, run_id, file, theorem_id, theorem_statement,
    original_proof, hypotheses, in_scope, namespace, similar_proofs,
    metadata, timing.
    """
    assert "status" in response, (
        f"Response missing 'status' field. Keys: {list(response.keys())}"
    )
    assert response["status"] in ("success", "error"), (
        f"Invalid status: {response['status']}"
    )
    
    # All responses should have envelope fields
    assert "api_version" in response, "Missing 'api_version'"
    assert "run_id" in response, "Missing 'run_id'"
    assert "file" in response, "Missing 'file'"
    assert "theorem_id" in response, "Missing 'theorem_id'"
    
    # Flat context fields (no context wrapper dict)
    assert "theorem_statement" in response, "Missing 'theorem_statement'"
    assert "original_proof" in response, "Missing 'original_proof'"
    assert "hypotheses" in response, "Missing 'hypotheses'"
    assert isinstance(response["hypotheses"], list), "hypotheses must be a list"
    assert "in_scope" in response, "Missing 'in_scope'"
    assert isinstance(response["in_scope"], list), "in_scope must be a list"
    assert "namespace" in response, "Missing 'namespace'"
    assert "similar_proofs" in response, "Missing 'similar_proofs'"
    assert isinstance(response["similar_proofs"], list), "similar_proofs must be a list"
    assert "metadata" in response, "Missing 'metadata'"
    assert "timing" in response, "Missing 'timing'"
    
    # For successful extraction, validate content completeness
    if response["status"] == "success":
        completeness = _validate_context_completeness(response)
        assert any(completeness.values()), (
            "context should include at least one of: theorem_statement, "
            "original_proof, hypotheses, in_scope, or similar_proofs"
        )


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
            # Find the fixture file matching this relative path
            fixture = next(
                (f for f in ALL_FIXTURE_FILES if f.relative_path == relative_path),
                None
            )
            if fixture:
                test_cases.append((fixture, theorem_id))
        
        if not test_cases:
            pytest.skip("No valid fixture files found for selected theorems")
        
        # Run get_proof_context on each test case
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
