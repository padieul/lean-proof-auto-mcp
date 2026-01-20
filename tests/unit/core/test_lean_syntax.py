"""Unit tests for core.lean_syntax module."""

import pytest
from src.lean_proof_auto_mcp.core.lean_syntax import (
    strip_comments,
    detect_string_literals,
    normalize_whitespace,
    get_indentation_level,
)
from src.lean_proof_auto_mcp.core.source import Span


class TestStripComments:
    """Test cases for strip_comments function."""
    
    def test_strip_single_line_comments(self):
        """Test removing single-line comments."""
        text = "theorem test : True := by -- this is a comment\n  trivial"
        result = strip_comments(text)
        expected = "theorem test : True := by \n  trivial"
        assert result == expected
    
    def test_strip_multi_line_comments(self):
        """Test removing multi-line comments."""
        text = "theorem test /- this is\na multi-line comment -/ : True := by\n  trivial"
        result = strip_comments(text)
        expected = "theorem test  : True := by\n  trivial"
        assert result == expected
    
    def test_strip_nested_multi_line_comments(self):
        """Test removing nested multi-line comments."""
        text = "theorem test /- outer /- inner -/ comment -/ : True"
        result = strip_comments(text)
        expected = "theorem test  : True"
        assert result == expected
    
    def test_strip_mixed_comments(self):
        """Test removing both types of comments."""
        text = """theorem example : True := by
  /- multi-line comment -/
  -- single line comment
  trivial"""
        result = strip_comments(text)
        expected = """theorem example : True := by
  
  
  trivial"""
        assert result == expected
    
    def test_comments_in_middle_of_line(self):
        """Test comments that don't start at beginning of line."""
        text = "let x := 42 -- comment\nlet y /- comment -/ := 24"
        result = strip_comments(text)
        expected = "let x := 42 \nlet y  := 24"
        assert result == expected
    
    def test_no_comments(self):
        """Test text without comments."""
        text = "theorem simple : 1 + 1 = 2 := rfl"
        result = strip_comments(text)
        assert result == text
    
    def test_empty_text(self):
        """Test empty text."""
        result = strip_comments("")
        assert result == ""
    
    def test_only_comments(self):
        """Test text that is only comments."""
        text = "-- just a comment\n/- another comment -/"
        result = strip_comments(text)
        expected = "\n"
        assert result == expected
    
    def test_unclosed_multiline_comment(self):
        """Test handling unclosed multi-line comment."""
        text = "theorem test /- unclosed comment\nmore text"
        result = strip_comments(text)
        expected = "theorem test \n"
        assert result == expected


class TestDetectStringLiterals:
    """Test cases for detect_string_literals function."""
    
    def test_simple_string_literal(self):
        """Test detecting simple string literal."""
        text = 'let msg := "hello world"'
        spans = detect_string_literals(text)
        assert len(spans) == 1
        assert spans[0] == Span(start_line=1, start_col=11, end_line=1, end_col=24)
    
    def test_multiple_string_literals(self):
        """Test detecting multiple string literals."""
        text = 'let a := "first"\nlet b := "second"'
        spans = detect_string_literals(text)
        assert len(spans) == 2
        assert spans[0] == Span(start_line=1, start_col=9, end_line=1, end_col=16)
        assert spans[1] == Span(start_line=2, start_col=9, end_line=2, end_col=17)
    
    def test_string_with_escaped_quotes(self):
        """Test string literal with escaped quotes."""
        text = r'let msg := "He said \"hello\""'
        spans = detect_string_literals(text)
        assert len(spans) == 1
        assert spans[0] == Span(start_line=1, start_col=11, end_line=1, end_col=30)
    
    def test_empty_string(self):
        """Test empty string literal."""
        text = 'let empty := ""'
        spans = detect_string_literals(text)
        assert len(spans) == 1
        assert spans[0] == Span(start_line=1, start_col=13, end_line=1, end_col=15)
    
    def test_unclosed_string(self):
        """Test unclosed string literal."""
        text = 'let broken := "unclosed string'
        spans = detect_string_literals(text)
        assert len(spans) == 1
        assert spans[0] == Span(start_line=1, start_col=14, end_line=1, end_col=30)
    
    def test_no_strings(self):
        """Test text without string literals."""
        text = "theorem simple : Nat := 42"
        spans = detect_string_literals(text)
        assert len(spans) == 0
    
    def test_empty_text(self):
        """Test empty text."""
        spans = detect_string_literals("")
        assert len(spans) == 0
    
    def test_string_with_backslash_at_end(self):
        """Test string ending with backslash."""
        text = r'let path := "C:\\"'
        spans = detect_string_literals(text)
        assert len(spans) == 1
        assert spans[0] == Span(start_line=1, start_col=12, end_line=1, end_col=18)


class TestNormalizeWhitespace:
    """Test cases for normalize_whitespace function."""
    
    def test_convert_tabs_to_spaces(self):
        """Test converting tabs to spaces."""
        text = "theorem test :\n\tTrue := by\n\t\ttrivial"
        result = normalize_whitespace(text)
        expected = "theorem test :\n  True := by\n    trivial"
        assert result == expected
    
    def test_mixed_tabs_and_spaces(self):
        """Test handling mixed tabs and spaces."""
        text = "def example :\n \tNat := by\n\t exact 42"
        result = normalize_whitespace(text)
        expected = "def example :\n   Nat := by\n   exact 42"
        assert result == expected
    
    def test_preserve_spaces(self):
        """Test that existing spaces are preserved."""
        text = "theorem test :\n  True := by\n    trivial"
        result = normalize_whitespace(text)
        assert result == text
    
    def test_empty_text(self):
        """Test empty text."""
        result = normalize_whitespace("")
        assert result == ""
    
    def test_no_indentation(self):
        """Test text without indentation."""
        text = "theorem simple : True := rfl"
        result = normalize_whitespace(text)
        assert result == text
    
    def test_only_whitespace_lines(self):
        """Test lines with only whitespace."""
        text = "theorem test :\n\t\n  \n    True"
        result = normalize_whitespace(text)
        expected = "theorem test :\n  \n  \n    True"
        assert result == expected


class TestGetIndentationLevel:
    """Test cases for get_indentation_level function."""
    
    def test_spaces_only(self):
        """Test counting spaces."""
        assert get_indentation_level("    hello") == 4
        assert get_indentation_level("  world") == 2
        assert get_indentation_level(" x") == 1
    
    def test_tabs_only(self):
        """Test counting tabs (2 spaces each)."""
        assert get_indentation_level("\thello") == 2
        assert get_indentation_level("\t\tworld") == 4
        assert get_indentation_level("\t\t\tx") == 6
    
    def test_mixed_tabs_and_spaces(self):
        """Test counting mixed tabs and spaces."""
        assert get_indentation_level("\t hello") == 3  # tab(2) + space(1)
        assert get_indentation_level("  \tworld") == 4  # spaces(2) + tab(2)
        assert get_indentation_level(" \t x") == 4     # space(1) + tab(2) + space(1)
    
    def test_no_indentation(self):
        """Test lines with no indentation."""
        assert get_indentation_level("hello") == 0
        assert get_indentation_level("theorem") == 0
    
    def test_empty_line(self):
        """Test empty line."""
        assert get_indentation_level("") == 0
    
    def test_only_whitespace(self):
        """Test line with only whitespace."""
        assert get_indentation_level("    ") == 4
        assert get_indentation_level("\t\t") == 4
        assert get_indentation_level("  \t ") == 5


class TestIntegrationScenarios:
    """Test integration scenarios with realistic Lean code."""
    
    def test_lean_theorem_with_comments_and_strings(self):
        """Test processing realistic Lean code."""
        lean_code = '''theorem string_example : String := by
  -- Define a string constant
  let msg := "Hello, Lean!" /- inline comment -/
  exact msg -- return the string'''
        
        # Test comment stripping
        no_comments = strip_comments(lean_code)
        assert "-- Define a string constant" not in no_comments
        assert "/- inline comment -/" not in no_comments
        assert "-- return the string" not in no_comments
        
        # Test string detection
        strings = detect_string_literals(lean_code)
        assert len(strings) == 1
        assert strings[0].start_line == 3
        
        # Test whitespace normalization
        normalized = normalize_whitespace(lean_code)
        assert "\t" not in normalized
    
    def test_nested_comments_with_strings(self):
        """Test handling nested comments containing string-like content."""
        text = '''def example : String := 
  /- This comment contains "fake strings" 
     /- nested comment with "more strings" -/
     end of outer comment -/
  "real string"'''
        
        # Strip comments first
        no_comments = strip_comments(text)
        assert "fake strings" not in no_comments
        assert "more strings" not in no_comments
        assert "real string" in no_comments
        
        # Detect strings in comment-stripped text
        strings = detect_string_literals(no_comments)
        assert len(strings) == 1
    
    def test_indentation_analysis(self):
        """Test indentation level analysis."""
        lean_code = '''theorem nested_proof : True := by
  intro
    cases h with
    | left => 
      trivial
    | right =>
      	exact True.intro'''
        
        lines = lean_code.splitlines()
        levels = [get_indentation_level(line) for line in lines]
        
        # Check expected indentation levels
        assert levels[0] == 0  # theorem line
        assert levels[1] == 2  # intro
        assert levels[2] == 4  # cases
        assert levels[3] == 4  # | left
        assert levels[4] == 6  # trivial
        assert levels[5] == 4  # | right
        assert levels[6] == 8  # exact (tab + 2 spaces = 8)


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""
    
    def test_comment_markers_in_strings(self):
        """Test that comment markers inside strings are preserved."""
        text = 'let msg := "This -- is not a comment"'
        result = strip_comments(text)
        assert result == text  # Should be unchanged
        
        text2 = 'let msg := "This /- is not -/ a comment"'
        result2 = strip_comments(text2)
        assert result2 == text2  # Should be unchanged
    
    def test_string_quotes_in_comments(self):
        """Test that string quotes in comments don't affect string detection."""
        text = '''let x := 42 -- comment with "fake string"
let y := "real string"'''
        
        no_comments = strip_comments(text)
        strings = detect_string_literals(no_comments)
        assert len(strings) == 1
        assert "real string" in no_comments
    
    def test_malformed_input(self):
        """Test handling of malformed input."""
        # Unmatched comment delimiters
        text1 = "theorem test -/ : True"
        result1 = strip_comments(text1)
        assert result1 == text1  # Should handle gracefully
        
        # Multiple quote characters
        text2 = 'let x := """triple quotes"""'
        strings = detect_string_literals(text2)
        # Should detect the first string from first quote to second quote
        assert len(strings) >= 1
    
    def test_very_long_lines(self):
        """Test handling very long lines."""
        long_string = '"' + "x" * 1000 + '"'
        text = f"let long := {long_string}"
        
        strings = detect_string_literals(text)
        assert len(strings) == 1
        assert strings[0].end_col - strings[0].start_col == 1002  # quotes + content
    
    def test_unicode_content(self):
        """Test handling unicode content."""
        text = 'let msg := "Hello, 世界! 🌍"'
        strings = detect_string_literals(text)
        assert len(strings) == 1
        
        # Test indentation with unicode
        unicode_line = "  theorem 测试 : True"
        level = get_indentation_level(unicode_line)
        assert level == 2