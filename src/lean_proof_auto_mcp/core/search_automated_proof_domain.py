"""
Core domain structures for search_automated_proof workflows.

This module defines immutable data structures used by candidate generation,
search orchestration, and feedback computation.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

logger = logging.getLogger(__name__)

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
