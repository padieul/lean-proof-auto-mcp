"""
Property-based tests for Candidate Source Extraction Accuracy.

These tests verify Property 5: Candidate Source Extraction Accuracy using
LeanInteract-based extraction methods.

Feature: iterative-orchestration-enhancements
Property 5: Candidate Source Extraction Accuracy

Requirements: 5.2, 5.3, 5.4, 5.5, 5.7
"""

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.candidate_generator import CandidateGenerator
from lean_proof_auto_mcp.core.indexer import build_index
from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    CandidateConfig,
    CandidateSource,
)
from lean_proof_auto_mcp.core.source import SourceText
from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range

# ============================================================================
# Mock LeanInteractQuerier for Testing
# ============================================================================


class MockLeanInteractQuerier:
    """Mock LeanInteractQuerier for testing candidate generation."""

    def __init__(self, declarations: list[Declaration], proof_references: dict[str, list[str]]):
        """
        Initialize mock querier.

        Args:
            declarations: List of declarations to return
            proof_references: Map of theorem_id to list of proof references
        """
        self.declarations = declarations
        self.proof_references = proof_references

    def extract_declarations(self, file_path: str) -> list[Declaration]:
        """Return mock declarations."""
        return self.declarations

    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        """Return mock proof references."""
        return self.proof_references.get(theorem_id, [])

    def get_theorem_context(self, file_path: str, theorem_id: str):
        """Not used in candidate generation tests."""
        raise NotImplementedError("get_theorem_context not needed for candidate generation tests")


# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_candidate_config(draw):
    """Generate valid CandidateConfig instances."""
    # Select at least one source
    all_sources = list(CandidateSource)
    num_sources = draw(st.integers(min_value=1, max_value=len(all_sources)))
    sources = draw(
        st.lists(
            st.sampled_from(all_sources), min_size=num_sources, max_size=num_sources, unique=True
        )
    )

    max_candidates = draw(st.integers(min_value=1, max_value=50))
    allow_simp = draw(st.booleans())
    allow_unfold = draw(st.booleans())

    return CandidateConfig(
        sources=sources,
        max_candidates_per_source=max_candidates,
        allow_simp_hints=allow_simp,
        allow_unfold_hints=allow_unfold,
    )


# ============================================================================
# Property 5: Candidate Source Extraction Accuracy
# ============================================================================


@given(config=valid_candidate_config())
@settings(max_examples=100)
def test_property_5_goal_symbols_extraction(config):
    """
    Feature: iterative-orchestration-enhancements, Property 5: Candidate Source Extraction Accuracy

    For any enabled candidate source (goal_symbols), the system SHALL extract
    candidates using LeanInteract-based methods and respect the
    max_candidates_per_source limit.

    Validates: Requirements 5.2, 5.7
    """
    # Create test theorem with goal symbols
    theorem_text = """
namespace Test

theorem test_theorem (n : Nat) : Nat.add n 0 = n := by
  rfl

end Test
"""

    source = SourceText(path="test.lean", text=theorem_text)
    index = build_index(source)

    # Create mock declarations
    mock_declarations = [
        Declaration(
            name="test_theorem",
            full_name="Test.test_theorem",
            type="(n : Nat) → Nat.add n 0 = n",
            value=None,
            attributes=[],
            range=Range(start_line=3, start_col=0, end_line=4, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="add",
            full_name="Nat.add",
            type="Nat → Nat → Nat",
            value=None,
            attributes=[],
            range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
            namespace="Nat",
        ),
    ]

    # Create mock querier
    querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

    # Create generator with mock querier
    if index.decls:
        theorem_decl = index.decls[0]
        generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

        # Execute: Generate candidates from goal_symbols source
        if CandidateSource.GOAL_SYMBOLS in config.sources:
            candidates = generator.generate(theorem_decl, [CandidateSource.GOAL_SYMBOLS], config)

            # Verify: Should return a list
            assert isinstance(candidates, list)

            # Verify: Should respect max_candidates_per_source limit
            assert len(candidates) <= config.max_candidates_per_source

            # Verify: All candidates should be from GOAL_SYMBOLS source
            for candidate in candidates:
                assert candidate.hint.source == CandidateSource.GOAL_SYMBOLS


@given(config=valid_candidate_config())
@settings(max_examples=100)
def test_property_5_same_namespace_extraction(config):
    """
    Feature: iterative-orchestration-enhancements, Property 5: Candidate Source Extraction Accuracy

    For any enabled candidate source (same_namespace), the system SHALL extract
    candidates using LeanInteract-based methods and respect the
    max_candidates_per_source limit.

    Validates: Requirements 5.4, 5.7
    """
    # Create test theorem with same namespace declarations
    theorem_text = """
namespace Test

theorem helper1 : True := trivial
theorem helper2 : True := trivial

theorem test_theorem : True := trivial

end Test
"""

    source = SourceText(path="test.lean", text=theorem_text)
    index = build_index(source)

    # Create mock declarations
    mock_declarations = [
        Declaration(
            name="test_theorem",
            full_name="Test.test_theorem",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=6, start_col=0, end_line=6, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="helper1",
            full_name="Test.helper1",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=3, start_col=0, end_line=3, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="helper2",
            full_name="Test.helper2",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=4, start_col=0, end_line=4, end_col=0),
            namespace="Test",
        ),
    ]

    # Create mock querier
    querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

    # Create generator with mock querier
    if index.decls:
        theorem_decl = index.decls[-1]  # Get test_theorem
        generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

        # Execute: Generate candidates from same_namespace source
        if CandidateSource.SAME_NAMESPACE in config.sources:
            candidates = generator.generate(theorem_decl, [CandidateSource.SAME_NAMESPACE], config)

            # Verify: Should return a list
            assert isinstance(candidates, list)

            # Verify: Should respect max_candidates_per_source limit
            assert len(candidates) <= config.max_candidates_per_source

            # Verify: All candidates should be from SAME_NAMESPACE source
            for candidate in candidates:
                assert candidate.hint.source == CandidateSource.SAME_NAMESPACE


@given(config=valid_candidate_config())
@settings(max_examples=100)
def test_property_5_original_proof_refs_extraction(config):
    """
    Feature: iterative-orchestration-enhancements, Property 5: Candidate Source Extraction Accuracy

    For any enabled candidate source (original_proof_refs), the system SHALL extract
    candidates using LeanInteract value.constants and respect the
    max_candidates_per_source limit.

    Validates: Requirements 5.5, 5.7, 2.1, 2.2, 2.3
    """
    # Create test theorem with proof references
    theorem_text = """
namespace Test

theorem test_theorem (n : Nat) : Nat.add n 0 = n := by
  apply Nat.add_zero

end Test
"""

    source = SourceText(path="test.lean", text=theorem_text)
    index = build_index(source)

    # Create mock declarations
    mock_declarations = [
        Declaration(
            name="test_theorem",
            full_name="Test.test_theorem",
            type="(n : Nat) → Nat.add n 0 = n",
            value=DeclValue(
                pp="apply Nat.add_zero",
                constants=["Nat.add_zero"],  # Primary source: value.constants
                range=Range(start_line=4, start_col=0, end_line=4, end_col=0),
            ),
            attributes=[],
            range=Range(start_line=3, start_col=0, end_line=4, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="add_zero",
            full_name="Nat.add_zero",
            type="∀ (n : Nat), Nat.add n 0 = n",
            value=None,
            attributes=["simp"],
            range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
            namespace="Nat",
        ),
    ]

    # Create mock querier with proof references
    querier = MockLeanInteractQuerier(
        declarations=mock_declarations,
        proof_references={"Test.test_theorem": ["Nat.add_zero"]},
    )

    # Create generator with mock querier
    if index.decls:
        theorem_decl = index.decls[0]
        generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

        # Execute: Generate candidates from original_proof_refs source
        if CandidateSource.ORIGINAL_PROOF_REFS in config.sources:
            candidates = generator.generate(
                theorem_decl, [CandidateSource.ORIGINAL_PROOF_REFS], config
            )

            # Verify: Should return a list
            assert isinstance(candidates, list)

            # Verify: Should respect max_candidates_per_source limit
            assert len(candidates) <= config.max_candidates_per_source

            # Verify: All candidates should be from ORIGINAL_PROOF_REFS source
            for candidate in candidates:
                assert candidate.hint.source == CandidateSource.ORIGINAL_PROOF_REFS

            # Verify: Should extract Nat.add_zero from proof references
            if candidates:
                candidate_names = {c.hint.name for c in candidates}
                assert "Nat.add_zero" in candidate_names


@given(config=valid_candidate_config())
@settings(max_examples=100)
def test_property_5_all_sources_respect_limits(config):
    """
    Feature: iterative-orchestration-enhancements, Property 5: Candidate Source Extraction Accuracy

    For ALL enabled candidate sources, the system SHALL respect the
    max_candidates_per_source limit for each source independently.

    Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.7
    """
    # Create comprehensive test theorem
    theorem_text = """
namespace Test

theorem helper1 : True := trivial
theorem helper2 : True := trivial
theorem helper3 : True := trivial

theorem test_theorem (n m : Nat) : Nat.add n m = Nat.add m n := by
  apply Nat.add_comm
  apply helper1
  apply helper2

end Test
"""

    source = SourceText(path="test.lean", text=theorem_text)
    index = build_index(source)

    # Create mock declarations
    mock_declarations = [
        Declaration(
            name="test_theorem",
            full_name="Test.test_theorem",
            type="(n m : Nat) → Nat.add n m = Nat.add m n",
            value=DeclValue(
                pp="apply Nat.add_comm; apply helper1; apply helper2",
                constants=["Nat.add_comm", "Test.helper1", "Test.helper2"],
                range=Range(start_line=8, start_col=0, end_line=10, end_col=0),
            ),
            attributes=[],
            range=Range(start_line=7, start_col=0, end_line=10, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="helper1",
            full_name="Test.helper1",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=3, start_col=0, end_line=3, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="helper2",
            full_name="Test.helper2",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=4, start_col=0, end_line=4, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="helper3",
            full_name="Test.helper3",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=5, start_col=0, end_line=5, end_col=0),
            namespace="Test",
        ),
        Declaration(
            name="add_comm",
            full_name="Nat.add_comm",
            type="∀ (n m : Nat), Nat.add n m = Nat.add m n",
            value=None,
            attributes=["simp"],
            range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
            namespace="Nat",
        ),
    ]

    # Create mock querier
    querier = MockLeanInteractQuerier(
        declarations=mock_declarations,
        proof_references={"Test.test_theorem": ["Nat.add_comm", "Test.helper1", "Test.helper2"]},
    )

    # Create generator with mock querier
    if index.decls:
        theorem_decl = index.decls[-1]  # Get test_theorem
        generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

        # Execute: Generate candidates from all configured sources
        candidates = generator.generate(theorem_decl, config.sources, config)

        # Verify: Should return a list
        assert isinstance(candidates, list)

        # Verify: For each source, count candidates and check limit
        for source_type in config.sources:
            source_candidates = [c for c in candidates if c.hint.source == source_type]

            # The number of candidates from this source should not exceed the limit
            assert len(source_candidates) <= config.max_candidates_per_source, (
                f"Source {source_type} has {len(source_candidates)} candidates, "
                f"exceeds limit {config.max_candidates_per_source}"
            )


@given(config=valid_candidate_config())
@settings(max_examples=100)
def test_property_5_leaninteract_based_extraction(config):
    """
    Feature: iterative-orchestration-enhancements, Property 5: Candidate Source Extraction Accuracy

    The system SHALL use LeanInteract-based methods for all candidate extraction,
    not regex-based parsing.

    Validates: Requirements 12.1, 12.2
    """
    # Create test theorem
    theorem_text = """
namespace Test

theorem test_theorem : True := trivial

end Test
"""

    source = SourceText(path="test.lean", text=theorem_text)
    index = build_index(source)

    # Create mock declarations
    mock_declarations = [
        Declaration(
            name="test_theorem",
            full_name="Test.test_theorem",
            type="True",
            value=None,
            attributes=[],
            range=Range(start_line=3, start_col=0, end_line=3, end_col=0),
            namespace="Test",
        ),
    ]

    # Create mock querier
    querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

    # Create generator with mock querier
    if index.decls:
        theorem_decl = index.decls[0]
        generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

        # Execute: Generate candidates
        try:
            candidates = generator.generate(theorem_decl, config.sources, config)

            # Verify: Should return a list without errors
            assert isinstance(candidates, list)

            # Verify: All candidates should have valid hint types
            for candidate in candidates:
                assert candidate.hint.type is not None

        except Exception as e:
            pytest.fail(f"LeanInteract-based extraction should not raise exceptions: {e}")
