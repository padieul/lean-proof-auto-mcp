"""
Skeleton-based proof search explorer.

This module implements skeleton-based search that explores proof structures
using tactic moves (cases, constructor, induction) combined with hint search.

Requirements: 14.1, 14.2, 14.3, 14.4
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .search_automated_proof_domain import (
    ExecutionOutcome,
    HintSet,
    SkeletonConfig,
)


@dataclass(frozen=True)
class TacticMove:
    """
    Represents a single tactic move in a proof skeleton.

    Requirements: 14.2, 14.4

    Attributes:
        name: Name of the tactic (cases, constructor, induction)
        target: Optional target for the tactic
    """

    name: str
    target: str | None = None

    def __post_init__(self) -> None:
        """Validate tactic move parameters."""
        if not self.name:
            raise ValueError("name must be non-empty")


@dataclass(frozen=True)
class ProofSkeleton:
    """
    Represents a proof skeleton structure.

    A proof skeleton is a sequence of tactic moves that form the
    structural outline of a proof, with hint sets applied at each step.

    Requirements: 14.2, 14.3, 14.4, 14.5

    Attributes:
        moves: Sequence of tactic moves
        hint_sets: Hint sets applied at each move (parallel to moves)
        depth: Current depth of the skeleton
    """

    moves: tuple[TacticMove, ...]
    hint_sets: tuple[HintSet, ...]
    depth: int

    def __post_init__(self) -> None:
        """Validate proof skeleton parameters."""
        if len(self.moves) != len(self.hint_sets):
            raise ValueError("moves and hint_sets must have same length")
        if self.depth < 0:
            raise ValueError("depth must be non-negative")
        if self.depth != len(self.moves):
            raise ValueError("depth must equal number of moves")

    def add_move(self, move: TacticMove, hint_set: HintSet) -> "ProofSkeleton":
        """
        Return new ProofSkeleton with move added.

        Args:
            move: Tactic move to add
            hint_set: Hint set for this move

        Returns:
            New ProofSkeleton with move included

        Requirements: 14.2, 14.3
        """
        return ProofSkeleton(
            moves=self.moves + (move,), hint_sets=self.hint_sets + (hint_set,), depth=self.depth + 1
        )

    @staticmethod
    def empty() -> "ProofSkeleton":
        """
        Create an empty proof skeleton.

        Returns:
            Empty ProofSkeleton
        """
        return ProofSkeleton(moves=(), hint_sets=(), depth=0)


@dataclass(frozen=True)
class SkeletonSearchResult:
    """
    Result from skeleton-based search.

    Requirements: 14.5, 14.6

    Attributes:
        outcome: Search outcome (closed, partial, failed)
        best_skeleton: Best proof skeleton found (None if failed)
        attempts: Number of skeleton attempts made
        explored_skeletons: Number of unique skeletons explored
        evidence: Execution outcome for best skeleton (None if failed)
    """

    outcome: str  # "closed", "partial", "failed"
    best_skeleton: ProofSkeleton | None
    attempts: int
    explored_skeletons: int
    evidence: ExecutionOutcome | None

    def __post_init__(self) -> None:
        """Validate skeleton search result parameters."""
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")
        if self.explored_skeletons < 0:
            raise ValueError("explored_skeletons must be non-negative")
        if self.outcome == "closed" and self.best_skeleton is None:
            raise ValueError("closed outcome requires best_skeleton")


class SkeletonProbeFunction(Protocol):
    """
    Protocol for skeleton probe function.

    A skeleton probe function tests whether a proof skeleton successfully
    closes the goal.
    """

    def __call__(self, skeleton: ProofSkeleton) -> ExecutionOutcome:
        """
        Test a proof skeleton.

        Args:
            skeleton: Proof skeleton to test

        Returns:
            Execution outcome
        """
        ...


class SkeletonExplorer:
    """
    Explores proof skeletons using tactic moves.

    This service implements skeleton-based search that explores proof
    structures by applying tactic moves (cases, constructor, induction)
    and combining them with hint search at each step.

    Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
    """

    def __init__(self) -> None:
        """Initialize skeleton explorer."""
        pass

    def explore(
        self,
        config: SkeletonConfig,
        probe_fn: SkeletonProbeFunction,
        hint_search_fn: Callable[[ProofSkeleton], HintSet | None],
        budget_s: float,
    ) -> SkeletonSearchResult:
        """
        Explore proof skeletons with tactic moves.

        This method performs depth-limited exploration of proof skeletons,
        applying tactic moves from the configured list and combining them
        with hint search at each step.

        Args:
            config: Skeleton configuration
            probe_fn: Function to test skeleton validity
            hint_search_fn: Function to search for hints at each step
            budget_s: Time budget in seconds

        Returns:
            SkeletonSearchResult with best skeleton found

        Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
        """
        import logging
        import time

        logger = logging.getLogger(__name__)

        # Check if skeleton search is enabled
        if not config.enabled:
            # Return empty result indicating standard search should be used
            logger.info("Skeleton search disabled, using standard hint search")
            return SkeletonSearchResult(
                outcome="failed",
                best_skeleton=None,
                attempts=0,
                explored_skeletons=0,
                evidence=None,
            )

        logger.info(
            f"Starting skeleton exploration (max_depth={config.max_depth}, moves={config.moves})"
        )

        start_time = time.time()
        attempts = 0
        explored_skeletons = 0
        best_skeleton: ProofSkeleton | None = None
        best_evidence: ExecutionOutcome | None = None

        # Initialize exploration queue with empty skeleton
        queue: list[ProofSkeleton] = [ProofSkeleton.empty()]

        while queue and (time.time() - start_time) < budget_s:
            # Get next skeleton to explore
            current_skeleton = queue.pop(0)
            explored_skeletons += 1

            # Check depth limit
            if current_skeleton.depth >= config.max_depth:
                logger.debug(f"Reached max depth {config.max_depth}, skipping expansion")
                continue

            # Try each allowed tactic move
            if config.moves is None:
                continue
            for move_name in config.moves:
                # Check budget
                if (time.time() - start_time) >= budget_s:
                    logger.info(f"Budget exhausted after {attempts} attempts")
                    break

                # Create tactic move
                move = TacticMove(name=move_name)

                # Search for hints at this step
                hint_set = hint_search_fn(current_skeleton)
                if hint_set is None:
                    hint_set = HintSet()  # Empty hint set

                # Create new skeleton with this move
                new_skeleton = current_skeleton.add_move(move, hint_set)

                # Test the skeleton
                attempts += 1
                evidence = probe_fn(new_skeleton)

                logger.debug(
                    f"Tested skeleton depth={new_skeleton.depth}, "
                    f"move={move_name}, hints={hint_set.size()}, "
                    f"status={evidence.status}"
                )

                # Check if this skeleton closes the goal
                if evidence.status == "success":
                    logger.info(f"Found closing skeleton at depth {new_skeleton.depth}")
                    return SkeletonSearchResult(
                        outcome="closed",
                        best_skeleton=new_skeleton,
                        attempts=attempts,
                        explored_skeletons=explored_skeletons,
                        evidence=evidence,
                    )

                # Track best partial result
                if best_skeleton is None or self._is_better_outcome(evidence, best_evidence):
                    best_skeleton = new_skeleton
                    best_evidence = evidence

                # Add to queue for further exploration if not at max depth
                if new_skeleton.depth < config.max_depth:
                    queue.append(new_skeleton)

        # No closing skeleton found
        if best_skeleton is not None:
            logger.info(
                f"No closing skeleton found, best partial result at depth {best_skeleton.depth}"
            )
            return SkeletonSearchResult(
                outcome="partial",
                best_skeleton=best_skeleton,
                attempts=attempts,
                explored_skeletons=explored_skeletons,
                evidence=best_evidence,
            )
        else:
            logger.info("No skeletons explored")
            return SkeletonSearchResult(
                outcome="failed",
                best_skeleton=None,
                attempts=attempts,
                explored_skeletons=explored_skeletons,
                evidence=None,
            )

    def _is_better_outcome(
        self, new_evidence: ExecutionOutcome, current_best: ExecutionOutcome | None
    ) -> bool:
        """
        Determine if new evidence is better than current best.

        Args:
            new_evidence: New execution outcome
            current_best: Current best outcome (None if no best yet)

        Returns:
            True if new evidence is better
        """
        if current_best is None:
            return True

        # Success > failure > timeout > error
        status_rank = {"success": 4, "failure": 3, "timeout": 2, "error": 1}

        new_rank = status_rank.get(new_evidence.status, 0)
        current_rank = status_rank.get(current_best.status, 0)

        return new_rank > current_rank
