"""File indexing for theorem declarations.

This module provides data structures and functions for building an index
of theorem-like declarations in Lean files and looking them up by ID or range.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Set

from .source import SourceText, Span
from .lean_syntax import strip_comments, detect_string_literals


@dataclass(frozen=True)
class TheoremDecl:
    """Represents a theorem-like declaration in a Lean file.
    
    Attributes:
        theorem_id: Stable identifier (e.g., "Nat.mul_comm")
        name: Short name (e.g., "mul_comm")
        kind: Declaration kind ("theorem" | "lemma" | "example" | "instance")
        decl_span: Span where declaration starts and ends
        proof_span: Span where proof lives (if found), None if no proof
        attributes: List of @[...] annotations (optional in v0.1)
    """
    theorem_id: str
    name: str
    kind: str
    decl_span: Span
    proof_span: Optional[Span] = None
    attributes: List[str] = None
    
    def __post_init__(self) -> None:
        """Validate theorem declaration invariants."""
        if not self.theorem_id:
            raise ValueError("theorem_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.kind not in {"theorem", "lemma", "example", "instance"}:
            raise ValueError(f"Invalid kind: {self.kind}")
        if self.attributes is None:
            object.__setattr__(self, 'attributes', [])


@dataclass(frozen=True)
class FileIndex:
    """Index of theorem declarations in a file.
    
    Attributes:
        file: Path to the source file
        decls: List of theorem declarations found in the file
    """
    file: str
    decls: List[TheoremDecl]


def build_index(source: SourceText) -> FileIndex:
    """Find all theorem-like declarations in file.
    
    Uses regex-based detection to find theorem, lemma, example, and instance
    declarations. Extracts declaration spans and proof spans where possible.
    Enhanced to include namespace context in theorem names.
    
    Args:
        source: The source text to index
        
    Returns:
        FileIndex containing all found declarations
    """
    if not source.text:
        return FileIndex(file=source.path, decls=[])
    
    # Strip comments to avoid false positives
    clean_text = strip_comments(source.text)
    
    # Detect string literals to avoid false positives
    string_spans = detect_string_literals(clean_text)
    
    # Find all theorem-like declarations
    decls = []
    existing_ids = set()  # Track existing theorem_id values to avoid collisions
    
    # Pattern to match theorem-like declarations
    # Matches: theorem|lemma|example|instance followed by optional name and eventually a colon
    # This pattern is more flexible to handle multi-line declarations and Unicode characters
    decl_pattern = r'\b(theorem|lemma|example|instance)(?:\s+([^\s:({}\[\]]+))?\s*'
    
    lines = clean_text.splitlines()
    
    # Track namespace context for proper theorem_id generation
    current_namespace_stack = []
    
    for match in re.finditer(decl_pattern, clean_text, re.MULTILINE):
        kind = match.group(1)
        full_name = match.group(2) if match.group(2) else None
        
        # Check if this match is inside a string literal
        match_start_pos = match.start()
        if _is_inside_string_literal(match_start_pos, clean_text, string_spans):
            continue
        
        # Find the line number where this declaration starts
        decl_start_line = clean_text[:match_start_pos].count('\n') + 1
        
        # Update namespace context up to this line
        current_namespace_stack = _update_namespace_context(
            lines, current_namespace_stack, decl_start_line
        )
        
        # Verify this is actually a declaration by looking for a colon within reasonable distance
        # Look ahead from the match position to find a colon
        remaining_text = clean_text[match.end():]
        colon_search = re.search(r':\s*(?!=)', remaining_text[:500])  # Look within 500 chars, avoid :=
        if not colon_search:
            continue  # Not a declaration if no colon found
        
        # Generate name and theorem_id with namespace context
        theorem_id, short_name = _generate_unique_theorem_id_with_namespace(
            full_name, kind, decl_start_line, existing_ids, current_namespace_stack
        )
        existing_ids.add(theorem_id)
        
        # Find declaration span (from keyword to end of declaration)
        decl_span, proof_span = _find_declaration_spans(
            lines, decl_start_line, match.start() - clean_text[:match_start_pos].rfind('\n', 0, match_start_pos) - 1
        )
        
        if decl_span:
            decl = TheoremDecl(
                theorem_id=theorem_id,
                name=short_name,
                kind=kind,
                decl_span=decl_span,
                proof_span=proof_span,
                attributes=[]  # TODO: Parse attributes in future version
            )
            decls.append(decl)
    
    return FileIndex(file=source.path, decls=decls)


def find_by_id(index: FileIndex, theorem_id: str) -> Optional[TheoremDecl]:
    """Lookup theorem by stable ID.
    
    Args:
        index: The file index to search in
        theorem_id: The stable theorem identifier to find
        
    Returns:
        TheoremDecl if found, None otherwise
    """
    for decl in index.decls:
        if decl.theorem_id == theorem_id:
            return decl
    return None


def find_by_range(index: FileIndex, start_line: int, end_line: int) -> Optional[TheoremDecl]:
    """Lookup theorem by line range.
    
    Finds a theorem declaration that overlaps with the given line range.
    If multiple theorems overlap, returns the one with the best overlap.
    
    Args:
        index: The file index to search in
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed)
        
    Returns:
        TheoremDecl if found, None otherwise
    """
    if start_line < 1 or end_line < start_line:
        return None
    
    best_match = None
    best_overlap = 0
    
    for decl in index.decls:
        # Check if declaration overlaps with the given range
        decl_start = decl.decl_span.start_line
        decl_end = decl.decl_span.end_line
        
        # Calculate overlap
        overlap_start = max(start_line, decl_start)
        overlap_end = min(end_line, decl_end)
        
        if overlap_start <= overlap_end:
            overlap_size = overlap_end - overlap_start + 1
            if overlap_size > best_overlap:
                best_overlap = overlap_size
                best_match = decl
    
    return best_match


def _is_inside_string_literal(pos: int, text: str, string_spans: List[Span]) -> bool:
    """Check if a position is inside a string literal.
    
    Args:
        pos: Character position in text
        text: The source text
        string_spans: List of string literal spans
        
    Returns:
        True if position is inside a string literal
    """
    # Convert character position to line/column
    lines_before = text[:pos].count('\n')
    line_num = lines_before + 1
    
    if lines_before == 0:
        col_num = pos
    else:
        last_newline = text.rfind('\n', 0, pos)
        col_num = pos - last_newline - 1
    
    # Check if this line/column is inside any string span
    for span in string_spans:
        if span.start_line == line_num == span.end_line:
            if span.start_col <= col_num < span.end_col:
                return True
        elif span.start_line <= line_num <= span.end_line:
            if line_num == span.start_line and col_num >= span.start_col:
                return True
            elif line_num == span.end_line and col_num < span.end_col:
                return True
            elif span.start_line < line_num < span.end_line:
                return True
    
    return False


def _find_declaration_spans(lines: List[str], start_line: int, start_col: int) -> tuple[Optional[Span], Optional[Span]]:
    """Find declaration and proof spans for a theorem.
    
    Args:
        lines: Lines of the source file
        start_line: Line where declaration keyword starts (1-indexed)
        start_col: Column where declaration keyword starts (0-indexed)
        
    Returns:
        Tuple of (declaration_span, proof_span), either may be None
    """
    if start_line < 1 or start_line > len(lines):
        return None, None
    
    # Find end of declaration (look for := or 'by')
    decl_end_line = start_line
    proof_start_line = None
    proof_end_line = None
    
    # Look for declaration end markers
    for line_idx in range(start_line - 1, len(lines)):
        line = lines[line_idx]
        current_line_num = line_idx + 1
        
        # Look for := (definition) or 'by' (tactic proof)
        if ':=' in line:
            decl_end_line = current_line_num
            
            # Check if there's a 'by' on the same line (tactic proof)
            by_pos = line.find('by')
            if by_pos != -1 and by_pos > line.find(':='):
                proof_start_line = current_line_num
                proof_end_line = _find_proof_end(lines, current_line_num)
            else:
                # Term-mode proof or definition - proof is on the same line or next lines
                proof_start_line = current_line_num
                proof_end_line = _find_term_proof_end(lines, current_line_num)
            break
        elif 'by' in line and current_line_num <= start_line + 5:  # Look within reasonable distance
            # Direct tactic proof without :=
            decl_end_line = current_line_num
            proof_start_line = current_line_num
            proof_end_line = _find_proof_end(lines, current_line_num)
            break
        elif current_line_num > start_line + 10:  # Don't search too far
            break
    
    # Create spans
    decl_span = Span(start_line=start_line, end_line=decl_end_line)
    
    proof_span = None
    if proof_start_line and proof_end_line:
        proof_span = Span(start_line=proof_start_line, end_line=proof_end_line)
    
    return decl_span, proof_span


def _find_proof_end(lines: List[str], start_line: int) -> int:
    """Find the end of a tactic proof starting with 'by'.
    
    Uses indentation-based heuristics to find where the proof block ends.
    
    Args:
        lines: Lines of the source file
        start_line: Line where proof starts (1-indexed)
        
    Returns:
        Line number where proof ends (1-indexed)
    """
    if start_line < 1 or start_line > len(lines):
        return start_line
    
    # Get base indentation level
    start_line_idx = start_line - 1
    base_indent = _get_line_indent(lines[start_line_idx])
    
    # Look for the end of the indented block
    end_line = start_line
    
    for line_idx in range(start_line_idx + 1, len(lines)):
        line = lines[line_idx]
        current_line_num = line_idx + 1
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Check indentation
        line_indent = _get_line_indent(line)
        
        # If we find a line with same or less indentation, proof likely ends
        if line_indent <= base_indent:
            # Check if this line starts a new declaration
            if re.match(r'\s*(theorem|lemma|example|instance|def|inductive|structure|class)\b', line):
                break
            # Check if this line is at the same level and looks like it's outside the proof
            if line_indent == base_indent and not line.strip().startswith(('·', '|', 'case', 'have', 'suffices')):
                break
        
        end_line = current_line_num
        
        # Don't search too far
        if current_line_num > start_line + 100:
            break
    
    return end_line


def _find_term_proof_end(lines: List[str], start_line: int) -> int:
    """Find the end of a term-mode proof or definition.
    
    Args:
        lines: Lines of the source file
        start_line: Line where proof/definition starts (1-indexed)
        
    Returns:
        Line number where proof ends (1-indexed)
    """
    if start_line < 1 or start_line > len(lines):
        return start_line
    
    # For term-mode proofs, look for the end of the expression
    # This is a simple heuristic - look for next declaration or significant dedent
    
    start_line_idx = start_line - 1
    base_indent = _get_line_indent(lines[start_line_idx])
    end_line = start_line
    
    for line_idx in range(start_line_idx + 1, len(lines)):
        line = lines[line_idx]
        current_line_num = line_idx + 1
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Check for new declaration
        if re.match(r'\s*(theorem|lemma|example|instance|def|inductive|structure|class)\b', line):
            break
        
        # Check indentation - if we dedent significantly, proof likely ends
        line_indent = _get_line_indent(line)
        if line_indent < base_indent:
            break
        
        end_line = current_line_num
        
        # Don't search too far
        if current_line_num > start_line + 20:
            break
    
    return end_line


def _get_line_indent(line: str) -> int:
    """Get indentation level of a line.
    
    Args:
        line: The line to analyze
        
    Returns:
        Number of spaces of indentation (tabs count as 2 spaces)
    """
    indent = 0
    for char in line:
        if char == ' ':
            indent += 1
        elif char == '\t':
            indent += 2
        else:
            break
    return indent


def _update_namespace_context(lines: List[str], current_stack: List[str], up_to_line: int) -> List[str]:
    """Update namespace context by scanning lines up to the given line.
    
    Args:
        lines: Lines of the source file
        current_stack: Current namespace stack
        up_to_line: Line number to scan up to (1-indexed)
        
    Returns:
        Updated namespace stack
    """
    # Pattern to match namespace declarations and ends
    namespace_pattern = r'^\s*namespace\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*$'
    end_pattern = r'^\s*end(?:\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*))?\s*$'
    
    # Start from where we left off or from the beginning
    start_line = 1
    namespace_stack = current_stack.copy()
    
    # Scan lines up to the target line
    for line_idx in range(start_line - 1, min(up_to_line, len(lines))):
        line = lines[line_idx]
        
        # Check for namespace declarations
        namespace_match = re.match(namespace_pattern, line)
        if namespace_match:
            namespace_name = namespace_match.group(1)
            namespace_stack.append(namespace_name)
            continue
        
        # Check for end declarations
        end_match = re.match(end_pattern, line)
        if end_match:
            end_name = end_match.group(1) if end_match.group(1) else None
            if namespace_stack:
                if end_name is None:
                    # Generic 'end' - pop the most recent namespace
                    namespace_stack.pop()
                else:
                    # Named 'end' - find and pop the matching namespace
                    for i in range(len(namespace_stack) - 1, -1, -1):
                        if namespace_stack[i] == end_name:
                            namespace_stack = namespace_stack[:i]
                            break
            continue
    
    return namespace_stack


def _generate_unique_theorem_id_with_namespace(
    full_name: Optional[str], 
    kind: str, 
    start_line: int, 
    existing_ids: Set[str], 
    namespace_stack: List[str]
) -> tuple[str, str]:
    """Generate unique theorem_id with namespace context and collision resolution.
    
    Strategy:
    1. If full_name already includes namespace (has dots), use it as-is
    2. If full_name is simple, prepend current namespace context
    3. For unnamed theorems, use kind + line number with namespace prefix
    4. For collisions, append line number (e.g., "Polynomial.eval_123")
    5. Ensure uniqueness within file scope
    
    Args:
        full_name: Full theorem name (e.g., "eval₂_zero") or None
        kind: Declaration kind ("theorem", "lemma", "example", "instance")
        start_line: Line number where declaration starts (1-indexed)
        existing_ids: Set of already used theorem_id values
        namespace_stack: Current namespace context stack
        
    Returns:
        Tuple of (unique_theorem_id, short_name)
    """
    if full_name:
        # Extract the short name (last component after dots)
        name_parts = full_name.split('.')
        short_name = name_parts[-1]
        
        # Determine the full theorem_id with namespace context
        if len(name_parts) > 1:
            # Name already includes namespace context (e.g., "Polynomial.eval₂_zero")
            candidate_id = full_name
        else:
            # Simple name - add current namespace context
            if namespace_stack:
                # Use the most recent (innermost) namespace
                namespace_prefix = namespace_stack[-1]
                candidate_id = f"{namespace_prefix}.{full_name}"
            else:
                # No namespace context - use name as-is
                candidate_id = full_name
        
        # Handle collisions by appending line number
        if candidate_id in existing_ids:
            candidate_id = f"{candidate_id}_{start_line}"
        
        # If still collision (very unlikely), keep incrementing
        counter = 1
        while candidate_id in existing_ids:
            base_name = candidate_id.rsplit('_', 1)[0] if '_' in candidate_id else candidate_id
            candidate_id = f"{base_name}_{start_line}_{counter}"
            counter += 1
            
        return candidate_id, short_name
    else:
        # For unnamed declarations (example, instance), use kind + line number
        short_name = f"{kind}_{start_line}"
        
        # Add namespace prefix if available
        if namespace_stack:
            namespace_prefix = namespace_stack[-1]
            candidate_id = f"{namespace_prefix}.{kind}_{start_line}"
        else:
            candidate_id = f"{kind}_{start_line}"
        
        # Handle collision (very unlikely for unnamed declarations)
        counter = 1
        while candidate_id in existing_ids:
            if namespace_stack:
                namespace_prefix = namespace_stack[-1]
                candidate_id = f"{namespace_prefix}.{kind}_{start_line}_{counter}"
            else:
                candidate_id = f"{kind}_{start_line}_{counter}"
            counter += 1
            
        return candidate_id, short_name