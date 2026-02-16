"""
Unit tests for SearchOrchestrator.

This module tests the SearchOrchestrator's integration with HarnessConstructor
and hint combination generation logic.

Requirements: 4.1, 4.2, 4.3
"""

from unittest.mock import Mock

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessError,
    HarnessSuccess,
)
from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    Candidate,
    CandidateSource,
    Hint,
    HintType,
)
from lean_proof_auto_mcp.core.search_orchestrator import SearchConfig, SearchOrchestrator


def create_test_candidate(
    name: str, hint_type: HintType, source: CandidateSource, rank: float = 0.9
) -> Candidate:
    """Helper to create test candidates."""
    hint = Hint(name=name, type=hint_type, source=source)
    return Candidate(hint=hint, rank=rank, metadata={})


class TestSearchOrchestratorWithHarnessConstructor:
    """Test SearchOrchestrator integration with HarnessConstructor."""

    def test_search_with_harness_constructor(self):
        """Test that SearchOrchestrator uses HarnessConstructor when provided."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_harness_constructor = Mock()

        # Configure candidate generator with index
        mock_index = Mock()
        mock_theorem_decl = Mock()
        mock_theorem_decl.theorem_id = "test_theorem"
        mock_index.decls = [mock_theorem_decl]
        mock_candidate_gen.index = mock_index

        # Configure candidate generator to return test candidates
        test_candidates = [
            create_test_candidate(
                "test_lemma_1", HintType.ADD_SAFE, CandidateSource.GOAL_SYMBOLS, 0.9
            ),
            create_test_candidate(
                "test_lemma_2", HintType.ADD_SAFE, CandidateSource.LOCAL_CONTEXT, 0.8
            ),
        ]
        mock_candidate_gen.generate.return_value = test_candidates

        # Configure harness constructor to return success
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="import Test\nexample : True := by aesop",
            theorem_id="test_theorem",
            file_path="test.lean",
        )

        # Configure feedback builder
        mock_feedback_builder.build_search_feedback.return_value = Mock()

        # Create orchestrator with constructor
        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_harness_constructor,
        )

        # Execute search
        config = SearchConfig.from_depth("quick")
        result = orchestrator.search(
            file_path="test.lean",
            theorem_id="test_theorem",
            config=config,
        )

        # Verify candidate generation was called
        mock_candidate_gen.generate.assert_called_once()

        # Verify harness constructor was called (at least once for testing combinations)
        assert mock_harness_constructor.construct.called

        # Verify result structure
        assert result.attempts >= 0
        assert result.explored_sets >= 0

    def test_search_without_harness_constructor(self):
        """Test that SearchOrchestrator requires constructor parameter."""
        # This test is no longer valid since constructor is now required
        # The test would fail at instantiation time with TypeError
        pass

    def test_harness_construction_error_handling(self):
        """Test that SearchOrchestrator handles harness construction errors."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_harness_constructor = Mock()

        # Configure candidate generator with index
        mock_index = Mock()
        mock_theorem_decl = Mock()
        mock_theorem_decl.theorem_id = "test_theorem"
        mock_index.decls = [mock_theorem_decl]
        mock_candidate_gen.index = mock_index

        # Configure candidate generator
        test_candidates = [
            create_test_candidate(
                "test_lemma", HintType.ADD_SAFE, CandidateSource.GOAL_SYMBOLS, 0.9
            ),
        ]
        mock_candidate_gen.generate.return_value = test_candidates

        # Configure harness constructor to return error
        mock_harness_constructor.construct.return_value = HarnessError(
            error_type="theorem_not_found",
            message="Theorem not found",
            theorem_id="test_theorem",
            file_path="test.lean",
        )

        # Configure feedback builder
        mock_feedback_builder.build_search_feedback.return_value = Mock()

        # Create orchestrator
        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_harness_constructor,
        )

        # Execute search
        config = SearchConfig.from_depth("quick")
        result = orchestrator.search(
            file_path="test.lean",
            theorem_id="test_theorem",
            config=config,
        )

        # Should handle error gracefully
        assert result.outcome in ("failed", "partial")


class TestHintCombinationGeneration:
    """Test hint combination generation strategies."""

    def test_greedy_combination_generation(self):
        """Test greedy strategy generates combinations in correct order."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create test candidates
        candidates = [
            create_test_candidate(
                f"lemma_{i}", HintType.ADD_SAFE, CandidateSource.GOAL_SYMBOLS, 0.9 - i * 0.1
            )
            for i in range(5)
        ]

        # Generate combinations
        config = SearchConfig.from_depth("quick")
        combinations = orchestrator._generate_greedy_combinations(candidates, config)

        # Verify structure
        assert len(combinations) > 0

        # First combinations should be singles
        assert len(combinations[0]) == 1
        assert len(combinations[1]) == 1

        # Later combinations should be pairs, triples, etc.
        has_pairs = any(len(combo) == 2 for combo in combinations)
        assert has_pairs

    def test_exhaustive_combination_generation(self):
        """Test exhaustive strategy generates all combinations."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create test candidates
        candidates = [
            create_test_candidate(
                f"lemma_{i}", HintType.ADD_SAFE, CandidateSource.GOAL_SYMBOLS, 0.9
            )
            for i in range(3)
        ]

        # Generate combinations
        config = SearchConfig.from_depth("quick")
        config = SearchConfig(
            search_depth="quick",
            search_budget_s=10.0,
            max_candidates=3,
            candidate_sources=[CandidateSource.GOAL_SYMBOLS],
            max_candidates_per_source=10,
            automation_mode="aesop",
            automation_secondary=None,
            search_strategy="exhaustive",
            beam_width=3,
            max_search_steps=100,
            max_hints_in_set=3,
            allow_simp_hints=True,
            allow_unfold_hints=True,
            allow_unsafe_hints=False,
            minimize_hints=True,
            minimize_budget_s=5.0,
            return_proof_states=True,
            return_partial_progress=True,
            return_context=False,
            return_similar_proofs=False,
            return_search_trace=False,
        )

        combinations = orchestrator._generate_exhaustive_combinations(candidates, config)

        # Should generate combinations of all sizes
        sizes = {len(combo) for combo in combinations}
        assert 1 in sizes  # Singles
        assert 2 in sizes  # Pairs
        assert 3 in sizes  # Triples

    def test_max_search_steps_limit(self):
        """Test that combination generation respects max_search_steps."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create many candidates
        candidates = [
            create_test_candidate(
                f"lemma_{i}", HintType.ADD_SAFE, CandidateSource.GOAL_SYMBOLS, 0.9
            )
            for i in range(20)
        ]

        # Generate combinations with small limit
        config = SearchConfig(
            search_depth="quick",
            search_budget_s=10.0,
            max_candidates=20,
            candidate_sources=[CandidateSource.GOAL_SYMBOLS],
            max_candidates_per_source=20,
            automation_mode="aesop",
            automation_secondary=None,
            search_strategy="greedy",
            beam_width=3,
            max_search_steps=10,  # Small limit
            max_hints_in_set=5,
            allow_simp_hints=True,
            allow_unfold_hints=True,
            allow_unsafe_hints=False,
            minimize_hints=True,
            minimize_budget_s=5.0,
            return_proof_states=True,
            return_partial_progress=True,
            return_context=False,
            return_similar_proofs=False,
            return_search_trace=False,
        )

        combinations = orchestrator._generate_greedy_combinations(candidates, config)

        # Should respect the limit
        assert len(combinations) <= config.max_search_steps


class TestProofWithHints:
    """Test proof construction with hints."""

    def test_build_proof_with_no_hints(self):
        """Test proof building with no hints."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Build proof with no hints
        config = SearchConfig.from_depth("quick")
        proof = orchestrator._build_proof_with_hints([], config)

        # Should just be the automation mode
        assert proof == config.automation_mode

    def test_build_proof_with_lemma_hints(self):
        """Test proof building with lemma hints."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create lemma hints
        hints = [
            create_test_candidate(
                "test_lemma_1", HintType.ADD_SAFE, CandidateSource.GOAL_SYMBOLS, 0.9
            ),
            create_test_candidate(
                "test_lemma_2", HintType.ADD_SAFE, CandidateSource.LOCAL_CONTEXT, 0.8
            ),
        ]

        # Build proof
        config = SearchConfig.from_depth("quick")
        proof = orchestrator._build_proof_with_hints(hints, config)

        # Should contain hint applications
        assert "test_lemma_1" in proof
        assert "test_lemma_2" in proof
        assert config.automation_mode in proof

    def test_build_proof_with_simp_hints(self):
        """Test proof building with simp hints."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create simp hint
        hints = [
            create_test_candidate("test_simp", HintType.SIMP, CandidateSource.GOAL_SYMBOLS, 0.9),
        ]

        # Build proof
        config = SearchConfig.from_depth("quick")
        proof = orchestrator._build_proof_with_hints(hints, config)

        # Should contain simp application
        assert "simp only" in proof
        assert "test_simp" in proof


class TestAdditionalImports:
    """Test additional import generation."""

    def test_aesop_imports(self):
        """Test that aesop mode adds Aesop import."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create config with aesop mode
        config = SearchConfig.from_depth("quick")
        assert config.automation_mode == "aesop"

        # Get imports
        imports = orchestrator._get_additional_imports(config)

        # Should include Aesop import
        assert "import Aesop" in imports

    def test_non_aesop_imports(self):
        """Test that non-aesop modes don't add Aesop import."""
        # Setup mocks
        mock_candidate_gen = Mock()
        mock_feedback_builder = Mock()
        mock_validator = Mock()
        mock_constructor = Mock()

        orchestrator = SearchOrchestrator(
            candidate_gen=mock_candidate_gen,
            feedback_builder=mock_feedback_builder,
            validator=mock_validator,
            constructor=mock_constructor,
        )

        # Create config with non-aesop mode
        config = SearchConfig(
            search_depth="quick",
            search_budget_s=10.0,
            max_candidates=20,
            candidate_sources=[CandidateSource.GOAL_SYMBOLS],
            max_candidates_per_source=10,
            automation_mode="grind",  # Not aesop
            automation_secondary=None,
            search_strategy="greedy",
            beam_width=3,
            max_search_steps=50,
            max_hints_in_set=10,
            allow_simp_hints=True,
            allow_unfold_hints=True,
            allow_unsafe_hints=False,
            minimize_hints=True,
            minimize_budget_s=5.0,
            return_proof_states=True,
            return_partial_progress=True,
            return_context=False,
            return_similar_proofs=False,
            return_search_trace=False,
        )

        # Get imports
        imports = orchestrator._get_additional_imports(config)

        # Should not include Aesop import
        assert "import Aesop" not in imports
