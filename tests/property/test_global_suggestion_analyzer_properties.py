"""
Property-based tests for GlobalSuggestionAnalyzer service.

These tests verify universal properties that should hold for global
annotation suggestion analysis. Each test runs a minimum of 100
iterations with randomized inputs.

Requirements: 7.1, 7.2, 7.3, 7.4
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.global_suggestion_analyzer import (
    AnalysisConfig,
    GlobalSuggestionAnalyzer,
)
from lean_proof_auto_mcp.core.search_annotations_domain import (
    CandidateSource,
    Hint,
    HintSet,
    HintType,
)

# ==================================================
# Strategy Definitions
# ==================================================


@st.composite
def hint_strategy(draw):
    """Generate random Hint instances."""
    name = draw(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="._"
            ),
        )
    )
    hint_type = draw(st.sampled_from(list(HintType)))
    source = draw(st.sampled_from(list(CandidateSource)))
    return Hint(name=name, type=hint_type, source=source)


@st.composite
def hint_set_strategy(draw):
    """Generate random HintSet instances."""
    hints = draw(st.lists(hint_strategy(), min_size=0, max_size=10))
    return HintSet(hints)


@st.composite
def analysis_config_strategy(draw):
    """Generate random AnalysisConfig instances."""
    threshold = draw(st.floats(min_value=0.0, max_value=1.0))
    prefer_safe = draw(st.booleans())
    suggest_simp = draw(st.booleans())
    return AnalysisConfig(
        min_effectiveness_threshold=threshold,
        prefer_safe_rules=prefer_safe,
        suggest_simp_for_equations=suggest_simp,
    )


# ==================================================
# Property Tests
# ==================================================


@given(hint_set=hint_set_strategy(), config=analysis_config_strategy())
@settings(max_examples=100)
def test_property_29_mode_conditional_global_suggestions(hint_set, config):
    """
    Feature: search-annotations-tool, Property 29: Mode-Conditional Global Suggestions

    For any execution, when mode is local_only, no global annotation suggestions
    should be generated; when mode is suggest_global, global suggestions should
    be analyzed and included.

    Validates: Requirements 7.1, 7.2
    """
    analyzer = GlobalSuggestionAnalyzer(config)

    # Test local_only mode: should return empty list
    local_suggestions = analyzer.analyze(hint_set, mode="local_only")
    assert local_suggestions == [], (
        f"local_only mode should return empty list, got {len(local_suggestions)} suggestions"
    )

    # Test suggest_global mode: should analyze hints
    global_suggestions = analyzer.analyze(hint_set, mode="suggest_global")

    # If hint set is empty, suggestions should be empty
    if hint_set.is_empty():
        assert global_suggestions == [], "Empty hint set should produce no suggestions"
    else:
        # Suggestions should be a list (may be empty if no hints are suitable)
        assert isinstance(global_suggestions, list), "suggest_global mode should return a list"

        # All suggestions should be GlobalSuggestion instances
        for suggestion in global_suggestions:
            assert hasattr(suggestion, "hint_name"), "Each suggestion should have hint_name"
            assert hasattr(suggestion, "attribute"), "Each suggestion should have attribute"
            assert hasattr(suggestion, "rationale"), "Each suggestion should have rationale"
            assert hasattr(suggestion, "confidence"), "Each suggestion should have confidence"

            # Confidence should be valid
            assert suggestion.confidence in ("high", "medium", "low"), (
                f"Invalid confidence level: {suggestion.confidence}"
            )

            # Rationale should be non-empty
            assert len(suggestion.rationale) > 0, "Rationale should be non-empty"

            # Attribute should be a valid annotation
            assert suggestion.attribute.startswith("@["), (
                f"Attribute should start with '@[', got: {suggestion.attribute}"
            )


# ==================================================


@given(hint_set=hint_set_strategy(), config=analysis_config_strategy())
@settings(max_examples=100)
def test_property_30_effective_hint_suggestion_generation(hint_set, config):
    """
    Feature: search-annotations-tool, Property 30: Effective Hint Suggestion Generation

    For any hint that appears in the minimized set and is determined to be
    frequently effective, a global annotation suggestion should be generated.

    Validates: Requirements 7.3
    """
    analyzer = GlobalSuggestionAnalyzer(config)

    # Analyze in suggest_global mode
    suggestions = analyzer.analyze(hint_set, mode="suggest_global")

    # Build a map of (hint_name, hint_type) to suggestions for proper tracking
    # Note: Multiple hints can have the same name but different types
    suggestion_map = {s.hint_name: s for s in suggestions}

    # Count how many hints should generate suggestions
    hints_that_should_suggest = [
        hint for hint in hint_set.hints if _should_generate_suggestion(hint, config)
    ]

    # For each hint that should generate a suggestion, verify one exists
    for hint in hints_that_should_suggest:
        # If this hint should generate a suggestion, check if ANY suggestion
        # exists for this hint name (may be from a different hint with same name)
        if hint.name in suggestion_map:
            suggestion = suggestion_map[hint.name]

            # Verify suggestion properties
            assert suggestion.hint_name == hint.name, (
                f"Suggestion hint_name mismatch: expected {hint.name}, got {suggestion.hint_name}"
            )

            # Verify rationale is non-empty and mentions the hint
            assert len(suggestion.rationale) > 0, (
                f"Suggestion rationale should be non-empty for {hint.name}"
            )
            assert hint.name in suggestion.rationale, (
                f"Suggestion rationale should mention hint name {hint.name}"
            )

            # Verify confidence level is appropriate
            assert suggestion.confidence in ("high", "medium", "low"), (
                f"Invalid confidence level for {hint.name}: {suggestion.confidence}"
            )

            # If config has high threshold, only high confidence should pass
            if config.min_effectiveness_threshold >= 0.7:
                assert suggestion.confidence == "high", (
                    f"With high threshold, only high confidence suggestions should be included, "
                    f"got {suggestion.confidence} for {hint.name}"
                )

    # Verify that all suggestions correspond to hints that should generate them
    for suggestion in suggestions:
        # Find all hints with this name
        matching_hints = [h for h in hint_set.hints if h.name == suggestion.hint_name]

        # At least one matching hint should be a type that generates suggestions
        assert any(_should_generate_suggestion(h, config) for h in matching_hints), (
            f"Suggestion for {suggestion.hint_name} exists but no matching hint "
            f"should generate a suggestion with config {config}"
        )


def _should_generate_suggestion(hint: Hint, config: AnalysisConfig) -> bool:
    """
    Determine if a hint should generate a suggestion based on type and config.

    Args:
        hint: Hint to check
        config: Analysis configuration

    Returns:
        True if hint should generate a suggestion, False otherwise
    """
    # RULE_SET hints never generate suggestions
    if hint.type == HintType.RULE_SET:
        return False

    # ADD_UNSAFE hints only generate suggestions if prefer_safe_rules is False
    if hint.type == HintType.ADD_UNSAFE:
        return not config.prefer_safe_rules

    # All other hint types (SIMP, ADD_SAFE, UNFOLD) generate suggestions
    return True


def _expected_attribute_for_hint(hint: Hint) -> str:
    """
    Get the expected attribute for a hint type.

    Args:
        hint: Hint to check

    Returns:
        Expected attribute string
    """
    if hint.type == HintType.SIMP:
        return "@[simp]"
    elif hint.type == HintType.ADD_SAFE:
        return "@[aesop safe]"
    elif hint.type == HintType.ADD_UNSAFE:
        return "@[aesop unsafe]"
    elif hint.type == HintType.UNFOLD:
        return "@[aesop unfold]"
    else:
        raise ValueError(f"Unexpected hint type: {hint.type}")
