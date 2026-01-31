"""
Property-based tests for FeedbackBuilder.

These tests verify Property 16: Feedback Builder Completeness.

Feature: iterative-orchestration-enhancements
Property 16: Feedback Builder Completeness

Requirements: 13.2, 13.3, 13.4, 13.5
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.feedback_builder import FeedbackBuilder
from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    Candidate,
    CandidateSource,
    ExecutionOutcome,
    Hint,
    HintSet,
    HintType,
    SearchResult,
)
from lean_proof_auto_mcp.lean.ports import ProofState


# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_proof_state(draw):
    """Generate valid ProofState instances."""
    goal = draw(st.text(min_size=1, max_size=200))
    num_hypotheses = draw(st.integers(min_value=0, max_value=10))
    hypotheses = [
        draw(st.text(min_size=1, max_size=50)) for _ in range(num_hypotheses)
    ]
    type_context = draw(st.text(min_size=0, max_size=100))
    goals_remaining = draw(st.integers(min_value=0, max_value=5))

    return ProofState(
        goal=goal,
        hypotheses=hypotheses,
        type_context=type_context,
        goals_remaining=goals_remaining,
    )


@st.composite
def valid_candidate(draw):
    """Generate valid Candidate instances."""
    name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="._"
    )))
    hint_type = draw(st.sampled_from(list(HintType)))
    source = draw(st.sampled_from(list(CandidateSource)))
    rank = draw(st.floats(min_value=0.0, max_value=10.0))

    hint = Hint(name=name, type=hint_type, source=source)
    return Candidate(hint=hint, rank=rank, metadata={})


@st.composite
def valid_search_result(draw):
    """Generate valid SearchResult instances."""
    outcome = draw(st.sampled_from(["closed", "partial", "failed"]))
    attempts = draw(st.integers(min_value=0, max_value=100))
    explored_sets = draw(st.integers(min_value=0, max_value=attempts + 1))

    # Generate hint set if outcome is closed or partial
    best_hint_set = None
    evidence = None
    if outcome in ("closed", "partial"):
        num_hints = draw(st.integers(min_value=1, max_value=5))
        hints = [
            Hint(
                name=f"hint_{i}",
                type=draw(st.sampled_from(list(HintType))),
                source=draw(st.sampled_from(list(CandidateSource))),
            )
            for i in range(num_hints)
        ]
        best_hint_set = HintSet(hints)

        # Create evidence
        evidence = ExecutionOutcome(
            status="success" if outcome == "closed" else "failure",
            automation_used="aesop",
            duration_s=draw(st.floats(min_value=0.1, max_value=10.0)),
            output="",
            error=None,
        )

    return SearchResult(
        outcome=outcome,
        best_hint_set=best_hint_set,
        attempts=attempts,
        explored_sets=explored_sets,
        evidence=evidence,
    )


# ============================================================================
# Property 16: Feedback Builder Completeness
# ============================================================================


@given(
    search_result=valid_search_result(),
    initial_state=valid_proof_state(),
    final_state=valid_proof_state(),
)
@settings(max_examples=100)
def test_property_16_partial_progress_completeness(
    search_result, initial_state, final_state
):
    """
    Feature: iterative-orchestration-enhancements, Property 16: Feedback Builder Completeness

    For any search result with partial progress, the Feedback_Builder SHALL identify
    which hints helped and their impact, calculate goal complexity reduction as a
    percentage, generate tactical suggestions with confidence scores between 0.0 and 1.0,
    and provide reasoning for all suggestions.

    Validates: Requirements 13.2, 13.3, 13.4, 13.5
    """
    builder = FeedbackBuilder()

    # Create candidates list
    candidates = []
    if search_result.best_hint_set:
        for hint in search_result.best_hint_set.hints:
            candidates.append(
                Candidate(hint=hint, rank=5.0, metadata={})
            )

    # Build feedback
    feedback = builder.build_search_feedback(
        search_result, initial_state, final_state, candidates
    )

    # Verify: Feedback should have valid status
    assert feedback.status in ("success", "partial", "fail")

    # Verify: If partial progress exists, it should be complete
    if feedback.partial_progress:
        # Verify: hints_that_helped should be a list of tuples
        assert isinstance(feedback.partial_progress.hints_that_helped, list)
        for hint_name, impact in feedback.partial_progress.hints_that_helped:
            assert isinstance(hint_name, str)
            assert isinstance(impact, str)
            assert impact in ("high", "medium", "low")

        # Verify: goal_complexity_reduction should be a percentage (0-100)
        assert 0.0 <= feedback.partial_progress.goal_complexity_reduction <= 100.0

        # Verify: progress_score should be between 0.0 and 1.0
        assert 0.0 <= feedback.partial_progress.progress_score <= 1.0

    # Verify: Suggestions should be complete
    assert isinstance(feedback.suggestions, list)
    for suggestion in feedback.suggestions:
        # Verify: confidence should be between 0.0 and 1.0
        assert 0.0 <= suggestion.confidence <= 1.0

        # Verify: reasoning should be non-empty
        assert len(suggestion.reasoning) > 0

        # Verify: type should be valid
        assert suggestion.type in ("tactic", "hint", "strategy")


@given(search_result=valid_search_result())
@settings(max_examples=100)
def test_property_16_suggestions_always_provided(search_result):
    """
    Feature: iterative-orchestration-enhancements, Property 16: Feedback Builder Completeness

    For any search result, the Feedback_Builder SHALL always provide tactical
    suggestions with confidence scores and reasoning.

    Validates: Requirements 13.4, 13.5
    """
    builder = FeedbackBuilder()

    # Create candidates list
    candidates = []
    if search_result.best_hint_set:
        for hint in search_result.best_hint_set.hints:
            candidates.append(
                Candidate(hint=hint, rank=5.0, metadata={})
            )

    # Build feedback without proof states
    feedback = builder.build_search_feedback(
        search_result, None, None, candidates
    )

    # Verify: Suggestions should always be provided
    assert isinstance(feedback.suggestions, list)
    assert len(feedback.suggestions) > 0

    # Verify: All suggestions should have confidence and reasoning
    for suggestion in feedback.suggestions:
        assert 0.0 <= suggestion.confidence <= 1.0
        assert len(suggestion.reasoning) > 0


@given(
    initial_state=valid_proof_state(),
    final_state=valid_proof_state(),
    candidates=st.lists(valid_candidate(), min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_property_16_hints_that_helped_identification(
    initial_state, final_state, candidates
):
    """
    Feature: iterative-orchestration-enhancements, Property 16: Feedback Builder Completeness

    For any search result with hints, the Feedback_Builder SHALL identify which
    hints helped and their impact (high, medium, low).

    Validates: Requirements 13.2
    """
    builder = FeedbackBuilder()

    # Create search result with hints
    hints = [c.hint for c in candidates]
    hint_set = HintSet(hints)

    search_result = SearchResult(
        outcome="partial",
        best_hint_set=hint_set,
        attempts=10,
        explored_sets=5,
        evidence=ExecutionOutcome(
            status="failure",
            automation_used="aesop",
            duration_s=1.0,
            output="",
            error=None,
        ),
    )

    # Build feedback
    feedback = builder.build_search_feedback(
        search_result, initial_state, final_state, candidates
    )

    # Verify: Partial progress should exist
    assert feedback.partial_progress is not None

    # Verify: hints_that_helped should match the candidates
    assert len(feedback.partial_progress.hints_that_helped) == len(candidates)

    # Verify: Each hint should have an impact rating
    for hint_name, impact in feedback.partial_progress.hints_that_helped:
        assert impact in ("high", "medium", "low")
        # Verify hint name is from candidates
        assert any(c.hint.name == hint_name for c in candidates)


@given(
    initial_complexity=st.floats(min_value=10.0, max_value=1000.0),
    final_complexity=st.floats(min_value=0.0, max_value=1000.0),
)
@settings(max_examples=100)
def test_property_16_complexity_reduction_calculation(
    initial_complexity, final_complexity
):
    """
    Feature: iterative-orchestration-enhancements, Property 16: Feedback Builder Completeness

    For any proof states, the Feedback_Builder SHALL calculate goal complexity
    reduction as a percentage between 0 and 100.

    Validates: Requirements 13.3
    """
    builder = FeedbackBuilder()

    # Create proof states with known complexity
    # We'll use goal length as a proxy for complexity
    initial_goal = "x" * int(initial_complexity)
    final_goal = "x" * int(final_complexity)

    initial_state = ProofState(
        goal=initial_goal,
        hypotheses=[],
        type_context="",
        goals_remaining=1,
    )

    final_state = ProofState(
        goal=final_goal,
        hypotheses=[],
        type_context="",
        goals_remaining=1,
    )

    # Create search result
    search_result = SearchResult(
        outcome="partial",
        best_hint_set=HintSet([]),
        attempts=1,
        explored_sets=1,
        evidence=None,
    )

    # Build feedback
    feedback = builder.build_search_feedback(
        search_result, initial_state, final_state, []
    )

    # Verify: Partial progress should exist
    assert feedback.partial_progress is not None

    # Verify: Complexity reduction should be a valid percentage
    reduction = feedback.partial_progress.goal_complexity_reduction
    assert 0.0 <= reduction <= 100.0

    # Verify: If final complexity is less, reduction should be positive
    if final_complexity < initial_complexity:
        assert reduction > 0.0


@given(search_result=valid_search_result())
@settings(max_examples=100)
def test_property_16_suggestion_confidence_bounds(search_result):
    """
    Feature: iterative-orchestration-enhancements, Property 16: Feedback Builder Completeness

    For any suggestions, the confidence scores SHALL be between 0.0 and 1.0.

    Validates: Requirements 13.4
    """
    builder = FeedbackBuilder()

    # Create candidates list
    candidates = []
    if search_result.best_hint_set:
        for hint in search_result.best_hint_set.hints:
            candidates.append(
                Candidate(hint=hint, rank=5.0, metadata={})
            )

    # Build feedback
    feedback = builder.build_search_feedback(
        search_result, None, None, candidates
    )

    # Verify: All confidence scores should be in valid range
    for suggestion in feedback.suggestions:
        assert 0.0 <= suggestion.confidence <= 1.0, (
            f"Confidence {suggestion.confidence} out of bounds for "
            f"suggestion: {suggestion.suggestion}"
        )
