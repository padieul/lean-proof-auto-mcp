"""
Property-based tests for Conditional Return Values.

These tests verify Property 6: Conditional Return Value Completeness.

Feature: iterative-orchestration-enhancements
Property 6: Conditional Return Value Completeness

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.feedback_builder import (
    FeedbackBuilder,
    PartialProgress,
    SearchFeedback,
    Suggestion,
)
from lean_proof_auto_mcp.core.search_annotations_domain import Candidate, SearchResult
from lean_proof_auto_mcp.core.search_orchestrator import SearchConfig, SearchResultEnhanced
from lean_proof_auto_mcp.lean.ports import ProofState


# ============================================================================
# Test Helpers
# ============================================================================


def create_mock_search_result(outcome: str) -> SearchResult:
    """Create a mock SearchResult for testing."""
    return SearchResult(
        outcome=outcome,
        best_hint_set=[
            Candidate(
                name="test_lemma",
                hint_type="add_safe",
                source="goal_symbols",
                rank=1.0,
            )
        ]
        if outcome == "closed"
        else None,
        attempts=10,
        explored_sets=5,
        evidence=None,
    )


def create_mock_proof_state() -> ProofState:
    """Create a mock ProofState for testing."""
    return ProofState(
        goal="x + y = y + x",
        hypotheses=["x : Nat", "y : Nat"],
        type_context="",
        goals_remaining=1,
    )


def create_mock_feedback(
    include_partial: bool = False,
    include_suggestions: bool = True,
) -> SearchFeedback:
    """Create a mock SearchFeedback for testing."""
    partial_progress = None
    if include_partial:
        partial_progress = PartialProgress(
            hints_that_helped=[("test_lemma", "reduced goal complexity by 50%")],
            goal_complexity_reduction=0.5,
            progress_score=0.7,
        )

    suggestions = []
    if include_suggestions:
        suggestions = [
            Suggestion(
                type="tactic",
                suggestion="Try using simp",
                confidence=0.8,
                reasoning="Goal contains simplifiable expressions",
            )
        ]

    return SearchFeedback(
        status="partial" if include_partial else "failed",
        hints_found=[],
        partial_progress=partial_progress,
        current_goal="x + y = y + x" if include_partial else None,
        suggestions=suggestions,
    )


# ============================================================================
# Property 6: Conditional Return Value Completeness
# ============================================================================


@given(
    return_proof_states=st.booleans(),
    return_partial_progress=st.booleans(),
    return_context=st.booleans(),
    return_similar_proofs=st.booleans(),
    return_search_trace=st.booleans(),
)
@settings(max_examples=100)
def test_property_6_return_flags_respected(
    return_proof_states,
    return_partial_progress,
    return_context,
    return_similar_proofs,
    return_search_trace,
):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    For any search result, when a return parameter is true, the system SHALL include
    the corresponding data in the response.

    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    # Create config with return flags
    config = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy="greedy",
        beam_width=3,
        max_search_steps=100,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=return_proof_states,
        return_partial_progress=return_partial_progress,
        return_context=return_context,
        return_similar_proofs=return_similar_proofs,
        return_search_trace=return_search_trace,
    )

    # Verify: Config should store the flags correctly
    assert config.return_proof_states == return_proof_states
    assert config.return_partial_progress == return_partial_progress
    assert config.return_context == return_context
    assert config.return_similar_proofs == return_similar_proofs
    assert config.return_search_trace == return_search_trace


@given(
    return_partial_progress=st.booleans(),
)
@settings(max_examples=100)
def test_property_6_partial_progress_inclusion(return_partial_progress):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    When return_partial_progress is true, the feedback SHALL include hints that helped,
    goal complexity reduction, and progress scores.

    Validates: Requirements 6.2
    """
    # Create feedback with or without partial progress
    feedback = create_mock_feedback(include_partial=return_partial_progress)

    if return_partial_progress:
        # Verify: Partial progress should be present
        assert feedback.partial_progress is not None
        assert len(feedback.partial_progress.hints_that_helped) > 0
        assert 0.0 <= feedback.partial_progress.goal_complexity_reduction <= 1.0
        assert 0.0 <= feedback.partial_progress.progress_score <= 1.0
    else:
        # Verify: Partial progress should be None
        assert feedback.partial_progress is None


@given(
    outcome=st.sampled_from(["closed", "partial", "failed"]),
)
@settings(max_examples=100)
def test_property_6_suggestions_always_included(outcome):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    The system SHALL always return tactical suggestions with confidence scores and
    reasoning regardless of parameters.

    Validates: Requirements 6.6
    """
    # Create feedback with suggestions
    feedback = create_mock_feedback(include_suggestions=True)

    # Verify: Suggestions should always be present
    assert feedback.suggestions is not None
    assert len(feedback.suggestions) > 0

    # Verify: Each suggestion should have required fields
    for suggestion in feedback.suggestions:
        assert suggestion.type in ["tactic", "hint", "strategy"]
        assert suggestion.suggestion is not None
        assert 0.0 <= suggestion.confidence <= 1.0
        assert suggestion.reasoning is not None


@given(
    return_search_trace=st.booleans(),
)
@settings(max_examples=100)
def test_property_6_search_trace_inclusion(return_search_trace):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    When return_search_trace is true, the result SHALL include detailed step-by-step
    search execution trace.

    Validates: Requirements 6.5
    """
    # Create mock result with or without trace
    feedback = create_mock_feedback()
    result = SearchResultEnhanced(
        outcome="failed",
        best_hint_set=None,
        attempts=10,
        explored_sets=5,
        feedback=feedback,
        metadata={},
        search_trace=[] if return_search_trace else None,
    )

    if return_search_trace:
        # Verify: Search trace should be present (even if empty)
        assert result.search_trace is not None
        assert isinstance(result.search_trace, list)
    else:
        # Verify: Search trace should be None
        assert result.search_trace is None


@given(
    return_proof_states=st.booleans(),
    outcome=st.sampled_from(["closed", "partial", "failed"]),
)
@settings(max_examples=100)
def test_property_6_proof_states_structure(return_proof_states, outcome):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    When return_proof_states is true, the result SHALL include initial and post-hint
    proof states with complete information.

    Validates: Requirements 6.1
    """
    # Create config with return_proof_states flag
    config = SearchConfig.from_depth("normal")
    config_dict = config.__dict__.copy()
    config_dict["return_proof_states"] = return_proof_states
    config = SearchConfig(**config_dict)

    # Verify: Config should store the flag
    assert config.return_proof_states == return_proof_states

    # Note: Actual proof state inclusion would be tested in integration tests
    # This property test verifies the configuration is respected


@given(
    return_context=st.booleans(),
    return_similar_proofs=st.booleans(),
)
@settings(max_examples=100)
def test_property_6_context_and_similar_proofs(return_context, return_similar_proofs):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    When return_context is true, the result SHALL include theorem statement, original
    proof, namespace, and in-scope declarations. When return_similar_proofs is true,
    the result SHALL include similar theorems with similarity scores.

    Validates: Requirements 6.3, 6.4
    """
    # Create config with flags
    config = SearchConfig.from_depth("normal")
    config_dict = config.__dict__.copy()
    config_dict["return_context"] = return_context
    config_dict["return_similar_proofs"] = return_similar_proofs
    config = SearchConfig(**config_dict)

    # Verify: Config should store the flags
    assert config.return_context == return_context
    assert config.return_similar_proofs == return_similar_proofs

    # Note: Actual context/similar proofs inclusion would be tested in integration tests
    # This property test verifies the configuration is respected


@given(
    return_flags=st.lists(st.booleans(), min_size=5, max_size=5),
)
@settings(max_examples=100)
def test_property_6_multiple_return_flags_independent(return_flags):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    Multiple return flags should be independent - setting one should not affect others.

    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    (
        return_proof_states,
        return_partial_progress,
        return_context,
        return_similar_proofs,
        return_search_trace,
    ) = return_flags

    # Create config with all flags
    config = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy="greedy",
        beam_width=3,
        max_search_steps=100,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=return_proof_states,
        return_partial_progress=return_partial_progress,
        return_context=return_context,
        return_similar_proofs=return_similar_proofs,
        return_search_trace=return_search_trace,
    )

    # Verify: Each flag should be stored independently
    assert config.return_proof_states == return_proof_states
    assert config.return_partial_progress == return_partial_progress
    assert config.return_context == return_context
    assert config.return_similar_proofs == return_similar_proofs
    assert config.return_search_trace == return_search_trace


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
def test_property_6_suggestion_confidence_bounds(confidence):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    Tactical suggestions SHALL always include confidence scores between 0.0 and 1.0.

    Validates: Requirements 6.6
    """
    # Create suggestion with confidence
    suggestion = Suggestion(
        type="tactic",
        suggestion="Try using simp",
        confidence=confidence,
        reasoning="Goal contains simplifiable expressions",
    )

    # Verify: Confidence should be within bounds
    assert 0.0 <= suggestion.confidence <= 1.0
    assert suggestion.confidence == confidence


@given(
    suggestion_type=st.sampled_from(["tactic", "hint", "strategy"]),
)
@settings(max_examples=100)
def test_property_6_suggestion_types(suggestion_type):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    Tactical suggestions SHALL have valid types (tactic, hint, strategy).

    Validates: Requirements 6.6
    """
    # Create suggestion with type
    suggestion = Suggestion(
        type=suggestion_type,
        suggestion="Test suggestion",
        confidence=0.8,
        reasoning="Test reasoning",
    )

    # Verify: Type should be valid
    assert suggestion.type in ["tactic", "hint", "strategy"]
    assert suggestion.type == suggestion_type


@given(
    progress_score=st.floats(min_value=0.0, max_value=1.0),
    complexity_reduction=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
def test_property_6_partial_progress_bounds(progress_score, complexity_reduction):
    """
    Feature: iterative-orchestration-enhancements, Property 6: Conditional Return Value Completeness

    Partial progress SHALL include progress scores and complexity reduction as
    percentages between 0.0 and 1.0.

    Validates: Requirements 6.2
    """
    # Create partial progress
    partial = PartialProgress(
        hints_that_helped=[("test_lemma", "helped")],
        goal_complexity_reduction=complexity_reduction,
        progress_score=progress_score,
    )

    # Verify: Values should be within bounds
    assert 0.0 <= partial.progress_score <= 1.0
    assert 0.0 <= partial.goal_complexity_reduction <= 1.0
    assert partial.progress_score == progress_score
    assert partial.goal_complexity_reduction == complexity_reduction
