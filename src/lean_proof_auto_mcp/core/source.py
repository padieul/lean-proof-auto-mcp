"""Source text representation and location utilities.

This module provides data structures and functions for representing
source text and extracting content from specific locations.
"""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Span:
    """Represents a location span in source text.
    
    Lines are 1-indexed. Columns are 0-indexed and optional in v0.1.
    """
    start_line: int
    start_col: int = 0  # optional in v0.1, defaults to 0
    end_line: int = 0
    end_col: int = 0    # optional in v0.1, defaults to 0
    
    def __post_init__(self) -> None:
        """Validate span invariants."""
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line == 0:
            # If end_line not specified, default to start_line
            object.__setattr__(self, 'end_line', self.start_line)
        if self.end_line < self.start_line:
            raise ValueError(f"end_line ({self.end_line}) must be >= start_line ({self.start_line})")


@dataclass(frozen=True)
class SourceText:
    """Represents source text with utilities for extracting content."""
    path: str
    text: str
    
    def get_lines(self, start: int, end: int) -> list[str]:
        """Extract lines [start, end] (1-indexed, inclusive).
        
        Args:
            start: Starting line number (1-indexed)
            end: Ending line number (1-indexed, inclusive)
            
        Returns:
            List of lines in the specified range
            
        Raises:
            ValueError: If start < 1 or end < start
        """
        if start < 1:
            raise ValueError(f"start must be >= 1, got {start}")
        if end < start:
            raise ValueError(f"end ({end}) must be >= start ({start})")
            
        if not self.text:
            return []
            
        lines = self.text.splitlines()
        
        # Convert to 0-indexed for slicing
        start_idx = start - 1
        end_idx = end  # end is inclusive, so we don't subtract 1
        
        # Handle bounds safely
        start_idx = max(0, start_idx)
        end_idx = min(len(lines), end_idx)
        
        return lines[start_idx:end_idx]
    
    def get_span_text(self, span: Span) -> str:
        """Extract text within the given span with enhanced proof text extraction.
        
        Enhanced to better handle proof text extraction by:
        1. Properly handling column-based extraction for single-line spans
        2. Better multi-line span extraction with precise boundaries
        3. Improved handling of indentation and whitespace preservation
        
        Args:
            span: The span to extract text from
            
        Returns:
            The text content within the span, properly extracted for proof analysis
        """
        lines = self.get_lines(span.start_line, span.end_line)
        
        if not lines:
            return ""
        
        if len(lines) == 1:
            # Single line span - use column information for precise extraction
            line = lines[0]
            if span.start_col > 0 or span.end_col > 0:
                start_col = span.start_col
                end_col = span.end_col if span.end_col > 0 else len(line)
                extracted = line[start_col:end_col]
                # For single-line proofs, strip leading/trailing whitespace but preserve structure
                return extracted.strip()
            return line.strip()
        
        # Multi-line span - handle proof text extraction carefully
        result_lines = []
        
        # First line - from start_col to end, preserving proof structure
        first_line = lines[0]
        if span.start_col > 0:
            first_line = first_line[span.start_col:]
        
        # For proof text, if the first line is just whitespace after extraction,
        # skip it and start from the next line (common with "by" on its own line)
        if first_line.strip():
            result_lines.append(first_line.rstrip())
        
        # Process all remaining lines (middle + last)
        remaining_lines = lines[1:] if len(lines) > 1 else []
        
        # Handle last line end_col constraint
        if remaining_lines and span.end_col > 0:
            # Apply end_col constraint to the last line
            remaining_lines[-1] = remaining_lines[-1][:span.end_col]
        
        # Find the base indentation level from non-empty lines
        # Look for the most common indentation level (excluding special patterns like |)
        indentation_counts = {}
        for line in remaining_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('--'):  # Skip empty lines and comments
                line_indent = len(line) - len(line.lstrip())
                # Don't count lines that start with special patterns as base indentation
                if not stripped.startswith(('|', '·', 'case ', 'next ')):
                    indentation_counts[line_indent] = indentation_counts.get(line_indent, 0) + 1
        
        # Find the most common indentation level
        base_indent = 0
        if indentation_counts:
            base_indent = max(indentation_counts.items(), key=lambda x: x[1])[0]
        
        # Add remaining lines with normalized indentation
        for line in remaining_lines:
            stripped = line.strip()
            if stripped:  # Non-empty line
                if len(line) >= base_indent:
                    # Remove base indentation to normalize proof text
                    normalized_line = line[base_indent:]
                    result_lines.append(normalized_line.rstrip())
                else:
                    # Line has less indentation than base - keep as is
                    result_lines.append(line.rstrip())
            else:
                # Preserve empty lines in proof structure
                result_lines.append("")
        
        # Join lines and clean up the result
        result = "\n".join(result_lines)
        
        # Remove leading/trailing empty lines but preserve internal structure
        result_lines = result.split('\n')
        while result_lines and not result_lines[0].strip():
            result_lines.pop(0)
        while result_lines and not result_lines[-1].strip():
            result_lines.pop()
        
        return "\n".join(result_lines)


# Pure functions for working with source text

def get_lines(source: SourceText, start: int, end: int) -> list[str]:
    """Safe line slicing with bounds checking.
    
    Args:
        source: The source text to extract from
        start: Starting line number (1-indexed)
        end: Ending line number (1-indexed, inclusive)
        
    Returns:
        List of lines in the specified range
    """
    return source.get_lines(start, end)


def get_span_text(source: SourceText, span: Span) -> str:
    """Extract text from span.
    
    Args:
        source: The source text to extract from
        span: The span to extract text from
        
    Returns:
        The text content within the span
    """
    return source.get_span_text(span)


def line_count(source: SourceText) -> int:
    """Get total number of lines in source text.
    
    Args:
        source: The source text to count lines in
        
    Returns:
        Total number of lines
    """
    if not source.text:
        return 0
    return len(source.text.splitlines())