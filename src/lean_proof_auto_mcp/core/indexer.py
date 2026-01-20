"""File indexing for theorem declarations.

This module provides data structures and functions for building an index
of theorem-like declarations in Lean files and looking them up by ID or range.
"""

import re
from dataclasses import dataclass, field

from .lean_syntax import detect_string_literals, strip_comments
from .source import SourceText, Span


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
    proof_span: Span | None = None
    attributes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate theorem declaration invariants."""
        if not self.theorem_id:
            raise ValueError("theorem_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.kind not in {"theorem", "lemma", "example", "instance"}:
            raise ValueError(f"Invalid kind: {self.kind}")
        if self.attributes is None:
            object.__setattr__(self, "attributes", [])


@dataclass(frozen=True)
class FileIndex:
    """Index of theorem declarations in a file.

    Attributes:
        file: Path to the source file
        decls: List of theorem declarations found in the file
    """

    file: str
    decls: list[TheoremDecl]


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
    existing_ids: set[str] = set()  # Track existing theorem_id values to avoid collisions

    # Pattern to match theorem-like declarations
    # Matches: theorem|lemma|example|instance followed by optional name and eventually a colon
    # This pattern is more flexible to handle multi-line declarations and Unicode characters
    # Updated to allow dots in theorem names for qualified names like List.length_append
    decl_pattern = (
        r"\b(theorem|lemma|example|instance)(?:\s+([^\s:({}\[\]]+(?:\.[^\s:({}\[\]]+)*))?\s*"
    )

    lines = clean_text.splitlines()

    # Track namespace context for proper theorem_id generation
    current_namespace_stack: list[str] = []

    for match in re.finditer(decl_pattern, clean_text, re.MULTILINE):
        kind = match.group(1)
        full_name = match.group(2) if match.group(2) else None

        # Check if this match is inside a string literal
        match_start_pos = match.start()
        if _is_inside_string_literal(match_start_pos, clean_text, string_spans):
            continue

        # Find the line number where this declaration starts
        decl_start_line = clean_text[:match_start_pos].count("\n") + 1

        # Update namespace context up to this line
        current_namespace_stack = _update_namespace_context(
            lines, current_namespace_stack, decl_start_line
        )

        # Verify this is actually a declaration by looking for a colon within reasonable distance
        # Look ahead from the match position to find a colon
        remaining_text = clean_text[match.end() :]
        colon_search = re.search(
            r":\s*(?!=)", remaining_text[:500]
        )  # Look within 500 chars, avoid :=
        if not colon_search:
            continue  # Not a declaration if no colon found

        # Generate name and theorem_id with namespace context
        theorem_id, short_name = _generate_unique_theorem_id_with_namespace(
            full_name, kind, decl_start_line, existing_ids, current_namespace_stack
        )
        existing_ids.add(theorem_id)

        # Find declaration span (from keyword to end of declaration)
        decl_span, proof_span = _find_declaration_spans(
            lines,
            decl_start_line,
            match.start() - clean_text[:match_start_pos].rfind("\n", 0, match_start_pos) - 1,
        )

        if decl_span:
            decl = TheoremDecl(
                theorem_id=theorem_id,
                name=short_name,
                kind=kind,
                decl_span=decl_span,
                proof_span=proof_span,
                attributes=[],  # TODO: Parse attributes in future version
            )
            decls.append(decl)

    return FileIndex(file=source.path, decls=decls)


def find_by_id(index: FileIndex, theorem_id: str) -> TheoremDecl | None:
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


def find_by_range(index: FileIndex, start_line: int, end_line: int) -> TheoremDecl | None:
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


def _is_inside_string_literal(pos: int, text: str, string_spans: list[Span]) -> bool:
    """Check if a position is inside a string literal.

    Args:
        pos: Character position in text
        text: The source text
        string_spans: List of string literal spans

    Returns:
        True if position is inside a string literal
    """
    # Convert character position to line/column
    lines_before = text[:pos].count("\n")
    line_num = lines_before + 1

    if lines_before == 0:
        col_num = pos
    else:
        last_newline = text.rfind("\n", 0, pos)
        col_num = pos - last_newline - 1

    # Check if this line/column is inside any string span
    for span in string_spans:
        if span.start_line == line_num == span.end_line:
            if span.start_col <= col_num < span.end_col:
                return True
        elif span.start_line <= line_num <= span.end_line and (
            line_num == span.start_line
            and col_num >= span.start_col
            or line_num == span.end_line
            and col_num < span.end_col
            or span.start_line < line_num < span.end_line
        ):
            return True

    return False


def _find_declaration_spans(
    lines: list[str], start_line: int, start_col: int
) -> tuple[Span | None, Span | None]:
    """Find declaration and proof spans for a theorem with enhanced detection.

    Enhanced to better handle:
    1. Multi-line declarations spanning multiple lines
    2. Better recognition of proof start markers in various syntactic contexts
    3. Enhanced indentation-based proof boundary detection
    4. Improved handling of nested proof constructs
    5. Better distinction between term-mode (:=) and tactic-mode (by) proofs
    6. Improved proof text extraction from detected boundaries

    Args:
        lines: Lines of the source file
        start_line: Line where declaration keyword starts (1-indexed)
        start_col: Column where declaration keyword starts (0-indexed)

    Returns:
        Tuple of (declaration_span, proof_span), either may be None
    """
    if start_line < 1 or start_line > len(lines):
        return None, None

    # Find end of declaration (look for main colon that starts the type)
    decl_end_line = start_line
    proof_start_line = None
    proof_end_line = None
    proof_start_col = 0

    # First, find the main colon that separates name/params from type
    main_colon_line = _find_main_colon(lines, start_line)
    if not main_colon_line:
        return None, None

    # Look for proof markers after the main colon
    proof_info = _find_proof_markers(lines, main_colon_line)

    if proof_info:
        decl_end_line = proof_info["decl_end_line"]
        proof_start_line = proof_info["proof_start_line"]
        proof_start_col = proof_info.get("proof_start_col", 0)
        proof_mode = proof_info["proof_mode"]  # 'term' or 'tactic'

        if proof_mode == "tactic":
            proof_end_line = _find_tactic_proof_end(lines, proof_start_line)
        else:  # term mode
            proof_end_line = _find_term_proof_end(lines, proof_start_line)
    else:
        # No proof found - might be a declaration without proof
        decl_end_line = main_colon_line

    # Create spans
    decl_span = Span(start_line=start_line, end_line=decl_end_line)

    proof_span = None
    if proof_start_line and proof_end_line:
        # Create proof span that excludes the declaration part
        proof_span = Span(
            start_line=proof_start_line, start_col=proof_start_col, end_line=proof_end_line
        )

    return decl_span, proof_span


def _find_main_colon(lines: list[str], start_line: int) -> int | None:
    """Find the main colon that separates theorem name/params from type.

    This function distinguishes between type annotation colons (like {R : Type*})
    and the main colon that starts the theorem type.

    Args:
        lines: Lines of the source file
        start_line: Line where declaration keyword starts (1-indexed)

    Returns:
        Line number where main colon is found, None if not found
    """
    # Look for the main colon within reasonable distance
    for line_idx in range(start_line - 1, min(len(lines), start_line + 20)):
        line = lines[line_idx]
        current_line_num = line_idx + 1

        # Look for colon that's not part of type annotations
        # Main colon is typically followed by the theorem type, not a type annotation
        colon_positions = []
        for i, char in enumerate(line):
            if char == ":":
                colon_positions.append(i)

        for colon_pos in colon_positions:
            # Check if this colon looks like the main colon
            if _is_main_colon(line, colon_pos):
                return current_line_num

    return None


def _is_main_colon(line: str, colon_pos: int) -> bool:
    """Check if a colon position represents the main theorem colon.

    Args:
        line: The line containing the colon
        colon_pos: Position of the colon in the line

    Returns:
        True if this looks like the main theorem colon
    """
    # Skip if this is part of :=
    if colon_pos + 1 < len(line) and line[colon_pos + 1] == "=":
        return False

    # Look at what comes before the colon
    before_colon = line[:colon_pos].strip()
    after_colon = line[colon_pos + 1 :].strip()

    # If the colon is at the end of the line (or followed only by whitespace),
    # and we have a reasonable theorem declaration before it, it's likely the main colon
    if not after_colon and re.match(r"(theorem|lemma|example|instance)\s+", before_colon):
        return True

    # Main colon typically has the theorem type after it
    # Type annotations typically have "Type*", "ℕ", etc. after them
    # Main colon often has more complex expressions

    # Heuristic: if what comes before looks like a parameter list ending,
    # and what comes after doesn't look like a simple type, it's likely the main colon
    if before_colon.endswith(")") or before_colon.endswith("}") or before_colon.endswith("]"):
        # This could be the end of parameter list
        if after_colon and not _looks_like_simple_type(after_colon):
            return True
        # If after_colon is empty, it could still be the main colon if the type is on the next line
        if not after_colon:
            return True

    # Another heuristic: if there's no opening bracket/paren before this colon
    # on the same line, it might be the main colon
    open_brackets = before_colon.count("(") + before_colon.count("{") + before_colon.count("[")
    close_brackets = before_colon.count(")") + before_colon.count("}") + before_colon.count("]")

    return open_brackets == close_brackets


def _looks_like_simple_type(text: str) -> bool:
    """Check if text looks like a simple type annotation.

    Args:
        text: Text after a colon

    Returns:
        True if it looks like a simple type (Type*, ℕ, etc.)
    """
    text = text.strip()

    # Common simple types
    simple_types = {"Type*", "Type", "ℕ", "ℤ", "ℚ", "ℝ", "ℂ", "Prop", "Sort*", "Sort"}

    if text in simple_types:
        return True

    # Check for Type u, Sort u patterns
    return bool(re.match(r"^(Type|Sort)\s+[a-zA-Z_][a-zA-Z0-9_]*$", text))


def _find_proof_markers(lines: list[str], main_colon_line: int) -> dict | None:
    """Find proof start markers after the main colon.

    Enhanced to detect both := and by patterns in various contexts and
    return precise proof start positions for better text extraction.

    Args:
        lines: Lines of the source file
        main_colon_line: Line where main colon was found (1-indexed)

    Returns:
        Dict with proof info including precise start position, or None if no proof found
    """
    # Look for proof markers starting from the main colon line
    for line_idx in range(main_colon_line - 1, min(len(lines), main_colon_line + 10)):
        line = lines[line_idx]
        current_line_num = line_idx + 1

        # Look for := pattern (term-mode proof)
        assign_match = re.search(r":=\s*", line)
        if assign_match:
            assign_end_pos = assign_match.end()
            remaining_line = line[assign_end_pos:].strip()

            # Check if there's a 'by' immediately after :=
            if remaining_line.startswith("by"):
                # This is := by pattern (tactic proof)
                by_start_pos = assign_end_pos + line[assign_end_pos:].find("by")
                by_end_pos = by_start_pos + 2

                # Check if there's content after 'by' on the same line
                after_by = line[by_end_pos:].strip()
                if after_by:
                    # Proof starts after 'by ' on the same line
                    proof_start_col = by_end_pos + (
                        len(line[by_end_pos:]) - len(line[by_end_pos:].lstrip())
                    )
                    return {
                        "decl_end_line": current_line_num,
                        "proof_start_line": current_line_num,
                        "proof_start_col": proof_start_col,
                        "proof_mode": "tactic",
                    }
                else:
                    # Proof starts on the next line
                    return {
                        "decl_end_line": current_line_num,
                        "proof_start_line": current_line_num + 1,
                        "proof_start_col": 0,
                        "proof_mode": "tactic",
                    }
            else:
                # This is := <term> pattern (term-mode proof)
                if remaining_line:
                    # Proof starts after := on the same line
                    proof_start_col = assign_end_pos + (
                        len(line[assign_end_pos:]) - len(remaining_line)
                    )
                    return {
                        "decl_end_line": current_line_num,
                        "proof_start_line": current_line_num,
                        "proof_start_col": proof_start_col,
                        "proof_mode": "term",
                    }
                else:
                    # Proof starts on the next line
                    return {
                        "decl_end_line": current_line_num,
                        "proof_start_line": current_line_num + 1,
                        "proof_start_col": 0,
                        "proof_mode": "term",
                    }

        # Look for standalone 'by' pattern (direct tactic proof)
        by_match = re.search(r"\bby\b", line)
        if by_match:
            # Make sure this 'by' is not part of a larger expression
            # and appears in a context where it could start a proof
            by_pos = by_match.start()
            before_by = line[:by_pos].strip()

            # Check if this looks like a proof-starting 'by'
            if _is_proof_starting_by(line, by_pos, before_by):
                by_end_pos = by_match.end()
                after_by = line[by_end_pos:].strip()

                if after_by:
                    # Proof starts after 'by ' on the same line
                    proof_start_col = by_end_pos + (len(line[by_end_pos:]) - len(after_by))
                    return {
                        "decl_end_line": current_line_num,
                        "proof_start_line": current_line_num,
                        "proof_start_col": proof_start_col,
                        "proof_mode": "tactic",
                    }
                else:
                    # Proof starts on the next line
                    return {
                        "decl_end_line": current_line_num,
                        "proof_start_line": current_line_num + 1,
                        "proof_start_col": 0,
                        "proof_mode": "tactic",
                    }

    return None


def _is_proof_starting_by(line: str, by_pos: int, before_by: str) -> bool:
    """Check if a 'by' token starts a proof.

    Args:
        line: The line containing 'by'
        by_pos: Position of 'by' in the line
        before_by: Text before the 'by' token

    Returns:
        True if this 'by' likely starts a proof
    """
    # If 'by' is at the start of the line or after whitespace, likely a proof starter
    if by_pos == 0 or line[:by_pos].isspace():
        return True

    # If 'by' comes after := on the same line
    if ":=" in before_by:
        return True

    # If 'by' comes after what looks like a theorem type
    # (this is a heuristic - could be improved)
    return before_by.endswith(":") or "→" in before_by or "↔" in before_by


def _find_tactic_proof_end(lines: list[str], start_line: int) -> int:
    """Find the end of a tactic proof starting with 'by'.

    Enhanced version with better indentation analysis and handling of nested proof constructs.
    Improved to correctly detect proof boundaries for better text extraction.

    Args:
        lines: Lines of the source file
        start_line: Line where proof starts (1-indexed)

    Returns:
        Line number where proof ends (1-indexed)
    """
    if start_line < 1 or start_line > len(lines):
        return start_line

    # Get base indentation level from the first non-empty proof line
    start_line_idx = start_line - 1
    base_indent = None

    # Find the base indentation from the first meaningful proof line
    for line_idx in range(start_line_idx, min(len(lines), start_line_idx + 5)):
        line = lines[line_idx]
        stripped_line = line.strip()

        if stripped_line and not stripped_line.startswith("--"):
            # This is a meaningful proof line
            line_indent = _get_line_indent(line)
            if base_indent is None:
                base_indent = line_indent
            break

    # If we couldn't find base indentation, use a reasonable default
    if base_indent is None:
        # Look for indentation from the 'by' line or use default
        if start_line_idx < len(lines):
            by_line = lines[start_line_idx]
            by_match = re.search(r"\bby\b", by_line)
            base_indent = by_match.start() + 2 if by_match else _get_line_indent(by_line) + 2
        else:
            base_indent = 2

    # Look for the end of the indented proof block
    end_line = start_line

    for line_idx in range(start_line_idx, len(lines)):
        line = lines[line_idx]
        current_line_num = line_idx + 1

        # Skip empty lines and comments
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("--"):
            # Empty lines and comments don't end the proof, but update end_line
            if stripped_line.startswith("--"):
                end_line = current_line_num
            continue

        # Check indentation
        line_indent = _get_line_indent(line)

        # If we find a line with less indentation than the base, check if proof ends
        if line_indent < base_indent:
            # Check if this line starts a new declaration or major construct
            if re.match(
                r"\s*(theorem|lemma|example|instance|def|inductive|structure|class|namespace|section|variable|end)\b",
                line,
            ):
                break

            # If this line is at a significantly lower indentation level, proof likely ends
            if line_indent < base_indent - 1:
                break

        # Check for new theorem/declaration at any indentation level - ends the proof
        if re.match(r"^\s*(theorem|lemma|example|instance|def|inductive|structure|class)\b", line):
            break

        # Update end_line for any meaningful content
        end_line = current_line_num

        # Don't search too far (safety limit)
        if current_line_num > start_line + 200:
            break

    return end_line


def _find_proof_end(lines: list[str], start_line: int) -> int:
    """Find the end of a tactic proof starting with 'by'.

    This is the legacy function - use _find_tactic_proof_end for enhanced detection.

    Args:
        lines: Lines of the source file
        start_line: Line where proof starts (1-indexed)

    Returns:
        Line number where proof ends (1-indexed)
    """
    return _find_tactic_proof_end(lines, start_line)


def _find_term_proof_end(lines: list[str], start_line: int) -> int:
    """Find the end of a term-mode proof or definition.

    Enhanced to better handle complex term expressions and nested constructs.

    Args:
        lines: Lines of the source file
        start_line: Line where proof/definition starts (1-indexed)

    Returns:
        Line number where proof ends (1-indexed)
    """
    if start_line < 1 or start_line > len(lines):
        return start_line

    start_line_idx = start_line - 1
    start_line_text = lines[start_line_idx]

    # Find the := position to determine base indentation
    assign_pos = start_line_text.find(":=")
    if assign_pos != -1:
        # If := is at the end of the line (or followed only by whitespace),
        # the proof continues on the next line
        after_assign = start_line_text[assign_pos + 2 :].strip()
        if not after_assign:
            # Proof starts on the next line, use its indentation as base
            if start_line < len(lines):
                next_line = lines[start_line_idx + 1]
                base_indent = _get_line_indent(next_line) if next_line.strip() else assign_pos
            else:
                base_indent = assign_pos
        else:
            # Proof starts on the same line after :=
            base_indent = assign_pos + 2
    else:
        base_indent = _get_line_indent(start_line_text)

    end_line = start_line
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0

    # Count initial bracket depth from the := line
    if assign_pos != -1:
        after_assign = start_line_text[assign_pos + 2 :]
        paren_depth += after_assign.count("(") - after_assign.count(")")
        brace_depth += after_assign.count("{") - after_assign.count("}")
        bracket_depth += after_assign.count("[") - after_assign.count("]")

    # If the proof starts on the next line, we need to scan from there
    scan_start_line = start_line
    if assign_pos != -1 and not start_line_text[assign_pos + 2 :].strip():
        scan_start_line = start_line + 1

    # Always scan at least one line ahead to check for where clauses and continuations
    for line_idx in range(scan_start_line - 1, len(lines)):
        line = lines[line_idx]
        current_line_num = line_idx + 1

        # Skip the start line if we already processed it
        if (
            current_line_num == start_line
            and assign_pos != -1
            and start_line_text[assign_pos + 2 :].strip()
        ):
            # Proof is on the same line as :=, but we still need to check for continuations
            end_line = current_line_num
            continue
        line = lines[line_idx]
        current_line_num = line_idx + 1

        # Skip empty lines and comments
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("--"):
            continue

        # Update bracket depths
        paren_depth += line.count("(") - line.count(")")
        brace_depth += line.count("{") - line.count("}")
        bracket_depth += line.count("[") - line.count("]")

        # Check if we're still inside brackets
        if paren_depth > 0 or brace_depth > 0 or bracket_depth > 0:
            end_line = current_line_num
            continue

        # Check for new declaration
        if re.match(
            r"\s*(theorem|lemma|example|instance|def|inductive|structure|class|namespace|section|variable)\b",
            line,
        ):
            break

        # Check indentation - if we dedent significantly, proof likely ends
        line_indent = _get_line_indent(line)
        if line_indent < base_indent and not re.match(r"\s*(where|deriving|extends)\b", line):
            break

        # Special handling for 'where' clauses - they should be included in the proof
        if re.match(r"\s*where\b", line):
            end_line = current_line_num
            continue

        end_line = current_line_num

        # Don't search too far (safety limit)
        if current_line_num > start_line + 50:
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
        if char == " ":
            indent += 1
        elif char == "\t":
            indent += 2
        else:
            break
    return indent


def _update_namespace_context(
    lines: list[str], current_stack: list[str], up_to_line: int
) -> list[str]:
    """Update namespace context by scanning lines up to the given line.

    Args:
        lines: Lines of the source file
        current_stack: Current namespace stack
        up_to_line: Line number to scan up to (1-indexed)

    Returns:
        Updated namespace stack
    """
    # Pattern to match namespace declarations and ends
    namespace_pattern = r"^\s*namespace\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*$"
    end_pattern = r"^\s*end(?:\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*))?\s*$"

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
    full_name: str | None,
    kind: str,
    start_line: int,
    existing_ids: set[str],
    namespace_stack: list[str],
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
        name_parts = full_name.split(".")
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
            base_name = candidate_id.rsplit("_", 1)[0] if "_" in candidate_id else candidate_id
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
