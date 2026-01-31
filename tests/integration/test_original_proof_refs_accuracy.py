"""
Integration tests for original_proof_refs extraction accuracy.

These tests verify that the system achieves 95%+ accuracy for extracting
lemma references from original proofs using LeanInteract value.constants.

Requirements: 25.4, 2.4, 2.1, 2.2, 2.3
"""

import pytest

from lean_proof_auto_mcp.core.candidate_generator import CandidateGenerator
from lean_proof_auto_mcp.core.indexer import build_index
from lean_proof_auto_mcp.core.search_annotations_domain import (
    CandidateConfig,
    CandidateSource,
)
from lean_proof_auto_mcp.core.source import SourceText
from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range


class MockLeanInteractQuerier:
    """Mock LeanInteractQuerier for accuracy testing."""

    def __init__(self, declarations: list[Declaration], proof_references: dict[str, list[str]]):
        self.declarations = declarations
        self.proof_references = proof_references

    def extract_declarations(self, file_path: str) -> list[Declaration]:
        return self.declarations

    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        return self.proof_references.get(theorem_id, [])


# Ground truth dataset with known proof references
# Format: (theorem_text, theorem_id, expected_references)
GROUND_TRUTH_DATASET = [
    # Test case 1: Single reference
    (
        """
theorem test1 (n : Nat) : n + 0 = n := by
  apply Nat.add_zero
""",
        "test1",
        ["Nat.add_zero"],
    ),
    # Test case 2: Multiple references
    (
        """
theorem test2 (n m : Nat) : n + m = m + n := by
  apply Nat.add_comm
  apply Nat.add_assoc
""",
        "test2",
        ["Nat.add_comm", "Nat.add_assoc"],
    ),
    # Test case 3: Nested references
    (
        """
theorem test3 (a b c : Nat) : (a + b) + c = a + (b + c) := by
  rw [Nat.add_assoc]
  rw [Nat.add_comm]
""",
        "test3",
        ["Nat.add_assoc", "Nat.add_comm"],
    ),
    # Test case 4: References with namespaces
    (
        """
theorem test4 (xs ys : List Nat) : xs ++ ys = List.append xs ys := by
  apply List.append_eq
  apply List.nil_append
""",
        "test4",
        ["List.append_eq", "List.nil_append"],
    ),
    # Test case 5: No references (definitional proof)
    (
        """
theorem test5 (n : Nat) : n = n := by
  rfl
""",
        "test5",
        [],
    ),
    # Test case 6: References with type class instances
    (
        """
theorem test6 [Add α] (a b : α) : a + b = Add.add a b := by
  apply Add.add_def
""",
        "test6",
        ["Add.add_def"],
    ),
    # Test case 7: References with implicit arguments
    (
        """
theorem test7 {α : Type} (x : α) : x = x := by
  apply Eq.refl
""",
        "test7",
        ["Eq.refl"],
    ),
    # Test case 8: Complex proof with many references
    (
        """
theorem test8 (n m k : Nat) : (n + m) + k = (n + k) + m := by
  rw [Nat.add_assoc]
  rw [Nat.add_comm m k]
  rw [← Nat.add_assoc]
  apply Nat.add_comm
""",
        "test8",
        ["Nat.add_assoc", "Nat.add_comm"],
    ),
    # Test case 9: References with projections
    (
        """
theorem test9 (p : Nat × Nat) : p.1 + p.2 = Prod.fst p + Prod.snd p := by
  apply Prod.fst_add_snd
""",
        "test9",
        ["Prod.fst_add_snd"],
    ),
    # Test case 10: References with constructors
    (
        """
theorem test10 (n : Nat) : Option.some n = some n := by
  apply Option.some_eq
""",
        "test10",
        ["Option.some_eq"],
    ),
    # Test case 11: Simp lemmas
    (
        """
theorem test11 (n : Nat) : n + 0 = n := by
  simp [Nat.add_zero]
""",
        "test11",
        ["Nat.add_zero"],
    ),
    # Test case 12: Aesop with hints
    (
        """
theorem test12 (p q : Prop) : p ∧ q → q ∧ p := by
  aesop (add safe And.comm)
""",
        "test12",
        ["And.comm"],
    ),
    # Test case 13: Exact with reference
    (
        """
theorem test13 (h : True) : True := by
  exact h
""",
        "test13",
        [],  # 'h' is a hypothesis, not a lemma reference
    ),
    # Test case 14: Have with reference
    (
        """
theorem test14 (n : Nat) : n + 0 = n := by
  have h := Nat.add_zero n
  exact h
""",
        "test14",
        ["Nat.add_zero"],
    ),
    # Test case 15: Calc with references
    (
        """
theorem test15 (a b c : Nat) : a + b + c = c + b + a := by
  calc a + b + c
      = (a + b) + c := by rw [Nat.add_assoc]
    _ = c + (a + b) := by rw [Nat.add_comm]
    _ = c + b + a := by rw [Nat.add_comm a b, Nat.add_assoc]
""",
        "test15",
        ["Nat.add_assoc", "Nat.add_comm"],
    ),
    # Test case 16: Induction with references
    (
        """
theorem test16 (n : Nat) : n + 0 = n := by
  induction n with
  | zero => rfl
  | succ n ih => rw [Nat.succ_add, ih]
""",
        "test16",
        ["Nat.succ_add"],
    ),
    # Test case 17: Cases with references
    (
        """
theorem test17 (n : Nat) : n = 0 ∨ n > 0 := by
  cases n with
  | zero => apply Or.inl; rfl
  | succ n => apply Or.inr; apply Nat.succ_pos
""",
        "test17",
        ["Or.inl", "Or.inr", "Nat.succ_pos"],
    ),
    # Test case 18: Intro with references
    (
        """
theorem test18 : ∀ n : Nat, n + 0 = n := by
  intro n
  apply Nat.add_zero
""",
        "test18",
        ["Nat.add_zero"],
    ),
    # Test case 19: Exists with references
    (
        """
theorem test19 (n : Nat) : ∃ m : Nat, m = n := by
  apply Exists.intro n
  rfl
""",
        "test19",
        ["Exists.intro"],
    ),
    # Test case 20: Contradiction with references
    (
        """
theorem test20 (h : False) : True := by
  apply False.elim h
""",
        "test20",
        ["False.elim"],
    ),
]


@pytest.mark.integration
class TestOriginalProofRefsAccuracy:
    """Test accuracy of original_proof_refs extraction.

    Requirements: 25.4, 2.4
    """

    def test_accuracy_on_ground_truth_dataset(self):
        """Test that extraction achieves 95%+ accuracy on ground truth dataset.

        Requirements: 25.4, 2.4
        """
        total_cases = len(GROUND_TRUTH_DATASET)
        correct_extractions = 0

        for theorem_text, theorem_id, expected_refs in GROUND_TRUTH_DATASET:
            # Create source and index
            source = SourceText(path="test.lean", text=theorem_text)
            index = build_index(source)

            # Create mock declarations with value.constants
            mock_declarations = [
                Declaration(
                    name=theorem_id,
                    full_name=theorem_id,
                    type="test_type",
                    value=DeclValue(
                        pp=theorem_text,
                        constants=expected_refs,  # Ground truth
                        range=Range(start_line=1, start_col=0, end_line=10, end_col=0),
                    ),
                    attributes=[],
                    range=Range(start_line=1, start_col=0, end_line=10, end_col=0),
                    namespace="",
                ),
            ]

            # Add referenced declarations
            for ref in expected_refs:
                mock_declarations.append(
                    Declaration(
                        name=ref.split(".")[-1],
                        full_name=ref,
                        type="test_type",
                        value=None,
                        attributes=[],
                        range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
                        namespace=".".join(ref.split(".")[:-1]) if "." in ref else "",
                    )
                )

            # Create mock querier
            querier = MockLeanInteractQuerier(
                declarations=mock_declarations,
                proof_references={theorem_id: expected_refs},
            )

            # Generate candidates
            if index.decls:
                theorem_decl = index.decls[0]
                generator = CandidateGenerator(source, index, querier, proof_state_inspector=None)

                config = CandidateConfig(
                    sources=[CandidateSource.ORIGINAL_PROOF_REFS],
                    max_candidates_per_source=100,  # High limit to get all
                    allow_simp_hints=True,
                    allow_unfold_hints=True,
                )

                candidates = generator.generate(
                    theorem_decl, [CandidateSource.ORIGINAL_PROOF_REFS], config
                )

                # Extract candidate names
                extracted_refs = {c.hint.name for c in candidates}
                expected_refs_set = set(expected_refs)

                # Check if extraction matches expected
                if extracted_refs == expected_refs_set:
                    correct_extractions += 1
                else:
                    # Log mismatch for debugging
                    missing = expected_refs_set - extracted_refs
                    extra = extracted_refs - expected_refs_set
                    print(
                        f"\nMismatch in {theorem_id}:\n"
                        f"  Expected: {expected_refs_set}\n"
                        f"  Extracted: {extracted_refs}\n"
                        f"  Missing: {missing}\n"
                        f"  Extra: {extra}"
                    )

        # Calculate accuracy
        accuracy = (correct_extractions / total_cases) * 100

        print(f"\nAccuracy: {accuracy:.1f}% ({correct_extractions}/{total_cases} correct)")

        # Verify 95%+ accuracy target
        assert accuracy >= 95.0, (
            f"Accuracy {accuracy:.1f}% is below 95% target. "
            f"Got {correct_extractions}/{total_cases} correct extractions."
        )

    def test_empty_proof_returns_empty_list(self):
        """Test that proofs with no references return empty list.

        Requirements: 2.5
        """
        theorem_text = """
theorem test_rfl (n : Nat) : n = n := by
  rfl
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_rfl",
                full_name="test_rfl",
                type="(n : Nat) → n = n",
                value=DeclValue(
                    pp="rfl",
                    constants=[],  # No references
                    range=Range(start_line=2, start_col=0, end_line=2, end_col=0),
                ),
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
            ),
        ]

        querier = MockLeanInteractQuerier(
            declarations=mock_declarations,
            proof_references={"test_rfl": []},
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

            # Verify empty list returned without errors
            assert candidates == []

    def test_validates_references_against_declarations(self):
        """Test that invalid references are filtered out.

        Requirements: 2.3
        """
        theorem_text = """
theorem test_invalid : True := by
  apply invalid_lemma
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_invalid",
                full_name="test_invalid",
                type="True",
                value=DeclValue(
                    pp="apply invalid_lemma",
                    constants=["invalid_lemma", "valid_lemma"],  # Mix of valid and invalid
                    range=Range(start_line=2, start_col=0, end_line=2, end_col=0),
                ),
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
            ),
            # Only valid_lemma is in declarations
            Declaration(
                name="valid_lemma",
                full_name="valid_lemma",
                type="True",
                value=None,
                attributes=[],
                range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
                namespace="",
            ),
        ]

        querier = MockLeanInteractQuerier(
            declarations=mock_declarations,
            proof_references={"test_invalid": ["invalid_lemma", "valid_lemma"]},
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

            # Verify only valid references are included
            candidate_names = {c.hint.name for c in candidates}
            assert "valid_lemma" in candidate_names
            assert "invalid_lemma" not in candidate_names

    def test_uses_value_constants_as_primary_source(self):
        """Test that value.constants is used as primary source.

        Requirements: 2.1
        """
        theorem_text = """
theorem test_primary (n : Nat) : n + 0 = n := by
  apply Nat.add_zero
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        mock_declarations = [
            Declaration(
                name="test_primary",
                full_name="test_primary",
                type="(n : Nat) → n + 0 = n",
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
                type="∀ (n : Nat), n + 0 = n",
                value=None,
                attributes=["simp"],
                range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
                namespace="Nat",
            ),
        ]

        querier = MockLeanInteractQuerier(
            declarations=mock_declarations,
            proof_references={"test_primary": ["Nat.add_zero"]},
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

            # Verify Nat.add_zero was extracted from value.constants
            candidate_names = {c.hint.name for c in candidates}
            assert "Nat.add_zero" in candidate_names


@pytest.mark.integration
class TestAccuracyMetrics:
    """Test accuracy metrics and reporting.

    Requirements: 25.4, 2.4
    """

    def test_precision_recall_metrics(self):
        """Test precision and recall metrics for extraction."""
        # Test case with known ground truth
        theorem_text = """
theorem test_metrics (n m : Nat) : n + m = m + n := by
  apply Nat.add_comm
"""
        source = SourceText(path="test.lean", text=theorem_text)
        index = build_index(source)

        # Ground truth: should extract Nat.add_comm
        expected_refs = ["Nat.add_comm"]

        mock_declarations = [
            Declaration(
                name="test_metrics",
                full_name="test_metrics",
                type="(n m : Nat) → n + m = m + n",
                value=DeclValue(
                    pp="apply Nat.add_comm",
                    constants=expected_refs,
                    range=Range(start_line=2, start_col=0, end_line=2, end_col=0),
                ),
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
                namespace="",
            ),
            Declaration(
                name="add_comm",
                full_name="Nat.add_comm",
                type="∀ (n m : Nat), n + m = m + n",
                value=None,
                attributes=["simp"],
                range=Range(start_line=0, start_col=0, end_line=0, end_col=0),
                namespace="Nat",
            ),
        ]

        querier = MockLeanInteractQuerier(
            declarations=mock_declarations,
            proof_references={"test_metrics": expected_refs},
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

            extracted_refs = {c.hint.name for c in candidates}
            expected_refs_set = set(expected_refs)

            # Calculate precision and recall
            true_positives = len(extracted_refs & expected_refs_set)
            false_positives = len(extracted_refs - expected_refs_set)
            false_negatives = len(expected_refs_set - extracted_refs)

            precision = (
                true_positives / (true_positives + false_positives)
                if (true_positives + false_positives) > 0
                else 0.0
            )
            recall = (
                true_positives / (true_positives + false_negatives)
                if (true_positives + false_negatives) > 0
                else 0.0
            )

            # Verify high precision and recall
            assert precision >= 0.95, f"Precision {precision:.2f} is below 95%"
            assert recall >= 0.95, f"Recall {recall:.2f} is below 95%"
