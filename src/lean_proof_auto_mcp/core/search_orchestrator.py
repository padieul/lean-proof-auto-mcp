"""
Search orchestration service for hint set search.

This module provides the SearchOrchestrator service that orchestrates
search strategies with configurable parameters, builds rich feedback,
and tracks partial progress during search.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.6, 5.7, 29.2, 29.3
"""

import logging
from dataclasses import dataclass
from typing import Literal

from ..lean.ports import ProofStateInspector, ProofValidator
from ..observability.ports import MetadataCollector
from .candidate_generator import CandidateGenerator
from .feedback_builder import FeedbackBuilder, SearchFeedback
from .search_annotations_domain import Candidate, CandidateSource, SearchResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchConfig:
    """
    Configuration for search operation.

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """

    search_depth: str  # "quick" | "normal" | "deep" | "exhaustive"
    search_budget_s: float
    max_candidates: int
    candidate_sources: list[CandidateSource]
    max_candidates_per_source: int
    automation_mode: str  # "aesop" | "simp" | "omega" | "grind"
    automation_secondary: str | None
    search_strategy: str  # "greedy" | "beam" | "exhaustive"
    beam_width: int
    max_search_steps: int
    max_hints_in_set: int
    allow_simp_hints: bool
    allow_unfold_hints: bool
    allow_unsafe_hints: bool
    minimize_hints: bool
    minimize_budget_s: float
    return_proof_states: bool
    return_partial_progress: bool
    return_context: bool
    return_similar_proofs: bool
    return_search_trace: bool

    @staticmethod
    def from_depth(depth: str) -> "SearchConfig":
        """
        Create config from depth preset.

        Args:
            depth: Search depth preset

        Returns:
            SearchConfig with preset parameters

        Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
        """
        presets = {
            "quick": (10.0, 20, 50, 5.0),
            "normal": (30.0, 50, 100, 30.0),
            "deep": (60.0, 100, 200, 60.0),
            "exhaustive": (120.0, 200, 500, 120.0),
        }

        if depth not in presets:
            raise ValueError(f"Invalid search depth: {depth}")

        budget, candidates, steps, min_budget = presets[depth]

        return SearchConfig(
            search_depth=depth,
            search_budget_s=budget,
            max_candidates=candidates,
            candidate_sources=[
                CandidateSource.GOAL_SYMBOLS,
                CandidateSource.LOCAL_CONTEXT,
                CandidateSource.SAME_NAMESPACE,
                CandidateSource.ORIGINAL_PROOF_REFS,
            ],
            max_candidates_per_source=candidates // 4,
            automation_mode="aesop",
            automation_secondary=None,
            search_strategy="greedy",
            beam_width=3,
            max_search_steps=steps,
            max_hints_in_set=10,
            allow_simp_hints=True,
            allow_unfold_hints=True,
            allow_unsafe_hints=False,
            minimize_hints=True,
            minimize_budget_s=min_budget,
            return_proof_states=True,
            return_partial_progress=True,
            return_context=False,
            return_similar_proofs=False,
            return_search_trace=False,
        )


@dataclass(frozen=True)
class SearchResultEnhanced:
    """
    Enhanced search result with rich feedback and metadata.

    Requirements: 4.4, 4.5, 4.6, 4.8, 29.2, 29.3
    """

    outcome: Literal["closed", "partial", "failed"]
    best_hint_set: list[Candidate] | None
    attempts: int
    explored_sets: int
    feedback: SearchFeedback
    metadata: dict[str, str]  # Version info from MetadataCollector
    search_trace: list[dict] | None  # Optional search trace


class SearchOrchestrator:
    """
    Orchestrate search strategies with configurable parameters.

    The SearchOrchestrator coordinates candidate generation, search execution,
    feedback building, and metadata collection to provide comprehensive
    search results with rich feedback for LLM iteration.

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.6, 5.7, 29.2, 29.3
    """

    def __init__(
        self,
        candidate_gen: CandidateGenerator,
        feedback_builder: FeedbackBuilder,
        validator: ProofValidator,
        proof_state_inspector: ProofStateInspector | None = None,
        metadata_collector: MetadataCollector | None = None,
    ):
        """
        Initialize SearchOrchestrator with dependency injection.

        Args:
            candidate_gen: CandidateGenerator for extracting hints
            feedback_builder: FeedbackBuilder for building feedback
            validator: ProofValidator for validating proofs
            proof_state_inspector: Optional ProofStateInspector for proof states
            metadata_collector: Optional MetadataCollector for environment metadata

        Requirements: 4.1, 9.2, 9.5, 29.2
        """
        self.candidate_gen = candidate_gen
        self.feedback_builder = feedback_builder
        self.validator = validator
        self.proof_state_inspector = proof_state_inspector
        self.metadata_collector = metadata_collector

    def search(
        self,
        file_path: str,
        theorem_id: str,
        config: SearchConfig,
    ) -> SearchResultEnhanced:
        """
        Execute search with given configuration.

        This method orchestrates the complete search process:
        1. Generate candidates from configured sources
        2. Execute search strategy (greedy, beam, exhaustive)
        3. Track partial progress during search
        4. Build rich feedback for LLM
        5. Collect metadata using MetadataCollector port

        Args:
            file_path: Path to Lean file
            theorem_id: Theorem identifier
            config: Search configuration

        Returns:
            SearchResultEnhanced with complete search information

        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.6, 5.7, 29.2, 29.3
        """
        logger.info(
            f"Starting search for {theorem_id} with depth={config.search_depth}, "
            f"strategy={config.search_strategy}"
        )

        # TODO: Implement actual search logic
        # For now, return a placeholder result

        # Collect metadata
        metadata = self._build_metadata()

        # Build placeholder feedback
        from ..lean.ports import ProofState

        feedback = self.feedback_builder.build_search_feedback(
            search_result=SearchResult(
                outcome="failed",
                best_hint_set=None,
                attempts=0,
                explored_sets=0,
                evidence=None,
            ),
            initial_proof_state=None,
            final_proof_state=None,
            candidates=[],
        )

        return SearchResultEnhanced(
            outcome="failed",
            best_hint_set=None,
            attempts=0,
            explored_sets=0,
            feedback=feedback,
            metadata=metadata,
            search_trace=None if not config.return_search_trace else [],
        )

    def _build_metadata(self) -> dict[str, str]:
        """
        Build metadata section with version information.

        Uses the injected MetadataCollector port to gather environment
        metadata (git commit, lean version, lake version). If no collector
        is provided, returns an empty dictionary.

        Returns:
            Metadata dictionary

        Requirements: 29.2, 29.3, 29.4, 29.7
        """
        if self.metadata_collector is None:
            logger.debug("No metadata collector configured, skipping metadata collection")
            return {}

        return self.metadata_collector.collect_version_info()
