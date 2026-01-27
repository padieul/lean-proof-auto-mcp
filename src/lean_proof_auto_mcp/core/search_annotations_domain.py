"""
Core domain structures for the search-annotations tool.

This module defines immutable data structures for hint search, minimization,
and proof patch generation following hexagonal architecture principles.

Requirements: 3.1, 3.7, 3.8, 4.1, 4.2, 5.1, 6.1, 7.3, 14.1
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


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
        if self.type == HintType.SIMP:
            return self.name
        elif self.type == HintType.UNFOLD:
            return self.name
        elif self.type == HintType.ADD_SAFE:
            return self.name
        elif self.type == HintType.ADD_UNSAFE:
            return self.name
        elif self.type == HintType.RULE_SET:
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
            object.__setattr__(self, 'hints', frozenset())
        elif isinstance(hints, frozenset):
            object.__setattr__(self, 'hints', hints)
        elif isinstance(hints, (set, list)):
            object.__setattr__(self, 'hints', frozenset(hints))
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
        return sorted(
            self.hints,
            key=lambda h: (h.name, h.type.value, h.source.value)
        )


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
            object.__setattr__(self, 'moves', ["cases", "constructor", "induction"])
