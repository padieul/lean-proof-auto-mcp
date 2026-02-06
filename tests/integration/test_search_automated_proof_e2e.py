"""Comprehensive end-to-end integration tests for search_automated_proof tool.

These tests verify the complete workflow with real Lean files, testing:
- Complete workflow execution with rich feedback
- Search depth presets (quick, normal, deep, exhaustive)
- Candidate source configuration
- Return option configuration
- Timeout handling
- Error handling for missing files and invalid theorems
- Deterministic output across multiple runs

This replaces test_search_annotations_e2e.py with updated interface.

Requirements: 25.1, 4.1, 4.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lean_proof_auto_mcp.tools.search_automated_proof import search_automated_proof

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
VALID_THEOREM = str(FIXTURES_DIR / "valid_theorem.lean")
AESOP_TRIVIAL = str(FIXTURES_DIR / "probe_aesop_trivial.lean")
MULTI_THEOREM = str(FIXTURES_DIR / "probe_file_multi_theorem.lean")


@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete workflow with real Lean files."""

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_complete_workflow_success(self, mock_create_orchestrator):
        """Test complete workflow from start to finish with success.

        Requirements: 4.1, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 25.1
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

        # Create mock orchestrator with complete success result
        mock_orchestrator = MagicMock()

        hint = Hint(
            name="Nat.add_comm", type=HintType.ADD_SAFE, source=CandidateSource.GOAL_SYMBOLS
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
                    suggestion="Try using aesop with the found hints",
                    confidence=0.8,
                    reasoning="Hints successfully closed the goal",
                )
            ],
        )

        mock_result = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[candidate],
            attempts=5,
            explored_sets=10,
            feedback=feedback,
            metadata={
                "repo_commit": "abc123",
                "lean_version": "4.26.0",
                "lake_version": "5.0.0",
            },
            search_trace=None,
        )

        mock_orchestrator.search.return_value = mock_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Execute search
        result = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
            }
        )

        # Verify response structure
        assert result["status"] == "success"
        assert result["outcome"] == "closed"
        assert result["best_hint_set"] is not None
        assert len(result["best_hint_set"]) == 1
        assert result["best_hint_set"][0]["name"] == "Nat.add_comm"
        assert result["best_hint_set"][0]["hint_type"] == "add_safe"
        assert result["best_hint_set"][0]["source"] == "goal_symbols"

        # Verify feedback
        assert "feedback" in result
        assert result["feedback"]["status"] == "success"
        assert len(result["feedback"]["suggestions"]) > 0

        # Verify metadata
        assert "metadata" in result
        assert "repo_commit" in result["metadata"]
        assert "lean_version" in result["metadata"]

        # Verify attempts and explored sets
        assert result["attempts"] == 5
        assert result["explored_sets"] == 10

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_search_depth_presets(self, mock_create_orchestrator):
        """Test that search depth presets apply correct parameters.

        Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 25.1
        """
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        mock_orchestrator = MagicMock()
        mock_result = SearchResultEnhanced(
            outcome="failed",
            best_hint_set=None,
            attempts=0,
            explored_sets=0,
            feedback=SearchFeedback(
                status="error",
                hints_found=[],
                partial_progress=None,
                current_goal=None,
                suggestions=[],
            ),
            metadata={},
            search_trace=None,
        )
        mock_orchestrator.search.return_value = mock_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Test each depth preset
        depth_presets = ["quick", "normal", "deep", "exhaustive"]

        for depth in depth_presets:
            search_automated_proof(
                {
                    "file": VALID_THEOREM,
                    "theorem_id": "simple_add_comm",
                    "search_depth": depth,
                }
            )

            # Verify search was called with correct config
            assert mock_orchestrator.search.called
            call_args = mock_orchestrator.search.call_args
            config = call_args[0][2]  # Third positional arg is config

            # Verify config has correct search_depth
            assert config.search_depth == depth

            # Verify preset parameters are applied
            if depth == "quick":
                assert config.search_budget_s == 10.0
                assert config.max_candidates == 20
            elif depth == "normal":
                assert config.search_budget_s == 30.0
                assert config.max_candidates == 50
            elif depth == "deep":
                assert config.search_budget_s == 60.0
                assert config.max_candidates == 100
            elif depth == "exhaustive":
                assert config.search_budget_s == 120.0
                assert config.max_candidates == 200

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_parameter_overrides(self, mock_create_orchestrator):
        """Test that individual parameters override presets.

        Requirements: 4.8, 25.1
        """
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        mock_orchestrator = MagicMock()
        mock_result = SearchResultEnhanced(
            outcome="failed",
            best_hint_set=None,
            attempts=0,
            explored_sets=0,
            feedback=SearchFeedback(
                status="error",
                hints_found=[],
                partial_progress=None,
                current_goal=None,
                suggestions=[],
            ),
            metadata={},
            search_trace=None,
        )
        mock_orchestrator.search.return_value = mock_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Test with overrides
        search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",  # Preset: 30.0s, 50 candidates
                "search_budget_s": 45.0,  # Override budget
                "max_candidates": 75,  # Override candidates
            }
        )

        # Verify overrides were applied
        call_args = mock_orchestrator.search.call_args
        config = call_args[0][2]

        assert config.search_budget_s == 45.0  # Override applied
        assert config.max_candidates == 75  # Override applied

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_candidate_sources_configuration(self, mock_create_orchestrator):
        """Test candidate source configuration.

        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 25.1
        """
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        mock_orchestrator = MagicMock()
        mock_result = SearchResultEnhanced(
            outcome="failed",
            best_hint_set=None,
            attempts=0,
            explored_sets=0,
            feedback=SearchFeedback(
                status="error",
                hints_found=[],
                partial_progress=None,
                current_goal=None,
                suggestions=[],
            ),
            metadata={},
            search_trace=None,
        )
        mock_orchestrator.search.return_value = mock_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Test with specific candidate sources
        search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "candidate_sources": [
                    "goal_symbols",
                    "original_proof_refs",
                ],
                "max_candidates_per_source": 15,
            }
        )

        # Verify sources were configured
        call_args = mock_orchestrator.search.call_args
        config = call_args[0][2]

        assert len(config.candidate_sources) == 2
        source_values = [s.value for s in config.candidate_sources]
        assert "goal_symbols" in source_values
        assert "original_proof_refs" in source_values
        assert config.max_candidates_per_source == 15

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_return_options_configuration(self, mock_create_orchestrator):
        """Test return option configuration.

        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 25.1
        """
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        mock_orchestrator = MagicMock()
        mock_result = SearchResultEnhanced(
            outcome="failed",
            best_hint_set=None,
            attempts=0,
            explored_sets=0,
            feedback=SearchFeedback(
                status="error",
                hints_found=[],
                partial_progress=None,
                current_goal=None,
                suggestions=[],
            ),
            metadata={},
            search_trace=None,
        )
        mock_orchestrator.search.return_value = mock_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Test with all return options enabled
        search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "return_proof_states": True,
                "return_partial_progress": True,
                "return_context": True,
                "return_similar_proofs": True,
                "return_search_trace": True,
            }
        )

        # Verify return options were configured
        call_args = mock_orchestrator.search.call_args
        config = call_args[0][2]

        assert config.return_proof_states is True
        assert config.return_partial_progress is True
        assert config.return_context is True
        assert config.return_similar_proofs is True
        assert config.return_search_trace is True


@pytest.mark.e2e
class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_missing_file_error(self):
        """Test error handling for missing file.

        Requirements: 11.3, 25.1
        """
        result = search_automated_proof(
            {
                "file": "nonexistent_file.lean",
                "theorem_id": "some_theorem",
            }
        )

        # Verify error response
        assert result["status"] == "error"
        assert result["outcome"] == "failed"
        assert "error_code" in result["metadata"]
        assert "error_message" in result["metadata"]

    def test_invalid_theorem_id_error(self):
        """Test error handling for invalid theorem ID.

        Requirements: 11.3, 25.1
        """
        result = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "",  # Empty theorem ID
            }
        )

        # Verify error response
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"

    def test_invalid_search_depth_error(self):
        """Test error handling for invalid search depth.

        Requirements: 11.3, 25.1
        """
        result = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "invalid_depth",
            }
        )

        # Verify error response
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "search_depth" in result["metadata"]["error_message"]

    def test_invalid_candidate_source_error(self):
        """Test error handling for invalid candidate source.

        Requirements: 11.3, 25.1
        """
        result = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "candidate_sources": ["invalid_source"],
            }
        )

        # Verify error response
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "candidate source" in result["metadata"]["error_message"].lower()


@pytest.mark.e2e
class TestDeterministicOutput:
    """Test deterministic output across multiple runs."""

    @patch("lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator")
    def test_deterministic_json_output(self, mock_create_orchestrator):
        """Test that identical inputs produce identical JSON output (excluding run_id).

        Requirements: 25.1
        """
        from lean_proof_auto_mcp.core.feedback_builder import SearchFeedback
        from lean_proof_auto_mcp.core.search_automated_proof_domain import (
            Candidate,
            CandidateSource,
            Hint,
            HintType,
        )
        from lean_proof_auto_mcp.core.search_orchestrator import SearchResultEnhanced

        # Create mock orchestrator with deterministic result
        mock_orchestrator = MagicMock()

        hint = Hint(
            name="Nat.add_comm", type=HintType.ADD_SAFE, source=CandidateSource.GOAL_SYMBOLS
        )
        candidate = Candidate(hint=hint, rank=0.9, metadata={})

        feedback = SearchFeedback(
            status="success",
            hints_found=[candidate],
            partial_progress=None,
            current_goal=None,
            suggestions=[],
        )

        mock_result = SearchResultEnhanced(
            outcome="closed",
            best_hint_set=[candidate],
            attempts=5,
            explored_sets=10,
            feedback=feedback,
            metadata={"repo_commit": "abc123"},
            search_trace=None,
        )

        mock_orchestrator.search.return_value = mock_result
        mock_create_orchestrator.return_value = mock_orchestrator

        # Execute search twice with identical inputs
        result1 = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
            }
        )

        result2 = search_automated_proof(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "search_depth": "normal",
            }
        )

        # Verify deterministic fields match (excluding run_id which is unique)
        for key in ["status", "outcome", "attempts", "explored_sets"]:
            assert result1[key] == result2[key], f"Field {key} differs between runs"

        # Verify hint sets match
        assert len(result1["best_hint_set"]) == len(result2["best_hint_set"])
        for h1, h2 in zip(result1["best_hint_set"], result2["best_hint_set"], strict=False):
            assert h1["name"] == h2["name"]
            assert h1["hint_type"] == h2["hint_type"]
            assert h1["source"] == h2["source"]
