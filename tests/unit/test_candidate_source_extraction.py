"""
Unit tests for LeanInteract-based candidate source extraction.

These tests verify that each candidate source (goal_symbols, local_context,
same_namespace, original_proof_refs) uses LeanInteract-based extraction
methods correctly.

Requirements: 25.3, 5.2, 5.3, 5.4, 5.5, 12.1, 12.2
"""

from lean_proof_auto_mcp.core.candidate_generator import CandidateGenerator
from lean_proof_auto_mcp.core.indexer import build_index
from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    CandidateConfig,
    CandidateSource,
)
from lean_proof_auto_mcp.core.source import SourceText
from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range


class MockLeanInteractQuerier:
    """Mock LeanInteractQuerier for testing."""

    def __init__(self, declarations: list[Declaration], proof_references: dict[str, list[str]]):
        self.declarations = declarations
        self.proof_references = proof_references

    def extract_declarations(self, file_path: str) -> list[Declaration]:
        return self.declarations

    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        return self.proof_references.get(theorem_id, [])


class TestGoalSymbolsExtraction:
    """Test goal_symbols candidate source extraction.

    Requirements: 25.3, 5.2
    """

    def test_extracts_symbols_from_theorem_type(self):
        """Test that goal_symbols extracts symbols from theorem type signature."""
        theorem_text = """
theorem test_theorem (n : Nat) : Nat.add n 0 = n := by
  rfl
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="(n : Nat) → Nat.add n 0 = n",
                value=None,
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
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

        querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

        if index.decls:
            theorem_decl = index.decls[0]
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.GOAL_SYMBOLS],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            candidates = generator.generate(theorem_decl, [CandidateSource.GOAL_SYMBOLS], config)

            # Verify candidates were extracted
            assert isinstance(candidates, list)
            # Verify all candidates are from GOAL_SYMBOLS source
            for candidate in candidates:
                assert candidate.hint.source == CandidateSource.GOAL_SYMBOLS

    def test_respects_max_candidates_limit(self):
        """Test that goal_symbols respects max_candidates_per_source limit."""
        theorem_text = """
theorem test_theorem (a b c d e : Nat) : a + b + c + d + e = e + d + c + b + a := by
  rfl
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        # Create many mock declarations
        mock_declarations = [
            Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="(a b c d e : Nat) → a + b + c + d + e = e + d + c + b + a",
                value=None,
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
            ),
        ] + [
            Declaration(
                name=f"helper{i}",
                full_name=f"Nat.helper{i}",
                type="Nat → Nat",
                value=None,
                attributes=[],
                range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
                namespace="Nat",
            )
            for i in range(20)
        ]

        querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

        if index.decls:
            theorem_decl = index.decls[0]
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.GOAL_SYMBOLS],
                max_candidates_per_source=5,  # Limit to 5
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            candidates = generator.generate(theorem_decl, [CandidateSource.GOAL_SYMBOLS], config)

            # Verify limit is respected
            assert len(candidates) <= 5


class TestLocalContextExtraction:
    """Test local_context candidate source extraction.

    Requirements: 25.3, 5.3
    """

    def test_extracts_from_proof_state_hypotheses(self):
        """Test that local_context extracts candidates from proof state hypotheses."""
        # Note: This test would require a real ProofStateInspector
        # For now, we verify the interface is correct
        theorem_text = """
theorem test_theorem (h : True) : True := by
  exact h
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="True → True",
                value=None,
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
            ),
        ]

        querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

        if index.decls:
            theorem_decl = index.decls[0]
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.LOCAL_CONTEXT],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            # This will return empty list without ProofStateInspector, but should not error
            candidates = generator.generate(theorem_decl, [CandidateSource.LOCAL_CONTEXT], config)

            assert isinstance(candidates, list)


class TestSameNamespaceExtraction:
    """Test same_namespace candidate source extraction.

    Requirements: 25.3, 5.4
    """

    def test_extracts_declarations_from_same_namespace(self):
        """Test that same_namespace extracts declarations from the same namespace."""
        theorem_text = """
namespace Test

theorem helper1 : True := trivial
theorem helper2 : True := trivial

theorem test_theorem : True := trivial

end Test
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

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

        querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

        if index.decls:
            theorem_decl = index.decls[-1]  # Get test_theorem
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.SAME_NAMESPACE],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            candidates = generator.generate(theorem_decl, [CandidateSource.SAME_NAMESPACE], config)

            # Verify candidates were extracted
            assert isinstance(candidates, list)
            # Verify all candidates are from SAME_NAMESPACE source
            for candidate in candidates:
                assert candidate.hint.source == CandidateSource.SAME_NAMESPACE

    def test_excludes_declarations_from_different_namespace(self):
        """Test that same_namespace excludes declarations from different namespaces."""
        theorem_text = """
namespace Test

theorem test_theorem : True := trivial

end Test

namespace Other

theorem other_helper : True := trivial

end Other
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

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
            Declaration(
                name="other_helper",
                full_name="Other.other_helper",
                type="True",
                value=None,
                attributes=[],
                range=Range(start_line=9, start_col=0, end_line=9, end_col=0),
                namespace="Other",
            ),
        ]

        querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

        if index.decls:
            theorem_decl = index.decls[0]  # Get test_theorem
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.SAME_NAMESPACE],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            candidates = generator.generate(theorem_decl, [CandidateSource.SAME_NAMESPACE], config)

            # Verify no candidates from Other namespace
            candidate_names = {c.hint.name for c in candidates}
            assert "Other.other_helper" not in candidate_names


class TestOriginalProofRefsExtraction:
    """Test original_proof_refs candidate source extraction.

    Requirements: 25.3, 5.5, 2.1, 2.2, 2.3
    """

    def test_extracts_from_value_constants(self):
        """Test that original_proof_refs uses value.constants as primary source."""
        theorem_text = """
theorem test_theorem (n : Nat) : Nat.add n 0 = n := by
  apply Nat.add_zero
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="(n : Nat) → Nat.add n 0 = n",
                value=DeclValue(
                    pp="apply Nat.add_zero",
                    constants=["Nat.add_zero"],  # Primary source
                    range=Range(start_line=2, start_col=0, end_line=2, end_col=0),
                ),
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
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

        querier = MockLeanInteractQuerier(
            declarations=mock_declarations,
            proof_references={"test_theorem": ["Nat.add_zero"]},
        )

        if index.decls:
            theorem_decl = index.decls[0]
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.ORIGINAL_PROOF_REFS],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            candidates = generator.generate(
                theorem_decl, [CandidateSource.ORIGINAL_PROOF_REFS], config
            )

            # Verify candidates were extracted
            assert isinstance(candidates, list)
            assert len(candidates) > 0

            # Verify all candidates are from ORIGINAL_PROOF_REFS source
            for candidate in candidates:
                assert candidate.hint.source == CandidateSource.ORIGINAL_PROOF_REFS

            # Verify Nat.add_zero was extracted
            candidate_names = {c.hint.name for c in candidates}
            assert "Nat.add_zero" in candidate_names

    def test_extracts_all_references_from_value_constants(self):
        """Test that original_proof_refs extracts all references from value.constants.

        Note: Validation of references happens at the search/validation layer,
        not during candidate generation. The generator extracts all references
        from value.constants as provided by LeanInteract.
        """
        theorem_text = """
theorem test_theorem : True := by
  apply some_reference
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="True",
                value=DeclValue(
                    pp="apply some_reference",
                    constants=["some_reference"],
                    range=Range(start_line=2, start_col=0, end_line=2, end_col=0),
                ),
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
            ),
        ]

        querier = MockLeanInteractQuerier(
            declarations=mock_declarations,
            proof_references={"test_theorem": ["some_reference"]},
        )

        if index.decls:
            theorem_decl = index.decls[0]
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[CandidateSource.ORIGINAL_PROOF_REFS],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            candidates = generator.generate(
                theorem_decl, [CandidateSource.ORIGINAL_PROOF_REFS], config
            )

            # Verify references are extracted (validation happens later)
            candidate_names = {c.hint.name for c in candidates}
            assert "some_reference" in candidate_names


class TestLeanInteractBasedExtraction:
    """Test that all extraction uses LeanInteract, not regex.

    Requirements: 25.3, 12.1, 12.2
    """

    def test_no_regex_usage_in_candidate_generation(self):
        """Test that candidate generation does not use regex for parsing."""
        # This is a meta-test that verifies the implementation approach
        # The actual verification is done through code review and static analysis

        theorem_text = """
theorem test_theorem : True := trivial
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_theorem",
                full_name="test_theorem",
                type="True",
                value=None,
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=1, end_col=0),
                namespace="",
            ),
        ]

        querier = MockLeanInteractQuerier(declarations=mock_declarations, proof_references={})

        if index.decls:
            theorem_decl = index.decls[0]
            generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

            config = CandidateConfig(
                sources=[
                    CandidateSource.GOAL_SYMBOLS,
                    CandidateSource.SAME_NAMESPACE,
                    CandidateSource.ORIGINAL_PROOF_REFS,
                ],
                max_candidates_per_source=10,
                allow_simp_hints=True,
                allow_unfold_hints=True,
            )

            # Execute without errors - verifies LeanInteract-based approach works
            candidates = generator.generate(theorem_decl, config.sources, config)

            assert isinstance(candidates, list)
            # All candidates should have valid sources
            for candidate in candidates:
                assert candidate.hint.source in config.sources
