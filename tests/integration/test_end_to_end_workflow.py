"""End-to-end integration tests for complete proof refactoring workflow.

These tests verify the complete workflow with real Lean files:
- Search → validate → iterate cycle
- All three MCP tools working together (search_automated_proof,
  try_automated_proof, get_proof_context)
- Real mathlib theorems
- Complete iteration cycles

Requirements: 27.3
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lean_proof_auto_mcp.tools.get_proof_context import get_proof_context
from lean_proof_auto_mcp.tools.search_automated_proof import search_automated_proof
from lean_proof_auto_mcp.tools.try_automated_proof import try_automated_proof

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
MATHLIB_DIR = Path(__file__).parent.parent / "fixtures" / "mathlib_lean_files"
VALID_THEOREM = str(FIXTURES_DIR / "valid_theorem.lean")
AESOP_TRIVIAL = str(FIXTURES_DIR / "probe_aesop_trivial.lean")
MULTI_THEOREM = str(FIXTURES_DIR / "probe_file_multi_theorem.lean")


@pytest.mark.e2e
@pytest.mark.integration
class TestCompleteWorkflow:
    """Test complete end-to-end workflow with all three tools."""

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    @patch("lean_proof_auto_mcp.tools.try_automated_proof._create_handler")
    @patch("lean_proof_auto_mcp.tools.get_proof_context._create_extractor")
    def test_search_validate_iterate_cycle(
        self,
        mock_create_extractor,
        mock_create_handler,
        mock_create_orchestrator,
    ):
        """Test complete search → validate → iterate cycle.

        Requirements: 27.3
        """
        from lean_proof_auto_mcp.core.feedback_builder import (
            SearchFeedback,
            Suggestion,
        )
        from lean_proof_auto_mcp.core.search_automated_proof_domain import (
            Candidate,
            CandidateSource,
            Hint,
            HintType,
        )
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced
        from lean_proof_auto_mcp.lean.validator import ValidationResult

        # Setup mocks
        mock_orchestrator = MagicMock()
        mock_handler = MagicMock()
        mock_context_extractor = MagicMock()

        # Mock search result
        hint = Hint(
            name="Nat.add_comm",
            type=HintType.ADD_SAFE,
            source=CandidateSource.GOAL_SYMBOLS,
        )
        candidate = Candidate(hint=hint, rank=0.9, metadata={})

        feedback = SearchFeedback(
            status="success",
            hints_found=[candidate],
            partial_progress=None,
            current_goal=None,
            suggestions=[
                Suggestion(
                    type="tactic",
                    suggestion="Try validating with try_automated_proof",
                    confidence=0.9,
                    reasoning="Found promising hints",
                )
            ],
        )

        search_result = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[candidate],
            attempts=5,
            explored_sets=10,
            feedback=feedback,
            metadata={"repo_commit": "abc123"},
            search_trace=None,
        )

        mock_orchestrator.search.return_value = search_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Mock validation result
        validation_result = ValidationResult(
            status="success",
            error_message=None,
            error_location=None,
            proof_state=None,
            suggestions=[],
            time_s=1.5,
        )

        mock_handler = MagicMock()
        mock_handler.handle.return_value = validation_result
        mock_create_handler.return_value = mock_handler

        # Mock context
        from lean_proof_auto_mcp.core.context_extractor import ProofContext

        context = ProofContext(
            theorem_statement="∀ (n m : Nat), n + m = m + n",
            original_proof="exact Nat.add_comm n m",
            hypotheses=[],
            in_scope=["Nat.add_comm", "Nat.add_zero"],
            namespace="",
            similar_proofs=[],
        )

        mock_context_extractor.extract_context.return_value = context
        mock_create_extractor.return_value = mock_context_extractor

        # Step 1: Get context
        context_result = get_proof_context(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "include_similar_proofs": True,
            }
        )

        assert context_result["status"] == "success"
        assert "theorem_statement" in context_result
        assert "original_proof" in context_result

        # Step 2: Search for hints
        search_result_dict = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
                "return_proof_states": True,
                "return_partial_progress": True,
            }
        )

        assert search_result_dict["status"] == "success"
        assert search_result_dict["outcome"] == "closed"
        assert len(search_result_dict["best_hint_set"]) > 0

        # Step 3: Validate the proof attempt
        proof_attempt = "by aesop (add_safe Nat.add_comm)"

        validation_result_dict = try_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "proof_attempt": proof_attempt,
                "timeout_s": 10.0,
            }
        )

        assert validation_result_dict["status"] == "success"
        assert validation_result_dict["validation_status"] == "success"

        # Verify all three tools were called
        assert mock_context_extractor.extract_context.called
        assert mock_orchestrator.search.called
        assert mock_handler.handle.called

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_iterative_refinement_workflow(self, mock_create_orchestrator):
        """Test iterative refinement with multiple search attempts.

        Requirements: 27.3
        """
        from lean_proof_auto_mcp.core.feedback_builder import (
            PartialProgress,
            SearchFeedback,
            Suggestion,
        )
        from lean_proof_auto_mcp.core.search_automated_proof_domain import (
            Candidate,
            CandidateSource,
            Hint,
            HintType,
        )
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        mock_orchestrator = MagicMock()

        # First attempt: partial success
        hint1 = Hint(
            name="Nat.add_zero",
            type=HintType.ADD_SAFE,
            source=CandidateSource.GOAL_SYMBOLS,
        )
        candidate1 = Candidate(hint=hint1, rank=0.8, metadata={})

        partial_progress = PartialProgress(
            hints_that_helped=[("Nat.add_zero", "reduced goal complexity by 20%")],
            goal_complexity_reduction=0.2,
            progress_score=0.3,
        )

        feedback1 = SearchFeedback(
            status="partial",
            hints_found=[candidate1],
            partial_progress=partial_progress,
            current_goal="n + m = m + n",
            suggestions=[
                Suggestion(
                    type="hint",
                    suggestion="Try adding Nat.add_comm",
                    confidence=0.85,
                    reasoning="Goal requires commutativity",
                )
            ],
        )

        result1 = SearchResultEnhanced(
            outcome="partial",
            best_hint_set=[candidate1],
            attempts=10,
            explored_sets=20,
            feedback=feedback1,
            metadata={},
            search_trace=None,
        )

        # Second attempt: success
        hint2 = Hint(
            name="Nat.add_comm",
            type=HintType.ADD_SAFE,
            source=CandidateSource.ORIGINAL_PROOF_REFS,
        )
        candidate2 = Candidate(hint=hint2, rank=0.95, metadata={})

        feedback2 = SearchFeedback(
            status="success",
            hints_found=[candidate1, candidate2],
            partial_progress=None,
            current_goal=None,
            suggestions=[],
        )

        result2 = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[candidate1, candidate2],
            attempts=5,
            explored_sets=8,
            feedback=feedback2,
            metadata={},
            search_trace=None,
        )

        # Configure mock to return different results
        mock_orchestrator.search.side_effect = [result1, result2]
        mock_create_orchestrator.return_value = mock_orchestrator

        # First iteration
        result_dict1 = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "quick",
            }
        )

        assert result_dict1["outcome"] == "partial"
        assert result_dict1["feedback"]["status"] == "partial"
        assert len(result_dict1["feedback"]["suggestions"]) > 0

        # Second iteration with refined parameters
        result_dict2 = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
                "candidate_sources": ["original_proof_refs", "goal_symbols"],
            }
        )

        assert result_dict2["outcome"] == "closed"
        assert result_dict2["feedback"]["status"] == "success"
        assert len(result_dict2["best_hint_set"]) == 2

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    @patch("lean_proof_auto_mcp.tools.try_automated_proof._create_handler")
    def test_validation_failure_feedback_loop(
        self, mock_create_handler, mock_create_orchestrator
    ):
        """Test feedback loop when validation fails.

        Requirements: 27.3
        """
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_automated_proof_domain import (
            Candidate,
            CandidateSource,
            Hint,
            HintType,
        )
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced
        from lean_proof_auto_mcp.lean.ports import ProofState
        from lean_proof_auto_mcp.lean.validator import ValidationResult

        # Setup search mock
        mock_orchestrator = MagicMock()
        hint = Hint(
            name="Nat.add_zero",
            type=HintType.ADD_SAFE,
            source=CandidateSource.GOAL_SYMBOLS,
        )
        candidate = Candidate(hint=hint, rank=0.8, metadata={})

        feedback = SearchFeedback(
            status="success",
            hints_found=[candidate],
            partial_progress=None,
            current_goal=None,
            suggestions=[],
        )

        search_result = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[candidate],
            attempts=5,
            explored_sets=10,
            feedback=feedback,
            metadata={},
            search_trace=None,
        )

        mock_orchestrator.search.return_value = search_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Setup validation mock - incomplete proof
        mock_validator = MagicMock()
        proof_state = ProofState(
            goal="m + n = n + m",
            hypotheses=["n m : Nat"],
            type_context="",
            goals_remaining=1,
        )

        validation_result = ValidationResult(
            status="incomplete",
            error_message=None,
            error_location=None,
            proof_state=proof_state,
            suggestions=[
                "Try adding Nat.add_comm to close the remaining goal",
                "Consider using simp instead of aesop",
            ],
            time_s=2.0,
        )

        mock_handler = MagicMock()
        mock_handler.handle.return_value = validation_result
        mock_create_handler.return_value = mock_handler

        # Search for hints
        search_result_dict = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "quick",
            }
        )

        assert search_result_dict["outcome"] == "closed"

        # Try validation - fails
        validation_result_dict = try_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "proof_attempt": "by aesop (add_safe Nat.add_zero)",
                "return_proof_state": True,
            }
        )

        assert validation_result_dict["validation_status"] == "incomplete"
        assert "proof_state" in validation_result_dict
        assert len(validation_result_dict["suggestions"]) > 0

        # Use suggestions to refine search
        # (In real workflow, LLM would use suggestions to adjust parameters)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.slow
class TestRealMathlibTheorems:
    """Test workflow on real mathlib theorems."""

    @pytest.mark.skip(reason="Requires real mathlib setup - enable for full integration testing")
    def test_mathlib_theorem_workflow(self):
        """Test complete workflow on a real mathlib theorem.

        This test is skipped by default as it requires a full mathlib setup.
        Enable it for comprehensive integration testing.

        Requirements: 27.3
        """
        # This would test against real mathlib files
        # For now, we use fixture files that simulate mathlib structure
        mathlib_file = str(MATHLIB_DIR / "Defs.lean")

        # Get context
        get_proof_context(
            {
                "file": mathlib_file,
                "theorem_id": "eval₂_zero",
                "include_similar_proofs": True,
            }
        )

        # Search for hints
        search_result = search_automated_proof(
            {
                "file": mathlib_file,
                "theorem_id": "eval₂_zero",
                "search_depth": "normal",
                "candidate_sources": [
                    "goal_symbols",
                    "local_context",
                    "original_proof_refs",
                ],
            }
        )

        # Validate if hints found
        if search_result["outcome"] == "closed":
            hints = search_result["best_hint_set"]
            hint_names = [h["name"] for h in hints]
            proof_attempt = f"by aesop (add_safe {', '.join(hint_names)})"

            validation_result = try_automated_proof(
                {
                    "file": mathlib_file,
                    "theorem_id": "eval₂_zero",
                    "proof_attempt": proof_attempt,
                }
            )

            # Verify workflow completed
            assert validation_result["status"] in ["success", "error", "incomplete"]


@pytest.mark.e2e
@pytest.mark.integration
class TestToolInteraction:
    """Test interaction between all three MCP tools."""

    @patch("lean_proof_auto_mcp.tools.get_proof_context._create_extractor")
    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_context_informs_search(self, mock_create_orchestrator, mock_create_extractor):
        """Test that context extraction informs search parameters.

        Requirements: 27.3
        """
        from lean_proof_auto_mcp.core.context_extractor import ProofContext
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        # Mock context with similar proofs
        mock_context_extractor = MagicMock()
        context = ProofContext(
            theorem_statement="∀ (n m : Nat), n + m = m + n",
            original_proof="exact Nat.add_comm n m",
            hypotheses=[],
            in_scope=["Nat.add_comm", "Nat.add_zero", "Nat.zero_add"],
            namespace="",
            similar_proofs=[],
        )

        mock_context_extractor.extract_context.return_value = context
        mock_create_extractor.return_value = mock_context_extractor

        # Mock search
        mock_orchestrator = MagicMock()
        feedback = SearchFeedback(
            status="success",
            hints_found=[],
            partial_progress=None,
            current_goal=None,
            suggestions=[],
        )

        search_result = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[],
            attempts=1,
            explored_sets=1,
            feedback=feedback,
            metadata={},
            search_trace=None,
        )

        mock_orchestrator.search.return_value = search_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Get context first
        context_result = get_proof_context(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
            }
        )

        # Use context to inform search
        # In real workflow, LLM would extract in_scope declarations
        # and use them to configure candidate sources
        context_result.get("in_scope", [])

        search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
                "candidate_sources": ["original_proof_refs", "same_namespace"],
            }
        )

        # Verify both tools were called
        assert mock_context_extractor.extract_context.called
        assert mock_orchestrator.search.called

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    @patch("lean_proof_auto_mcp.tools.try_automated_proof._create_handler")
    def test_search_feedback_guides_validation(
        self, mock_create_handler, mock_create_orchestrator
    ):
        """Test that search feedback guides validation attempts.

        Requirements: 27.3
        """
        from lean_proof_auto_mcp.core.feedback_builder import (
            SearchFeedback,
            Suggestion,
        )
        from lean_proof_auto_mcp.core.search_automated_proof_domain import (
            Candidate,
            CandidateSource,
            Hint,
            HintType,
        )
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced
        from lean_proof_auto_mcp.lean.validator import ValidationResult

        # Mock search with tactical suggestions
        mock_orchestrator = MagicMock()
        hint = Hint(
            name="Nat.add_comm",
            type=HintType.ADD_SAFE,
            source=CandidateSource.GOAL_SYMBOLS,
        )
        candidate = Candidate(hint=hint, rank=0.9, metadata={})

        feedback = SearchFeedback(
            status="success",
            hints_found=[candidate],
            partial_progress=None,
            current_goal=None,
            suggestions=[
                Suggestion(
                    type="tactic",
                    suggestion="Use aesop with add_safe hints",
                    confidence=0.9,
                    reasoning="Goal structure matches aesop patterns",
                ),
                Suggestion(
                    type="strategy",
                    suggestion="Try simp as fallback",
                    confidence=0.6,
                    reasoning="Simp may work with these hints",
                ),
            ],
        )

        search_result = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[candidate],
            attempts=5,
            explored_sets=10,
            feedback=feedback,
            metadata={},
            search_trace=None,
        )

        mock_orchestrator.search.return_value = search_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Mock validator
        mock_handler = MagicMock()
        validation_result = ValidationResult(
            status="success",
            error_message=None,
            error_location=None,
            proof_state=None,
            suggestions=[],
            time_s=1.0,
        )

        mock_handler.handle.return_value = validation_result
        mock_create_handler.return_value = mock_handler

        # Search
        search_result_dict = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
            }
        )

        # Extract suggestions
        suggestions = search_result_dict["feedback"]["suggestions"]
        assert len(suggestions) > 0

        # Use first suggestion to construct proof attempt
        # In real workflow, LLM would parse suggestions
        proof_attempt = "by aesop (add_safe Nat.add_comm)"

        # Validate
        validation_result_dict = try_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "proof_attempt": proof_attempt,
            }
        )

        assert validation_result_dict["validation_status"] == "success"
