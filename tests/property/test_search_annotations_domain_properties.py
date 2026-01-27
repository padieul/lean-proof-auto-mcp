"""
Property-based tests for search-annotations domain structures.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 5.2
"""

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.search_annotations_domain import (
    Candidate,
    CandidateSource,
    Hint,
    HintSet,
    HintType,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_hints(draw):
    """Generate valid Hint instances."""
    name = draw(st.text(min_size=1, max_size=100))
    hint_type = draw(st.sampled_from(list(HintType)))
    source = draw(st.sampled_from(list(CandidateSource)))
    
    return Hint(name=name, type=hint_type, source=source)


@st.composite
def valid_hint_sets(draw):
    """Generate valid HintSet instances."""
    hints = draw(st.lists(valid_hints(), min_size=0, max_size=20))
    return HintSet(hints)


# ============================================================================
# Property: HintSet Operations Preserve Immutability
# ============================================================================


@given(hint_set=valid_hint_sets(), hint=valid_hints())
@settings(max_examples=100)
def test_property_hintset_add_preserves_immutability(hint_set, hint):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet and Hint, the add operation should return a new HintSet
    without modifying the original HintSet.
    
    Validates: Requirements 5.2
    """
    # Record original state
    original_hints = hint_set.hints
    original_size = hint_set.size()
    
    # Execute: Add hint
    new_hint_set = hint_set.add(hint)
    
    # Verify: Original is unchanged
    assert hint_set.hints == original_hints
    assert hint_set.size() == original_size
    
    # Verify: New set contains the hint
    assert hint in new_hint_set.hints
    
    # Verify: New set is different object
    assert new_hint_set is not hint_set


@given(hint_set=valid_hint_sets())
@settings(max_examples=100)
def test_property_hintset_remove_preserves_immutability(hint_set):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet with at least one hint, the remove operation should
    return a new HintSet without modifying the original HintSet.
    
    Validates: Requirements 5.2
    """
    # Skip if empty
    if hint_set.is_empty():
        return
    
    # Pick a hint to remove
    hint_to_remove = next(iter(hint_set.hints))
    
    # Record original state
    original_hints = hint_set.hints
    original_size = hint_set.size()
    
    # Execute: Remove hint
    new_hint_set = hint_set.remove(hint_to_remove)
    
    # Verify: Original is unchanged
    assert hint_set.hints == original_hints
    assert hint_set.size() == original_size
    
    # Verify: New set does not contain the hint
    assert hint_to_remove not in new_hint_set.hints
    
    # Verify: New set is different object
    assert new_hint_set is not hint_set


@given(hint_set=valid_hint_sets(), hint1=valid_hints(), hint2=valid_hints())
@settings(max_examples=100)
def test_property_hintset_chained_operations_preserve_immutability(hint_set, hint1, hint2):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet and multiple operations, each operation should return
    a new HintSet without modifying any previous HintSet in the chain.
    
    Validates: Requirements 5.2
    """
    # Record original state
    original_hints = hint_set.hints
    original_size = hint_set.size()
    
    # Execute: Chain operations
    set1 = hint_set.add(hint1)
    set2 = set1.add(hint2)
    set3 = set2.remove(hint1)
    
    # Verify: Original is unchanged
    assert hint_set.hints == original_hints
    assert hint_set.size() == original_size
    
    # Verify: Intermediate sets are unchanged
    assert hint1 in set1.hints
    assert hint1 in set2.hints
    assert hint2 in set2.hints
    
    # Verify: Final set has correct state
    assert hint1 not in set3.hints
    # If hint1 == hint2, removing hint1 also removes hint2 (correct set behavior)
    if hint1 != hint2:
        assert hint2 in set3.hints
    else:
        assert hint2 not in set3.hints
    
    # Verify: All sets are different objects
    assert set1 is not hint_set
    assert set2 is not set1
    assert set3 is not set2


@given(hint_set=valid_hint_sets())
@settings(max_examples=100)
def test_property_hintset_size_is_consistent(hint_set):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet, the size() method should always return the correct
    number of hints in the set.
    
    Validates: Requirements 5.2
    """
    # Verify: Size matches actual count
    assert hint_set.size() == len(hint_set.hints)
    
    # Verify: is_empty is consistent with size
    assert hint_set.is_empty() == (hint_set.size() == 0)


@given(hint_set=valid_hint_sets(), hint=valid_hints())
@settings(max_examples=100)
def test_property_hintset_add_idempotent(hint_set, hint):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet and Hint, adding the same hint twice should result
    in the same set as adding it once (set semantics).
    
    Validates: Requirements 5.2
    """
    # Execute: Add hint twice
    set1 = hint_set.add(hint)
    set2 = set1.add(hint)
    
    # Verify: Both sets are equal
    assert set1.hints == set2.hints
    assert set1.size() == set2.size()


@given(hint_set=valid_hint_sets(), hint=valid_hints())
@settings(max_examples=100)
def test_property_hintset_add_remove_inverse(hint_set, hint):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet and Hint not in the set, adding then removing the hint
    should result in the original set.
    
    Validates: Requirements 5.2
    """
    # Skip if hint already in set
    if hint in hint_set.hints:
        return
    
    # Execute: Add then remove
    set_with_hint = hint_set.add(hint)
    set_after_remove = set_with_hint.remove(hint)
    
    # Verify: Back to original
    assert set_after_remove.hints == hint_set.hints
    assert set_after_remove.size() == hint_set.size()


@given(hints=st.lists(valid_hints(), min_size=0, max_size=20))
@settings(max_examples=100)
def test_property_hintset_to_sorted_list_deterministic(hints):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet, calling to_sorted_list() multiple times should
    return the same ordering (deterministic).
    
    Validates: Requirements 5.2, 13.2
    """
    # Create hint set
    hint_set = HintSet(hints)
    
    # Execute: Get sorted list multiple times
    sorted1 = hint_set.to_sorted_list()
    sorted2 = hint_set.to_sorted_list()
    
    # Verify: Same ordering
    assert sorted1 == sorted2
    
    # Verify: Contains all hints
    assert set(sorted1) == hint_set.hints


@given(hint_set=valid_hint_sets())
@settings(max_examples=100)
def test_property_hintset_frozen_hints_immutable(hint_set):
    """
    Feature: search-annotations-tool
    Property: HintSet operations preserve immutability
    
    For any HintSet, the hints attribute should be a frozenset,
    ensuring immutability at the type level.
    
    Validates: Requirements 5.2
    """
    # Verify: hints is a frozenset
    assert isinstance(hint_set.hints, frozenset)
    
    # Verify: Cannot modify hints directly
    with pytest.raises((AttributeError, TypeError)):
        hint_set.hints.add(Hint("test", HintType.SIMP, CandidateSource.GOAL_SYMBOLS))
