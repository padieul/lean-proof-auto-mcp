"""Unit tests for core.features module."""

import pytest

from lean_proof_auto_mcp.core.features import (
    TheoremFeatures,
    count_local_lemmas,
    count_rewrites,
    count_simps,
    detect_tactics,
    extract_features,
)
from lean_proof_auto_mcp.core.indexer import TheoremDecl
from lean_proof_auto_mcp.core.source import SourceText, Span


class TestTheoremFeatures:
    """Test cases for TheoremFeatures dataclass."""

    def test_valid_features(self):
        """Test creating valid TheoremFeatures."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "apply", "exact"},
            has_induction=False,
            has_cases=True,
            rewrite_count=3,
            simp_count=1,
            local_lemmas_count=2,
            confidence=0.8,
        )

        assert features.proof_lines == 10
        assert features.tactic_kinds == {"intro", "apply", "exact"}
        assert not features.has_induction
        assert features.has_cases
        assert features.rewrite_count == 3
        assert features.simp_count == 1
        assert features.local_lemmas_count == 2
        assert features.confidence == 0.8

    def test_invalid_proof_lines(self):
        """Test validation of proof_lines."""
        with pytest.raises(ValueError, match="proof_lines must be >= 0"):
            TheoremFeatures(
                proof_lines=-1,
                tactic_kinds=set(),
                has_induction=False,
                has_cases=False,
                rewrite_count=0,
                simp_count=0,
                local_lemmas_count=0,
                confidence=0.5,
            )

    def test_invalid_confidence_low(self):
        """Test validation of confidence (too low)."""
        with pytest.raises(ValueError, match="confidence must be in \\[0.0, 1.0\\]"):
            TheoremFeatures(
                proof_lines=5,
                tactic_kinds=set(),
                has_induction=False,
                has_cases=False,
                rewrite_count=0,
                simp_count=0,
                local_lemmas_count=0,
                confidence=-0.1,
            )

    def test_invalid_confidence_high(self):
        """Test validation of confidence (too high)."""
        with pytest.raises(ValueError, match="confidence must be in \\[0.0, 1.0\\]"):
            TheoremFeatures(
                proof_lines=5,
                tactic_kinds=set(),
                has_induction=False,
                has_cases=False,
                rewrite_count=0,
                simp_count=0,
                local_lemmas_count=0,
                confidence=1.1,
            )

    def test_invalid_counts(self):
        """Test validation of count fields."""
        with pytest.raises(ValueError, match="rewrite_count must be >= 0"):
            TheoremFeatures(
                proof_lines=5,
                tactic_kinds=set(),
                has_induction=False,
                has_cases=False,
                rewrite_count=-1,
                simp_count=0,
                local_lemmas_count=0,
                confidence=0.5,
            )


class TestDetectTactics:
    """Test cases for detect_tactics function."""

    def test_basic_tactics(self):
        """Test detecting basic tactics."""
        proof_text = """by
  intro h
  apply some_lemma
  exact h"""

        tactics = detect_tactics(proof_text)
        assert "intro" in tactics
        assert "apply" in tactics
        assert "exact" in tactics

    def test_structural_tactics(self):
        """Test detecting structural tactics."""
        proof_text = """by
  induction n with
  | zero => trivial
  | succ n ih =>
    cases h with
    | left => constructor
    | right => split"""

        tactics = detect_tactics(proof_text)
        assert "induction" in tactics
        assert "cases" in tactics
        assert "trivial" in tactics
        assert "constructor" in tactics
        assert "split" in tactics

    def test_rewrite_tactics(self):
        """Test detecting rewrite-related tactics."""
        proof_text = """by
  rw [lemma1, lemma2]
  rewrite [← lemma3]
  simp [lemma4]
  simp_rw [lemma5]"""

        tactics = detect_tactics(proof_text)
        assert "rw" in tactics
        assert "rewrite" in tactics
        assert "simp" in tactics
        assert "simp_rw" in tactics

    def test_advanced_tactics(self):
        """Test detecting advanced tactics."""
        proof_text = """by
  linarith
  omega
  tauto
  norm_num
  field_simp
  push_neg
  contrapose"""

        tactics = detect_tactics(proof_text)
        assert "linarith" in tactics
        assert "omega" in tactics
        assert "tauto" in tactics
        assert "norm_num" in tactics
        assert "field_simp" in tactics
        assert "push_neg" in tactics
        assert "contrapose" in tactics

    def test_case_insensitive(self):
        """Test that tactic detection is case insensitive."""
        proof_text = """by
  INTRO h
  Apply lemma
  EXACT h"""

        tactics = detect_tactics(proof_text)
        assert "intro" in tactics
        assert "apply" in tactics
        assert "exact" in tactics

    def test_no_tactics(self):
        """Test text without tactics."""
        proof_text = "some random text without tactics"
        tactics = detect_tactics(proof_text)
        assert len(tactics) == 0

    def test_empty_text(self):
        """Test empty text."""
        tactics = detect_tactics("")
        assert len(tactics) == 0

    def test_tactics_in_context(self):
        """Test tactics in realistic proof context."""
        proof_text = """by
  intro x y h
  have h1 : x + y = y + x := by ring
  rw [h1] at h
  exact h"""

        tactics = detect_tactics(proof_text)
        assert "intro" in tactics
        assert "have" in tactics
        assert "rw" in tactics
        assert "exact" in tactics


class TestCountRewrites:
    """Test cases for count_rewrites function."""

    def test_basic_rewrites(self):
        """Test counting basic rw and rewrite."""
        proof_text = """by
  rw [lemma1]
  rewrite [lemma2]
  rw [← lemma3, lemma4]"""

        count = count_rewrites(proof_text)
        assert count == 3  # rw, rewrite, rw

    def test_rewrite_variants(self):
        """Test counting rewrite variants."""
        proof_text = """by
  rw [lemma1]
  rw_mod_cast [lemma2]
  simp_rw [lemma3]
  rewrite [lemma4]"""

        count = count_rewrites(proof_text)
        assert count == 4

    def test_no_rewrites(self):
        """Test text without rewrites."""
        proof_text = """by
  intro h
  apply lemma
  exact h"""

        count = count_rewrites(proof_text)
        assert count == 0

    def test_empty_text(self):
        """Test empty text."""
        count = count_rewrites("")
        assert count == 0

    def test_case_insensitive(self):
        """Test case insensitive counting."""
        proof_text = """by
  RW [lemma1]
  REWRITE [lemma2]"""

        count = count_rewrites(proof_text)
        assert count == 2


class TestCountSimps:
    """Test cases for count_simps function."""

    def test_basic_simps(self):
        """Test counting basic simp tactics."""
        proof_text = """by
  simp
  simp [lemma1]
  simp only [lemma2]"""

        count = count_simps(proof_text)
        assert count == 3

    def test_simp_variants(self):
        """Test counting simp variants."""
        proof_text = """by
  simp
  simp_all
  simp_only [lemma]
  dsimp
  field_simp"""

        count = count_simps(proof_text)
        assert count == 5

    def test_no_simps(self):
        """Test text without simps."""
        proof_text = """by
  intro h
  rw [lemma]
  exact h"""

        count = count_simps(proof_text)
        assert count == 0

    def test_empty_text(self):
        """Test empty text."""
        count = count_simps("")
        assert count == 0


class TestCountLocalLemmas:
    """Test cases for count_local_lemmas function."""

    def test_basic_local_lemmas(self):
        """Test counting basic local lemmas."""
        proof_text = """by
  have h1 : P := by exact p
  suffices h2 : Q by exact q
  let x := 42
  obtain ⟨y, hy⟩ := exists_y"""

        count = count_local_lemmas(proof_text)
        assert count == 4  # have, suffices, let, obtain

    def test_no_local_lemmas(self):
        """Test text without local lemmas."""
        proof_text = """by
  intro h
  rw [lemma]
  exact h"""

        count = count_local_lemmas(proof_text)
        assert count == 0

    def test_empty_text(self):
        """Test empty text."""
        count = count_local_lemmas("")
        assert count == 0

    def test_multiple_occurrences(self):
        """Test multiple occurrences of same construct."""
        proof_text = """by
  have h1 : P := p1
  have h2 : Q := q1
  have h3 : R := r1"""

        count = count_local_lemmas(proof_text)
        assert count == 3


class TestExtractFeatures:
    """Test cases for extract_features function."""

    def test_theorem_with_proof(self):
        """Test extracting features from theorem with proof."""
        source_text = """theorem example : True := by
  intro
  have h : True := True.intro
  exact h"""

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="example",
            name="example",
            kind="theorem",
            decl_span=Span(1, 0, 4, 0),
            proof_span=Span(1, 25, 4, 0),  # from "by" to end
        )

        features = extract_features(source, decl)

        assert features.proof_lines == 4  # 4 non-empty lines (including "by" line)
        assert "intro" in features.tactic_kinds
        assert "have" in features.tactic_kinds
        assert "exact" in features.tactic_kinds
        assert not features.has_induction
        assert not features.has_cases
        assert features.rewrite_count == 0
        assert features.simp_count == 0
        assert features.local_lemmas_count == 1  # have
        assert 0.0 <= features.confidence <= 1.0

    def test_theorem_without_proof(self):
        """Test extracting features from theorem without proof."""
        source_text = "theorem example : True := True.intro"

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="example",
            name="example",
            kind="theorem",
            decl_span=Span(1, 0, 1, 36),
            proof_span=None,  # No proof span
        )

        features = extract_features(source, decl)

        assert features.proof_lines == 0
        assert len(features.tactic_kinds) == 0
        assert not features.has_induction
        assert not features.has_cases
        assert features.rewrite_count == 0
        assert features.simp_count == 0
        assert features.local_lemmas_count == 0
        assert features.confidence == 0.0

    def test_complex_proof_with_induction(self):
        """Test extracting features from complex proof with induction."""
        source_text = """theorem nat_add_comm (n m : Nat) : n + m = m + n := by
  induction n with
  | zero =>
    simp [Nat.zero_add, Nat.add_zero]
  | succ n ih =>
    rw [Nat.succ_add, ih, Nat.add_succ]"""

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="nat_add_comm",
            name="nat_add_comm",
            kind="theorem",
            decl_span=Span(1, 0, 6, 0),
            proof_span=Span(2, 0, 6, 0),  # Start from line 2 where induction begins
        )

        features = extract_features(source, decl)

        assert features.proof_lines == 5  # Non-empty lines in proof
        assert "induction" in features.tactic_kinds
        assert "simp" in features.tactic_kinds
        assert "rw" in features.tactic_kinds
        assert features.has_induction
        assert not features.has_cases
        assert features.rewrite_count == 1  # one rw
        assert features.simp_count == 1  # one simp
        assert features.local_lemmas_count == 0
        assert features.confidence > 0.5  # Should have good confidence

    def test_proof_with_cases(self):
        """Test extracting features from proof with cases."""
        source_text = """theorem bool_cases (b : Bool) : b = true ∨ b = false := by
  cases b with
  | true => left; rfl
  | false => right; rfl"""

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="bool_cases",
            name="bool_cases",
            kind="theorem",
            decl_span=Span(1, 0, 4, 0),
            proof_span=Span(1, 62, 4, 0),
        )

        features = extract_features(source, decl)

        assert "cases" in features.tactic_kinds
        assert "left" in features.tactic_kinds
        assert "right" in features.tactic_kinds
        assert "rfl" in features.tactic_kinds
        assert not features.has_induction
        assert features.has_cases

    def test_proof_with_comments(self):
        """Test extracting features from proof with comments."""
        source_text = """theorem example : True := by
  -- First, we introduce the hypothesis
  intro
  -- Then we use the fact that True is always true
  exact True.intro -- This completes the proof"""

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="example",
            name="example",
            kind="theorem",
            decl_span=Span(1, 0, 5, 0),
            proof_span=Span(1, 25, 5, 0),  # from "by" to end
        )

        features = extract_features(source, decl)

        # Comments should be stripped, so only tactic lines count
        assert features.proof_lines == 3  # "by", intro and exact lines (comment lines become empty)
        assert "intro" in features.tactic_kinds
        assert "exact" in features.tactic_kinds

    def test_sorry_proof(self):
        """Test extracting features from incomplete proof with sorry."""
        source_text = """theorem hard_theorem : P := by
  sorry"""

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="hard_theorem",
            name="hard_theorem",
            kind="theorem",
            decl_span=Span(1, 0, 2, 0),
            proof_span=Span(1, 32, 2, 0),
        )

        features = extract_features(source, decl)

        assert "sorry" in features.tactic_kinds
        assert features.confidence < 0.5  # Should have low confidence due to sorry


class TestIntegrationScenarios:
    """Test integration scenarios with realistic Lean proofs."""

    def test_mathlib_style_proof(self):
        """Test features extraction from Mathlib-style proof."""
        source_text = """theorem list_length_append (l1 l2 : List α) :
  (l1 ++ l2).length = l1.length + l2.length := by
  induction l1 with
  | nil =>
    simp [List.nil_append, List.length_nil, Nat.zero_add]
  | cons head tail ih =>
    simp [List.cons_append, List.length_cons]
    rw [Nat.succ_add, ih]"""

        source = SourceText("mathlib.lean", source_text)
        decl = TheoremDecl(
            theorem_id="list_length_append",
            name="list_length_append",
            kind="theorem",
            decl_span=Span(1, 0, 8, 0),
            proof_span=Span(3, 0, 8, 0),  # Start from line 3 where induction begins
        )

        features = extract_features(source, decl)

        # Verify comprehensive feature detection
        assert features.proof_lines > 0
        assert features.has_induction
        assert not features.has_cases
        assert features.simp_count >= 2
        assert features.rewrite_count >= 1
        assert "induction" in features.tactic_kinds
        assert "simp" in features.tactic_kinds
        assert "rw" in features.tactic_kinds
        assert features.confidence > 0.6

    def test_tactic_heavy_proof(self):
        """Test features extraction from tactic-heavy proof."""
        source_text = """theorem complex_example : ∀ n : Nat, n + 0 = n := by
  intro n
  have h1 : n + 0 = 0 + n := Nat.add_comm n 0
  have h2 : 0 + n = n := Nat.zero_add n
  rw [h1, h2]
  simp_rw [Nat.add_zero]
  exact rfl"""

        source = SourceText("tactics.lean", source_text)
        decl = TheoremDecl(
            theorem_id="complex_example",
            name="complex_example",
            kind="theorem",
            decl_span=Span(1, 0, 7, 0),
            proof_span=Span(1, 50, 7, 0),
        )

        features = extract_features(source, decl)

        assert features.local_lemmas_count == 2  # two have statements
        assert features.rewrite_count >= 2  # rw and simp_rw
        assert "intro" in features.tactic_kinds
        assert "have" in features.tactic_kinds
        assert "rw" in features.tactic_kinds
        assert "simp_rw" in features.tactic_kinds
        assert "exact" in features.tactic_kinds

    def test_empty_proof_by_definition(self):
        """Test theorem that's proven by definition (no tactics)."""
        source_text = "theorem trivial_example : True := True.intro"

        source = SourceText("simple.lean", source_text)
        decl = TheoremDecl(
            theorem_id="trivial_example",
            name="trivial_example",
            kind="theorem",
            decl_span=Span(1, 0, 1, 44),
            proof_span=Span(1, 34, 1, 44),  # Just the term proof
        )

        features = extract_features(source, decl)

        # Term proofs should have minimal features
        assert features.proof_lines == 1
        # Note: "True.intro" contains "intro" substring, so it gets detected as a tactic
        # This is expected behavior for the regex-based detection
        assert "intro" in features.tactic_kinds  # "intro" detected in "True.intro"
        assert not features.has_induction
        assert not features.has_cases
        assert features.rewrite_count == 0
        assert features.simp_count == 0
        assert features.local_lemmas_count == 0


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_very_short_proof(self):
        """Test very short proof."""
        source_text = "theorem t : True := by trivial"

        source = SourceText("short.lean", source_text)
        decl = TheoremDecl(
            theorem_id="t",
            name="t",
            kind="theorem",
            decl_span=Span(1, 0, 1, 31),
            proof_span=Span(1, 23, 1, 31),
        )

        features = extract_features(source, decl)

        assert features.proof_lines == 1
        assert "trivial" in features.tactic_kinds
        assert features.confidence > 0.0

    def test_very_long_proof(self):
        """Test very long proof (confidence adjustment)."""
        # Create a proof with many lines
        proof_lines = ["  intro"] + ["  rw [lemma]"] * 60 + ["  exact h"]
        source_text = "theorem long_proof : P := by\n" + "\n".join(proof_lines)

        source = SourceText("long.lean", source_text)
        decl = TheoremDecl(
            theorem_id="long_proof",
            name="long_proof",
            kind="theorem",
            decl_span=Span(1, 0, 63, 0),
            proof_span=Span(1, 30, 63, 0),
        )

        features = extract_features(source, decl)

        assert features.proof_lines > 50
        assert features.rewrite_count == 60
        # Very long proofs might have slightly reduced confidence
        assert 0.0 < features.confidence <= 1.0

    def test_malformed_proof_span(self):
        """Test handling malformed proof spans."""
        source_text = "theorem example : True := by trivial"

        source = SourceText("test.lean", source_text)

        # Test with invalid span (beyond file bounds)
        decl = TheoremDecl(
            theorem_id="example",
            name="example",
            kind="theorem",
            decl_span=Span(1, 0, 1, 37),
            proof_span=Span(10, 0, 20, 0),  # Beyond file bounds
        )

        features = extract_features(source, decl)

        # Should handle gracefully
        assert features.proof_lines >= 0
        assert features.confidence >= 0.0


class TestEnhancedTacticDetection:
    """Test cases for enhanced tactic detection improvements."""

    def test_term_mode_proof_patterns(self):
        """Test detection of term-mode proof patterns."""
        proof_text = "eval₂_list_sum .."
        tactics = detect_tactics(proof_text)
        assert "inference_placeholder" in tactics

        proof_text2 = "eval₂_X _ _"
        tactics2 = detect_tactics(proof_text2)
        assert "term_application" in tactics2

        proof_text3 = "(eval₂RingHom _ _).map_pow _ _"
        tactics3 = detect_tactics(proof_text3)
        assert "term_application" in tactics3

    def test_enhanced_confidence_for_term_proofs(self):
        """Test that term-mode proofs get reasonable confidence scores."""
        from lean_proof_auto_mcp.core.features import _calculate_confidence
        from lean_proof_auto_mcp.core.source import Span

        # Test term-mode proof with inference placeholder
        proof_text = "eval₂_list_sum .."
        tactic_kinds = {"inference_placeholder"}
        span = Span(1, 0, 1, 20)
        confidence = _calculate_confidence(proof_text, span, tactic_kinds)
        assert confidence > 0.0, f"Expected positive confidence, got {confidence}"

        # Test rfl proof
        proof_text2 = "rfl"
        tactic_kinds2 = {"rfl"}
        confidence2 = _calculate_confidence(proof_text2, span, tactic_kinds2)
        assert confidence2 > 0.0, f"Expected positive confidence for rfl, got {confidence2}"

    def test_extract_features_with_term_proof(self):
        """Test feature extraction with term-mode proofs."""
        source_text = """theorem eval_listSum (l : List R[X]) (x : R) :
  eval x l.sum = (l.map (eval x)).sum :=
  eval₂_list_sum .."""

        source = SourceText("test.lean", source_text)
        decl = TheoremDecl(
            theorem_id="eval_listSum",
            name="eval_listSum",
            kind="theorem",
            decl_span=Span(1, 0, 3, 0),
            proof_span=Span(3, 2, 3, 19),  # Include both dots
        )

        features = extract_features(source, decl)

        assert features.proof_lines == 1
        assert "inference_placeholder" in features.tactic_kinds
        assert features.confidence > 0.0, f"Expected positive confidence, got {features.confidence}"

    def test_multiline_tactic_detection(self):
        """Test detection of multi-line tactics."""
        proof_text = """induction n with
| zero => simp
| succ n ih => rw [ih]"""

        tactics = detect_tactics(proof_text)
        assert "induction" in tactics
        assert "simp" in tactics
        assert "rw" in tactics

    def test_custom_mathlib_tactics(self):
        """Test detection of custom Mathlib tactics."""
        proof_text = """by
  field_simp
  norm_cast
  push_cast
  simp_mod_cast"""

        tactics = detect_tactics(proof_text)
        assert "field_simp" in tactics
        assert "norm_cast" in tactics
        assert "push_cast" in tactics
        assert "simp_mod_cast" in tactics

    def test_proof_structure_patterns(self):
        """Test detection of proof structure patterns."""
        proof_text1 = """by
  trivial"""
        tactics1 = detect_tactics(proof_text1)
        assert "tactic_mode" in tactics1

        proof_text2 = ":= by simp"
        tactics2 = detect_tactics(proof_text2)
        assert "tactic_proof" in tactics2

        proof_text3 = ":= some_lemma.property"
        tactics3 = detect_tactics(proof_text3)
        assert "term_proof" in tactics3
