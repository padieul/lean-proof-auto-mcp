"""
Harness construction for theorem testing.

This module provides components for constructing test harnesses that preserve
all context from the original file using range-based splicing. The core
RangeBasedHarnessConstructor is pure (zero I/O, zero dependencies).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..lean.ports import Declaration

# ============================================================================
# Module-level constants
# ============================================================================

# Declaration kinds that can be targeted for probing / proof validation.
# Includes "instance" because Lean instances can carry proof obligations
# (e.g. `Monoid.toNatPow`, `AddMonoid.toNatSMul`).
_PROVABLE_DECL_KINDS: frozenset[str] = frozenset(
    {
        "theorem",
        "lemma",
        "instance",
    }
)

# Declaration kinds whose non-target bodies are safe to replace with sorry.
# Excludes "instance" because sorry-ing instance bodies destroys definitional
# equality: `sorry` is an axiom that doesn't reduce, so proofs relying on
# definitional unfolding of instance fields (e.g. `rfl`) will break.
_SORRY_SAFE_DECL_KINDS: frozenset[str] = frozenset(
    {
        "theorem",
        "lemma",
    }
)

# Lean declaration keywords. If a DeclValue.range starts with one of these,
# the range likely covers declaration syntax rather than just a proof value.
_DECLARATION_KEYWORDS: frozenset[str] = frozenset(
    {
        "private",
        "protected",
        "noncomputable",
        "irreducible_def",
        "def",
        "instance",
        "class",
        "structure",
        "inductive",
        "abbrev",
        "opaque",
        "unsafe",
    }
)

# Command-level keywords. If a value range starts with one of these, splicing
# it is unsafe because it likely destroys command syntax.
_COMMAND_KEYWORDS: frozenset[str] = frozenset(
    {
        "import",
        "open",
        "namespace",
        "section",
        "end",
        "set_option",
        "attribute",
        "macro",
        "syntax",
        "elab",
        "notation",
        "infix",
        "infixl",
        "infixr",
        "prefix",
        "postfix",
        "scoped",
        "universe",
        "variable",
        "axiom",
        "constant",
        "example",
        "mutual",
        "theorem",
        "lemma",
    }
)

_TACTIC_KEYWORDS: frozenset[str] = frozenset(
    {
        "simp",
        "simpa",
        "simp_all",
        "rw",
        "rewrite",
        "ring",
        "linarith",
        "omega",
        "norm_num",
        "exact",
        "apply",
        "intro",
        "intros",
        "constructor",
        "cases",
        "induction",
        "have",
        "let",
        "obtain",
        "rcases",
        "ext",
        "funext",
        "congr",
        "trivial",
        "tauto",
        "decide",
        "norm_cast",
        "push_cast",
        "field_simp",
        "aesop",
        "grind",
        "sorry",
        "assumption",
        "contradiction",
        "exfalso",
        "refine",
        "calc",
        "show",
        "suffices",
        "specialize",
        "clear",
        "rename_i",
        "subst",
        "injection",
        "absurd",
        "left",
        "right",
    }
)


# ============================================================================
# Core Data Types
# ============================================================================


@dataclass(frozen=True)
class ImportPath:
    """A Lean import path."""

    path: str  # e.g., "Fixtures.Algebra.Group"

    def to_import_statement(self) -> str:
        """Convert to import statement."""
        return f"import {self.path}"


@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for harness construction."""

    theorem_id: str
    file_path: str
    proof_attempt: str
    file_content: str = ""  # Source file content (caller reads via Querier)
    declarations: list["Declaration"] = field(default_factory=list)  # Caller extracts via Querier
    additional_imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HarnessSuccess:
    """Successful harness construction."""

    code: str
    theorem_id: str
    file_path: str
    theorem_statement: str = ""  # theorem type expression for validate_proof paths


@dataclass(frozen=True)
class HarnessError:
    """Failed harness construction."""

    # theorem_not_found | ambiguous_theorem_id | unsafe_target_range
    # target_splice_cardinality | invalid_proof_attempt | construction_failed
    error_type: str
    message: str
    theorem_id: str
    file_path: str
    generated_code: str | None = None


HarnessResult = HarnessSuccess | HarnessError


# ============================================================================
# Exceptions
# ============================================================================


class HarnessConstructionError(Exception):
    """Base exception for harness construction errors."""

    def __init__(self, message: str, generated_code: str | None = None):
        super().__init__(message)
        self.generated_code = generated_code


class TheoremNotFoundError(HarnessConstructionError):
    """Raised when a theorem cannot be found."""


class AmbiguousTheoremMatchError(HarnessConstructionError):
    """Raised when theorem matching is ambiguous."""


class UnsafeTargetRangeError(HarnessConstructionError):
    """Raised when target value range cannot be safely spliced."""


class TargetSpliceCardinalityError(HarnessConstructionError):
    """Raised when target is spliced zero or multiple times."""


class InvalidProofAttemptError(HarnessConstructionError):
    """Raised when a proof attempt normalizes to empty text."""


# ============================================================================
# Protocols (Ports)
# ============================================================================


class ImportPathConverter(Protocol):
    """Convert file paths to import paths."""

    def convert(self, file_path: str) -> ImportPath:
        """
        Convert file path to import path.

        Args:
            file_path: e.g., "Fixtures/Algebra/Group.lean"

        Returns:
            ImportPath, e.g. "Fixtures.Algebra.Group"
        """
        ...


class HarnessConstructor(Protocol):
    """Strategy for constructing test harnesses."""

    def construct(self, config: HarnessConfig) -> HarnessResult:
        """
        Construct a test harness.

        Returns:
            HarnessSuccess or HarnessError
        """
        ...


# ============================================================================
# Range-Based Harness Construction (Pure Core)
# ============================================================================


@dataclass(frozen=True)
class Splice:
    """Immutable descriptor for a source-text replacement."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int
    replacement: str


@dataclass(frozen=True)
class RangeShape:
    """Classified shape of a declaration value range."""

    kind: str
    source: str


def _strip_leading_doc_comment(text: str) -> str:
    """Strip leading Lean doc comments (/-- ... -/), if present."""
    stripped = text
    while stripped.startswith("/--"):
        close_idx = stripped.find("-/", 3)
        if close_idx == -1:
            return stripped
        stripped = stripped[close_idx + 2 :].lstrip()
    return stripped


def _extract_source_at_range(
    file_content: str,
    start_line: int,
    start_col: int,
    end_line: int,
    end_col: int,
) -> str:
    """Extract source text at a given range (1-based lines, 0-based columns)."""
    lines = file_content.split("\n")
    sl = start_line - 1
    el = end_line - 1
    if sl < 0 or el >= len(lines):
        return ""
    if sl == el:
        return lines[sl][start_col:end_col]
    result = lines[sl][start_col:]
    for i in range(sl + 1, el):
        result += "\n" + lines[i]
    result += "\n" + lines[el][:end_col]
    return result


def _starts_with_keyword(text: str, keyword: str) -> bool:
    """Check whether text starts with a standalone keyword token."""
    if text == keyword:
        return True
    if not text.startswith(keyword):
        return False
    if len(text) == len(keyword):
        return True
    return text[len(keyword)].isspace()


def _first_word(text: str) -> str:
    """Extract a normalized first token-like word from text."""
    tokens = text.split()
    if not tokens:
        return ""
    return tokens[0].rstrip(":=;,()[]{}")


def _infer_body_context(file_content: str, start_line: int, start_col: int) -> str:
    """Infer whether a body range starts after ':=' or after 'by'."""
    lines = file_content.split("\n")
    line_idx = start_line - 1
    if line_idx < 0 or line_idx >= len(lines):
        return "unknown"

    prefix_lines = lines[:line_idx]
    current_prefix = lines[line_idx][:start_col]
    before = ("\n".join(prefix_lines + [current_prefix])).rstrip()
    if not before:
        return "unknown"

    if before.endswith(":="):
        return "after_assign"

    end = len(before) - 1
    while end >= 0 and before[end].isspace():
        end -= 1
    if end < 0:
        return "unknown"

    start = end
    while start >= 0 and (before[start].isalnum() or before[start] in "_'"):
        start -= 1
    token = before[start + 1 : end + 1]
    if token == "by":
        return "after_by"
    return "unknown"


def _classify_range_shape(
    file_content: str,
    start_line: int,
    start_col: int,
    end_line: int,
    end_col: int,
) -> RangeShape:
    """Classify how a DeclValue range starts so replacement can be shape-aware."""
    if not file_content:
        # Backward-compatible fallback for callers that do not pass source.
        return RangeShape(kind="term_body", source="")

    source = _extract_source_at_range(file_content, start_line, start_col, end_line, end_col)
    stripped = source.lstrip()

    if not stripped:
        return RangeShape(kind="empty", source=source)
    if stripped.startswith(":="):
        return RangeShape(kind="assign", source=source)
    if _starts_with_keyword(stripped, "by"):
        return RangeShape(kind="by", source=source)
    if _starts_with_keyword(stripped, "where"):
        return RangeShape(kind="where", source=source)

    if stripped.startswith("|"):
        context = _infer_body_context(file_content, start_line, start_col)
        if context == "after_by":
            return RangeShape(kind="tactic_body", source=source)
        return RangeShape(kind="equation_clauses", source=source)

    check_text = _strip_leading_doc_comment(stripped)
    first_word = _first_word(check_text)
    if first_word in _DECLARATION_KEYWORDS or first_word in _COMMAND_KEYWORDS:
        return RangeShape(kind="unsafe_command", source=source)

    context = _infer_body_context(file_content, start_line, start_col)
    if context == "after_by":
        return RangeShape(kind="tactic_body", source=source)
    return RangeShape(kind="term_body", source=source)


def _format_by_block(tactic_body: str) -> str:
    """Format tactic body as a by-block with stable indentation."""
    lines = tactic_body.splitlines()
    if not lines:
        return "by"
    indented = "\n".join(f"  {line}" if line else "  " for line in lines)
    return f"by\n{indented}"


def _format_inline_tactic_body(tactic_body: str) -> str:
    """Format tactic body for insertion where surrounding by already exists."""
    lines = tactic_body.splitlines()
    if not lines:
        return ""
    first = lines[0].strip()
    rest = "".join(f"\n  {line.strip()}" if line.strip() else "\n  " for line in lines[1:])
    return first + rest


def _format_exact_tactic(term_expr: str) -> str:
    """Format term expression as a tactic script using exact."""
    if "\n" not in term_expr:
        return f"exact {term_expr}"
    indented = "\n".join(f"    {line}" if line else "" for line in term_expr.splitlines())
    return f"exact (\n{indented}\n  )"


def _resolve_target_index(declarations: list["Declaration"], theorem_id: str) -> int:
    """Resolve theorem match deterministically with explicit ambiguity errors."""
    theorem_entries = [
        (idx, decl) for idx, decl in enumerate(declarations) if decl.kind in _PROVABLE_DECL_KINDS
    ]

    def _select_unique(matches: list[tuple[int, "Declaration"]], label: str) -> int | None:
        if len(matches) == 1:
            return matches[0][0]
        if len(matches) > 1:
            names = ", ".join((decl.full_name or decl.name) for _, decl in matches[:5])
            raise AmbiguousTheoremMatchError(
                f"Ambiguous theorem match ({label}) for '{theorem_id}': {names}"
            )
        return None

    full_exact = [(i, d) for i, d in theorem_entries if d.full_name == theorem_id]
    selected = _select_unique(full_exact, "exact_full_name")
    if selected is not None:
        return selected

    name_exact = [(i, d) for i, d in theorem_entries if d.name == theorem_id]
    selected = _select_unique(name_exact, "exact_name")
    if selected is not None:
        return selected

    local_name = theorem_id.split(".")[-1]
    local_matches = [
        (i, d)
        for i, d in theorem_entries
        if d.name == local_name
        or d.full_name == local_name
        or d.full_name.endswith(f".{local_name}")
    ]
    selected = _select_unique(local_matches, "local_name_fallback")
    if selected is not None:
        return selected

    raise TheoremNotFoundError(f"Theorem {theorem_id} not found in declarations")


def _target_mode_hint(range_shape: str) -> str | None:
    """Map target range shape to a mode hint for proof classification."""
    if range_shape in ("by", "tactic_body"):
        return "tactic"
    if range_shape in ("assign", "where", "term_body", "equation_clauses"):
        return "term"
    return None


def _target_replacement_for_shape(range_shape: str, mode: str, cleaned_proof: str) -> str:
    """Build target replacement based on range shape and proof mode."""
    if range_shape == "assign":
        if mode == "tactic":
            return f":= {_format_by_block(cleaned_proof)}"
        return f":= {cleaned_proof}"

    if range_shape == "by":
        if mode == "tactic":
            return _format_by_block(cleaned_proof)
        return f"by\n  {_format_exact_tactic(cleaned_proof)}"

    if range_shape == "where":
        if mode == "tactic":
            return f":= {_format_by_block(cleaned_proof)}"
        return f":= {cleaned_proof}"

    if range_shape == "term_body":
        if mode == "tactic":
            return _format_by_block(cleaned_proof)
        return cleaned_proof

    if range_shape == "tactic_body":
        if mode == "tactic":
            return _format_inline_tactic_body(cleaned_proof)
        return _format_exact_tactic(cleaned_proof)

    if range_shape == "equation_clauses":
        if _starts_with_keyword(cleaned_proof.lstrip(), "where"):
            raise UnsafeTargetRangeError(
                "Target theorem proof starts with 'where', cannot rewrite equation clauses to ':='"
            )
        if mode == "tactic":
            return f":= {_format_by_block(cleaned_proof)}"
        return f":= {cleaned_proof}"

    raise UnsafeTargetRangeError(f"Unsafe target range shape: {range_shape}")


def _non_target_replacement_for_shape(range_shape: str) -> str:
    """Build safe non-target replacement for a range shape."""
    if range_shape == "assign":
        return ":= by sorry"
    if range_shape == "by":
        return "by sorry"
    if range_shape == "where":
        return ":= by sorry"
    if range_shape == "term_body":
        return "by sorry"
    if range_shape == "tactic_body":
        return "sorry"
    raise UnsafeTargetRangeError(f"Unsafe non-target range shape: {range_shape}")


def classify_proof_attempt(
    proof_attempt: str,
    mode_hint: str | None = None,
) -> tuple[str, str]:
    """Classify a proof attempt as tactic-mode or term-mode and normalize it.

    Explicit syntax precedence:
    1. Leading ':=' (if present) is removed.
    2. Leading 'by' wins and returns tactic-mode.
    3. Leading 'where' wins and returns term-mode passthrough.

    For ambiguous bare proofs, mode_hint is used before falling back to term.
    """
    text = proof_attempt.strip()
    if not text:
        return ("term", "")

    if text.startswith(":="):
        text = text[2:].lstrip()
        if not text:
            return ("term", "")

    if _starts_with_keyword(text, "by"):
        if text == "by":
            return ("tactic", "")
        return ("tactic", text[2:].strip())

    if _starts_with_keyword(text, "where"):
        return ("term", text)

    first_token = text.split()[0] if text.split() else ""
    first_word = first_token.rstrip(";,")
    first_word_base = first_word.rstrip("?")

    # Heuristic for obvious tactic starts.
    if first_word_base in _TACTIC_KEYWORDS:
        return ("tactic", text)

    # Ambiguous bare proof: prefer range-shape hint.
    if mode_hint in ("tactic", "term"):
        return (mode_hint, text)

    return ("term", text)


def build_splice_plan(
    declarations: list["Declaration"],
    target_theorem_id: str,
    proof_attempt: str,
    file_content: str = "",
) -> list[Splice]:
    """Build splices that transform source into a validation harness."""
    target_index = _resolve_target_index(declarations, target_theorem_id)
    target_decl = declarations[target_index]

    if target_decl.value is None:
        raise UnsafeTargetRangeError(f"Target theorem '{target_theorem_id}' has no value range")
    target_range = target_decl.value.range
    if target_range.start_line == 0 and target_range.end_line == 0:
        raise UnsafeTargetRangeError(f"Target theorem '{target_theorem_id}' has empty value range")

    target_shape = _classify_range_shape(
        file_content,
        target_range.start_line,
        target_range.start_col,
        target_range.end_line,
        target_range.end_col,
    )
    if target_shape.kind in ("unsafe_command", "empty"):
        raise UnsafeTargetRangeError(
            "Target theorem "
            f"'{target_theorem_id}' has unsafe value range shape: {target_shape.kind}"
        )

    mode_hint = _target_mode_hint(target_shape.kind)
    mode, cleaned_proof = classify_proof_attempt(proof_attempt, mode_hint=mode_hint)
    if not cleaned_proof.strip():
        raise InvalidProofAttemptError("Proof attempt is empty after normalization")

    splices: list[Splice] = []
    target_splice_count = 0

    for idx, decl in enumerate(declarations):
        is_target = idx == target_index

        # Target must be in _PROVABLE_DECL_KINDS (includes instances).
        # Non-targets are only sorry'd if in _SORRY_SAFE_DECL_KINDS (excludes
        # instances, whose bodies carry computational content needed for
        # definitional equality).
        if is_target:
            if decl.kind not in _PROVABLE_DECL_KINDS:
                continue
        else:
            if decl.kind not in _SORRY_SAFE_DECL_KINDS:
                continue
        if decl.value is None:
            continue

        vr = decl.value.range
        if vr.start_line == 0 and vr.end_line == 0:
            continue

        range_shape = _classify_range_shape(
            file_content,
            vr.start_line,
            vr.start_col,
            vr.end_line,
            vr.end_col,
        ).kind

        is_target = idx == target_index
        if range_shape in ("unsafe_command", "empty"):
            if is_target:
                raise UnsafeTargetRangeError(
                    "Target theorem "
                    f"'{target_theorem_id}' has unsafe value range shape: {range_shape}"
                )
            # Skip non-target declarations that are unsafe to splice.
            continue

        if range_shape == "equation_clauses" and not is_target:
            # Equation-clause non-target bodies cannot be replaced with "by sorry"
            # without corrupting theorem header syntax; keep original source intact.
            continue

        if is_target:
            replacement = _target_replacement_for_shape(range_shape, mode, cleaned_proof)
            target_splice_count += 1
        else:
            replacement = _non_target_replacement_for_shape(range_shape)

        splices.append(
            Splice(
                start_line=vr.start_line,
                start_col=vr.start_col,
                end_line=vr.end_line,
                end_col=vr.end_col,
                replacement=replacement,
            )
        )

    if target_splice_count != 1:
        raise TargetSpliceCardinalityError(
            f"Target splice cardinality is {target_splice_count}; expected exactly 1"
        )

    # Sort bottom-to-top so earlier splices do not shift later coordinates.
    splices.sort(key=lambda s: (s.start_line, s.start_col), reverse=True)
    return splices


def apply_splices(file_content: str, splices: list[Splice]) -> str:
    """Apply splices to file content."""
    lines = file_content.split("\n")

    for splice in splices:
        sl = splice.start_line - 1
        sc = splice.start_col
        el = splice.end_line - 1
        ec = splice.end_col

        if sl < 0 or el >= len(lines):
            continue

        prefix = lines[sl][:sc]
        suffix = lines[el][ec:]
        replacement_text = prefix + splice.replacement + suffix
        replacement_lines = replacement_text.split("\n")
        lines[sl : el + 1] = replacement_lines

    return "\n".join(lines)


class RangeBasedHarnessConstructor:
    """Pure core-layer strategy. Zero I/O and zero adapter dependencies."""

    def construct(self, config: HarnessConfig) -> HarnessResult:
        """Construct a test harness from pre-loaded file content/declarations."""
        if not config.file_content:
            return HarnessError(
                error_type="construction_failed",
                message="file_content is empty - caller must provide source file content",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )

        if not config.declarations:
            return HarnessError(
                error_type="construction_failed",
                message="declarations list is empty - caller must provide declarations",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )

        try:
            splices = build_splice_plan(
                config.declarations,
                config.theorem_id,
                config.proof_attempt,
                file_content=config.file_content,
            )

            code = apply_splices(config.file_content, splices)
            if config.additional_imports:
                code = _prepend_imports(code, config.additional_imports)

            return HarnessSuccess(
                code=code,
                theorem_id=config.theorem_id,
                file_path=config.file_path,
                theorem_statement=config.theorem_id,
            )
        except TheoremNotFoundError as e:
            return HarnessError(
                error_type="theorem_not_found",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )
        except AmbiguousTheoremMatchError as e:
            return HarnessError(
                error_type="ambiguous_theorem_id",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )
        except UnsafeTargetRangeError as e:
            return HarnessError(
                error_type="unsafe_target_range",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )
        except TargetSpliceCardinalityError as e:
            return HarnessError(
                error_type="target_splice_cardinality",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )
        except InvalidProofAttemptError as e:
            return HarnessError(
                error_type="invalid_proof_attempt",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )
        except Exception as e:
            return HarnessError(
                error_type="construction_failed",
                message=f"Splice failed: {e}",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )


def _prepend_imports(code: str, additional_imports: list[str]) -> str:
    """Insert additional imports after the last existing import line."""
    lines = code.split("\n")
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i

    import_lines = []
    for imp in additional_imports:
        if not imp.startswith("import "):
            imp = f"import {imp}"
        import_lines.append(imp)

    if last_import_idx >= 0:
        lines = lines[: last_import_idx + 1] + import_lines + lines[last_import_idx + 1 :]
    else:
        lines = import_lines + lines

    return "\n".join(lines)


class StandardImportPathConverter:
    """Convert file paths to Lean import paths."""

    def convert(self, file_path: str) -> ImportPath:
        """Convert file path to import path."""
        from pathlib import Path

        normalized_path = file_path.replace("\\", "/")
        path = Path(normalized_path)

        if path.suffix == ".lean":
            path = path.with_suffix("")

        parts = list(path.parts)

        start_idx = 0
        for i, part in enumerate(parts):
            if part and part[0].isupper():
                start_idx = i
                break

        import_parts = parts[start_idx:]
        import_path = ".".join(import_parts)
        return ImportPath(path=import_path)
