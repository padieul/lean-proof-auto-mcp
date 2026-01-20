"""Lightweight Lean tokenization utilities.

This module provides functions for basic Lean syntax processing including
comment stripping, string literal detection, and whitespace normalization.
"""

import re
from typing import List

from .source import Span


def strip_comments(text: str) -> str:
    """Remove -- and /- -/ comments (imperfect is OK for v0.1).
    
    Handles both single-line (--) and multi-line (/- -/) comments.
    Uses simple stack-based approach for nested multi-line comments.
    Avoids removing comment markers inside string literals.
    
    Args:
        text: The source text to process
        
    Returns:
        Text with comments removed, preserving line structure
    """
    if not text:
        return text
    
    result = []
    i = 0
    in_multiline = 0  # Stack depth for nested comments
    in_string = False
    
    while i < len(text):
        # Handle string literals to avoid processing comment markers inside them
        if not in_multiline and text[i] == '"':
            # Check if this quote is escaped
            escaped = False
            if i > 0:
                # Count preceding backslashes
                backslash_count = 0
                j = i - 1
                while j >= 0 and text[j] == '\\':
                    backslash_count += 1
                    j -= 1
                escaped = (backslash_count % 2) == 1
            
            if not escaped:
                in_string = not in_string
            result.append(text[i])
            i += 1
            continue
        
        # If we're inside a string, just copy characters
        if in_string:
            result.append(text[i])
            i += 1
            continue
        
        # Check for multi-line comment start
        if i < len(text) - 1 and text[i:i+2] == "/-":
            in_multiline += 1
            i += 2
            continue
        
        # Check for multi-line comment end
        if i < len(text) - 1 and text[i:i+2] == "-/" and in_multiline > 0:
            in_multiline -= 1
            i += 2
            continue
        
        # Check for single-line comment start (only if not in multi-line)
        if i < len(text) - 1 and text[i:i+2] == "--" and in_multiline == 0:
            # Skip to end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            # Include the newline if present
            if i < len(text) and text[i] == '\n':
                result.append('\n')
                i += 1
            continue
        
        # If not in comment, add character
        if in_multiline == 0:
            result.append(text[i])
        
        i += 1
    
    # Handle unclosed multiline comments: if we ended in a multiline comment,
    # we need to add a newline if the original text had newlines in the comment
    if in_multiline > 0:
        # Find the last newline in the original text to preserve structure
        last_newline_pos = text.rfind('\n')
        if last_newline_pos != -1:
            # Check if we have any content after the last processed non-comment character
            # This is a simple heuristic: if the result doesn't end with newline but
            # the original had newlines after the comment start, add one
            if result and result[-1] != '\n':
                result.append('\n')
    
    return "".join(result)


def detect_string_literals(text: str) -> List[Span]:
    """Find string literal spans to avoid false positives.
    
    Detects string literals in "..." format. Handles escaped quotes.
    
    Args:
        text: The source text to analyze
        
    Returns:
        List of Span objects representing string literal locations
    """
    if not text:
        return []
    
    spans = []
    lines = text.splitlines()
    
    for line_num, line in enumerate(lines, 1):
        i = 0
        while i < len(line):
            if line[i] == '"':
                start_col = i
                i += 1  # Skip opening quote
                
                # Find closing quote, handling escapes
                while i < len(line):
                    if line[i] == '\\':
                        # Skip escaped character (including escaped quotes)
                        i += 2 if i + 1 < len(line) else 1
                    elif line[i] == '"':
                        # Found closing quote
                        end_col = i + 1
                        spans.append(Span(
                            start_line=line_num,
                            start_col=start_col,
                            end_line=line_num,
                            end_col=end_col
                        ))
                        i += 1
                        break
                    else:
                        i += 1
                else:
                    # Unclosed string literal - treat as extending to end of line
                    spans.append(Span(
                        start_line=line_num,
                        start_col=start_col,
                        end_line=line_num,
                        end_col=len(line)
                    ))
            else:
                i += 1
    
    return spans


def normalize_whitespace(text: str) -> str:
    """Normalize indentation for consistent parsing.
    
    Converts tabs to spaces and normalizes indentation levels.
    Preserves relative indentation structure.
    
    Args:
        text: The source text to normalize
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return text
    
    lines = text.splitlines()
    result_lines = []
    
    for line in lines:
        # Convert tabs to 2 spaces, but do it properly by expanding at tab stops
        # For simplicity, we'll just replace each tab with 2 spaces
        normalized = line.replace('\t', '  ')
        result_lines.append(normalized)
    
    return "\n".join(result_lines)


def get_indentation_level(line: str) -> int:
    """Count leading spaces/tabs.
    
    Counts the indentation level of a line, treating tabs as 2 spaces.
    
    Args:
        line: The line to analyze
        
    Returns:
        Number of spaces of indentation
    """
    if not line:
        return 0
    
    count = 0
    for char in line:
        if char == ' ':
            count += 1
        elif char == '\t':
            count += 2  # Tab counts as 2 spaces
        else:
            break
    
    return count