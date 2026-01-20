"""Source text representation and location utilities.

This module provides data structures and functions for representing
source text and extracting content from specific locations.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """Represents a location span in source text.

    Lines are 1-indexed. Columns are 0-indexed and optional in v0.1.
    """

    start_line: int
    start_col: int = 0  # optional in v0.1, defaults to 0
    end_line: int = 0
    end_col: int = 0  # optional in v0.1, defaults to 0

    def __post_init__(self) -> None:
        """Validate span invariants."""
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line == 0:
            # If end_line not specified, default to start_line
            object.__setattr__(self, "end_line", self.start_line)
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )


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

    def get_span_text(self, span: Span, normalize_for_proof: bool = False) -> str:
        """Extract text within the given span.

        Args:
            span: The span to extract text from
            normalize_for_proof: If True, apply proof-specific normalization

        Returns:
            The text content within the span
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
                return line[start_col:end_col]
            return line

        # Multi-line span
        result_lines = []

        # First line - from start_col to end
        first_line = lines[0]
        if span.start_col > 0:
            first_line = first_line[span.start_col :]
        result_lines.append(first_line)

        # Middle lines (if any)
        if len(lines) > 2:
            result_lines.extend(lines[1:-1])

        # Last line - up to end_col
        if len(lines) > 1:
            last_line = lines[-1]
            if span.end_col > 0:
                last_line = last_line[: span.end_col]
            result_lines.append(last_line)

        result = "\n".join(result_lines)

        # Apply proof-specific normalization if requested
        if normalize_for_proof:
            result = self._normalize_proof_text(result)

        return result

    def _normalize_proof_text(self, text: str) -> str:
        """Apply proof-specific text normalization."""
        lines = text.split("\n")
        result_lines = []

        # Find the base indentation level from non-empty lines
        indentation_counts: dict[int, int] = {}
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("--"):  # Skip empty lines and comments
                line_indent = len(line) - len(line.lstrip())
                # Don't count lines that start with special patterns as base indentation
                if not stripped.startswith(("|", "·", "case ", "next ")):
                    indentation_counts[line_indent] = indentation_counts.get(line_indent, 0) + 1

        # Find the most common indentation level, but ensure it's not 0 if we have indented content
        base_indent = 0
        if indentation_counts:
            # Get the minimum non-zero indentation as base to preserve content
            non_zero_indents = [indent for indent in indentation_counts if indent > 0]
            if non_zero_indents:
                base_indent = min(non_zero_indents)
            else:
                base_indent = max(indentation_counts.items(), key=lambda x: x[1])[0]

        # Normalize indentation
        for line in lines:
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

        # Remove leading/trailing empty lines but preserve internal structure
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
