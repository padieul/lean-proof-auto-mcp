"""
Import-based harness construction for theorem testing.

This module provides components for constructing test harnesses that preserve
ALL context from the original file by using Lean's import system instead of
manual signature reconstruction.
"""

from dataclasses import dataclass, field
from typing import Protocol

# ============================================================================
# Core Data Types
# ============================================================================


@dataclass(frozen=True)
class ScopedNotationContext:
    """Information about scoped notation in a theorem."""

    has_scoped_notation: bool
    scope_modules: list[str]  # e.g., ["Relator", "BigOperators"]
    scope_declaration: str  # e.g., "open scoped Relator in"

    @property
    def is_empty(self) -> bool:
        """Check if there is no scoped notation."""
        return not self.has_scoped_notation


@dataclass(frozen=True)
class ImportPath:
    """A Lean import path."""

    path: str  # e.g., "Fixtures.Algebra.Group"

    def to_import_statement(self) -> str:
        """Convert to import statement."""
        return f"import {self.path}"


@dataclass(frozen=True)
class TheoremType:
    """Extracted theorem type information."""

    type_expr: str  # The type expression
    source: str  # Where it came from (for debugging)


@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for harness construction."""

    theorem_id: str
    file_path: str
    proof_attempt: str
    additional_imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HarnessSuccess:
    """Successful harness construction."""

    code: str
    theorem_id: str
    file_path: str
    theorem_statement: str = ""  # The theorem type expression (for passing to validate_proof)


@dataclass(frozen=True)
class HarnessError:
    """Failed harness construction."""

    error_type: str  # "theorem_not_found", "invalid_path", "construction_failed"
    message: str
    theorem_id: str
    file_path: str
    generated_code: str | None = None  # For debugging


# Result type for harness construction
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

    pass


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

        Returns: ImportPath e.g., "Fixtures.Algebra.Group"
        """
        ...


class TheoremTypeExtractor(Protocol):
    """Extract theorem types from Lean files."""

    def extract_type(self, file_path: str, theorem_id: str) -> TheoremType:
        """
        Extract the type of a theorem.

        Args:
            file_path: Path to Lean file
            theorem_id: Fully qualified theorem name

        Returns: TheoremType with type expression
        Raises: TheoremNotFoundError if theorem doesn't exist
        """
        ...


class HarnessConstructor(Protocol):
    """Strategy for constructing test harnesses."""

    def construct(self, config: HarnessConfig) -> HarnessResult:
        """
        Construct a test harness.

        Returns: HarnessSuccess or HarnessError
        """
        ...


class ScopedNotationDetector(Protocol):
    """Detect scoped notation in theorem declarations."""

    def detect(self, theorem_text: str) -> ScopedNotationContext:
        """
        Detect scoped notation in a theorem declaration.

        Args:
            theorem_text: The complete theorem declaration text

        Returns: ScopedNotationContext with scope information
        """
        ...


# ============================================================================
# Implementations
# ============================================================================


class RegexScopedNotationDetector:
    """Detect scoped notation using regex patterns."""

    # Pattern: open scoped <modules> in
    SCOPED_PATTERN = r"open\s+scoped\s+([\w\s]+)\s+in\s+"

    def detect(self, theorem_text: str) -> ScopedNotationContext:
        """
        Detect scoped notation in a theorem declaration.

        Examples:
            "open scoped Relator in theorem ..." -> has_scoped_notation=True,
            scope_modules=["Relator"]
            "open scoped A B C in theorem ..." -> has_scoped_notation=True,
            scope_modules=["A", "B", "C"]
            "theorem foo : ..." -> has_scoped_notation=False, scope_modules=[]

        Args:
            theorem_text: The complete theorem declaration text

        Returns: ScopedNotationContext with detected scope information
        """
        import re

        # Search for scoped notation pattern
        match = re.search(self.SCOPED_PATTERN, theorem_text)

        if match:
            # Extract the modules string (e.g., "Relator" or "A B C")
            modules_str = match.group(1)

            # Split by whitespace to get individual modules
            scope_modules = modules_str.split()

            # Extract the complete scope declaration
            scope_declaration = match.group(0).rstrip()  # Remove trailing whitespace

            return ScopedNotationContext(
                has_scoped_notation=True,
                scope_modules=scope_modules,
                scope_declaration=scope_declaration,
            )
        else:
            # No scoped notation found
            return ScopedNotationContext(
                has_scoped_notation=False, scope_modules=[], scope_declaration=""
            )


class StandardImportPathConverter:
    """Convert file paths to Lean import paths."""

    def convert(self, file_path: str) -> ImportPath:
        """
        Convert file path to import path.

        Examples:
            "Fixtures/Algebra/Group.lean" -> "Fixtures.Algebra.Group"
            "fixtures/mathlib/Fixtures/Algebra/Group.lean" -> "Fixtures.Algebra.Group"

        Args:
            file_path: Path to Lean file

        Returns: ImportPath with dotted notation
        """
        from pathlib import Path

        # Normalize path separators (handle both Unix and Windows)
        normalized_path = file_path.replace("\\", "/")

        # Normalize path
        path = Path(normalized_path)

        # Remove .lean extension
        if path.suffix == ".lean":
            path = path.with_suffix("")

        # Convert to parts
        parts = list(path.parts)

        # Find the Lean project root (heuristic: first capitalized directory)
        start_idx = 0
        for i, part in enumerate(parts):
            if part and part[0].isupper():
                start_idx = i
                break

        # Take from project root onwards
        import_parts = parts[start_idx:]

        # Join with dots
        import_path = ".".join(import_parts)

        return ImportPath(path=import_path)


class LeanInteractTheoremTypeExtractor:
    """Extract theorem types using LeanInteract."""

    def __init__(self, querier: "Querier") -> None:  # type: ignore[name-defined]
        """
        Initialize with querier.

        Args:
            querier: Querier instance for extracting declarations
        """
        from ..lean.ports import Querier

        self.querier: Querier = querier
        # Cache declarations per file path to avoid O(n) extract_declarations
        # calls when probing multiple theorems in the same file.
        self._declarations_cache: dict[str, list] = {}
        # Cache extraction failures per file path so we fail fast instead of
        # repeatedly hitting a dead server (negative caching).
        self._declarations_errors: dict[str, Exception] = {}

    def clear_cache(self) -> None:
        """Clear the declarations cache after batch operations."""
        self._declarations_cache.clear()
        self._declarations_errors.clear()

    def extract_type(self, file_path: str, theorem_id: str) -> TheoremType:
        """
        Extract the full file content with the theorem location.

        This method returns the ENTIRE source file content, which preserves
        all variable declarations, imports, and context. The caller will
        replace just the theorem proof with the test tactic.

        Declarations are cached per file_path so that probing N theorems
        in the same file calls extract_declarations only once (O(1) not O(n)).
        Failures are also cached (negative caching) to avoid hammering a dead
        server when the first call fails.

        Args:
            file_path: Path to Lean file (absolute or relative to workspace)
            theorem_id: Fully qualified theorem name (may include namespace like
                "Subgroup.top_prod_top")

        Returns: TheoremType with full file content and theorem location
        Raises: TheoremNotFoundError if theorem doesn't exist
        """
        from pathlib import Path

        # First, use LeanInteract to verify the theorem exists
        file_path_obj = Path(file_path)
        file_path_str = str(file_path_obj) if not file_path_obj.is_absolute() else file_path

        # Fail fast if we already know this file's declarations can't be extracted
        if file_path_str in self._declarations_errors:
            cached_err = self._declarations_errors[file_path_str]
            raise type(cached_err)(str(cached_err)) from cached_err

        # Use cached declarations if available (critical for batch probe_file)
        if file_path_str in self._declarations_cache:
            declarations = self._declarations_cache[file_path_str]
        else:
            try:
                declarations = self.querier.extract_declarations(file_path_str)
                self._declarations_cache[file_path_str] = declarations
            except Exception as e:
                # Negative cache: remember the failure so subsequent theorems
                # in the same file fail immediately instead of waiting for timeout
                self._declarations_errors[file_path_str] = e
                raise

        # Extract the local name (without namespace) for matching
        local_name = theorem_id.split(".")[-1] if "." in theorem_id else theorem_id

        # Find the theorem to verify it exists
        theorem_found = False
        for decl in declarations:
            if (
                decl.name == theorem_id
                or decl.full_name == theorem_id
                or decl.name == local_name
                or decl.full_name == local_name
            ):
                theorem_found = True
                break

        if not theorem_found:
            raise TheoremNotFoundError(f"Theorem {theorem_id} not found in {file_path}")

        # Now read the ENTIRE source file
        workspace_path = self.querier.server_manager.workspace_path
        full_file_path = workspace_path / file_path_str if workspace_path else Path(file_path_str)

        if not full_file_path.exists():
            # Try to find it by looking for capitalized parts
            parts = Path(file_path_str).parts
            for i, part in enumerate(parts):
                if part and part[0].isupper():
                    relative_from_capital = Path(*parts[i:])
                    candidate = (
                        workspace_path / relative_from_capital
                        if workspace_path
                        else relative_from_capital
                    )
                    if candidate.exists():
                        full_file_path = candidate
                        break

        # Read the entire source file
        try:
            with open(full_file_path, encoding="utf-8") as f:
                f.read()

            # Return the full file content with a marker for the theorem location
            # The type_expr will be "FULL_FILE:<theorem_id>"
            return TheoremType(type_expr=f"FULL_FILE:{theorem_id}", source=f"FullFile:{file_path}")

        except Exception as e:
            raise TheoremNotFoundError(f"Failed to read source file {file_path}: {e}") from e

    def _infer_free_variables(
        self, constants: list[str], type_str: str
    ) -> dict[str, tuple[str, str | None]]:
        """
        Infer free variables and their types from constants and type string.

        This is a heuristic approach that identifies likely type variables
        (single uppercase letters or capitalized identifiers) and infers
        their types based on usage patterns in the type string.

        Args:
            constants: List of constant names from the type
            type_str: The type expression string

        Returns: Dict mapping variable names to their inferred types
        """
        import re

        free_vars: dict[str, tuple[str, str | None]] = {}

        # Look for patterns like "Subgroup G" or "Group G" to infer types
        # Pattern: TypeConstructor followed by a single uppercase letter
        type_patterns = [
            (r"Subgroup\s+([A-Z])\b", "Type _", "Group"),
            (r"AddSubgroup\s+([A-Z])\b", "Type _", "AddGroup"),
            (r"Group\s+([A-Z])\b", "Type _", "Group"),
            (r"AddGroup\s+([A-Z])\b", "Type _", "AddGroup"),
            (r"Monoid\s+([A-Z])\b", "Type _", "Monoid"),
            (r"Ring\s+([A-Z])\b", "Type _", "Ring"),
            (r"Field\s+([A-Z])\b", "Type _", "Field"),
        ]

        for pattern, base_type, instance_type in type_patterns:
            matches = re.findall(pattern, type_str)
            for var in matches:
                if var not in free_vars:
                    free_vars[var] = (base_type, instance_type)

        # Also check for variables in constants that appear in type_str
        for const in constants:
            # Single uppercase letters are likely type variables
            if len(const) == 1 and const.isupper() and const in type_str and const not in free_vars:
                # Default to Type _ without instance
                free_vars[const] = ("Type _", None)

        return free_vars

    def _generate_variable_declarations(self, free_vars: dict[str, tuple[str, str | None]]) -> str:
        """
        Generate variable declarations from inferred free variables.

        Args:
            free_vars: Dict mapping variable names to (base_type, instance_type) tuples

        Returns: Variable declaration string
        """
        if not free_vars:
            return ""

        # Group variables by their type signature
        type_groups: dict[tuple[str, str | None], list[str]] = {}
        for var, (base_type, instance_type) in free_vars.items():
            key = (base_type, instance_type)
            if key not in type_groups:
                type_groups[key] = []
            type_groups[key].append(var)

        # Generate variable declarations
        var_decls = []
        for (base_type, instance_type), vars in type_groups.items():
            vars_str = " ".join(vars)
            if instance_type:
                # Generate both type and instance declarations
                # Each instance needs its own brackets
                instances = " ".join(f"[{instance_type} {v}]" for v in vars)
                var_decls.append(f"variable {{{vars_str} : {base_type}}} {instances}")
            else:
                var_decls.append(f"variable {{{vars_str} : {base_type}}}")

        return "\n".join(var_decls)


# ============================================================================
# Pure helpers for harness construction
# ============================================================================

# Keywords that signal a new top-level Lean construct.
# Used by _skip_proof_block to detect where a proof ends.
_DECLARATION_STARTERS: tuple[str, ...] = (
    "theorem ",
    "lemma ",
    "def ",
    "instance ",
    "variable ",
    "namespace ",
    "section ",
    "end ",
    "open ",
    "set_option ",
    "attribute ",
    "class ",
    "structure ",
    "inductive ",
    "abbrev ",
    "noncomputable ",
    "protected ",
    "private ",
    "nonrec ",
    "#check ",
    "#eval ",
    "#print ",
    "import ",
    "@[",
    "/-",
)


def _is_declaration_start(stripped: str) -> bool:
    """Check whether a stripped line begins a new Lean declaration or scope.

    Pure function — no side effects, no I/O.
    """
    if stripped == "end" or stripped == "section":
        return True
    return any(stripped.startswith(kw) for kw in _DECLARATION_STARTERS)


def _is_theorem_or_lemma(stripped: str) -> bool:
    """Check whether a stripped line declares a theorem or lemma.

    Handles prefixed variants: noncomputable, protected, private.
    Pure function — no side effects, no I/O.
    """
    return (
        stripped.startswith("theorem ")
        or stripped.startswith("lemma ")
        or " theorem " in stripped
        or " lemma " in stripped
    )


def _find_proof_assignment(line: str) -> int:
    """Find the index of the proof-starting ':=' in a line.

    Skips ':=' that appear inside brace-delimited type signatures
    (e.g., ``{x : Nat := 0}``).  Returns -1 if no proof ':=' is found.

    Pure function — no side effects, no I/O.
    """
    depth = 0  # brace nesting depth
    i = 0
    while i < len(line) - 1:
        ch = line[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth = max(0, depth - 1)
        elif ch == ':' and line[i + 1] == '=' and depth == 0:
            return i
        i += 1
    return -1


class ImportBasedHarnessConstructor:
    """Construct test harnesses using import-based approach."""

    def __init__(
        self, type_extractor: TheoremTypeExtractor, path_converter: ImportPathConverter
    ) -> None:
        """
        Initialize with dependencies.

        Args:
            type_extractor: Extracts theorem types
            path_converter: Converts file paths to import paths
        """
        self.type_extractor = type_extractor
        self.path_converter = path_converter
        
        # Caching infrastructure
        self._file_cache: dict[str, str] = {}
        self._decl_cache: dict[str, TheoremType] = {}
        self._theorem_verified: dict[str, bool] = {}

    def construct(self, config: HarnessConfig) -> HarnessResult:
        """
        Construct test harness by copying imports, variables, and the target
        theorem (with modified proof) from the source file.

        Returns: HarnessSuccess or HarnessError
        """
        try:
            # Step 1: Extract theorem type (with caching)
            cache_key = f"{config.file_path}::{config.theorem_id}"

            # Check theorem_verified cache to short-circuit repeated lookups
            if cache_key in self._decl_cache:
                theorem_type = self._decl_cache[cache_key]
            elif cache_key in self._theorem_verified:
                # Theorem was verified to exist but type not cached (shouldn't happen,
                # but handle gracefully by re-extracting)
                theorem_type = self.type_extractor.extract_type(config.file_path, config.theorem_id)
                self._decl_cache[cache_key] = theorem_type
            else:
                theorem_type = self.type_extractor.extract_type(config.file_path, config.theorem_id)
                self._decl_cache[cache_key] = theorem_type
                self._theorem_verified[cache_key] = True
        except TheoremNotFoundError as e:
            return HarnessError(
                error_type="theorem_not_found",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )
        except Exception as e:
            return HarnessError(
                error_type="type_extraction_failed",
                message=f"Failed to extract theorem type: {e}",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )

        # Determine the actual theorem statement (type expression)
        # Strip FULL_FILE: prefix if present
        if theorem_type.type_expr.startswith("FULL_FILE:"):
            theorem_stmt = theorem_type.type_expr[len("FULL_FILE:"):]
        else:
            theorem_stmt = theorem_type.type_expr

        try:
            # Step 2: Check if we got the full file marker
            if theorem_type.type_expr.startswith("FULL_FILE:"):
                # Strategy: Copy ENTIRE file, then modify only what's needed
                # This preserves ALL context (imports, variables, namespaces, etc.)
                from pathlib import Path

                # Access server_manager through the querier
                # Type ignore because we know the concrete implementation has this attribute
                workspace_path = self.type_extractor.querier.server_manager.workspace_path  # type: ignore[attr-defined]
                if workspace_path:
                    full_file_path = workspace_path / config.file_path
                else:
                    full_file_path = Path(config.file_path)

                if not full_file_path.exists():
                    # Try to find it
                    parts = Path(config.file_path).parts
                    for i, part in enumerate(parts):
                        if part and part[0].isupper():
                            relative_from_capital = Path(*parts[i:])
                            candidate = (
                                workspace_path / relative_from_capital
                                if workspace_path
                                else relative_from_capital
                            )
                            if candidate.exists():
                                full_file_path = candidate
                                break

                # Check file content cache
                file_path_str = str(full_file_path)
                if file_path_str in self._file_cache:
                    file_content = self._file_cache[file_path_str]
                else:
                    with open(full_file_path, encoding="utf-8") as f:
                        file_content = f.read()
                    self._file_cache[file_path_str] = file_content

                # Build harness by copying whole file and modifying proofs
                harness = self._build_harness_by_proof_replacement(
                    file_content=file_content,
                    theorem_id=config.theorem_id,
                    proof_attempt=config.proof_attempt,
                    additional_imports=config.additional_imports,
                )

                return HarnessSuccess(
                    code=harness,
                    theorem_id=config.theorem_id,
                    file_path=config.file_path,
                    theorem_statement=theorem_stmt,
                )

            else:
                # Fallback to old approach (shouldn't happen with new extractor)
                import_path = self.path_converter.convert(config.file_path)
                imports = [import_path.to_import_statement()]
                imports.extend(config.additional_imports)
                import_block = "\n".join(imports)

                example_block = f"""-- Test harness for {config.theorem_id}
    example : {theorem_type.type_expr} := by
      {config.proof_attempt}
    """
                harness = f"{import_block}\n\n{example_block}"

                return HarnessSuccess(
                    code=harness,
                    theorem_id=config.theorem_id,
                    file_path=config.file_path,
                    theorem_statement=theorem_stmt,
                )

        except Exception as e:
            return HarnessError(
                error_type="construction_failed",
                message=f"Unexpected error during construction: {e}",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
                generated_code=None,
            )


    def _build_harness_by_proof_replacement(
        self, file_content: str, theorem_id: str, proof_attempt: str, additional_imports: list[str]
    ) -> str:
        """
        Build harness by copying entire file and replacing proofs.

        Strategy:
        1. Copy ENTIRE file (preserves all context)
        2. Replace target theorem's proof with test tactic
        3. Replace other theorem/lemma proofs with 'sorry' (keep declarations)

        This ensures ALL context is preserved without complex parsing.

        Args:
            file_content: Complete source file content
            theorem_id: Target theorem to test (e.g., "Subgroup.mem_prod")
            proof_attempt: Tactic to test (e.g., "aesop")
            additional_imports: Extra imports to add

        Returns: Harness code
        """

        lines = file_content.split("\n")
        result_lines: list[str] = []

        # Step 1: Add any additional imports at the top (after existing imports)
        if additional_imports:
            # Find where imports end
            last_import_idx = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("import "):
                    last_import_idx = i

            # Insert additional imports after last import
            if last_import_idx >= 0:
                for i in range(last_import_idx + 1):
                    result_lines.append(lines[i])
                for imp in additional_imports:
                    if not imp.startswith("import "):
                        imp = f"import {imp}"
                    result_lines.append(imp)
                lines = lines[last_import_idx + 1 :]
            else:
                # No imports found, add at beginning
                for imp in additional_imports:
                    if not imp.startswith("import "):
                        imp = f"import {imp}"
                    result_lines.append(imp)

        # Step 2: Process the rest of the file
        # Find all theorem/lemma declarations and their proofs
        local_name = theorem_id.split(".")[-1] if "." in theorem_id else theorem_id

        i = 0
        in_doc_comment = False

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Track doc comment state
            if stripped.startswith("/-"):
                in_doc_comment = True
            if in_doc_comment:
                result_lines.append(line)
                if "-/" in stripped:
                    in_doc_comment = False
                i += 1
                continue

            # Track attribute state (skip attributes for theorems/lemmas)
            if stripped.startswith("@["):
                # Peek ahead to see if next non-empty line is theorem/lemma
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and _is_theorem_or_lemma(lines[j].strip()):
                    # Skip this attribute line — the theorem handler will emit sorry
                    i += 1
                    continue
                # Not a theorem/lemma attribute, keep it

            # Check if this is a theorem or lemma declaration
            if _is_theorem_or_lemma(stripped):
                # Extract the declaration name
                decl_name = self._extract_declaration_name(stripped)
                is_target = (
                    decl_name in (local_name, theorem_id)
                    or stripped.startswith(f"theorem {local_name}")
                    or stripped.startswith(f"lemma {local_name}")
                )

                # Find ':=' — use brace-aware search to skip ':=' inside type sigs
                assign_pos = _find_proof_assignment(line)

                if assign_pos >= 0:
                    # ':=' on the same line as the declaration
                    before_proof = line[:assign_pos]

                    if is_target:
                        result_lines.append(f"{before_proof}:= by")
                        result_lines.append(f"  {proof_attempt}")
                    else:
                        result_lines.append(f"{before_proof}:= by sorry")

                    # Skip the original proof
                    i += 1
                    i = self._skip_proof_block(lines, i)
                else:
                    # Multi-line declaration — collect until we find ':='
                    decl_lines = [line]
                    i += 1

                    while i < len(lines):
                        assign_pos = _find_proof_assignment(lines[i])
                        if assign_pos >= 0:
                            break
                        # Stop collecting if we hit a new declaration (malformed source)
                        if _is_declaration_start(lines[i].strip()):
                            break
                        decl_lines.append(lines[i])
                        i += 1

                    # Now we're at the ':=' line (or ran out of lines)
                    if i < len(lines) and assign_pos >= 0:
                        proof_line = lines[i]
                        before_proof = proof_line[:assign_pos]

                        # Add all declaration lines
                        result_lines.extend(decl_lines)

                        if is_target:
                            result_lines.append(f"{before_proof}:= by")
                            result_lines.append(f"  {proof_attempt}")
                        else:
                            result_lines.append(f"{before_proof}:= by sorry")

                        # Skip the original proof (start from next line)
                        i += 1
                        i = self._skip_proof_block(lines, i)
                    else:
                        # No ':=' found — copy declaration as-is (e.g., axiom)
                        result_lines.extend(decl_lines)
            else:
                # Not a theorem/lemma — copy as-is
                result_lines.append(line)
                i += 1

        return "\n".join(result_lines)

    def _extract_declaration_name(self, line: str) -> str:
        """
        Extract theorem/lemma name from declaration line.

        Examples:
            "theorem mem_prod : ..." -> "mem_prod"
            "  theorem top_prod_top {G N : Type*} : ..." -> "top_prod_top"
        """
        import re

        # Match: (theorem|lemma) <name>
        match = re.search(r"(?:theorem|lemma)\s+(\w+)", line)
        if match:
            return match.group(1)
        return ""

    def _skip_proof_block(self, lines: list[str], start_idx: int) -> int:
        """
        Skip over a proof block, handling nested structures and doc comments.

        A proof ends when we return to the same indentation level
        and hit a new declaration or end of block.

        Uses the module-level ``_is_declaration_start`` helper to detect
        Lean keywords that signal the start of a new top-level construct.

        Args:
            lines: All lines
            start_idx: Index after ':=' line

        Returns: Index of first line after proof
        """
        if start_idx >= len(lines):
            return start_idx

        # Base indentation is the indentation of the ':=' line (the line before start_idx)
        base_indent = len(lines[start_idx - 1]) - len(lines[start_idx - 1].lstrip())

        i = start_idx
        in_doc_comment = False

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Track doc comment state
            if stripped.startswith("/-"):
                in_doc_comment = True
            if in_doc_comment:
                if "-/" in stripped:
                    in_doc_comment = False
                i += 1
                continue

            # Empty lines or single-line comments — keep skipping
            if not stripped or stripped.startswith("--"):
                i += 1
                continue

            # Check for new declarations at same or lower indentation
            current_indent = len(line) - len(line.lstrip())

            if current_indent <= base_indent and _is_declaration_start(stripped):
                break

            i += 1

        return i


    def _validate_harness(self, harness: str) -> None:
        """
        Validate generated harness structure.

        Raises: HarnessConstructionError if invalid
        """
        lines = harness.split("\n")

        # Check 1: Should have at least one import
        has_import = any(line.strip().startswith("import") for line in lines)
        if not has_import:
            raise HarnessConstructionError(
                "Harness should contain at least one import statement", generated_code=harness
            )

        # Check 2: Should contain at least one theorem or lemma
        has_theorem = any("theorem " in line or "lemma " in line for line in lines)
        if not has_theorem:
            raise HarnessConstructionError(
                "Harness must contain at least one theorem or lemma", generated_code=harness
            )

    def clear_cache(self) -> None:
        """Clear all caches after batch operation."""
        self._file_cache.clear()
        self._decl_cache.clear()
        self._theorem_verified.clear()
        # Also clear the type extractor's declarations cache if it supports it
        if hasattr(self.type_extractor, 'clear_cache'):
            self.type_extractor.clear_cache()
