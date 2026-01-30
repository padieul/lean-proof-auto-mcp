"""
Property-based tests for Search Strategy Behavior.

These tests verify Property 10: Search Strategy Behavior Consistency.

Feature: iterative-orchestration-enhancements
Property 10: Search Strategy Behavior Consistency

Requirements: 19.2, 19.3, 19.4
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.search_orchestrator import SearchConfig


# ============================================================================
# Property 10: Search Strategy Behavior Consistency
# ============================================================================


@given(strategy=st.sampled_from(["greedy", "beam", "exhaustive"]))
@settings(max_examples=100)
def test_property_10_strategy_configuration(strategy):
    """
    Feature: iterative-orchestration-enhancements, Property 10: Search Strategy Behavior Consistency

    For any search strategy (greedy, beam, exhaustive), the system SHALL accept
    the strategy configuration and create a valid SearchConfig.

    Validates: Requirements 19.2, 19.3, 19.4
    """
    # Create config with specified strategy
    config = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy=strategy,
        beam_width=3,
        max_search_steps=100,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=True,
        return_partial_progress=True,
        return_context=False,
        return_similar_proofs=False,
        return_search_trace=False,
    )

    # Verify: Strategy should be set correctly
    assert config.search_strategy == strategy


@given(
    strategy=st.sampled_from(["greedy", "beam", "exhaustive"]),
    beam_width=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_property_10_beam_width_configuration(strategy, beam_width):
    """
    Feature: iterative-orchestration-enhancements, Property 10: Search Strategy Behavior Consistency

    For beam search strategy, the system SHALL accept and use the configured
    beam_width parameter.

    Validates: Requirements 19.3
    """
    # Create config with beam strategy and custom beam_width
    config = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy=strategy,
        beam_width=beam_width,
        max_search_steps=100,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=True,
        return_partial_progress=True,
        return_context=False,
        return_similar_proofs=False,
        return_search_trace=False,
    )

    # Verify: Beam width should be set correctly
    assert config.beam_width == beam_width

    # Verify: Beam width should be positive
    assert config.beam_width > 0


@given(
    strategy=st.sampled_from(["greedy", "beam", "exhaustive"]),
    max_steps=st.integers(min_value=1, max_value=1000),
)
@settings(max_examples=100)
def test_property_10_max_search_steps_configuration(strategy, max_steps):
    """
    Feature: iterative-orchestration-enhancements, Property 10: Search Strategy Behavior Consistency

    For any search strategy, the system SHALL accept and use the configured
    max_search_steps parameter.

    Validates: Requirements 19.2, 19.3, 19.4
    """
    # Create config with custom max_search_steps
    config = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy=strategy,
        beam_width=3,
        max_search_steps=max_steps,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=True,
        return_partial_progress=True,
        return_context=False,
        return_similar_proofs=False,
        return_search_trace=False,
    )

    # Verify: Max search steps should be set correctly
    assert config.max_search_steps == max_steps

    # Verify: Max search steps should be positive
    assert config.max_search_steps > 0


@given(strategy=st.sampled_from(["greedy", "beam", "exhaustive"]))
@settings(max_examples=100)
def test_property_10_strategy_consistency(strategy):
    """
    Feature: iterative-orchestration-enhancements, Property 10: Search Strategy Behavior Consistency

    For any search strategy, creating config multiple times with the same
    parameters should produce consistent results.

    Validates: Requirements 19.2, 19.3, 19.4
    """
    # Create config twice with same parameters
    config1 = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy=strategy,
        beam_width=3,
        max_search_steps=100,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=True,
        return_partial_progress=True,
        return_context=False,
        return_similar_proofs=False,
        return_search_trace=False,
    )

    config2 = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy=strategy,
        beam_width=3,
        max_search_steps=100,
        max_hints_in_set=10,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=True,
        return_partial_progress=True,
        return_context=False,
        return_similar_proofs=False,
        return_search_trace=False,
    )

    # Verify: All parameters should match
    assert config1.search_strategy == config2.search_strategy
    assert config1.beam_width == config2.beam_width
    assert config1.max_search_steps == config2.max_search_steps


@given(depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]))
@settings(max_examples=100)
def test_property_10_default_strategy(depth):
    """
    Feature: iterative-orchestration-enhancements, Property 10: Search Strategy Behavior Consistency

    For any depth preset, the default search strategy should be "greedy".

    Validates: Requirements 19.2
    """
    # Create config from depth preset
    config = SearchConfig.from_depth(depth)

    # Verify: Default strategy should be greedy
    assert config.search_strategy == "greedy"


@given(
    strategy=st.sampled_from(["greedy", "beam", "exhaustive"]),
    max_hints=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_property_10_max_hints_in_set(strategy, max_hints):
    """
    Feature: iterative-orchestration-enhancements, Property 10: Search Strategy Behavior Consistency

    For any search strategy, the system SHALL respect the max_hints_in_set
    parameter which limits the size of hint sets explored.

    Validates: Requirements 19.2, 19.3, 19.4
    """
    # Create config with custom max_hints_in_set
    config = SearchConfig(
        search_depth="normal",
        search_budget_s=30.0,
        max_candidates=50,
        candidate_sources=[],
        max_candidates_per_source=10,
        automation_mode="aesop",
        automation_secondary=None,
        search_strategy=strategy,
        beam_width=3,
        max_search_steps=100,
        max_hints_in_set=max_hints,
        allow_simp_hints=True,
        allow_unfold_hints=True,
        allow_unsafe_hints=False,
        minimize_hints=True,
        minimize_budget_s=30.0,
        return_proof_states=True,
        return_partial_progress=True,
        return_context=False,
        return_similar_proofs=False,
        return_search_trace=False,
    )

    # Verify: Max hints in set should be set correctly
    assert config.max_hints_in_set == max_hints

    # Verify: Max hints in set should be positive
    assert config.max_hints_in_set > 0
