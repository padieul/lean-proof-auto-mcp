"""
Search orchestration service for hint set search.

This module provides the SearchOrchestrator service that orchestrates
search strategies with configurable parameters, builds rich feedback,
and tracks partial progress during search.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.6, 5.7, 29.2, 29.3
"""

import logging
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING, Literal

from ..lean.ports import ProofStateInspector, ProofValidator
from ..observability.ports import MetadataCollector
from .candidate_generator import CandidateGenerator
from .feedback_builder import FeedbackBuilder, SearchFeedback
from .search_automated_proof_domain import (
    Candidate,
    CandidateSource,
    HintSet,
    HintType,
    SearchResult,
)

if TYPE_CHECKING:
    from .harness_construction import HarnessConstructor
    from .verify_domain import LeanRunner

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
    best_hint_set: "HintSet | None"
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
        harness_constructor: "HarnessConstructor | None" = None,
        lean_runner: "LeanRunner | None" = None,
        proof_state_inspector: ProofStateInspector | None = None,
        metadata_collector: MetadataCollector | None = None,
    ):
        """
        Initialize SearchOrchestrator with dependency injection.

        Args:
            candidate_gen: CandidateGenerator for extracting hints
            feedback_builder: FeedbackBuilder for building feedback
            validator: ProofValidator for validating proofs
            harness_constructor: Optional HarnessConstructor for building test harnesses
            lean_runner: Optional LeanRunner for running Lean verification
            proof_state_inspector: Optional ProofStateInspector for proof states
            metadata_collector: Optional MetadataCollector for environment metadata

        Requirements: 4.1, 9.2, 9.5, 29.2
        """
        self.candidate_gen = candidate_gen
        self.feedback_builder = feedback_builder
        self.validator = validator
        self.harness_constructor = harness_constructor
        self.lean_runner = lean_runner
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

        # If harness_constructor is not provided, return placeholder result
        if self.harness_constructor is None:
            logger.warning("No harness_constructor provided, returning placeholder result")
            return self._build_placeholder_result(config)

        # 1. Generate candidates from configured sources
        try:
            # Get theorem declaration from index
            from .search_automated_proof_domain import CandidateConfig

            # Find theorem in index
            # Try exact match first, then try with namespace prefix
            theorem_decl = None
            for decl in self.candidate_gen.index.decls:
                if decl.theorem_id == theorem_id:
                    theorem_decl = decl
                    break
                # Also try matching the short name (without namespace)
                if "." in decl.theorem_id and decl.theorem_id.split(".")[-1] == theorem_id:
                    theorem_decl = decl
                    break

            if theorem_decl is None:
                raise ValueError(f"Theorem not found in index: {theorem_id}")

            # Build candidate config from search config
            candidate_config = CandidateConfig(
                sources=config.candidate_sources,
                max_candidates_per_source=config.max_candidates_per_source,
                allow_simp_hints=config.allow_simp_hints,
                allow_unfold_hints=config.allow_unfold_hints,
            )

            # Generate candidates using the correct method signature
            candidates = self.candidate_gen.generate(
                theorem_decl=theorem_decl,
                sources=config.candidate_sources,
                config=candidate_config,
            )
            logger.info(f"Generated {len(candidates)} candidates")
        except Exception as e:
            logger.error(f"Candidate generation failed: {e}")
            return self._build_error_result(config, f"Candidate generation failed: {e}")

        # 2. Execute search strategy
        search_result = self._execute_search_strategy(
            file_path=file_path,
            theorem_id=theorem_id,
            candidates=candidates,
            config=config,
        )

        # 3. Collect metadata
        metadata = self._build_metadata()

        # 4. Build rich feedback
        feedback = self.feedback_builder.build_search_feedback(
            search_result=search_result,
            initial_proof_state=None,
            final_proof_state=None,
            candidates=candidates,
        )

        # 5. Build enhanced result
        return SearchResultEnhanced(
            outcome=search_result.outcome,
            best_hint_set=search_result.best_hint_set,
            attempts=search_result.attempts,
            explored_sets=search_result.explored_sets,
            feedback=feedback,
            metadata=metadata,
            search_trace=None if not config.return_search_trace else [],
        )

    def _execute_search_strategy(
        self,
        file_path: str,
        theorem_id: str,
        candidates: list[Candidate],
        config: SearchConfig,
    ) -> SearchResult:
        """
        Execute the configured search strategy.

        This method implements the core search logic, testing hint combinations
        using the harness constructor and lean runner.

        Args:
            file_path: Path to Lean file
            theorem_id: Theorem identifier
            candidates: List of candidate hints
            config: Search configuration

        Returns:
            SearchResult with best hint set and statistics

        Requirements: 4.1, 4.2, 4.3
        """
        attempts = 0
        explored_sets = 0
        best_hint_set = None

        # Generate hint combinations based on strategy
        hint_combinations = self._generate_hint_combinations(candidates, config)

        logger.info(f"Testing {len(hint_combinations)} hint combinations")

        # Test each combination
        for hint_set in hint_combinations:
            if attempts >= config.max_search_steps:
                logger.info(f"Reached max search steps: {config.max_search_steps}")
                break

            attempts += 1
            explored_sets += 1

            # Test this hint combination
            success = self._test_hint_combination(
                file_path=file_path,
                theorem_id=theorem_id,
                hints=hint_set,
                config=config,
            )

            if success:
                logger.info(f"Found successful hint set with {len(hint_set)} hints")
                best_hint_set = HintSet([c.hint for c in hint_set])
                return SearchResult(
                    outcome="closed",
                    best_hint_set=best_hint_set,
                    attempts=attempts,
                    explored_sets=explored_sets,
                    evidence=None,
                )

        # No successful combination found
        outcome: Literal["closed", "partial", "failed"] = "partial" if best_hint_set else "failed"
        return SearchResult(
            outcome=outcome,
            best_hint_set=best_hint_set,
            attempts=attempts,
            explored_sets=explored_sets,
            evidence=None,
        )

    def _generate_hint_combinations(
        self,
        candidates: list[Candidate],
        config: SearchConfig,
    ) -> list[list[Candidate]]:
        """
        Generate hint combinations based on search strategy.

        This method implements different search strategies:
        - greedy: Test individual hints, then pairs, then triples, etc.
        - beam: Keep top-k partial solutions at each step
        - exhaustive: Test all possible combinations up to max_hints_in_set

        Args:
            candidates: List of candidate hints
            config: Search configuration

        Returns:
            List of hint combinations to test

        Requirements: 4.2
        """
        if config.search_strategy == "greedy":
            return self._generate_greedy_combinations(candidates, config)
        elif config.search_strategy == "beam":
            return self._generate_beam_combinations(candidates, config)
        elif config.search_strategy == "exhaustive":
            return self._generate_exhaustive_combinations(candidates, config)
        else:
            logger.warning(f"Unknown search strategy: {config.search_strategy}, using greedy")
            return self._generate_greedy_combinations(candidates, config)

    def _generate_greedy_combinations(
        self,
        candidates: list[Candidate],
        config: SearchConfig,
    ) -> list[list[Candidate]]:
        """
        Generate combinations in greedy order: singles, pairs, triples, etc.

        Args:
            candidates: List of candidate hints
            config: Search configuration

        Returns:
            List of hint combinations in greedy order

        Requirements: 4.2
        """
        combinations_list = []

        # Start with individual hints
        for candidate in candidates[: config.max_candidates]:
            combinations_list.append([candidate])
            if len(combinations_list) >= config.max_search_steps:
                return combinations_list

        # Then pairs, triples, etc. up to max_hints_in_set
        for size in range(2, min(config.max_hints_in_set + 1, len(candidates) + 1)):
            for combo in combinations(candidates[: config.max_candidates], size):
                combinations_list.append(list(combo))
                if len(combinations_list) >= config.max_search_steps:
                    return combinations_list

        return combinations_list

    def _generate_beam_combinations(
        self,
        candidates: list[Candidate],
        config: SearchConfig,
    ) -> list[list[Candidate]]:
        """
        Generate combinations using beam search.

        Beam search maintains top-k partial solutions at each step.

        Args:
            candidates: List of candidate hints
            config: Search configuration

        Returns:
            List of hint combinations from beam search

        Requirements: 4.2
        """
        # For now, fall back to greedy
        # TODO: Implement proper beam search with scoring
        logger.warning("Beam search not fully implemented, using greedy")
        return self._generate_greedy_combinations(candidates, config)

    def _generate_exhaustive_combinations(
        self,
        candidates: list[Candidate],
        config: SearchConfig,
    ) -> list[list[Candidate]]:
        """
        Generate all possible combinations up to max_hints_in_set.

        Args:
            candidates: List of candidate hints
            config: Search configuration

        Returns:
            List of all hint combinations

        Requirements: 4.2
        """
        combinations_list = []

        # Generate all combinations of all sizes
        for size in range(1, min(config.max_hints_in_set + 1, len(candidates) + 1)):
            for combo in combinations(candidates[: config.max_candidates], size):
                combinations_list.append(list(combo))
                if len(combinations_list) >= config.max_search_steps:
                    return combinations_list

        return combinations_list

    def _test_hint_combination(
        self,
        file_path: str,
        theorem_id: str,
        hints: list[Candidate],
        config: SearchConfig,
    ) -> bool:
        """
        Test a specific hint combination using harness constructor.

        This method constructs a test harness with the given hints and
        runs automation to check if the proof succeeds.

        Args:
            file_path: Path to Lean file
            theorem_id: Theorem identifier
            hints: List of hints to test
            config: Search configuration

        Returns:
            True if proof succeeds with these hints, False otherwise

        Requirements: 4.1
        """
        if self.harness_constructor is None or self.lean_runner is None:
            logger.warning("Cannot test hints without harness_constructor and lean_runner")
            return False

        try:
            # Build proof attempt with hints
            proof_attempt = self._build_proof_with_hints(hints, config)

            # Construct harness
            from .harness_construction import HarnessConfig, HarnessError, HarnessSuccess

            harness_config = HarnessConfig(
                theorem_id=theorem_id,
                file_path=file_path,
                proof_attempt=proof_attempt,
                additional_imports=self._get_additional_imports(config),
            )

            result = self.harness_constructor.construct(harness_config)

            # Handle construction errors
            if isinstance(result, HarnessError):
                logger.debug(f"Harness construction failed: {result.message}")
                return False

            # Extract harness code
            assert isinstance(result, HarnessSuccess)

            # Run Lean verification
            # TODO: Implement actual Lean verification
            # For now, return False (no successful proofs)
            logger.debug(f"Testing hint combination with {len(hints)} hints")
            return False

        except Exception as e:
            logger.debug(f"Error testing hint combination: {e}")
            return False

    def _build_proof_with_hints(
        self,
        hints: list[Candidate],
        config: SearchConfig,
    ) -> str:
        """
        Build proof attempt string with hints.

        This method constructs a proof tactic that includes the hints
        followed by the automation mode.

        Args:
            hints: List of hints to include
            config: Search configuration

        Returns:
            Proof attempt string

        Requirements: 4.1
        """
        if not hints:
            # No hints, just use automation
            return config.automation_mode

        # Build hint applications
        hint_lines = []
        for candidate in hints:
            hint = candidate.hint
            # Format hint based on type
            if hint.type == HintType.ADD_SAFE or hint.type == HintType.ADD_UNSAFE:
                hint_lines.append(f"  have := {hint.name}")
            elif hint.type == HintType.SIMP:
                hint_lines.append(f"  simp only [{hint.name}]")
            elif hint.type == HintType.UNFOLD:
                hint_lines.append(f"  unfold {hint.name}")
            else:
                # Generic hint application
                hint_lines.append(f"  apply {hint.name}")

        # Combine hints with automation
        proof_lines = hint_lines + [f"  {config.automation_mode}"]
        return "\n".join(proof_lines)

    def _get_additional_imports(self, config: SearchConfig) -> list[str]:
        """
        Get additional imports needed for automation mode.

        Args:
            config: Search configuration

        Returns:
            List of import statements

        Requirements: 4.1
        """
        imports = []

        if config.automation_mode in ("aesop", "aesop?"):
            imports.append("import Aesop")

        if config.automation_secondary and config.automation_secondary in ("aesop", "aesop?"):
            imports.append("import Aesop")

        return imports

    def _build_placeholder_result(self, config: SearchConfig) -> SearchResultEnhanced:
        """
        Build placeholder result when harness_constructor is not available.

        Args:
            config: Search configuration

        Returns:
            SearchResultEnhanced with placeholder data

        Requirements: 4.1
        """
        metadata = self._build_metadata()

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

    def _build_error_result(self, config: SearchConfig, error_message: str) -> SearchResultEnhanced:
        """
        Build error result when search fails.

        Args:
            config: Search configuration
            error_message: Error message

        Returns:
            SearchResultEnhanced with error information

        Requirements: 4.1
        """
        metadata = self._build_metadata()
        metadata["error"] = error_message

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
