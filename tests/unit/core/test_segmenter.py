"""Unit tests for core/segmenter.py module."""

import pytest
from lean_proof_auto_mcp.core.segmenter import (
    ProofBlock, CaseBlock, ProofStructure,
    segment_proof, extract_skeleton, identify_blocks, extract_cases,
    _classify_line
)
from lean_proof_auto_mcp.core.source import SourceText, Span
from lean_proof_auto_mcp.core.indexer import TheoremDecl


class TestProofBlock:
    """Test ProofBlock dataclass."""
    
    def test_valid_proof_block(self):
        """Test creating valid proof blocks."""
        span = Span(start_line=1, end_line=3)
        
        # Test all valid kinds
        for kind in ["skeleton", "rewrite_simp", "closing", "unknown"]:
            block = ProofBlock(kind=kind, span=span)
            assert block.kind == kind
            assert block.span == span
    
    def test_invalid_proof_block_kind(self):
        """Test that invalid kinds raise ValueError."""
        span = Span(start_line=1, end_line=3)
        
        with pytest.raises(ValueError, match="Invalid block kind"):
            ProofBlock(kind="invalid", span=span)


class TestCaseBlock:
    """Test CaseBlock dataclass."""
    
    def test_valid_case_block(self):
        """Test creating valid case blocks."""
        span = Span(start_line=1, end_line=3)
        block = CaseBlock(label="zero", span=span)
        
        assert block.label == "zero"
        assert block.span == span
    
    def test_empty_label_raises_error(self):
        """Test that empty labels raise ValueError."""
        span = Span(start_line=1, end_line=3)
        
        with pytest.raises(ValueError, match="Case label cannot be empty"):
            CaseBlock(label="", span=span)


class TestProofStructure:
    """Test ProofStructure dataclass."""
    
    def test_empty_proof_structure(self):
        """Test creating empty proof structure."""
        structure = ProofStructure(skeleton=[], blocks=[], cases=[])
        
        assert structure.skeleton == []
        assert structure.blocks == []
        assert structure.cases == []
    
    def test_proof_structure_with_data(self):
        """Test creating proof structure with data."""
        skeleton = ["intro", "cases"]
        blocks = [ProofBlock(kind="skeleton", span=Span(1, 1, 2, 0))]
        cases = [CaseBlock(label="zero", span=Span(2, 0, 3, 0))]
        
        structure = ProofStructure(skeleton=skeleton, blocks=blocks, cases=cases)
        
        assert structure.skeleton == skeleton
        assert structure.blocks == blocks
        assert structure.cases == cases


class TestExtractSkeleton:
    """Test extract_skeleton function."""
    
    def test_empty_proof(self):
        """Test skeleton extraction from empty proof."""
        result = extract_skeleton("")
        assert result == []
    
    def test_simple_structural_tactics(self):
        """Test extraction of basic structural tactics."""
        proof_text = """
        intro h
        cases h with
        | zero => exact rfl
        | succ n => apply ih
        """
        
        result = extract_skeleton(proof_text)
        assert "intro" in result
        assert "cases" in result
        assert "apply" in result
        
        # Should preserve order of first appearance
        assert result.index("intro") < result.index("cases")
        assert result.index("cases") < result.index("apply")
    
    def test_no_duplicates_in_skeleton(self):
        """Test that skeleton doesn't contain duplicates."""
        proof_text = """
        intro h1
        intro h2
        cases h1
        cases h2
        """
        
        result = extract_skeleton(proof_text)
        assert result.count("intro") == 1
        assert result.count("cases") == 1
    
    def test_case_insensitive_matching(self):
        """Test that tactic matching is case insensitive."""
        proof_text = """
        INTRO h
        Cases x with
        APPLY theorem
        """
        
        result = extract_skeleton(proof_text)
        assert "intro" in result
        assert "cases" in result
        assert "apply" in result
    
    def test_word_boundary_matching(self):
        """Test that tactics are matched with word boundaries."""
        proof_text = """
        -- This should not match 'intro' in 'introduction'
        introduction_lemma
        intro h  -- This should match
        """
        
        result = extract_skeleton(proof_text)
        assert result == ["intro"]


class TestClassifyLine:
    """Test _classify_line function."""
    
    def test_skeleton_tactics(self):
        """Test classification of structural tactics."""
        skeleton_lines = [
            "intro h",
            "cases x with",
            "apply theorem",
            "have h : P := by simp",
            "suffices : Q by exact h"
        ]
        
        for line in skeleton_lines:
            assert _classify_line(line) == "skeleton"
    
    def test_rewrite_simp_tactics(self):
        """Test classification of rewrite/simp tactics."""
        rewrite_lines = [
            "rw [theorem]",
            "simp only [lemma]",
            "simp_rw [eq]",
            "field_simp",
            "dsimp at h"
        ]
        
        for line in rewrite_lines:
            assert _classify_line(line) == "rewrite_simp"
    
    def test_closing_tactics(self):
        """Test classification of closing tactics."""
        closing_lines = [
            "exact h",
            "rfl",
            "trivial",
            "done",
            "assumption",
            "linarith"
        ]
        
        for line in closing_lines:
            assert _classify_line(line) == "closing"
    
    def test_unknown_lines(self):
        """Test classification of unknown lines."""
        unknown_lines = [
            "",
            "-- comment",
            "some_custom_tactic",
            "variable (x : Nat)"
        ]
        
        for line in unknown_lines:
            assert _classify_line(line) == "unknown"


class TestIdentifyBlocks:
    """Test identify_blocks function."""
    
    def test_empty_proof_lines(self):
        """Test block identification with empty proof."""
        result = identify_blocks([], 1)
        assert result == []
    
    def test_single_block(self):
        """Test identification of single homogeneous block."""
        proof_lines = [
            "intro h",
            "cases h with",
            "apply theorem"
        ]
        
        result = identify_blocks(proof_lines, 10)
        assert len(result) == 1
        assert result[0].kind == "skeleton"
        assert result[0].span.start_line == 10
        assert result[0].span.end_line == 12
    
    def test_multiple_blocks(self):
        """Test identification of multiple different blocks."""
        proof_lines = [
            "intro h",           # skeleton
            "cases h with",      # skeleton  
            "rw [theorem]",      # rewrite_simp
            "simp only [lemma]", # rewrite_simp
            "exact h"            # closing
        ]
        
        result = identify_blocks(proof_lines, 5)
        assert len(result) == 3
        
        # First block: skeleton
        assert result[0].kind == "skeleton"
        assert result[0].span.start_line == 5
        assert result[0].span.end_line == 6
        
        # Second block: rewrite_simp
        assert result[1].kind == "rewrite_simp"
        assert result[1].span.start_line == 7
        assert result[1].span.end_line == 8
        
        # Third block: closing
        assert result[2].kind == "closing"
        assert result[2].span.start_line == 9
        assert result[2].span.end_line == 9
    
    def test_blocks_with_empty_lines(self):
        """Test that empty lines are skipped in block identification."""
        proof_lines = [
            "intro h",
            "",
            "cases h with",
            "",
            "",
            "exact rfl"
        ]
        
        result = identify_blocks(proof_lines, 1)
        assert len(result) == 2
        
        # Should group intro and cases together as skeleton
        assert result[0].kind == "skeleton"
        assert result[1].kind == "closing"


class TestExtractCases:
    """Test extract_cases function."""
    
    def test_empty_proof(self):
        """Test case extraction from empty proof."""
        result = extract_cases("", 1)
        assert result == []
    
    def test_case_with_arrow_syntax(self):
        """Test extraction of cases with => syntax."""
        proof_text = """
        cases h with
        | zero => exact rfl
        | succ n => apply ih
        """
        
        result = extract_cases(proof_text, 10)
        assert len(result) == 2
        
        assert result[0].label == "zero"
        assert result[0].span.start_line == 12  # Line with "| zero =>"
        
        assert result[1].label == "succ"
        assert result[1].span.start_line == 13  # Line with "| succ n =>"
    
    def test_case_with_colon_syntax(self):
        """Test extraction of cases with : syntax."""
        proof_text = """
        induction n with
        case zero:
          exact rfl
        case succ n ih:
          apply theorem
        """
        
        result = extract_cases(proof_text, 5)
        assert len(result) == 2
        
        assert result[0].label == "zero"
        assert result[1].label == "succ"
    
    def test_bullet_point_cases(self):
        """Test extraction of bullet point cases."""
        proof_text = """
        cases h with
        · -- zero case
          exact rfl
        · -- succ case  
          apply ih
        """
        
        result = extract_cases(proof_text, 1)
        assert len(result) == 2
        
        assert result[0].label == "zero"
        assert result[1].label == "succ"
    
    def test_simple_bullet_cases(self):
        """Test extraction of simple bullet cases."""
        proof_text = """
        cases h with
        · zero
          exact rfl
        · succ
          apply ih
        """
        
        result = extract_cases(proof_text, 1)
        assert len(result) == 2
        
        assert result[0].label == "zero"
        assert result[1].label == "succ"


class TestSegmentProof:
    """Test segment_proof function."""
    
    def test_theorem_without_proof(self):
        """Test segmentation of theorem without proof."""
        source = SourceText(path="test.lean", text="theorem test : P := sorry")
        decl = TheoremDecl(
            theorem_id="test",
            name="test", 
            kind="theorem",
            decl_span=Span(1, 0, 1, 0),
            proof_span=None
        )
        
        result = segment_proof(source, decl)
        
        assert result.skeleton == []
        assert result.blocks == []
        assert result.cases == []
    
    def test_simple_proof_segmentation(self):
        """Test segmentation of simple proof."""
        proof_text = """theorem test : P → Q := by
  intro h
  cases h with
  | zero => exact rfl
  | succ n => apply ih"""
        
        source = SourceText(path="test.lean", text=proof_text)
        decl = TheoremDecl(
            theorem_id="test",
            name="test",
            kind="theorem", 
            decl_span=Span(1, 0, 5, 0),
            proof_span=Span(1, 30, 5, 20)  # Just the "by ..." part
        )
        
        result = segment_proof(source, decl)
        
        # Should extract skeleton
        assert "intro" in result.skeleton
        assert "cases" in result.skeleton
        
        # Should identify blocks
        assert len(result.blocks) >= 1
        
        # Should extract cases
        assert len(result.cases) == 2
        assert any(case.label == "zero" for case in result.cases)
        assert any(case.label == "succ" for case in result.cases)
    
    def test_complex_proof_structure(self):
        """Test segmentation of more complex proof."""
        proof_text = """theorem complex_theorem : P := by
  intro h1 h2
  have aux : Q := by simp
  cases h1 with
  | zero => 
    rw [theorem1]
    simp only [lemma1]
    exact aux
  | succ n =>
    apply induction_hypothesis
    exact rfl"""
        
        source = SourceText(path="test.lean", text=proof_text)
        decl = TheoremDecl(
            theorem_id="complex_theorem",
            name="complex_theorem",
            kind="theorem",
            decl_span=Span(1, 0, 11, 0),
            proof_span=Span(1, 35, 11, 15)
        )
        
        result = segment_proof(source, decl)
        
        # Should have rich skeleton
        assert "intro" in result.skeleton
        assert "cases" in result.skeleton
        assert "apply" in result.skeleton
        
        # Should have multiple block types
        block_kinds = {block.kind for block in result.blocks}
        assert "skeleton" in block_kinds
        
        # Should extract cases
        case_labels = {case.label for case in result.cases}
        assert "zero" in case_labels
        assert "succ" in case_labels