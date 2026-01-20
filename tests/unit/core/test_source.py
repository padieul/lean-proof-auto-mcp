"""Unit tests for core.source module."""

import pytest
from lean_proof_auto_mcp.core.source import (
    Span,
    SourceText,
    get_lines,
    get_span_text,
    line_count,
)


class TestSpan:
    """Test cases for Span dataclass."""
    
    def test_span_creation_valid(self):
        """Test creating valid spans."""
        span = Span(start_line=1, end_line=5)
        assert span.start_line == 1
        assert span.end_line == 5
        assert span.start_col == 0  # default
        assert span.end_col == 0    # default
    
    def test_span_creation_with_columns(self):
        """Test creating spans with column information."""
        span = Span(start_line=2, start_col=5, end_line=3, end_col=10)
        assert span.start_line == 2
        assert span.start_col == 5
        assert span.end_line == 3
        assert span.end_col == 10
    
    def test_span_auto_end_line(self):
        """Test that end_line defaults to start_line when not specified."""
        span = Span(start_line=5)
        assert span.start_line == 5
        assert span.end_line == 5
    
    def test_span_invalid_start_line(self):
        """Test that start_line must be >= 1."""
        with pytest.raises(ValueError, match="start_line must be >= 1"):
            Span(start_line=0)
        
        with pytest.raises(ValueError, match="start_line must be >= 1"):
            Span(start_line=-1)
    
    def test_span_invalid_end_line(self):
        """Test that end_line must be >= start_line."""
        with pytest.raises(ValueError, match="end_line .* must be >= start_line"):
            Span(start_line=5, end_line=3)


class TestSourceText:
    """Test cases for SourceText dataclass."""
    
    @pytest.fixture
    def sample_source(self):
        """Sample source text for testing."""
        text = """theorem example : True := by
  -- This is a comment
  trivial
  
def helper : Nat := 42

lemma simple : 1 + 1 = 2 := rfl"""
        return SourceText(path="test.lean", text=text)
    
    def test_source_creation(self):
        """Test creating SourceText."""
        source = SourceText(path="test.lean", text="hello\nworld")
        assert source.path == "test.lean"
        assert source.text == "hello\nworld"
    
    def test_get_lines_single_line(self, sample_source):
        """Test extracting a single line."""
        lines = sample_source.get_lines(1, 1)
        assert lines == ["theorem example : True := by"]
    
    def test_get_lines_multiple_lines(self, sample_source):
        """Test extracting multiple lines."""
        lines = sample_source.get_lines(2, 4)
        assert lines == ["  -- This is a comment", "  trivial", "  "]
    
    def test_get_lines_all_lines(self, sample_source):
        """Test extracting all lines."""
        lines = sample_source.get_lines(1, 7)
        expected = [
            "theorem example : True := by",
            "  -- This is a comment", 
            "  trivial",
            "  ",
            "def helper : Nat := 42",
            "",
            "lemma simple : 1 + 1 = 2 := rfl"
        ]
        assert lines == expected
    
    def test_get_lines_out_of_bounds(self, sample_source):
        """Test extracting lines beyond file bounds."""
        # Should handle gracefully by clamping to available lines
        lines = sample_source.get_lines(5, 10)
        assert lines == ["def helper : Nat := 42", "", "lemma simple : 1 + 1 = 2 := rfl"]
    
    def test_get_lines_invalid_range(self, sample_source):
        """Test invalid line ranges."""
        with pytest.raises(ValueError, match="start must be >= 1"):
            sample_source.get_lines(0, 5)
        
        with pytest.raises(ValueError, match="end .* must be >= start"):
            sample_source.get_lines(5, 3)
    
    def test_get_span_text_single_line_full(self, sample_source):
        """Test extracting full single line span."""
        span = Span(start_line=1, end_line=1)
        text = sample_source.get_span_text(span)
        assert text == "theorem example : True := by"
    
    def test_get_span_text_single_line_partial(self, sample_source):
        """Test extracting partial single line span with columns."""
        span = Span(start_line=1, start_col=8, end_line=1, end_col=15)
        text = sample_source.get_span_text(span)
        assert text == "example"
    
    def test_get_span_text_multi_line(self, sample_source):
        """Test extracting multi-line span."""
        span = Span(start_line=1, end_line=3)
        text = sample_source.get_span_text(span)
        expected = "theorem example : True := by\n  -- This is a comment\n  trivial"
        assert text == expected
    
    def test_get_span_text_multi_line_with_columns(self, sample_source):
        """Test extracting multi-line span with column bounds."""
        span = Span(start_line=1, start_col=8, end_line=3, end_col=4)
        text = sample_source.get_span_text(span)
        expected = "example : True := by\n  -- This is a comment\n  tr"
        assert text == expected
    
    def test_get_span_text_empty_span(self, sample_source):
        """Test extracting from empty or invalid span."""
        span = Span(start_line=10, end_line=10)  # Beyond file bounds
        text = sample_source.get_span_text(span)
        assert text == ""


class TestPureFunctions:
    """Test cases for pure functions."""
    
    @pytest.fixture
    def sample_source(self):
        """Sample source text for testing."""
        text = "line1\nline2\nline3"
        return SourceText(path="test.lean", text=text)
    
    def test_get_lines_function(self, sample_source):
        """Test get_lines pure function."""
        lines = get_lines(sample_source, 1, 2)
        assert lines == ["line1", "line2"]
    
    def test_get_span_text_function(self, sample_source):
        """Test get_span_text pure function."""
        span = Span(start_line=2, end_line=3)
        text = get_span_text(sample_source, span)
        assert text == "line2\nline3"
    
    def test_line_count_function(self, sample_source):
        """Test line_count pure function."""
        count = line_count(sample_source)
        assert count == 3
    
    def test_line_count_empty_file(self):
        """Test line count for empty file."""
        source = SourceText(path="empty.lean", text="")
        count = line_count(source)
        assert count == 0  # Empty string should return 0 lines
    
    def test_line_count_single_line(self):
        """Test line count for single line file."""
        source = SourceText(path="single.lean", text="single line")
        count = line_count(source)
        assert count == 1


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""
    
    def test_empty_text(self):
        """Test handling empty text."""
        source = SourceText(path="empty.lean", text="")
        lines = source.get_lines(1, 1)
        assert lines == []
    
    def test_single_character(self):
        """Test handling single character text."""
        source = SourceText(path="char.lean", text="x")
        span = Span(start_line=1, start_col=0, end_line=1, end_col=1)
        text = source.get_span_text(span)
        assert text == "x"
    
    def test_text_with_only_newlines(self):
        """Test handling text with only newlines."""
        source = SourceText(path="newlines.lean", text="\n\n\n")
        lines = source.get_lines(1, 4)
        assert lines == ["", "", ""]
        assert line_count(source) == 3
    
    def test_text_without_final_newline(self):
        """Test handling text without final newline."""
        source = SourceText(path="no_newline.lean", text="line1\nline2")
        lines = source.get_lines(1, 2)
        assert lines == ["line1", "line2"]
    
    def test_span_at_line_boundary(self):
        """Test span extraction at line boundaries."""
        source = SourceText(path="boundary.lean", text="abc\ndef\nghi")
        
        # Test end of first line
        span = Span(start_line=1, start_col=2, end_line=1, end_col=3)
        text = source.get_span_text(span)
        assert text == "c"
        
        # Test start of second line  
        span = Span(start_line=2, start_col=0, end_line=2, end_col=1)
        text = source.get_span_text(span)
        assert text == "d"