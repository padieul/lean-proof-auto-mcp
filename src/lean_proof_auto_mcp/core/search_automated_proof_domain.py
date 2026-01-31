"""
Core domain structures for the search-annotations tool.

This module defines immutable data structures for hint search, minimization,
and proof patch generation following hexagonal architecture principles.

Requirements: 3.1, 3.7, 3.8, 4.1, 4.2, 5.1, 6.1, 7.3, 14.1
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..observability.ports import MetadataCollector

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class HintType(Enum):
    """
    Type of hint for automation.

    Requirements: 3.7, 3.8, 6.2, 6.3
    """

    ADD_SAFE = "add_safe"  # Safe aesop rule
    ADD_UNSAFE = "add_unsafe"  # Unsafe aesop rule
    UNFOLD = "unfold"  # Definition unfolding
    SIMP = "simp"  # Simp lemma
    RULE_SET = "rule_set"  # Rule set reference


class CandidateSource(Enum):
    """
    Source from which a candidate hint was extracted.

    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
    """

    GOAL_SYMBOLS = "goal_symbols"  # Symbols in goal statement
    LOCAL_CONTEXT = "local_context"  # Hypotheses and local definitions
    SAME_NAMESPACE = "same_namespace"  # Declarations in same namespace
    NEARBY_DECLS = "nearby_decls"  # Declarations within ±N lines
    ORIGINAL_PROOF_REFS = "original_proof_refs"  # References in original proof


# ============================================================================
# Core Domain Models (Immutable)
# ============================================================================


@dataclass(frozen=True)
class Hint:
    """
    Immutable hint for automation.

    A hint represents a single piece of information (lemma, definition, rule)
    that can be provided to automation to help close a goal.

    Requirements: 3.1, 3.7, 3.8, 6.1

    Attributes:
        name: Fully-qualified name of the hint
        type: Type of hint (add_safe, unfold, simp, etc.)
        source: Source from which this hint was extracted
    """

    name: str
    type: HintType
    source: CandidateSource

    def __post_init__(self) -> None:
        """Validate hint parameters."""
        if not self.name:
            raise ValueError("name must be non-empty")

    def to_lean_syntax(self) -> str:
        """
        Convert hint to Lean syntax.

        Returns:
            Lean syntax string for this hint

        Requirements: 6.1, 6.2, 6.3
        """
        if self.type in (
            HintType.SIMP,
            HintType.UNFOLD,
            HintType.ADD_SAFE,
            HintType.ADD_UNSAFE,
            HintType.RULE_SET,
        ):
            return self.name
        else:
            return self.name


@dataclass(frozen=True)
class HintSet:
    """
    Immutable set of hints.

    HintSet maintains immutability through frozenset and provides
    functional operations (add, remove) that return new HintSet instances.

    Requirements: 4.1, 4.2, 5.1, 5.2

    Attributes:
        hints: Frozen set of hints
    """

    hints: frozenset[Hint]

    def __init__(self, hints: frozenset[Hint] | set[Hint] | list[Hint] | None = None):
        """
        Initialize HintSet from various collection types.

        Args:
            hints: Collection of hints or None for empty set
        """
        if hints is None:
            object.__setattr__(self, "hints", frozenset())
        elif isinstance(hints, frozenset):
            object.__setattr__(self, "hints", hints)
        elif isinstance(hints, (set, list)):
            object.__setattr__(self, "hints", frozenset(hints))
        else:
            raise TypeError(f"hints must be frozenset, set, list, or None, got {type(hints)}")

    def add(self, hint: Hint) -> "HintSet":
        """
        Return new HintSet with hint added.

        Args:
            hint: Hint to add

        Returns:
            New HintSet with hint included

        Requirements: 5.2
        """
        return HintSet(self.hints | {hint})

    def remove(self, hint: Hint) -> "HintSet":
        """
        Return new HintSet with hint removed.

        Args:
            hint: Hint to remove

        Returns:
            New HintSet without hint

        Requirements: 5.2
        """
        return HintSet(self.hints - {hint})

    def size(self) -> int:
        """
        Return number of hints in set.

        Returns:
            Number of hints

        Requirements: 4.7
        """
        return len(self.hints)

    def is_empty(self) -> bool:
        """
        Check if hint set is empty.

        Returns:
            True if empty, False otherwise
        """
        return len(self.hints) == 0

    def to_sorted_list(self) -> list[Hint]:
        """
        Return hints as sorted list for deterministic output.

        Sorts by (name, type, source) for stable ordering.

        Returns:
            Sorted list of hints

        Requirements: 13.2
        """
        return sorted(self.hints, key=lambda h: (h.name, h.type.value, h.source.value))


@dataclass(frozen=True)
class Candidate:
    """
    Candidate hint with ranking metadata.

    A candidate represents a potential hint that has been extracted
    from some source and ranked for search priority.

    Requirements: 3.1, 3.9, 3.10

    Attributes:
        hint: The hint itself
        rank: Ranking score (higher is better)
        metadata: Additional metadata about the candidate
    """

    hint: Hint
    rank: float
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate candidate parameters."""
        if self.rank < 0:
            raise ValueError("rank must be non-negative")


@dataclass(frozen=True)
class SearchResult:
    """
    Result from hint set search.

    Encapsulates the outcome of searching for a closing hint set,
    including the best hint set found, search statistics, and evidence.

    Requirements: 4.4, 4.5, 4.6, 4.8

    Attributes:
        outcome: Search outcome (closed, partial, failed)
        best_hint_set: Best hint set found (None if failed)
        attempts: Number of probe attempts made
        explored_sets: Number of unique hint sets explored
        evidence: Execution outcome for best hint set (None if failed)
    """

    outcome: Literal["closed", "partial", "failed"]
    best_hint_set: HintSet | None
    attempts: int
    explored_sets: int
    evidence: "ExecutionOutcome | None"

    def __post_init__(self) -> None:
        """Validate search result parameters."""
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")
        if self.explored_sets < 0:
            raise ValueError("explored_sets must be non-negative")
        if self.outcome == "closed" and self.best_hint_set is None:
            raise ValueError("closed outcome requires best_hint_set")


@dataclass(frozen=True)
class ExecutionOutcome:
    """
    Outcome from executing automation with a hint set.

    Requirements: 4.3, 4.9

    Attributes:
        status: Execution status (success, failure, timeout, error)
        automation_used: Automation tool used (aesop, grind, simp)
        duration_s: Execution duration in seconds
        output: Standard output from execution
        error: Error message if status is error (None otherwise)
    """

    status: Literal["success", "failure", "timeout", "error"]
    automation_used: str
    duration_s: float
    output: str
    error: str | None = None

    def __post_init__(self) -> None:
        """Validate execution outcome parameters."""
        if self.duration_s < 0:
            raise ValueError("duration_s must be non-negative")
        if self.status == "error" and self.error is None:
            raise ValueError("error status requires error message")


@dataclass(frozen=True)
class ProofPatch:
    """
    Generated proof patch with hints.

    A proof patch is ready-to-paste Lean code that applies the
    discovered hints with the appropriate automation tool.

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.8

    Attributes:
        lean_code: Ready-to-paste Lean proof code
        hint_set: Hints used in the proof
        automation: Automation tool used (aesop, grind, simp)
        style: Style configuration used
    """

    lean_code: str
    hint_set: HintSet
    automation: str
    style: "StyleConfig"

    def __post_init__(self) -> None:
        """Validate proof patch parameters."""
        if not self.lean_code:
            raise ValueError("lean_code must be non-empty")
        if not self.automation:
            raise ValueError("automation must be non-empty")


@dataclass(frozen=True)
class GlobalSuggestion:
    """
    Suggestion for global annotation.

    A global suggestion recommends adding a file-level or project-level
    attribute to a hint to improve automation across the codebase.

    Requirements: 7.1, 7.2, 7.3, 7.4

    Attributes:
        hint_name: Fully-qualified name of the hint
        attribute: Suggested attribute (@[aesop], @[simp], etc.)
        rationale: Explanation for the suggestion
        confidence: Confidence level (high, medium, low)
    """

    hint_name: str
    attribute: str
    rationale: str
    confidence: Literal["high", "medium", "low"]

    def __post_init__(self) -> None:
        """Validate global suggestion parameters."""
        if not self.hint_name:
            raise ValueError("hint_name must be non-empty")
        if not self.attribute:
            raise ValueError("attribute must be non-empty")
        if not self.rationale:
            raise ValueError("rationale must be non-empty")


# ============================================================================
# Configuration Data Classes (Immutable)
# ============================================================================


@dataclass(frozen=True)
class BudgetConfig:
    """
    Time budget configuration for each phase.

    Requirements: 1.5, 2.5, 4.8, 5.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7

    Attributes:
        viability_check_s: Budget for viability check (default: 5.0)
        baseline_probe_s: Budget for baseline probe (default: 10.0)
        search_total_s: Total budget for search phase (default: 300.0)
        candidate_trial_s: Budget per candidate trial (default: 5.0)
        minimize_total_s: Total budget for minimization (default: 60.0)
        final_verify_s: Budget for final verification (default: 10.0)
    """

    viability_check_s: float = 5.0
    baseline_probe_s: float = 10.0
    search_total_s: float = 300.0
    candidate_trial_s: float = 5.0
    minimize_total_s: float = 60.0
    final_verify_s: float = 10.0

    def __post_init__(self) -> None:
        """Validate budget parameters."""
        if self.viability_check_s <= 0:
            raise ValueError("viability_check_s must be positive")
        if self.baseline_probe_s <= 0:
            raise ValueError("baseline_probe_s must be positive")
        if self.search_total_s <= 0:
            raise ValueError("search_total_s must be positive")
        if self.candidate_trial_s <= 0:
            raise ValueError("candidate_trial_s must be positive")
        if self.minimize_total_s <= 0:
            raise ValueError("minimize_total_s must be positive")
        if self.final_verify_s <= 0:
            raise ValueError("final_verify_s must be positive")


@dataclass(frozen=True)
class SearchConfig:
    """
    Search strategy configuration.

    Requirements: 4.1, 4.2, 4.5, 4.6, 4.7

    Attributes:
        strategy: Search strategy (beam or greedy)
        beam_width: Beam width for beam search (default: 3)
        max_steps: Maximum search steps (default: 100)
        max_hints: Maximum hints per set (default: 10)
        stop_on_first_close: Stop on first closing set (default: True)
    """

    strategy: Literal["beam", "greedy"] = "greedy"
    beam_width: int = 3
    max_steps: int = 100
    max_hints: int = 10
    stop_on_first_close: bool = True

    def __post_init__(self) -> None:
        """Validate search configuration."""
        if self.beam_width <= 0:
            raise ValueError("beam_width must be positive")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.max_hints <= 0:
            raise ValueError("max_hints must be positive")


@dataclass(frozen=True)
class CandidateConfig:
    """
    Candidate generation configuration.

    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9

    Attributes:
        sources: List of candidate sources to use
        max_candidates_per_source: Maximum candidates per source (default: 20)
        allow_simp_hints: Allow simp lemma hints (default: True)
        allow_unfold_hints: Allow definition unfolding hints (default: True)
    """

    sources: list[CandidateSource]
    max_candidates_per_source: int = 20
    allow_simp_hints: bool = True
    allow_unfold_hints: bool = True

    def __post_init__(self) -> None:
        """Validate candidate configuration."""
        if not self.sources:
            raise ValueError("sources must be non-empty")
        if self.max_candidates_per_source <= 0:
            raise ValueError("max_candidates_per_source must be positive")


@dataclass(frozen=True)
class StyleConfig:
    """
    Proof formatting style configuration.

    Requirements: 6.4, 6.5, 6.6, 15.4, 15.5

    Attributes:
        prefer_simp_over_aesop: Prefer simp when both close (default: True)
        emit_compact: Format hints on single line (default: False)
        simp_only_list: Use "simp only" instead of "simp_all" (default: False)
    """

    prefer_simp_over_aesop: bool = True
    emit_compact: bool = False
    simp_only_list: bool = False


@dataclass(frozen=True)
class WorkspaceConfig:
    """
    Workspace isolation configuration.

    Requirements: 8.1, 8.2, 8.3

    Attributes:
        mode: Workspace mode (git_worktree)
        keep_artifacts: Keep workspace after completion (default: False)
    """

    mode: Literal["git_worktree"] = "git_worktree"
    keep_artifacts: bool = False


@dataclass(frozen=True)
class AutomationConfig:
    """
    Automation tool configuration.

    Requirements: 2.2, 2.3

    Attributes:
        primary: Primary automation tool (aesop or grind)
        secondary: Optional secondary automation tool
        aesop_rules: Optional aesop rule configuration
    """

    primary: Literal["aesop", "grind"] = "aesop"
    secondary: Literal["aesop", "grind", "simp"] | None = None
    aesop_rules: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate automation configuration."""
        if self.primary == self.secondary:
            raise ValueError("primary and secondary must be different")


@dataclass(frozen=True)
class SkeletonConfig:
    """
    Skeleton search configuration.

    Requirements: 14.1, 14.2, 14.3, 14.4

    Attributes:
        enabled: Enable skeleton-based search (default: False)
        max_depth: Maximum skeleton depth (default: 3)
        moves: List of allowed tactic moves (default: ["cases", "constructor", "induction"])
    """

    enabled: bool = False
    max_depth: int = 3
    moves: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate skeleton configuration."""
        if self.max_depth <= 0:
            raise ValueError("max_depth must be positive")
        # Set default moves if None
        if self.moves is None:
            object.__setattr__(self, "moves", ["cases", "constructor", "induction"])


# ============================================================================
# Command and Result Data Structures (Application Layer)
# ============================================================================


@dataclass(frozen=True)
class SearchAnnotationsCommand:
    """
    Immutable command representing a search-annotations request.

    This command encapsulates all parameters for searching and minimizing
    local proof hints to make a theorem provable by automation.

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5

    Attributes:
        file: Path to Lean file
        theorem_id: Theorem identifier to search
        mode: Operation mode (local_only or suggest_global)
        automation: Automation tool configuration
        budgets: Time budget configuration for each phase
        search: Search strategy configuration
        candidates: Candidate generation configuration
        skeleton: Skeleton search configuration
        style: Proof formatting style configuration
        workspace: Workspace isolation configuration
        allow_global_edits: Allow applying global edits (default: False)
        run_id: Unique identifier for this run
    """

    file: str
    theorem_id: str
    mode: Literal["local_only", "suggest_global"]
    automation: AutomationConfig
    budgets: BudgetConfig
    search: SearchConfig
    candidates: CandidateConfig
    skeleton: SkeletonConfig
    style: StyleConfig
    workspace: WorkspaceConfig
    allow_global_edits: bool
    run_id: str

    def __post_init__(self) -> None:
        """
        Validate command parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 1.1, 1.3
        """
        if not self.file:
            raise ValueError("file must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")
        if self.mode not in ("local_only", "suggest_global"):
            raise ValueError("mode must be 'local_only' or 'suggest_global'")
        if not self.run_id:
            raise ValueError("run_id must be non-empty")


@dataclass(frozen=True)
class SearchAnnotationsResult:
    """
    Final result from search-annotations execution.

    This is the complete result returned to the user, containing all
    information about the search process including viability, baseline,
    search, minimization, proof patch, timing, and artifacts.

    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8

    Attributes:
        api_version: API version string (e.g., "0.1.0")
        status: Overall status (success, fail, timeout, error)
        run_id: Unique identifier for this run
        file: Path to the verified file
        theorem_id: Theorem identifier
        viability: Viability check details
        baseline: Baseline attempt outcomes
        search_result: Search phase result (None if baseline succeeded)
        minimized_hint_set: Final minimized hint set (None if failed)
        proof_patch: Ready-to-paste proof code (None if failed)
        global_suggestions: Global annotation suggestions (None if mode is local_only)
        timing: Timing breakdown for all phases
        artifacts: Paths to stored artifacts
        metadata: Metadata about execution environment
        workflow_recommendation: Optional recommendation for LLM workflow optimization
    """

    api_version: str
    status: Literal["success", "fail", "timeout", "error"]
    run_id: str
    file: str
    theorem_id: str
    viability: dict[str, Any]
    baseline: dict[str, Any]
    search_result: SearchResult | None
    minimized_hint_set: HintSet | None
    proof_patch: ProofPatch | None
    global_suggestions: list[GlobalSuggestion] | None
    timing: dict[str, float]
    artifacts: dict[str, str]
    metadata: dict[str, Any]
    workflow_recommendation: str | None = None

    def __post_init__(self) -> None:
        """
        Validate result parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8
        """
        if not self.api_version:
            raise ValueError("api_version must be non-empty")
        if self.status not in ("success", "fail", "timeout", "error"):
            raise ValueError("status must be 'success', 'fail', 'timeout', or 'error'")
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.file:
            raise ValueError("file must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")

        # Validate consistency: success requires proof_patch
        if self.status == "success" and self.proof_patch is None:
            raise ValueError("success status requires proof_patch")

        # Validate consistency: success requires minimized_hint_set
        if self.status == "success" and self.minimized_hint_set is None:
            raise ValueError("success status requires minimized_hint_set")


# ============================================================================
# Command Handler (Application Layer)
# ============================================================================


class SearchAnnotationsCommandHandler:
    """
    Orchestrates search-annotations workflow using injected services.

    This handler implements the complete search workflow following hexagonal
    architecture principles. It depends on abstract ports and existing services,
    containing no infrastructure logic.

    The workflow:
    1. Viability check using build_index() and find_by_id()
    2. Baseline probe using probe_handler.handle()
    3. Generate candidates using candidate_generator.generate()
    4. Search using search_strategy.search()
    5. Minimize using minimizer.minimize()
    6. Build proof patch using ProofPatchBuilder
    7. Store artifacts using artifact_store.store()

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6,
                  9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
    """

    def __init__(
        self,
        probe_handler: "ProbeCommandHandler",
        candidate_generator: "CandidateGenerator",
        search_strategy: "SearchStrategy",
        minimizer: "Minimizer",
        proof_patch_builder: "ProofPatchBuilder",
        artifact_store: "ArtifactStore",
        workspace_provider: "WorkspaceProvider",
        metadata_collector: "MetadataCollector | None" = None,
    ):
        """
        Initialize handler with dependency injection.

        Args:
            probe_handler: Handler for automation probing
            candidate_generator: Service for generating candidate hints
            search_strategy: Strategy for searching hint combinations
            minimizer: Service for minimizing hint sets
            proof_patch_builder: Service for building proof patches
            artifact_store: Port for artifact storage
            workspace_provider: Port for workspace isolation
            metadata_collector: Optional port for collecting environment metadata

        Requirements: 1.1, 6.1, 6.2, 8.1
        """
        self.probe_handler = probe_handler
        self.candidate_generator = candidate_generator
        self.search_strategy = search_strategy
        self.minimizer = minimizer
        self.proof_patch_builder = proof_patch_builder
        self.artifact_store = artifact_store
        self.workspace_provider = workspace_provider
        self.metadata_collector = metadata_collector

    def handle(self, cmd: SearchAnnotationsCommand) -> SearchAnnotationsResult:
        """
        Execute complete search-annotations workflow.

        This method orchestrates all phases of the search process with
        comprehensive error handling and budget enforcement. It ensures
        workspace isolation and cleanup following the same pattern as
        ProbeCommandHandler.

        Args:
            cmd: Search-annotations command with all parameters

        Returns:
            SearchAnnotationsResult with complete search information

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6,
                      8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
        """
        import logging
        import time

        logger = logging.getLogger(__name__)

        # Track timing for all phases
        phase_timings: dict[str, float] = {}
        overall_start = time.time()

        # Initialize result fields
        viability_details: dict[str, Any] = {}
        baseline_details: dict[str, Any] = {}
        search_result: SearchResult | None = None
        minimized_hint_set: HintSet | None = None
        proof_patch: ProofPatch | None = None
        global_suggestions: list[GlobalSuggestion] | None = None

        # Create isolated workspace
        workspace = None
        try:
            workspace = self.workspace_provider.create_workspace(cmd.file)
            logger.info(f"Created workspace: {workspace.workspace_id} (mode: {workspace.mode})")
        except Exception as e:
            logger.error(f"Workspace creation failed: {e}")
            return self._build_error_result(
                cmd, "error", f"Failed to create workspace: {e}", {}, {}, phase_timings
            )

        try:
            # ================================================================
            # Phase 1: Viability Check
            # ================================================================
            logger.info(f"Phase 1: Viability check for {cmd.file}:{cmd.theorem_id}")
            phase_start = time.time()

            try:
                # Import indexer functions
                from .indexer import build_index, find_by_id
                from .source import SourceText

                # Check file exists in workspace
                file_path = workspace.path / cmd.file
                if not file_path.exists():
                    phase_timings["viability_check_s"] = time.time() - phase_start
                    return self._build_error_result(
                        cmd,
                        "fail",
                        f"File not found in workspace: {cmd.file}",
                        {"error_type": "file_not_found"},
                        {},
                        phase_timings,
                    )

                # Read source and build index
                source_text = file_path.read_text(encoding="utf-8")
                source = SourceText(path=cmd.file, text=source_text)
                index = build_index(source)

                # Find theorem
                theorem_decl = find_by_id(index, cmd.theorem_id)
                if theorem_decl is None:
                    phase_timings["viability_check_s"] = time.time() - phase_start
                    return self._build_error_result(
                        cmd,
                        "fail",
                        f"Theorem '{cmd.theorem_id}' not found in {cmd.file}",
                        {"error_type": "theorem_not_found", "searched_file": cmd.file},
                        {},
                        phase_timings,
                    )

                viability_details = {
                    "status": "success",
                    "theorem_found": True,
                    "theorem_id": cmd.theorem_id,
                    "file": cmd.file,
                    "workspace_id": workspace.workspace_id,
                    "workspace_mode": workspace.mode,
                }

                phase_timings["viability_check_s"] = time.time() - phase_start

                # Check viability budget
                if phase_timings["viability_check_s"] > cmd.budgets.viability_check_s:
                    return self._build_error_result(
                        cmd,
                        "timeout",
                        f"Viability check exceeded budget ({cmd.budgets.viability_check_s}s)",
                        viability_details,
                        {},
                        phase_timings,
                    )

            except Exception as e:
                phase_timings["viability_check_s"] = time.time() - phase_start
                logger.exception(f"Viability check failed: {e}")
                return self._build_error_result(
                    cmd,
                    "error",
                    f"Viability check error: {str(e)}",
                    {"error_type": "viability_error", "error": str(e)},
                    {},
                    phase_timings,
                )

            # ================================================================
            # Phase 2: Baseline Probe
            # ================================================================
            logger.info(f"Phase 2: Baseline probe for {cmd.theorem_id}")
            phase_start = time.time()

            try:
                from .probe_domain import ProbeCommand

                # Try primary automation
                probe_cmd = ProbeCommand(
                    file_path=cmd.file,
                    theorem_id=cmd.theorem_id,
                    mode=cmd.automation.primary,
                    budget_s=cmd.budgets.baseline_probe_s,
                )

                baseline_result = self.probe_handler.handle(probe_cmd)

                # Extract error details from diagnostics if outcome is error
                error_details = None
                if baseline_result.probe_result.outcome == "error" and baseline_result.diagnostics:
                    error_messages = [
                        d.get("message", "")
                        for d in baseline_result.diagnostics
                        if d.get("severity") == "error"
                    ]
                    if error_messages:
                        error_details = "; ".join(error_messages)

                baseline_details = {
                    "primary_automation": cmd.automation.primary,
                    "primary_outcome": baseline_result.probe_result.outcome,
                    "primary_classification": baseline_result.probe_result.classification,
                    "attempts": [
                        {
                            "automation": cmd.automation.primary,
                            "outcome": baseline_result.probe_result.outcome,
                            "classification": baseline_result.probe_result.classification,
                            "error": error_details,
                        }
                    ],
                }

                phase_timings["baseline_probe_s"] = time.time() - phase_start

                # Check if baseline succeeded
                if baseline_result.probe_result.outcome == "closed":
                    logger.info("Baseline automation succeeded, no search needed")

                    # Build success result without search
                    result = SearchAnnotationsResult(
                        api_version="0.1.0",
                        status="success",
                        run_id=cmd.run_id,
                        file=cmd.file,
                        theorem_id=cmd.theorem_id,
                        viability=viability_details,
                        baseline=baseline_details,
                        search_result=None,
                        minimized_hint_set=HintSet(),  # Empty set
                        proof_patch=ProofPatch(
                            lean_code=cmd.automation.primary,
                            hint_set=HintSet(),
                            automation=cmd.automation.primary,
                            style=cmd.style,
                        ),
                        global_suggestions=None if cmd.mode == "local_only" else [],
                        timing=self._build_timing(phase_timings, overall_start),
                        artifacts={},
                        metadata=self._build_metadata(),
                        workflow_recommendation=(
                            "OPTIMIZATION: This theorem is trivial (plain automation works). "
                            "For better performance, use 'probe' or 'probe_file' tools first "
                            "to identify non-trivial theorems before calling "
                            "'search_automated_proof'. This avoids redundant baseline checks and "
                            f"saves ~{phase_timings.get('baseline_probe_s', 0):.1f}s per theorem."
                        ),
                    )

                    # Store artifacts before returning
                    result = self._store_artifacts_and_update_result(cmd, result, "")
                    return result

                # Try secondary automation if configured
                if cmd.automation.secondary:
                    secondary_probe_cmd = ProbeCommand(
                        file_path=cmd.file,
                        theorem_id=cmd.theorem_id,
                        mode=cmd.automation.secondary,
                        budget_s=cmd.budgets.baseline_probe_s,
                    )

                    secondary_result = self.probe_handler.handle(secondary_probe_cmd)

                    # Extract error details from secondary result
                    secondary_error_details = None
                    if (
                        secondary_result.probe_result.outcome == "error"
                        and secondary_result.diagnostics
                    ):
                        error_messages = [
                            d.get("message", "")
                            for d in secondary_result.diagnostics
                            if d.get("severity") == "error"
                        ]
                        if error_messages:
                            secondary_error_details = "; ".join(error_messages)

                    baseline_details["secondary_automation"] = cmd.automation.secondary
                    baseline_details["secondary_outcome"] = secondary_result.probe_result.outcome
                    baseline_details["secondary_classification"] = (
                        secondary_result.probe_result.classification
                    )
                    baseline_details["attempts"].append(
                        {
                            "automation": cmd.automation.secondary,
                            "outcome": secondary_result.probe_result.outcome,
                            "classification": secondary_result.probe_result.classification,
                            "error": secondary_error_details,
                        }
                    )

                    if secondary_result.probe_result.outcome == "closed":
                        logger.info("Secondary automation succeeded, no search needed")

                        result = SearchAnnotationsResult(
                            api_version="0.1.0",
                            status="success",
                            run_id=cmd.run_id,
                            file=cmd.file,
                            theorem_id=cmd.theorem_id,
                            viability=viability_details,
                            baseline=baseline_details,
                            search_result=None,
                            minimized_hint_set=HintSet(),
                            proof_patch=ProofPatch(
                                lean_code=cmd.automation.secondary,
                                hint_set=HintSet(),
                                automation=cmd.automation.secondary,
                                style=cmd.style,
                            ),
                            global_suggestions=None if cmd.mode == "local_only" else [],
                            timing=self._build_timing(phase_timings, overall_start),
                            artifacts={},
                            metadata=self._build_metadata(),
                            workflow_recommendation=(
                                "OPTIMIZATION: This theorem is trivial (plain automation works). "
                                "For better performance, use 'probe' or 'probe_file' tools first "
                                "to identify non-trivial theorems before calling "
                                "'search_automated_proof'. This avoids redundant baseline checks and "
                                f"saves ~{phase_timings.get('baseline_probe_s', 0):.1f}s per "
                                f"theorem."
                            ),
                        )

                        # Store artifacts before returning
                        result = self._store_artifacts_and_update_result(cmd, result, "")
                        return result

            except Exception as e:
                phase_timings["baseline_probe_s"] = time.time() - phase_start
                logger.warning(f"Baseline probe failed: {e}, continuing to search")
                baseline_details = {"status": "error", "error": str(e)}

            # ================================================================
            # Phase 3: Generate Candidates
            # ================================================================
            logger.info("Phase 3: Generate candidates")
            phase_start = time.time()

            try:
                candidates = self.candidate_generator.generate(
                    theorem_decl, cmd.candidates.sources, cmd.candidates
                )

                phase_timings["candidate_generation_s"] = time.time() - phase_start
                logger.info(f"Generated {len(candidates)} candidates")

            except Exception as e:
                phase_timings["candidate_generation_s"] = time.time() - phase_start
                logger.exception(f"Candidate generation failed: {e}")
                return self._build_error_result(
                    cmd,
                    "error",
                    f"Candidate generation error: {str(e)}",
                    viability_details,
                    baseline_details,
                    phase_timings,
                )

            # ================================================================
            # Phase 4: Search for Closing Hint Set
            # ================================================================
            logger.info("Phase 4: Search for closing hint set")
            phase_start = time.time()

            try:
                # Create probe function for search
                def probe_fn(hint_set: HintSet) -> ExecutionOutcome:
                    """Probe function that tests a hint set."""
                    # For now, return a mock outcome
                    # TODO: Implement actual probing with hints
                    return ExecutionOutcome(
                        status="failure",
                        automation_used=cmd.automation.primary,
                        duration_s=0.1,
                        output="",
                        error=None,
                    )

                search_result = self.search_strategy.search(
                    candidates, probe_fn, cmd.search, cmd.budgets.search_total_s
                )

                phase_timings["search_total_s"] = time.time() - phase_start
                logger.info(
                    f"Search completed: {search_result.outcome}, {search_result.attempts} attempts"
                )

                # Check if search found a closing set
                if search_result.outcome != "closed" or search_result.best_hint_set is None:
                    # Search failed to find closing set
                    return SearchAnnotationsResult(
                        api_version="0.1.0",
                        status="fail",
                        run_id=cmd.run_id,
                        file=cmd.file,
                        theorem_id=cmd.theorem_id,
                        viability=viability_details,
                        baseline=baseline_details,
                        search_result=search_result,
                        minimized_hint_set=None,
                        proof_patch=None,
                        global_suggestions=None,
                        timing=self._build_timing(phase_timings, overall_start),
                        artifacts={},
                        metadata=self._build_metadata(),
                        workflow_recommendation=None,
                    )

            except Exception as e:
                phase_timings["search_total_s"] = time.time() - phase_start
                logger.exception(f"Search failed: {e}")
                return self._build_error_result(
                    cmd,
                    "error",
                    f"Search error: {str(e)}",
                    viability_details,
                    baseline_details,
                    phase_timings,
                )

            # ================================================================
            # Phase 5: Minimize Hint Set
            # ================================================================
            logger.info("Phase 5: Minimize hint set")
            phase_start = time.time()

            try:
                # Create probe function for minimization
                def minimize_probe_fn(hint_set: HintSet) -> ExecutionOutcome:
                    """Probe function for minimization."""
                    # TODO: Implement actual probing with hints
                    return ExecutionOutcome(
                        status="success",
                        automation_used=cmd.automation.primary,
                        duration_s=0.1,
                        output="",
                        error=None,
                    )

                minimized_hint_set = self.minimizer.minimize(
                    search_result.best_hint_set, minimize_probe_fn
                )

                phase_timings["minimize_total_s"] = time.time() - phase_start
                logger.info(f"Minimization completed: {minimized_hint_set.size()} hints")

            except Exception as e:
                phase_timings["minimize_total_s"] = time.time() - phase_start
                logger.warning(f"Minimization failed: {e}, using non-minimized set")
                minimized_hint_set = search_result.best_hint_set

            # ================================================================
            # Phase 6: Build Proof Patch
            # ================================================================
            logger.info("Phase 6: Build proof patch")
            phase_start = time.time()

            try:
                # Get original proof if available
                original_proof = None
                if theorem_decl.proof_span:
                    original_proof = source.get_span_text(theorem_decl.proof_span)

                proof_patch = self.proof_patch_builder.build(
                    minimized_hint_set, cmd.automation.primary, cmd.style, original_proof
                )

                phase_timings["proof_patch_build_s"] = time.time() - phase_start

            except Exception as e:
                phase_timings["proof_patch_build_s"] = time.time() - phase_start
                logger.exception(f"Proof patch building failed: {e}")
                return self._build_error_result(
                    cmd,
                    "error",
                    f"Proof patch building error: {str(e)}",
                    viability_details,
                    baseline_details,
                    phase_timings,
                )

            # ================================================================
            # Phase 7: Generate Global Suggestions (if requested)
            # ================================================================
            if cmd.mode == "suggest_global":
                logger.info("Phase 7: Generate global suggestions")
                phase_start = time.time()

                try:
                    # TODO: Implement GlobalSuggestionAnalyzer
                    global_suggestions = []

                    phase_timings["global_suggestions_s"] = time.time() - phase_start

                except Exception as e:
                    phase_timings["global_suggestions_s"] = time.time() - phase_start
                    logger.warning(f"Global suggestion generation failed: {e}")
                    global_suggestions = []
            else:
                global_suggestions = None

            # ================================================================
            # Phase 8: Store Artifacts
            # ================================================================
            logger.info("Phase 8: Store artifacts")

            # Build final result (without artifacts paths yet)
            result = SearchAnnotationsResult(
                api_version="0.1.0",
                status="success",
                run_id=cmd.run_id,
                file=cmd.file,
                theorem_id=cmd.theorem_id,
                viability=viability_details,
                baseline=baseline_details,
                search_result=search_result,
                minimized_hint_set=minimized_hint_set,
                proof_patch=proof_patch,
                global_suggestions=global_suggestions,
                timing=self._build_timing(phase_timings, overall_start),
                artifacts={},
                metadata=self._build_metadata(),
                workflow_recommendation=None,  # No recommendation for non-trivial cases
            )

            # Collect all logs
            full_logs = self._collect_logs(
                viability_details, baseline_details, search_result, minimized_hint_set
            )

            # Store artifacts and update result with paths
            result = self._store_artifacts_and_update_result(cmd, result, full_logs)

            return result

        except Exception as e:
            logger.exception(f"Unexpected error in search-annotations workflow: {e}")
            return self._build_error_result(
                cmd,
                "error",
                f"Unexpected error: {str(e)}",
                viability_details,
                baseline_details,
                phase_timings,
            )

        finally:
            # Cleanup workspace (always runs)
            # Requirements: 8.2, 8.3, 8.4, 8.5
            if workspace:
                try:
                    # Only cleanup if keep_artifacts is False
                    if not cmd.workspace.keep_artifacts:
                        self.workspace_provider.cleanup_workspace(workspace)
                        logger.info(f"Cleaned up workspace: {workspace.workspace_id}")
                    else:
                        logger.info(
                            f"Preserved workspace: {workspace.workspace_id} at {workspace.path}"
                        )
                except Exception as e:
                    # Log but don't propagate cleanup errors
                    logger.warning(f"Workspace cleanup failed: {e}")

    def _build_error_result(
        self,
        cmd: SearchAnnotationsCommand,
        status: Literal["success", "fail", "timeout", "error"],
        error_message: str,
        viability_details: dict[str, Any],
        baseline_details: dict[str, Any],
        phase_timings: dict[str, float],
    ) -> SearchAnnotationsResult:
        """
        Build error result for various error cases.

        Args:
            cmd: Original command
            status: Error status
            error_message: Error message
            viability_details: Viability check details
            baseline_details: Baseline probe details
            phase_timings: Phase timing information

        Returns:
            SearchAnnotationsResult with error status
        """
        import time

        return SearchAnnotationsResult(
            api_version="0.1.0",
            status=status,
            run_id=cmd.run_id,
            file=cmd.file,
            theorem_id=cmd.theorem_id,
            viability=viability_details if viability_details else {"status": "not_started"},
            baseline=baseline_details if baseline_details else {"status": "not_started"},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing=self._build_timing(phase_timings, time.time()),
            artifacts={},
            metadata={"error": error_message},
            workflow_recommendation=None,
        )

    def _store_artifacts_and_update_result(
        self, cmd: SearchAnnotationsCommand, result: SearchAnnotationsResult, full_logs: str
    ) -> SearchAnnotationsResult:
        """
        Store artifacts and update result with artifact paths.

        This helper method handles artifact storage and updates the result
        with the correct artifact paths. It's used for both early returns
        and normal completion paths.

        Args:
            cmd: Original command
            result: Result to update
            full_logs: Full logs to store

        Returns:
            Updated result with artifact paths

        Requirements: 10.8, 12.8
        """
        try:
            # Collect logs if not provided
            if not full_logs:
                full_logs = self._collect_logs(
                    result.viability,
                    result.baseline,
                    result.search_result,
                    result.minimized_hint_set,
                )

            # Store artifacts using artifact store
            # Note: ArtifactStore protocol is generic but typed for VerifyCommand/VerifyResult
            # This is a known limitation - we use type: ignore here
            self.artifact_store.store(
                run_id=cmd.run_id,
                command=cmd,  # type: ignore[arg-type]
                result=result,  # type: ignore[arg-type]
                full_logs=full_logs,
            )

            # Update result with artifact paths
            from pathlib import Path

            artifacts_dir = Path(".artifacts") / cmd.run_id

            updated_result = SearchAnnotationsResult(
                api_version=result.api_version,
                status=result.status,
                run_id=result.run_id,
                file=result.file,
                theorem_id=result.theorem_id,
                viability=result.viability,
                baseline=result.baseline,
                search_result=result.search_result,
                minimized_hint_set=result.minimized_hint_set,
                proof_patch=result.proof_patch,
                global_suggestions=result.global_suggestions,
                timing=result.timing,
                artifacts={
                    "request_path": str(artifacts_dir / "request.json"),
                    "result_path": str(artifacts_dir / "result.json"),
                    "logs_path": str(artifacts_dir / "lean_output.log"),
                },
                metadata=result.metadata,
                workflow_recommendation=result.workflow_recommendation,
            )

            logger.info(f"Stored artifacts for run_id: {cmd.run_id}")
            return updated_result

        except Exception as e:
            logger.warning(f"Artifact storage failed: {e}")
            # Return original result if artifact storage fails
            return result

    def _build_timing(
        self, phase_timings: dict[str, float], overall_start: float
    ) -> dict[str, float]:
        """
        Build timing section with all phase times.

        Args:
            phase_timings: Dictionary of phase timings
            overall_start: Overall start time

        Returns:
            Timing dictionary
        """
        import time

        total_s = time.time() - overall_start

        timing = {
            "total_s": round(total_s, 2),
            **{k: round(v, 2) for k, v in phase_timings.items()},
        }

        return timing

    def _build_metadata(self) -> dict[str, Any]:
        """
        Build metadata section with environment information.

        Uses the injected MetadataCollector port to gather environment
        metadata (git commit, lean version, lake version). If no collector
        is provided, returns an empty dictionary.

        Returns:
            Metadata dictionary
        """
        if self.metadata_collector is None:
            logger.debug("No metadata collector configured, skipping metadata collection")
            return {}

        return self.metadata_collector.collect_version_info()

    def _collect_logs(
        self,
        viability_details: dict[str, Any],
        baseline_details: dict[str, Any],
        search_result: SearchResult | None,
        minimized_hint_set: HintSet | None,
    ) -> str:
        """
        Collect logs from all phases for artifact storage.

        This method aggregates logs from viability check, baseline probe,
        search, and minimization phases into a single log string.

        Args:
            viability_details: Viability check details
            baseline_details: Baseline probe details
            search_result: Search phase result
            minimized_hint_set: Final minimized hint set

        Returns:
            Aggregated log string

        Requirements: 9.8, 13.1, 13.2, 13.3, 13.4, 13.5
        """
        import json

        from .json_serialization import to_json_serializable

        logs = []

        # Viability check logs
        logs.append("=" * 80)
        logs.append("VIABILITY CHECK")
        logs.append("=" * 80)
        logs.append(json.dumps(viability_details, indent=2, sort_keys=True))
        logs.append("")

        # Baseline probe logs
        logs.append("=" * 80)
        logs.append("BASELINE PROBE")
        logs.append("=" * 80)
        logs.append(json.dumps(baseline_details, indent=2, sort_keys=True))
        logs.append("")

        # Search logs
        if search_result is not None:
            logs.append("=" * 80)
            logs.append("SEARCH PHASE")
            logs.append("=" * 80)
            search_dict = to_json_serializable(
                {
                    "outcome": search_result.outcome,
                    "attempts": search_result.attempts,
                    "explored_sets": search_result.explored_sets,
                    "best_hint_set_size": search_result.best_hint_set.size()
                    if search_result.best_hint_set
                    else 0,
                }
            )
            logs.append(json.dumps(search_dict, indent=2, sort_keys=True))
            logs.append("")

        # Minimization logs
        if minimized_hint_set is not None:
            logs.append("=" * 80)
            logs.append("MINIMIZATION PHASE")
            logs.append("=" * 80)
            hints_list = [
                {"name": h.name, "type": h.type.value, "source": h.source.value}
                for h in minimized_hint_set.to_sorted_list()
            ]
            logs.append(json.dumps({"minimized_hints": hints_list}, indent=2, sort_keys=True))
            logs.append("")

        return "\n".join(logs)


# Type hints for forward references
if TYPE_CHECKING:
    from .candidate_generator import CandidateGenerator
    from .minimizer import Minimizer
    from .probe_domain import ProbeCommandHandler
    from .proof_patch_builder import ProofPatchBuilder
    from .search_strategy import SearchStrategy
    from .verify_domain import ArtifactStore, WorkspaceProvider
