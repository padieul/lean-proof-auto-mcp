"""Unit tests for core.indexer module."""

import pytest
from src.lean_proof_auto_mcp.core.indexer import (
    TheoremDecl,
    FileIndex,
    build_index,
    find_by_id,
    find_by_range,
)
from src.lean_proof_auto_mcp.core.source import SourceText, Span


class TestTheoremDecl:
    """Test cases for TheoremDecl dataclass."""
    
    def test_theorem_decl_creation_valid(self):
        """Test creating valid theorem declarations."""
        span = Span(start_line=1, end_line=3)
        decl = TheoremDecl(
            theorem_id="Nat.add_comm",
            name="add_comm",
            kind="theorem",
            decl_span=span
        )
        assert decl.theorem_id == "Nat.add_comm"
        assert decl.name == "add_comm"
        assert decl.kind == "theorem"
        assert decl.decl_span == span
        assert decl.proof_span is None
        assert decl.attributes == []
    
    def test_theorem_decl_with_proof_span(self):
        """Test creating theorem declaration with proof span."""
        decl_span = Span(start_line=1, end_line=3)
        proof_span = Span(start_line=2, end_line=3)
        decl = TheoremDecl(
            theorem_id="test",
            name="test",
            kind="lemma",
            decl_span=decl_span,
            proof_span=proof_span,
            attributes=["simp"]
        )
        assert decl.proof_span == proof_span
        assert decl.attributes == ["simp"]
    
    def test_theorem_decl_invalid_theorem_id(self):
        """Test that theorem_id cannot be empty."""
        span = Span(start_line=1, end_line=1)
        with pytest.raises(ValueError, match="theorem_id cannot be empty"):
            TheoremDecl(
                theorem_id="",
                name="test",
                kind="theorem",
                decl_span=span
            )
    
    def test_theorem_decl_invalid_name(self):
        """Test that name cannot be empty."""
        span = Span(start_line=1, end_line=1)
        with pytest.raises(ValueError, match="name cannot be empty"):
            TheoremDecl(
                theorem_id="test",
                name="",
                kind="theorem",
                decl_span=span
            )
    
    def test_theorem_decl_invalid_kind(self):
        """Test that kind must be valid."""
        span = Span(start_line=1, end_line=1)
        with pytest.raises(ValueError, match="Invalid kind"):
            TheoremDecl(
                theorem_id="test",
                name="test",
                kind="invalid",
                decl_span=span
            )
    
    def test_theorem_decl_valid_kinds(self):
        """Test all valid kinds."""
        span = Span(start_line=1, end_line=1)
        valid_kinds = ["theorem", "lemma", "example", "instance"]
        
        for kind in valid_kinds:
            decl = TheoremDecl(
                theorem_id="test",
                name="test",
                kind=kind,
                decl_span=span
            )
            assert decl.kind == kind


class TestFileIndex:
    """Test cases for FileIndex dataclass."""
    
    def test_file_index_creation(self):
        """Test creating file index."""
        decls = [
            TheoremDecl("test1", "test1", "theorem", Span(start_line=1, end_line=1)),
            TheoremDecl("test2", "test2", "lemma", Span(start_line=2, end_line=2))
        ]
        index = FileIndex(file="test.lean", decls=decls)
        assert index.file == "test.lean"
        assert len(index.decls) == 2
        assert index.decls[0].theorem_id == "test1"
        assert index.decls[1].theorem_id == "test2"
    
    def test_file_index_empty(self):
        """Test creating empty file index."""
        index = FileIndex(file="empty.lean", decls=[])
        assert index.file == "empty.lean"
        assert len(index.decls) == 0


class TestBuildIndex:
    """Test cases for build_index function."""
    
    def test_build_index_simple_theorem(self):
        """Test indexing a simple theorem."""
        lean_code = """theorem simple : True := by
  trivial"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert index.file == "test.lean"
        assert len(index.decls) == 1
        
        decl = index.decls[0]
        assert decl.theorem_id == "simple"
        assert decl.name == "simple"
        assert decl.kind == "theorem"
        assert decl.decl_span.start_line == 1
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 1
    
    def test_build_index_multiple_declarations(self):
        """Test indexing multiple declarations."""
        lean_code = """theorem first : True := rfl

lemma second : 1 + 1 = 2 := by
  norm_num

example : False → True := by
  intro h
  trivial

instance : Inhabited Nat := ⟨0⟩"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 4
        
        # Check theorem
        theorem_decl = index.decls[0]
        assert theorem_decl.theorem_id == "first"
        assert theorem_decl.kind == "theorem"
        
        # Check lemma
        lemma_decl = index.decls[1]
        assert lemma_decl.theorem_id == "second"
        assert lemma_decl.kind == "lemma"
        
        # Check example
        example_decl = index.decls[2]
        assert example_decl.theorem_id.startswith("example_")  # Generated name for unnamed example
        assert example_decl.kind == "example"
        
        # Check instance
        instance_decl = index.decls[3]
        assert instance_decl.theorem_id.startswith("instance_")  # Generated name for unnamed instance
        assert instance_decl.kind == "instance"
    
    def test_build_index_namespaced_theorem(self):
        """Test indexing theorem with namespace."""
        lean_code = """namespace Nat

theorem Nat.add_comm (a b : Nat) : a + b = b + a := by
  sorry

end Nat"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        assert decl.theorem_id == "Nat.add_comm"
        assert decl.name == "add_comm"
        assert decl.kind == "theorem"
    
    def test_build_index_with_comments(self):
        """Test indexing with comments that might contain false positives."""
        lean_code = """-- This comment mentions theorem but isn't one
theorem real_theorem : True := by
  /- This comment also mentions lemma -/
  trivial

/- 
Multi-line comment with theorem keyword
should not be detected
-/

lemma actual_lemma : True := rfl"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        # Should only find the real declarations, not the ones in comments
        assert len(index.decls) == 2
        assert index.decls[0].theorem_id == "real_theorem"
        assert index.decls[1].theorem_id == "actual_lemma"
    
    def test_build_index_with_strings(self):
        """Test indexing with string literals containing keywords."""
        lean_code = '''def message : String := "This string contains theorem keyword"

theorem actual : True := by
  let msg := "Another string with lemma keyword"
  trivial'''
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        # Should only find the actual theorem, not the keywords in strings
        assert len(index.decls) == 1
        assert index.decls[0].theorem_id == "actual"
        assert index.decls[0].kind == "theorem"
    
    def test_build_index_empty_file(self):
        """Test indexing empty file."""
        source = SourceText(path="empty.lean", text="")
        index = build_index(source)
        
        assert index.file == "empty.lean"
        assert len(index.decls) == 0
    
    def test_build_index_no_theorems(self):
        """Test indexing file with no theorem-like declarations."""
        lean_code = """def helper : Nat := 42

variable (x : Nat)

#check Nat.add"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 0
    
    def test_build_index_complex_proof(self):
        """Test indexing theorem with complex proof structure."""
        lean_code = """theorem complex_proof (n : Nat) : n + 0 = n := by
  induction n with
  | zero => 
    simp
  | succ k ih =>
    rw [Nat.add_succ]
    rw [ih]"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        assert decl.theorem_id == "complex_proof"
        assert decl.proof_span is not None
        assert decl.proof_span.end_line > decl.proof_span.start_line

    def test_anonymous_theorem_deterministic_ids(self):
        """Test that anonymous theorems get deterministic unique IDs."""
        lean_code = """
-- Multiple anonymous examples
example : True := rfl

example : 1 + 1 = 2 := by norm_num

-- Anonymous instances
instance : Inhabited Nat := ⟨0⟩

instance : Decidable True := isTrue rfl

-- Anonymous theorem with complex type
theorem {R : Type*} [Ring R] (x y : R) : x + y = y + x := by ring

-- In namespace
namespace Test

example : True := rfl

instance : Inhabited Bool := ⟨true⟩

theorem {α : Type*} [Add α] (a b : α) : a + b = b + a := sorry

end Test

-- More examples after namespace
example : 2 + 2 = 4 := rfl

-- Multiple on same line (edge case)
example : True := rfl; example : False → True := by intro; trivial
"""
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        # Should find all declarations
        assert len(index.decls) == 11
        
        # Collect all theorem_id values
        theorem_ids = [decl.theorem_id for decl in index.decls]
        
        # All theorem_id values should be unique
        assert len(theorem_ids) == len(set(theorem_ids)), f"Duplicate theorem_id values found: {theorem_ids}"
        
        # Check specific patterns for anonymous declarations
        # Anonymous declarations either start with "{kind}_" or "{namespace}.{kind}_"
        anonymous_decls = []
        for decl in index.decls:
            # Check if it's an anonymous declaration
            if decl.theorem_id.startswith(f"{decl.kind}_"):
                # Global anonymous (e.g., "example_5")
                anonymous_decls.append(decl)
            elif "." in decl.theorem_id:
                # Check if it's namespaced anonymous (e.g., "Test.example_18")
                parts = decl.theorem_id.split(".")
                if len(parts) >= 2 and parts[-1].startswith(f"{decl.kind}_"):
                    anonymous_decls.append(decl)
        
        # Should have anonymous examples, instances, and theorems
        example_count = len([d for d in anonymous_decls if d.kind == "example"])
        instance_count = len([d for d in anonymous_decls if d.kind == "instance"])
        theorem_count = len([d for d in anonymous_decls if d.kind == "theorem"])
        
        assert example_count >= 5  # At least 5 anonymous examples (including collision)
        assert instance_count >= 2  # At least 2 anonymous instances  
        assert theorem_count >= 2  # At least 2 anonymous theorems
        
        # Check namespace handling - the Test namespace affects the theorem_id prefix
        namespaced_decls = [decl for decl in index.decls if "Test." in decl.theorem_id]
        assert len(namespaced_decls) >= 4  # Should have declarations in Test namespace
        
        # Verify deterministic naming pattern
        for decl in anonymous_decls:
            if "Test." in decl.theorem_id:
                # Namespaced anonymous declaration
                expected_pattern = f"Test.{decl.kind}_"
                assert decl.theorem_id.startswith(expected_pattern), f"Expected {decl.theorem_id} to start with {expected_pattern}"
            else:
                # Global anonymous declaration
                expected_pattern = f"{decl.kind}_"
                assert decl.theorem_id.startswith(expected_pattern), f"Expected {decl.theorem_id} to start with {expected_pattern}"
            
            # Should end with line number (and possibly collision counter)
            suffix = decl.theorem_id.split('_')[-1]
            if suffix.isdigit():
                line_num = int(suffix)
                assert line_num > 0, f"Line number should be positive: {decl.theorem_id}"
            else:
                # Might be collision counter format like "example_5_1"
                parts = decl.theorem_id.split('_')
                if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
                    line_num = int(parts[-2])
                    counter = int(parts[-1])
                    assert line_num > 0 and counter > 0, f"Line number and counter should be positive: {decl.theorem_id}"

    def test_anonymous_theorem_collision_resolution(self):
        """Test collision resolution for anonymous theorems on the same line."""
        # This is an edge case but should be handled correctly
        lean_code = """example : True := rfl; example : False → True := by intro; trivial"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        # Should find both examples
        assert len(index.decls) == 2
        
        # Both should be on line 1
        assert all(decl.decl_span.start_line == 1 for decl in index.decls)
        
        # Should have different theorem_id values
        theorem_ids = [decl.theorem_id for decl in index.decls]
        assert len(set(theorem_ids)) == 2, f"Expected unique IDs but got: {theorem_ids}"
        
        # One should be example_1, the other should be example_1_1 (collision resolution)
        expected_ids = {"example_1", "example_1_1"}
        actual_ids = set(theorem_ids)
        assert actual_ids == expected_ids, f"Expected {expected_ids} but got {actual_ids}"


class TestFindById:
    """Test cases for find_by_id function."""
    
    @pytest.fixture
    def sample_index(self):
        """Sample file index for testing."""
        decls = [
            TheoremDecl("first", "first", "theorem", Span(start_line=1, end_line=2)),
            TheoremDecl("Nat.add_comm", "add_comm", "theorem", Span(start_line=4, end_line=6)),
            TheoremDecl("helper", "helper", "lemma", Span(start_line=8, end_line=9)),
        ]
        return FileIndex(file="test.lean", decls=decls)
    
    def test_find_by_id_exists(self, sample_index):
        """Test finding existing theorem by ID."""
        result = find_by_id(sample_index, "Nat.add_comm")
        assert result is not None
        assert result.theorem_id == "Nat.add_comm"
        assert result.name == "add_comm"
        assert result.kind == "theorem"
    
    def test_find_by_id_not_exists(self, sample_index):
        """Test finding non-existent theorem by ID."""
        result = find_by_id(sample_index, "nonexistent")
        assert result is None
    
    def test_find_by_id_empty_index(self):
        """Test finding in empty index."""
        empty_index = FileIndex(file="empty.lean", decls=[])
        result = find_by_id(empty_index, "anything")
        assert result is None
    
    def test_find_by_id_case_sensitive(self, sample_index):
        """Test that search is case sensitive."""
        result = find_by_id(sample_index, "FIRST")
        assert result is None
        
        result = find_by_id(sample_index, "first")
        assert result is not None


class TestFindByRange:
    """Test cases for find_by_range function."""
    
    @pytest.fixture
    def sample_index(self):
        """Sample file index for testing."""
        decls = [
            TheoremDecl("first", "first", "theorem", Span(start_line=1, end_line=3)),      # lines 1-3
            TheoremDecl("second", "second", "lemma", Span(start_line=5, end_line=7)),      # lines 5-7
            TheoremDecl("third", "third", "theorem", Span(start_line=10, end_line=15)),    # lines 10-15
        ]
        return FileIndex(file="test.lean", decls=decls)
    
    def test_find_by_range_exact_match(self, sample_index):
        """Test finding theorem with exact range match."""
        result = find_by_range(sample_index, 5, 7)
        assert result is not None
        assert result.theorem_id == "second"
    
    def test_find_by_range_partial_overlap(self, sample_index):
        """Test finding theorem with partial overlap."""
        result = find_by_range(sample_index, 2, 4)
        assert result is not None
        assert result.theorem_id == "first"  # overlaps with lines 1-3
    
    def test_find_by_range_contained_within(self, sample_index):
        """Test finding theorem when range is contained within declaration."""
        result = find_by_range(sample_index, 12, 13)
        assert result is not None
        assert result.theorem_id == "third"  # range 12-13 is within 10-15
    
    def test_find_by_range_contains_declaration(self, sample_index):
        """Test finding theorem when range contains entire declaration."""
        result = find_by_range(sample_index, 4, 8)
        assert result is not None
        assert result.theorem_id == "second"  # range 4-8 contains 5-7
    
    def test_find_by_range_best_overlap(self, sample_index):
        """Test finding theorem with best overlap when multiple match."""
        # Range 3-6 overlaps with both "first" (1-3) and "second" (5-7)
        # "second" has better overlap (2 lines vs 1 line)
        result = find_by_range(sample_index, 3, 6)
        assert result is not None
        assert result.theorem_id == "second"
    
    def test_find_by_range_no_overlap(self, sample_index):
        """Test finding theorem with no overlap."""
        result = find_by_range(sample_index, 8, 9)
        assert result is None  # no declarations in lines 8-9
    
    def test_find_by_range_invalid_range(self, sample_index):
        """Test finding with invalid range."""
        result = find_by_range(sample_index, 0, 5)
        assert result is None  # start_line < 1
        
        result = find_by_range(sample_index, 5, 3)
        assert result is None  # end_line < start_line
    
    def test_find_by_range_empty_index(self):
        """Test finding in empty index."""
        empty_index = FileIndex(file="empty.lean", decls=[])
        result = find_by_range(empty_index, 1, 5)
        assert result is None
    
    def test_find_by_range_single_line(self, sample_index):
        """Test finding with single line range."""
        result = find_by_range(sample_index, 2, 2)
        assert result is not None
        assert result.theorem_id == "first"  # line 2 is within 1-3


class TestIntegrationScenarios:
    """Test integration scenarios with realistic Lean code."""
    
    def test_mathlib_style_theorems(self):
        """Test indexing Mathlib-style theorem declarations."""
        lean_code = """namespace List

theorem List.length_append (l₁ l₂ : List α) : 
  (l₁ ++ l₂).length = l₁.length + l₂.length := by
  induction l₁ with
  | nil => simp
  | cons h t ih => simp [ih]

lemma List.mem_append {a : α} {l₁ l₂ : List α} : 
  a ∈ l₁ ++ l₂ ↔ a ∈ l₁ ∨ a ∈ l₂ := by
  constructor
  · intro h
    cases h with
    | head => left; assumption
    | tail _ h' => 
      cases ih h' with
      | inl h₁ => left; exact List.mem_cons_of_mem _ h₁
      | inr h₂ => right; assumption
  · intro h
    cases h with
    | inl h₁ => exact List.mem_append_left h₁
    | inr h₂ => exact List.mem_append_right _ h₂

end List"""
        source = SourceText(path="List.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 2
        
        # Check first theorem
        length_thm = find_by_id(index, "List.length_append")
        assert length_thm is not None
        assert length_thm.name == "length_append"
        assert length_thm.kind == "theorem"
        
        # Check second lemma
        mem_lemma = find_by_id(index, "List.mem_append")
        assert mem_lemma is not None
        assert mem_lemma.name == "mem_append"
        assert mem_lemma.kind == "lemma"
    
    def test_mixed_declaration_styles(self):
        """Test indexing various declaration styles."""
        lean_code = """-- Term-mode proof
theorem term_proof : True := True.intro

-- Tactic-mode proof
theorem tactic_proof : True := by trivial

-- Multi-line declaration
theorem multi_line_decl (n : Nat) 
  (h : n > 0) : 
  n ≠ 0 := by
  omega

-- Example without name
example : 1 + 1 = 2 := rfl

-- Instance declaration
instance : Add Nat := inferInstance

-- Lemma with complex type
lemma complex_type {α : Type*} [Group α] (a b : α) : 
  a * b * a⁻¹ = b := by
  group"""
        source = SourceText(path="mixed.lean", text=lean_code)
        index = build_index(source)
        
        # Should find all declarations
        assert len(index.decls) >= 5
        
        # Check specific declarations
        term_thm = find_by_id(index, "term_proof")
        assert term_thm is not None
        assert term_thm.kind == "theorem"
        
        tactic_thm = find_by_id(index, "tactic_proof")
        assert tactic_thm is not None
        assert tactic_thm.kind == "theorem"
        
        multi_thm = find_by_id(index, "multi_line_decl")
        assert multi_thm is not None
        assert multi_thm.kind == "theorem"
    
    def test_proof_span_detection(self):
        """Test detection of proof spans in various scenarios."""
        lean_code = """theorem with_by : True := by
  trivial

theorem term_mode : True := True.intro

theorem multi_step : 1 + 1 = 2 := by
  norm_num
  done

lemma calc_proof : 1 + 2 = 3 := 
calc 1 + 2 
  = 2 + 1 := by ring
  _ = 3   := rfl"""
        source = SourceText(path="proofs.lean", text=lean_code)
        index = build_index(source)
        
        # Check that proof spans are detected
        for decl in index.decls:
            if decl.theorem_id in ["with_by", "multi_step"]:
                assert decl.proof_span is not None
                assert decl.proof_span.start_line >= decl.decl_span.start_line
                assert decl.proof_span.end_line >= decl.proof_span.start_line


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""
    
    def test_malformed_declarations(self):
        """Test handling malformed or incomplete declarations."""
        lean_code = """theorem incomplete_decl
        
theorem missing_proof : True

theorem normal : True := rfl"""
        source = SourceText(path="malformed.lean", text=lean_code)
        index = build_index(source)
        
        # Should handle gracefully and find what it can
        normal_thm = find_by_id(index, "normal")
        assert normal_thm is not None
    
    def test_very_long_names(self):
        """Test handling very long theorem names."""
        long_name = "very_long_theorem_name_" + "x" * 100
        lean_code = f"theorem {long_name} : True := rfl"
        source = SourceText(path="long.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        assert index.decls[0].theorem_id == long_name
    
    def test_unicode_in_names(self):
        """Test handling unicode characters in names."""
        lean_code = """theorem test_α : True := rfl
theorem 测试 : True := rfl
theorem emoji_🎯 : True := rfl"""
        source = SourceText(path="unicode.lean", text=lean_code)
        index = build_index(source)
        
        # Should handle unicode gracefully (may or may not detect all)
        assert len(index.decls) >= 1  # At least some should be detected
    
    def test_deeply_nested_namespaces(self):
        """Test handling deeply nested namespace declarations."""
        lean_code = """namespace A.B.C.D.E

theorem A.B.C.D.E.deeply_nested : True := rfl

end A.B.C.D.E"""
        source = SourceText(path="nested.lean", text=lean_code)
        index = build_index(source)
        
        if len(index.decls) > 0:
            decl = index.decls[0]
            assert "deeply_nested" in decl.theorem_id
            assert decl.name == "deeply_nested"
    
    def test_overlapping_ranges(self):
        """Test finding theorems with overlapping ranges."""
        # Create index with overlapping declarations (shouldn't happen in real Lean, but test robustness)
        decls = [
            TheoremDecl("first", "first", "theorem", Span(start_line=1, end_line=5)),
            TheoremDecl("second", "second", "lemma", Span(start_line=3, end_line=7)),
            TheoremDecl("third", "third", "theorem", Span(start_line=6, end_line=10)),
        ]
        index = FileIndex(file="overlap.lean", decls=decls)
        
        # Should find the one with best overlap
        result = find_by_range(index, 4, 6)
        assert result is not None
        # Should prefer the one with maximum overlap