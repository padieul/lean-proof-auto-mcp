"""
Property-based tests for Search Configuration.

These tests verify Property 4: Search Depth Configuration Consistency.

Feature: iterative-orchestration-enhancements
Property 4: Search Depth Configuration Consistency

Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.search_orchestrator import SearchConfig

# ============================================================================
# Property 4: Search Depth Configuration Consistency
# ============================================================================


@given(depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]))
@settings(max_examples=100)
def test_property_4_depth_preset_parameters(depth):
    """
    Feature: iterative-orchestration-enhancements, Property 4: Search Depth
    Configuration Consistency

    For any search_depth value (quick, normal, deep, exhaustive), the system SHALL
    apply the corresponding preset parameters (search_budget_s, max_candidates,
    max_search_steps, minimize_budget_s) consistently.

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    # Create config from depth preset
    config = SearchConfig.from_depth(depth)

    # Verify: search_depth should match
    assert config.search_depth == depth

    # Verify: Parameters should match expected presets
    expected_presets = {
        "quick": (10.0, 20, 50, 5.0),
        "normal": (30.0, 50, 100, 30.0),
        "deep": (60.0, 100, 200, 60.0),
        "exhaustive": (120.0, 200, 500, 120.0),
    }

    expected_budget, expected_candidates, expected_steps, expected_min_budget = expected_presets[
        depth
    ]

    assert config.search_budget_s == expected_budget
    assert config.max_candidates == expected_candidates
    assert config.max_search_steps == expected_steps
    assert config.minimize_budget_s == expected_min_budget


@given(depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]))
@settings(max_examples=100)
def test_property_4_depth_preset_consistency(depth):
    """
    Feature: iterative-orchestration-enhancements, Property 4: Search Depth
    Configuration Consistency

    For any search_depth value, creating config multiple times should produce
    consistent results.

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    # Create config twice
    config1 = SearchConfig.from_depth(depth)
    config2 = SearchConfig.from_depth(depth)

    # Verify: All parameters should match
    assert config1.search_depth == config2.search_depth
    assert config1.search_budget_s == config2.search_budget_s
    assert config1.max_candidates == config2.max_candidates
    assert config1.max_search_steps == config2.max_search_steps
    assert config1.minimize_budget_s == config2.minimize_budget_s


@given(
    depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]),
    custom_budget=st.floats(min_value=1.0, max_value=300.0),
)
@settings(max_examples=100)
def test_property_4_parameter_override(depth, custom_budget):
    """
    Feature: iterative-orchestration-enhancements, Property 4: Search Depth
    Configuration Consistency

    Individual parameter overrides should take precedence over presets.

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    # Create base config from depth
    base_config = SearchConfig.from_depth(depth)

    # Create config with custom budget (simulating override)
    custom_config = SearchConfig(
        search_depth=base_config.search_depth,
        search_budget_s=custom_budget,  # Override
        max_candidates=base_config.max_candidates,
        candidate_sources=base_config.candidate_sources,
        max_candidates_per_source=base_config.max_candidates_per_source,
        automation_mode=base_config.automation_mode,
        automation_secondary=base_config.automation_secondary,
        search_strategy=base_config.search_strategy,
        beam_width=base_config.beam_width,
        max_search_steps=base_config.max_search_steps,
        max_hints_in_set=base_config.max_hints_in_set,
        allow_simp_hints=base_config.allow_simp_hints,
        allow_unfold_hints=base_config.allow_unfold_hints,
        allow_unsafe_hints=base_config.allow_unsafe_hints,
        minimize_hints=base_config.minimize_hints,
        minimize_budget_s=base_config.minimize_budget_s,
        return_proof_states=base_config.return_proof_states,
        return_partial_progress=base_config.return_partial_progress,
        return_context=base_config.return_context,
        return_similar_proofs=base_config.return_similar_proofs,
        return_search_trace=base_config.return_search_trace,
    )

    # Verify: Custom budget should be used
    assert custom_config.search_budget_s == custom_budget

    # Verify: Other parameters should match base config
    assert custom_config.max_candidates == base_config.max_candidates
    assert custom_config.max_search_steps == base_config.max_search_steps


@given(depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]))
@settings(max_examples=100)
def test_property_4_depth_ordering(depth):
    """
    Feature: iterative-orchestration-enhancements, Property 4: Search Depth
    Configuration Consistency

    Search depth presets should follow a consistent ordering:
    quick < normal < deep < exhaustive

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    # Create configs for all depths
    quick = SearchConfig.from_depth("quick")
    normal = SearchConfig.from_depth("normal")
    deep = SearchConfig.from_depth("deep")
    exhaustive = SearchConfig.from_depth("exhaustive")

    # Verify: Budget ordering
    assert quick.search_budget_s < normal.search_budget_s
    assert normal.search_budget_s < deep.search_budget_s
    assert deep.search_budget_s < exhaustive.search_budget_s

    # Verify: Candidates ordering
    assert quick.max_candidates < normal.max_candidates
    assert normal.max_candidates < deep.max_candidates
    assert deep.max_candidates < exhaustive.max_candidates

    # Verify: Steps ordering
    assert quick.max_search_steps < normal.max_search_steps
    assert normal.max_search_steps < deep.max_search_steps
    assert deep.max_search_steps < exhaustive.max_search_steps


@given(depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]))
@settings(max_examples=100)
def test_property_4_default_values(depth):
    """
    Feature: iterative-orchestration-enhancements, Property 4: Search Depth
    Configuration Consistency

    All depth presets should have sensible default values for all parameters.

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    config = SearchConfig.from_depth(depth)

    # Verify: All parameters should be set
    assert config.search_depth is not None
    assert config.search_budget_s > 0
    assert config.max_candidates > 0
    assert config.max_search_steps > 0
    assert config.minimize_budget_s > 0

    # Verify: Candidate sources should be non-empty
    assert len(config.candidate_sources) > 0

    # Verify: Boolean flags should be set
    assert isinstance(config.allow_simp_hints, bool)
    assert isinstance(config.allow_unfold_hints, bool)
    assert isinstance(config.allow_unsafe_hints, bool)
    assert isinstance(config.minimize_hints, bool)

    # Verify: Return flags should be set
    assert isinstance(config.return_proof_states, bool)
    assert isinstance(config.return_partial_progress, bool)
    assert isinstance(config.return_context, bool)
    assert isinstance(config.return_similar_proofs, bool)
    assert isinstance(config.return_search_trace, bool)


@given(depth=st.sampled_from(["quick", "normal", "deep", "exhaustive"]))
@settings(max_examples=100)
def test_property_4_budget_relationships(depth):
    """
    Feature: iterative-orchestration-enhancements, Property 4: Search Depth
    Configuration Consistency

    Budget parameters should have sensible relationships:
    - minimize_budget_s should be <= search_budget_s

    Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    config = SearchConfig.from_depth(depth)

    # Verify: Minimize budget should not exceed search budget
    assert config.minimize_budget_s <= config.search_budget_s

    # Verify: All budgets should be positive
    assert config.search_budget_s > 0
    assert config.minimize_budget_s > 0
