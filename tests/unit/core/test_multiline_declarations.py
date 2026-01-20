"""Tests for multi-line declaration handling improvements."""

import pytest
from src.lean_proof_auto_mcp.core.source import SourceText
from src.lean_proof_auto_mcp.core.indexer import build_index


class TestMultiLineDeclarations:
    """Test enhanced multi-line declaration handling."""

    def test_long_parameter_list(self):
        """Test theorem with very long parameter list spanning multiple lines."""
        lean_code = """theorem very_long_theorem_name_with_many_parameters
    {R S T : Type*} [Semiring R] [Semiring S] [Semiring T]
    {f : R →+* S} {g : S →+* T} {h : R →+* T}
    {x : R} {y : S} {z : T}
    (hfg : h = g.comp f)
    (hxy : g (f x) = y)
    : some_complex_property x y z := by
  sorry"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        
        assert decl.theorem_id == "very_long_theorem_name_with_many_parameters"
        assert decl.name == "very_long_theorem_name_with_many_parameters"
        assert decl.kind == "theorem"
        
        # Declaration should span from line 1 to line 7 (where the colon is)
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 7
        
        # Proof should start at line 7 (where := by is)
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 7

    def test_theorem_name_on_separate_line(self):
        """Test theorem where name is on a separate line from keyword."""
        lean_code = """theorem
  another_complex_theorem
    {α β : Type*} [Group α] [Group β]
    : α × β ≃* β × α := by
  sorry"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        
        assert decl.theorem_id == "another_complex_theorem"
        assert decl.name == "another_complex_theorem"
        assert decl.kind == "theorem"
        
        # Declaration should span from line 1 to line 4 (where the colon is)
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 4

    def test_distant_colon_theorem(self):
        """Test theorem with colon very far from theorem keyword."""
        lean_code = """theorem distant_colon_theorem
    {R : Type*} [Ring R]
    {p q r s t u v w : R[X]}
    (h1 : p * q = r)
    (h2 : s * t = u)
    (h3 : v * w = p)
    (h4 : some_condition p q r s t u v w)
    (h5 : another_condition p q)
    : final_conclusion p q r s t u v w := by
  sorry"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        
        assert decl.theorem_id == "distant_colon_theorem"
        assert decl.name == "distant_colon_theorem"
        assert decl.kind == "theorem"
        
        # Declaration should span from line 1 to line 9 (where the colon is)
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 9
        
        # Proof should start at line 9
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 9

    def test_anonymous_theorem_with_immediate_parameters(self):
        """Test anonymous theorem with immediate parameters."""
        lean_code = """theorem {R : Type*} [Ring R] (x y : R) : x + y = y + x := by
  ring"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        
        # Should generate anonymous name
        assert decl.theorem_id.startswith("theorem_")
        assert decl.name.startswith("theorem_")
        assert decl.kind == "theorem"
        
        # Declaration should be on line 1 only (single line)
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 1

    def test_complex_type_annotations(self):
        """Test theorem with complex type annotations."""
        lean_code = """theorem complex_type_theorem
    {F : Type*} [Field F]
    {V : Type*} [AddCommGroup V] [Module F V]
    {W : Type*} [AddCommGroup W] [Module F W]
    (f : V →ₗ[F] W)
    (hf : Function.Injective f)
    : ∃ (g : W →ₗ[F] V), g.comp f = LinearMap.id := by
  sorry"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        
        assert decl.theorem_id == "complex_type_theorem"
        assert decl.name == "complex_type_theorem"
        assert decl.kind == "theorem"
        
        # Declaration should span from line 1 to line 7 (where the colon is)
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 7

    def test_type_annotation_colons_ignored(self):
        """Test that type annotation colons don't interfere with main colon detection."""
        lean_code = """theorem test_colons
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
        
        assert decl.theorem_id == "test_colons"
        assert decl.name == "test_colons"
        
        # Declaration should span to line 6 (where the main colon is)
        # NOT to line 2 where the first type annotation colon appears
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 6

    def test_mathlib_style_declaration(self):
        """Test real Mathlib-style multi-line declaration."""
        lean_code = """theorem eval₂_congr {R S : Type*} [Semiring R] [Semiring S] {f g : R →+* S} {s t : S}
    {φ ψ : R[X]} : f = g → s = t → φ = ψ → eval₂ f s φ = eval₂ g t ψ := by
  rintro rfl rfl rfl; rfl"""
        
        source = SourceText(path="test.lean", text=lean_code)
        index = build_index(source)
        
        assert len(index.decls) == 1
        decl = index.decls[0]
        
        assert decl.theorem_id == "eval₂_congr"
        assert decl.name == "eval₂_congr"
        assert decl.kind == "theorem"
        
        # Declaration should span from line 1 to line 2 (where the colon is)
        assert decl.decl_span.start_line == 1
        assert decl.decl_span.end_line == 2
        
        # Proof should start at line 2
        assert decl.proof_span is not None
        assert decl.proof_span.start_line == 2