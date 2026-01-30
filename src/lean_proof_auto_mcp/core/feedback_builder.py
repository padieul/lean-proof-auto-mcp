"""
Feedback building service for search results.

This module provides the FeedbackBuilder service that builds structured
feedback from search results including hints that helped, goal complexity
reduction, and tactical suggestions for LLM iteration.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

import logging
from dataclasses import dataclass

from ..lean.ports import ProofState
from .search_annotations_domain import Candidate, HintSet, SearchResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PartialProgress:
    """
    Partial progress information from search.

    Requirements: 13.2, 13.3
    """

    hints_that_helped: list[tuple[str, str]]  # (hint, impact)
    goal_complexity_reduction: float  # Percentage reduction
    progress_score: float  # Overall progress score (0.0 to 1.0)


@dataclass(frozen=True)
class Suggestion:
    """
    Tactical suggestion for next steps.

    Requirements: 13.4, 13.5
    """

    type: str  # "tactic" | "hint" | "strategy"
    suggestion: str
    confidence: float  # 0.0 to 1.0
    reasoning: str


@dataclass(frozen=True)
class SearchFeedback:
    """
    Structured feedback from search results.

    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
    """

    status: str  # "success" | "partial" | "fail"
    hints_found: list[Candidate]
    partial_progress: PartialProgress | None
    current_goal: str | None
    suggestions: list[Suggestion]


class FeedbackBuilder:
    """
    Build structured feedback from search results.

    The FeedbackBuilder analyzes search results to provide actionable
    feedback for LLM iteration including which hints helped, goal
    complexity reduction, and tactical suggestions.

    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
    """

    def __init__(self):
        """
        Initialize FeedbackBuilder.

        Requirements: 13.1
        """
        pass

    def build_search_feedback(
        self,
        search_result: SearchResult,
        initial_proof_state: ProofState | None,
        final_proof_state: ProofState | None,
        candidates: list[Candidate],
    ) -> SearchFeedback:
        """
        Build structured feedback from search results.

        This method analyzes the search result to identify:
        - Which hints helped and their impact
        - Goal complexity reduction
        - Progress score
        - Tactical suggestions for next steps

        Args:
            search_result: Result from search operation
            initial_proof_state: Initial proof state before hints
            final_proof_state: Final proof state after hints
            candidates: List of candidate hints that were tried

        Returns:
            SearchFeedback with complete analysis

        Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
        """
        # Determine status
        if search_result.outcome == "closed":
            status = "success"
        elif search_result.outcome == "partial":
            status = "partial"
        else:
            status = "fail"

        # Extract hints found
        hints_found = []
        if search_result.best_hint_set:
            # Map hint set back to candidates
            hint_names = {h.name for h in search_result.best_hint_set.hints}
            hints_found = [c for c in candidates if c.hint.name in hint_names]

        # Build partial progress if we have proof states
        partial_progress = None
        if initial_proof_state and final_proof_state:
            partial_progress = self._build_partial_progress(
                initial_proof_state, final_proof_state, hints_found
            )

        # Extract current goal
        current_goal = None
        if final_proof_state:
            current_goal = final_proof_state.goal

        # Generate suggestions
        suggestions = self._generate_suggestions(
            status, search_result, initial_proof_state, final_proof_state, hints_found
        )

        return SearchFeedback(
            status=status,
            hints_found=hints_found,
            partial_progress=partial_progress,
            current_goal=current_goal,
            suggestions=suggestions,
        )

    def _build_partial_progress(
        self,
        initial_state: ProofState,
        final_state: ProofState,
        hints_found: list[Candidate],
    ) -> PartialProgress:
        """
        Build partial progress information.

        Analyzes how hints affected the proof state and calculates
        goal complexity reduction and progress score.

        Args:
            initial_state: Initial proof state
            final_state: Final proof state
            hints_found: Hints that were applied

        Returns:
            PartialProgress with analysis

        Requirements: 13.2, 13.3
        """
        # Track which hints helped
        hints_that_helped: list[tuple[str, str]] = []
        for candidate in hints_found:
            # Estimate impact based on hint type and rank
            if candidate.rank >= 8.0:
                impact = "high"
            elif candidate.rank >= 5.0:
                impact = "medium"
            else:
                impact = "low"

            hints_that_helped.append((candidate.hint.name, impact))

        # Calculate goal complexity reduction
        initial_complexity = initial_state.complexity_score()
        final_complexity = final_state.complexity_score()

        if initial_complexity > 0:
            complexity_reduction = (
                (initial_complexity - final_complexity) / initial_complexity
            ) * 100.0
            complexity_reduction = max(0.0, min(100.0, complexity_reduction))
        else:
            complexity_reduction = 0.0

        # Calculate progress score
        # Based on: goals remaining, complexity reduction, hints applied
        progress_score = 0.0

        # Goals remaining factor (0.4 weight)
        if initial_state.goals_remaining > 0:
            goals_factor = (
                initial_state.goals_remaining - final_state.goals_remaining
            ) / initial_state.goals_remaining
            progress_score += 0.4 * goals_factor

        # Complexity reduction factor (0.4 weight)
        progress_score += 0.4 * (complexity_reduction / 100.0)

        # Hints applied factor (0.2 weight)
        if hints_found:
            progress_score += 0.2

        progress_score = max(0.0, min(1.0, progress_score))

        return PartialProgress(
            hints_that_helped=hints_that_helped,
            goal_complexity_reduction=complexity_reduction,
            progress_score=progress_score,
        )

    def _generate_suggestions(
        self,
        status: str,
        search_result: SearchResult,
        initial_state: ProofState | None,
        final_state: ProofState | None,
        hints_found: list[Candidate],
    ) -> list[Suggestion]:
        """
        Generate tactical suggestions for next steps.

        Provides actionable suggestions based on search outcome and
        proof state analysis.

        Args:
            status: Search status
            search_result: Search result
            initial_state: Initial proof state
            final_state: Final proof state
            hints_found: Hints that were found

        Returns:
            List of suggestions with confidence scores and reasoning

        Requirements: 13.4, 13.5
        """
        suggestions: list[Suggestion] = []

        if status == "success":
            # Success: suggest verification
            suggestions.append(
                Suggestion(
                    type="strategy",
                    suggestion="Verify the proof with Lean to ensure correctness",
                    confidence=1.0,
                    reasoning="Search found a closing hint set, verification recommended",
                )
            )

        elif status == "partial":
            # Partial: suggest tactics or additional hints
            if final_state:
                # Analyze remaining goal
                goal = final_state.goal

                # Suggest tactics based on goal structure
                if "∀" in goal:
                    suggestions.append(
                        Suggestion(
                            type="tactic",
                            suggestion="Try 'intro' to introduce universal quantifiers",
                            confidence=0.8,
                            reasoning="Goal contains universal quantifiers (∀)",
                        )
                    )

                if "∃" in goal:
                    suggestions.append(
                        Suggestion(
                            type="tactic",
                            suggestion="Try 'constructor' or 'use' to provide witness",
                            confidence=0.8,
                            reasoning="Goal contains existential quantifiers (∃)",
                        )
                    )

                if "→" in goal:
                    suggestions.append(
                        Suggestion(
                            type="tactic",
                            suggestion="Try 'intro' to introduce hypothesis",
                            confidence=0.7,
                            reasoning="Goal contains implication (→)",
                        )
                    )

            # Suggest more hints (always provide this for partial)
            if hints_found:
                suggestions.append(
                    Suggestion(
                        type="hint",
                        suggestion="Try adding more hints from the same namespace",
                        confidence=0.6,
                        reasoning=f"Current hints ({len(hints_found)}) made partial progress",
                    )
                )
            else:
                # No hints found yet, suggest trying different sources
                suggestions.append(
                    Suggestion(
                        type="strategy",
                        suggestion="Try different candidate sources to find relevant hints",
                        confidence=0.7,
                        reasoning="No hints found yet, expanding search may help",
                    )
                )

        else:
            # Fail: suggest alternative strategies
            suggestions.append(
                Suggestion(
                    type="strategy",
                    suggestion="Try different candidate sources (e.g., original_proof_refs)",
                    confidence=0.7,
                    reasoning="Current search strategy did not find closing hints",
                )
            )

            suggestions.append(
                Suggestion(
                    type="strategy",
                    suggestion="Try increasing search depth or max_candidates",
                    confidence=0.6,
                    reasoning="Expanding search space may find additional hints",
                )
            )

            # Suggest manual tactics
            if initial_state:
                suggestions.append(
                    Suggestion(
                        type="tactic",
                        suggestion="Consider manual proof tactics (rw, simp, exact)",
                        confidence=0.5,
                        reasoning="Automation may not be sufficient for this theorem",
                    )
                )
            else:
                # No proof state available, suggest getting context
                suggestions.append(
                    Suggestion(
                        type="strategy",
                        suggestion="Use get_proof_context to understand theorem structure",
                        confidence=0.6,
                        reasoning="Understanding theorem context may reveal better strategies",
                    )
                )

        return suggestions
