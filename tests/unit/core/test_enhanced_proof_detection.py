"""Tests for enhanced proof detection capabilities.

This module tests the improved detection of both := (term-mode) and by (tactic-mode) proofs
with better handling of multi-line declarations and complex proof structures.
"""

from lean_proof_auto_mcp.core.indexer import build_index
from lean_proof_auto_mcp.core.source import SourceText


class TestTermModeProofDetection:
    """Test enhanced detection of term-mode proofs (using :=)."""

    def test_simple_term_proof(self):
        """Test basic term-mode proof detection."""
        lean_code = """theorem simple_term : True := True.intro"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "simple_term"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 1
        assert decl.proof_span.end_line == 1

    def test_multiline_term_proof(self):
        """Test term-mode proof spanning multiple lines."""
        lean_code = """theorem multiline_term : 1 + 1 = 2 :=
  calc 1 + 1
    = 2 := by norm_num"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "multiline_term"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 3

    def test_complex_term_with_brackets(self):
        """Test term-mode proof with nested brackets."""
        lean_code = """theorem complex_term : (1 + 1) * (2 + 2) = 8 :=
  by simp [add_mul, mul_add]"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "complex_term"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 2

    def test_term_proof_with_where_clause(self):
        """Test term-mode proof with where clause."""
        lean_code = """theorem with_where : ∃ x, x > 0 := ⟨1, h⟩
  where h : 1 > 0 := by norm_num"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "with_where"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 1
        assert decl.proof_span.end_line == 2


class TestTacticModeProofDetection:
    """Test enhanced detection of tactic-mode proofs (using by)."""

    def test_same_line_proof(self):
        """Test proof that starts on the same line as := by."""
        lean_code = """theorem same_line : True := by trivial"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "same_line"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 1  # Proof content is on the same line
        assert decl.proof_span.end_line == 1

    def test_assign_by_pattern(self):
        """Test := by pattern detection."""
        lean_code = """theorem assign_by : True := by
  trivial"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "assign_by"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 2

    def test_direct_by_pattern(self):
        """Test direct by pattern (without :=)."""
        lean_code = """theorem direct_by : True
  by trivial"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "direct_by"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2
        assert decl.proof_span.end_line == 2

    def test_multiline_tactic_proof(self):
        """Test multi-line tactic proof with proper indentation."""
        lean_code = """theorem multiline_tactic : 1 + 1 = 2 := by
  norm_num
  done"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "multiline_tactic"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 3

    def test_nested_tactic_constructs(self):
        """Test tactic proof with nested constructs (have, suffices)."""
        lean_code = """theorem nested_tactics : 1 + 1 = 2 := by
  have h1 : 1 = 1 := rfl
  have h2 : 1 + 1 = 1 + 1 := rfl
  norm_num"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "nested_tactics"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 4

    def test_case_analysis_proof(self):
        """Test tactic proof with case analysis."""
        lean_code = """theorem case_analysis (n : ℕ) : n = 0 ∨ n > 0 := by
  cases n with
  | zero => left; rfl
  | succ k => right; simp"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "case_analysis"
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 4


class TestComplexDeclarationPatterns:
    """Test enhanced detection with complex declaration patterns."""

    def test_multiline_declaration_with_term_proof(self):
        """Test multi-line declaration with term-mode proof."""
        lean_code = """theorem complex_multiline
    {R : Type*} [Ring R]
    (x y : R)
    : x + y = y + x :=
  add_comm x y"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "complex_multiline"
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 4
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 5  # Proof content starts on line 5
        assert decl.proof_span.end_line == 5

    def test_multiline_declaration_with_tactic_proof(self):
        """Test multi-line declaration with tactic-mode proof."""
        lean_code = """theorem complex_multiline_tactic
    {R : Type*} [Ring R]
    (x y : R)
    : x + y = y + x := by
  ring"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "complex_multiline_tactic"
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 4
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 5  # Proof content starts on line 5
        assert decl.proof_span.end_line == 5

    def test_type_annotation_colons_ignored(self):
        """Test that type annotation colons don't interfere with main colon detection."""
        lean_code = """theorem ignore_type_colons
    {R : Type*} [Ring R]
    {S : Type*} [Ring S]
    (f : R →+* S)
    (x : R) (y : S)
    : f x = y := by
  sorry"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "ignore_type_colons"
        # Should find the main colon on line 6, not the type annotation colons
        assert decl.decl_span.end_line == 6
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 7  # Proof content starts on line 7
        assert decl.proof_span.end_line == 7

    def test_anonymous_theorem_with_complex_type(self):
        """Test anonymous theorem with complex type signature."""
        lean_code = """theorem {R : Type*} [Ring R] (x y : R) : x + y = y + x := by
  ring"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        # Should generate anonymous name
        assert decl.theorem_id.startswith("theorem_")
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2  # Proof content starts on line 2
        assert decl.proof_span.end_line == 2
        assert decl.proof_span.end_line == 2


class TestMixedProofPatterns:
    """Test detection of mixed proof patterns in the same file."""

    def test_mixed_proof_modes(self):
        """Test file with both term-mode and tactic-mode proofs."""
        lean_code = """theorem term_proof : True := True.intro

theorem tactic_proof : True := by
  trivial

theorem assign_by_proof : 1 = 1 := by rfl

theorem calc_proof : 1 + 1 = 2 :=
calc 1 + 1 = 2 := by norm_num"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 4

        # Check each proof type is detected correctly
        term_proof = next(d for d in index.decls if d.theorem_id == "term_proof")
        assert term_proof.proof_span is not None
        assert term_proof.proof_span.start_line == 1

        tactic_proof = next(d for d in index.decls if d.theorem_id == "tactic_proof")
        assert tactic_proof.proof_span is not None
        assert tactic_proof.proof_span.start_line == 4  # Proof content starts on line 4

        assign_by_proof = next(d for d in index.decls if d.theorem_id == "assign_by_proof")
        assert assign_by_proof.proof_span is not None
        assert assign_by_proof.proof_span.start_line == 6

        calc_proof = next(d for d in index.decls if d.theorem_id == "calc_proof")
        assert calc_proof.proof_span is not None
        assert calc_proof.proof_span.start_line == 9  # Proof content starts on line 9


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_proof_with_comments(self):
        """Test proof detection with comments interspersed."""
        lean_code = """theorem with_comments : True := by
  -- This is a comment
  trivial -- Another comment
  -- Final comment"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "with_comments"
        assert decl.proof_span is not None
        # Should include the proof content, comments are handled by strip_comments

    def test_proof_with_string_literals(self):
        """Test proof detection with string literals containing keywords."""
        lean_code = """theorem with_strings : String := by
  exact "this string contains by and := keywords"
  done"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "with_strings"
        assert decl.proof_span is not None

    def test_very_long_proof(self):
        """Test detection of very long proofs."""
        # Create a proof with many lines
        proof_lines = ["  simp"] * 50
        lean_code = f"""theorem long_proof : True := by
{chr(10).join(proof_lines)}
  trivial"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "long_proof"
        assert decl.proof_span is not None
        assert decl.proof_span.end_line > 50  # Should detect the full long proof

    def test_no_proof_declaration(self):
        """Test declaration without proof (axiom-like)."""
        lean_code = """theorem no_proof : True"""

        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)

        assert len(index.decls) == 1
        decl = index.decls[0]

        assert decl.theorem_id == "no_proof"
        # Should handle gracefully - proof_span may be None
        # This is acceptable behavior for declarations without proofs
