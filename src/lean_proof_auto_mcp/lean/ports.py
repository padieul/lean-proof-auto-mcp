"""
Abstract interfaces (ports) for LeanInteract Adapter Layer.

This module defines the protocols that the Core Domain Layer depends on.
These are abstract interfaces that enable testing without LeanInteract and
allow swapping implementations.

Following hexagonal architecture:
- Core Domain depends on these protocols
- Adapter implementations depend inward toward these protocols
- No dependency on LeanInteract implementation details

Requirements: 9.1, 9.2, 9.3, 9.5
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..core.verify_domain import LeanRunResult
    from .server_manager import LeanInteractServerManager as _ServerManager


@dataclass(frozen=True)
class Range:
    """Position range in a file."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class DeclValue:
    """

    The value (proof/definition body) of a declaration.


    This represents the proof or definition body extracted from LeanInteract,

    including both the pretty-printed text and the list of constants referenced.


    Requirements: 1.2, 1.3, 2.1, 2.2
    """

    pp: str  # Pretty-printed proof text

    constants: list[str]  # Constants/lemmas referenced

    range: Range  # Position in file

    def get_all_references(self) -> list[str]:
        """

        Get all references (constants + parsed from pp).


        Primary: Use constants list (from LeanInteract value.constants)

        Fallback: Parse pp text for additional references


        Returns:

            List of all unique references


        Requirements: 2.1, 2.2
        """

        # Primary: use constants list

        refs = set(self.constants)

        # Fallback: parse pp text for additional references

        # This is a simple implementation - can be enhanced with proper parsing

        # For now, we rely primarily on constants list

        # TODO: Implement pp text parsing if constants list is incomplete

        return list(refs)


@dataclass(frozen=True)
class Declaration:
    """

    A Lean declaration (theorem, lemma, definition).


    This represents a complete declaration extracted from LeanInteract,

    including all metadata needed for hint extraction and context building.


    Requirements: 1.1, 1.2, 1.3
    """

    name: str  # Short name

    full_name: str  # Fully qualified name

    type: str  # Type signature

    value: DeclValue | None  # Proof/definition body

    attributes: list[str]  # [simp], [instance], etc.

    range: Range  # Position in file

    namespace: str  # Current namespace

    kind: str = ""  # "theorem", "lemma", "def", "instance", etc.

    @property
    def is_theorem(self) -> bool:
        """Check if this is a theorem or lemma."""

        return self.kind in ("theorem", "lemma")

    @property
    def has_simp_attribute(self) -> bool:
        """Check if this has the simp attribute."""

        return "simp" in self.attributes


@dataclass(frozen=True)
class ProofState:
    """

    The state of a proof at a given point.


    This represents the current goal, hypotheses, and type context during

    proof construction, extracted from LeanInteract proof state.


    Requirements: 16.1, 16.2, 16.3, 16.4
    """

    goal: str  # Current goal

    hypotheses: list[str]  # Available hypotheses

    type_context: str  # Type context

    goals_remaining: int  # Number of goals left

    def complexity_score(self) -> float:
        """

        Estimate goal complexity (higher = more complex).


        This is a simple heuristic based on goal length and structure.

        Can be enhanced with more sophisticated analysis.


        Returns:

            Complexity score (higher = more complex)


        Requirements: 13.2
        """

        # Based on goal length, nesting depth, etc.

        score = len(self.goal)

        score += self.goal.count("∀") * 10

        score += self.goal.count("∃") * 10

        score += self.goal.count("→") * 5

        return float(score)


@dataclass(frozen=True)
class TacticResult:
    """

    Result of applying a tactic to a proof state.


    Requirements: 16.2
    """

    success: bool

    new_proof_state: ProofState | None

    error_message: str | None


@dataclass(frozen=True)
class ValidationResult:
    """

    Result of validating a proof attempt.


    This represents the outcome of validating a proof using LeanInteract,

    including structured error information and tactical suggestions.


    Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 17.1, 17.2, 17.3, 17.4, 17.5
    """

    status: str  # "success" | "rejected" | "error" | "incomplete" | "timeout"
    # "success"    — proof closes all goals
    # "rejected"   — Lean processed the proof but reported errors (type mismatch,
    #                tactic failure, etc.). The tool worked correctly; the proof is wrong.
    # "error"      — infrastructure/tool failure (server crash, missing library, etc.)
    # "incomplete" — proof compiles but leaves unsolved goals
    # "timeout"    — validation exceeded time budget

    error_message: str | None

    error_location: tuple[int, int] | None  # (line, column)

    proof_state: ProofState | None  # If incomplete

    suggestions: list[str]

    time_s: float


@dataclass(frozen=True)
class TheoremContext:
    """

    Rich context about a theorem.


    This includes the theorem statement, original proof, hypotheses,

    in-scope declarations, and namespace information.


    Requirements: 3.1, 3.2, 3.3, 3.4, 8.2, 8.3, 8.4
    """

    theorem_statement: str

    original_proof: str

    hypotheses: list[str]

    in_scope: list[str]  # Declarations in scope
    namespace: str
    value_range: Range | None = None  # Exact DeclValue range for raw source extraction


class Querier(Protocol):
    """

    Port for extracting declarations and references from Lean files.


    This protocol defines how the Core Domain Layer queries Lean files

    for declarations, proof references, and theorem context without

    depending on LeanInteract implementation details.


    Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4
    """

    @property
    def server_manager(self) -> "_ServerManager":
        """Get the server manager instance."""
        ...

    def extract_declarations(self, file_path: str) -> list[Declaration]:
        """

        Extract all declarations from a file using FileCommand(declarations=True).


        Args:

            file_path: Path to Lean file


        Returns:

            List of declarations with complete information


        Raises:

            RuntimeError: If LeanInteract fails or file not found


        Requirements: 1.1, 1.2, 1.3
        """
        ...

    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        """

        Extract lemma references from a proof using value.constants + text parsing.


        Primary: Use declaration.value.constants

        Fallback: Parse declaration.value.pp text


        Args:

            file_path: Path to Lean file

            theorem_id: Theorem identifier


        Returns:

            List of lemma references (fully qualified names)


        Raises:

            ValueError: If theorem not found

            RuntimeError: If LeanInteract fails


        Requirements: 2.1, 2.2, 2.3
        """
        ...

    def get_theorem_context(self, file_path: str, theorem_id: str) -> TheoremContext:
        """

        Get full context for a theorem including scope and hypotheses.


        Args:

            file_path: Path to Lean file

            theorem_id: Theorem identifier


        Returns:

            TheoremContext with complete information


        Raises:

            ValueError: If theorem not found

            RuntimeError: If LeanInteract fails


        Requirements: 3.1, 3.2, 3.3, 3.4
        """
        ...

    def clear_cache(self) -> None:
        """
        Clear any cached declarations.

        Call when file contents may have changed to force fresh extraction.
        """
        ...

    def read_source_file(self, file_path: str) -> str:
        """
        Read source file content, resolving path via workspace_path.

        This moves file-reading I/O from the core layer to the adapter layer
        where it belongs (hexagonal architecture).

        Args:
            file_path: Path to Lean file (relative to workspace)

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file cannot be found
        """
        ...


class ProofStateInspector(Protocol):
    """

    Port for inspecting proof states and applying tactics.


    This protocol defines how the Core Domain Layer inspects proof states

    and applies tactics without depending on LeanInteract implementation details.


    Requirements: 16.1, 16.2, 16.3, 16.4
    """

    def get_initial_proof_state(self, theorem: Declaration) -> ProofState:
        """

        Get initial proof state using Command with sorry.


        Args:

            theorem: Declaration to get proof state for


        Returns:

            Initial proof state


        Raises:

            RuntimeError: If LeanInteract fails


        Requirements: 16.1
        """
        ...

    def apply_tactic(self, proof_state_id: int, tactic: str) -> TacticResult:
        """

        Apply a tactic using ProofStep.


        Args:

            proof_state_id: ID of proof state to apply tactic to

            tactic: Tactic to apply


        Returns:

            TacticResult with new proof state or error


        Requirements: 16.2
        """
        ...


class ProofValidator(Protocol):
    """

    Port for validating proof attempts and verifying files.


    This protocol defines how the Core Domain Layer validates proofs
    and verifies entire Lean files without depending on LeanInteract
    implementation details.


    Requirements: 6.1, 6.2, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
    """

    def validate_proof(
        self,
        theorem_statement: str,
        proof_attempt: str,
        timeout_s: float = 10.0,
        file_path: str | None = None,
        theorem_id: str | None = None,
    ) -> ValidationResult:
        """

        Validate a proof attempt using Command.


        Args:

            theorem_statement: Theorem statement

            proof_attempt: Proof to validate

            timeout_s: Timeout in seconds

            file_path: Optional path to original file (for context preservation)

            theorem_id: Optional theorem identifier (for context preservation)


        Returns:

            ValidationResult with status and feedback


        Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
        """
        ...

    def validate_harness_code(
        self,
        harness_code: str,
        timeout_s: float = 10.0,
        file_path: str | None = None,
    ) -> ValidationResult:
        """
        Validate prebuilt harness code exactly as provided.

        Args:
            harness_code: Fully constructed harness source to execute
            timeout_s: Timeout in seconds
            file_path: Optional file key for server selection

        Returns:
            ValidationResult with status and feedback
        """
        ...

    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> "LeanRunResult":
        """
        Run Lean verification on file or theorem.

        This method performs file-level or theorem-level verification using
        LeanInteract. When theorem_id is None, performs file-level verification.
        When theorem_id is provided, performs theorem-level verification.

        Args:
            workspace_path: Path to workspace root
            file_path: Path to Lean file (relative to workspace)
            theorem_id: Optional theorem identifier for theorem-level verification
            budget_s: Timeout budget in seconds

        Returns:
            LeanRunResult with status, diagnostics, logs, and timing information

        Raises:
            TimeoutError: If verification exceeds budget_s
            RuntimeError: If Lean verification fails

        Requirements: 6.1, 6.2
        """
        ...


class ServerManager(Protocol):
    """

    Port for managing LeanInteract server lifecycle.


    This protocol defines how the Core Domain Layer manages server instances

    without depending on LeanInteract implementation details.


    Requirements: 10.6, 28.3, 28.4, 28.5, 28.6
    """

    def get_server(self, file_path: str) -> "LeanServer":
        """

        Get or create server instance for file.


        Maintains one server instance per file to avoid startup overhead.


        Args:

            file_path: Path to Lean file


        Returns:

            LeanServer instance


        Requirements: 10.6, 28.4
        """
        ...

    def restart_server(self, file_path: str) -> None:
        """

        Restart crashed server.


        Args:

            file_path: Path to Lean file


        Requirements: 28.5
        """
        ...

    def shutdown_all(self) -> None:
        """

        Shutdown all server instances.


        Requirements: 28.6
        """
        ...


class LeanServer(Protocol):
    """

    Port for a LeanInteract server instance.


    This is a minimal protocol for server operations needed by the Core Domain.
    """

    def run(self, command: object, timeout: float) -> object:
        """Run a command with timeout."""
        ...

    def kill(self) -> None:
        """Kill the server process."""
        ...
