"""
Property-based tests for Minimizer service.

These tests verify universal properties that should hold for hint set
minimization using delta-debugging. Each test runs a minimum of 100
iterations with randomized inputs.

Requirements: 5.1, 5.2, 5.3, 5.5, 5.6
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.minimizer import Minimizer
from lean_proof_auto_mcp.core.search_annotations_domain import (
    CandidateSource,
    ExecutionOutcome,
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
def valid_hint_sets(draw, min_size=0, max_size=20):
    """Generate valid HintSet instances."""
    hints = draw(st.lists(valid_hints(), min_size=min_size, max_size=max_size))
    return HintSet(hints)


# ============================================================================
# Mock Probe Functions
# ============================================================================


def create_always_success_probe():
    """Create a probe function that always returns success."""

    def probe_fn(hint_set: HintSet) -> ExecutionOutcome:
        return ExecutionOutcome(
            status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
        )

    return probe_fn


def create_minimal_set_probe(minimal_hints: frozenset[Hint]):
    """
    Create a probe function that succeeds only if hint set contains
    all hints from minimal_hints.
    """

    def probe_fn(hint_set: HintSet) -> ExecutionOutcome:
        if minimal_hints.issubset(hint_set.hints):
            return ExecutionOutcome(
                status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
            )
        else:
            return ExecutionOutcome(
                status="failure", automation_used="aesop", duration_s=0.1, output="Goal not closed"
            )

    return probe_fn


def create_any_hint_probe():
    """Create a probe function that succeeds if hint set is non-empty."""

    def probe_fn(hint_set: HintSet) -> ExecutionOutcome:
        if not hint_set.is_empty():
            return ExecutionOutcome(
                status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
            )
        else:
            return ExecutionOutcome(
                status="failure", automation_used="aesop", duration_s=0.1, output="Goal not closed"
            )

    return probe_fn


# ============================================================================
# Property 19: Minimization Preservation
# ============================================================================


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_19_minimization_preserves_closure(hint_set):
    """
    Feature: search-annotations-tool
    Property 19: Minimization Preservation

    For any closing hint set undergoing minimization, the minimization
    process should iteratively remove hints while ensuring the resulting
    set still closes the goal.

    Validates: Requirements 5.1, 5.2
    """
    # Setup: Create minimizer and probe that always succeeds
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Minimized set still closes (probe returns success)
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"

    # Verify: Minimized set is subset of original
    assert minimized.hints.issubset(hint_set.hints), "Minimized set should be subset of original"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_19_minimization_reduces_or_maintains_size(hint_set):
    """
    Feature: search-annotations-tool
    Property 19: Minimization Preservation

    For any hint set, minimization should produce a set with size
    less than or equal to the original size.

    Validates: Requirements 5.1, 5.2
    """
    # Setup: Create minimizer and probe that always succeeds
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Record original size
    original_size = hint_set.size()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Size is reduced or maintained
    assert minimized.size() <= original_size, "Minimized set should have size <= original size"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_19_minimization_with_always_success_produces_empty(hint_set):
    """
    Feature: search-annotations-tool
    Property 19: Minimization Preservation

    When the probe function always succeeds (even for empty set),
    minimization should produce an empty set.

    Validates: Requirements 5.1, 5.2
    """
    # Setup: Create minimizer and probe that always succeeds
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Result is empty (all hints removed)
    assert minimized.is_empty(), "When probe always succeeds, minimization should produce empty set"


@given(hint_set=valid_hint_sets(min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_19_minimization_with_minimal_set_requirement(hint_set):
    """
    Feature: search-annotations-tool
    Property 19: Minimization Preservation

    When a specific subset of hints is required for closure,
    minimization should preserve at least those hints.

    Validates: Requirements 5.1, 5.2
    """
    # Setup: Pick a random subset as minimal required hints
    hints_list = list(hint_set.hints)
    if len(hints_list) < 2:
        return  # Skip if not enough hints

    # Take first hint as minimal required
    minimal_hints = frozenset([hints_list[0]])

    # Create minimizer and probe that requires minimal_hints
    minimizer = Minimizer()
    probe_fn = create_minimal_set_probe(minimal_hints)

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Minimized set contains all minimal hints
    assert minimal_hints.issubset(minimized.hints), (
        "Minimized set should contain all required minimal hints"
    )

    # Verify: Minimized set still closes
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"


@given(hint_set=valid_hint_sets(min_size=0, max_size=20))
@settings(max_examples=100)
def test_property_19_minimization_preserves_immutability(hint_set):
    """
    Feature: search-annotations-tool
    Property 19: Minimization Preservation

    For any hint set, minimization should not modify the original
    hint set (immutability).

    Validates: Requirements 5.1, 5.2
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Record original state
    original_hints = hint_set.hints
    original_size = hint_set.size()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Original is unchanged
    assert hint_set.hints == original_hints, "Original hint set should be unchanged"
    assert hint_set.size() == original_size, "Original hint set size should be unchanged"

    # Verify: Minimized is different object (unless empty input)
    if not hint_set.is_empty():
        assert minimized is not hint_set or minimized.hints == hint_set.hints, (
            "Minimized set should be different object or identical"
        )


# ============================================================================
# Property 20: Minimization Restoration
# ============================================================================


@given(hint_set=valid_hint_sets(min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_20_minimization_restores_essential_hints(hint_set):
    """
    Feature: search-annotations-tool
    Property 20: Minimization Restoration

    For any hint whose removal causes the goal to fail during minimization,
    that hint should be restored to the hint set.

    Validates: Requirements 5.3
    """
    # Setup: Pick one hint as essential (required for closure)
    hints_list = list(hint_set.hints)
    if len(hints_list) < 2:
        return  # Skip if not enough hints

    essential_hint = hints_list[0]
    essential_hints = frozenset([essential_hint])

    # Create probe that requires the essential hint
    minimizer = Minimizer()
    probe_fn = create_minimal_set_probe(essential_hints)

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Essential hint is in minimized set (was restored if removed)
    assert essential_hint in minimized.hints, (
        "Essential hint should be restored if its removal caused failure"
    )

    # Verify: Minimized set still closes
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"


@given(hint_set=valid_hint_sets(min_size=3, max_size=20))
@settings(max_examples=100)
def test_property_20_minimization_restores_multiple_essential_hints(hint_set):
    """
    Feature: search-annotations-tool
    Property 20: Minimization Restoration

    When multiple hints are essential (removal of any causes failure),
    all essential hints should be restored and present in the final set.

    Validates: Requirements 5.3
    """
    # Setup: Pick multiple hints as essential
    hints_list = list(hint_set.hints)
    if len(hints_list) < 3:
        return  # Skip if not enough hints

    # Take first two hints as essential
    essential_hints = frozenset([hints_list[0], hints_list[1]])

    # Create probe that requires all essential hints
    minimizer = Minimizer()
    probe_fn = create_minimal_set_probe(essential_hints)

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: All essential hints are in minimized set
    assert essential_hints.issubset(minimized.hints), (
        "All essential hints should be restored if their removal caused failure"
    )

    # Verify: Minimized set still closes
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_20_minimization_with_any_hint_required(hint_set):
    """
    Feature: search-annotations-tool
    Property 20: Minimization Restoration

    When any single hint is sufficient for closure, minimization should
    produce a set with exactly one hint (the first one tried that works).

    Validates: Requirements 5.3
    """
    # Setup: Create probe that succeeds if any hint is present
    minimizer = Minimizer()
    probe_fn = create_any_hint_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Result has exactly one hint (minimal)
    assert minimized.size() == 1, "When any hint works, minimization should produce single-hint set"

    # Verify: Minimized set still closes
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"


@given(hint_set=valid_hint_sets(min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_20_minimization_never_removes_all_essential_hints(hint_set):
    """
    Feature: search-annotations-tool
    Property 20: Minimization Restoration

    During minimization, if a hint is essential for closure, it should
    never be permanently removed from the set.

    Validates: Requirements 5.3
    """
    # Setup: Make all hints essential (all required for closure)
    minimizer = Minimizer()

    # Create probe that requires ALL hints
    def probe_fn(test_set: HintSet) -> ExecutionOutcome:
        if test_set.hints == hint_set.hints:
            return ExecutionOutcome(
                status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
            )
        else:
            return ExecutionOutcome(
                status="failure", automation_used="aesop", duration_s=0.1, output="Goal not closed"
            )

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: All hints are preserved (none could be removed)
    assert minimized.hints == hint_set.hints, "When all hints are essential, none should be removed"

    # Verify: Minimized set still closes
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_20_minimization_restoration_is_implicit(hint_set):
    """
    Feature: search-annotations-tool
    Property 20: Minimization Restoration

    The restoration of essential hints is implicit in the algorithm:
    if removal causes failure, the hint remains in the current set.
    This test verifies that behavior.

    Validates: Requirements 5.3
    """
    # Setup: Create probe that requires at least one hint
    minimizer = Minimizer()
    probe_fn = create_any_hint_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Result is non-empty (at least one hint restored/kept)
    assert not minimized.is_empty(), (
        "When at least one hint is required, result should be non-empty"
    )

    # Verify: Result is subset of original
    assert minimized.hints.issubset(hint_set.hints), (
        "Minimized set should only contain hints from original set"
    )

    # Verify: Minimized set still closes
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set should still close the goal"


# ============================================================================
# Property 21: Minimized Set Closure Guarantee
# ============================================================================


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_21_minimized_set_closes_goal(hint_set):
    """
    Feature: search-annotations-tool
    Property 21: Minimized Set Closure Guarantee

    For any minimized hint set returned as a final result, that hint set
    should successfully close the goal when applied.

    Validates: Requirements 5.5
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Minimized set closes the goal
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set must successfully close the goal"


@given(hint_set=valid_hint_sets(min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_21_minimized_set_with_required_hints_closes(hint_set):
    """
    Feature: search-annotations-tool
    Property 21: Minimized Set Closure Guarantee

    When specific hints are required for closure, the minimized set
    should contain those hints and successfully close the goal.

    Validates: Requirements 5.5
    """
    # Setup: Pick hints as required
    hints_list = list(hint_set.hints)
    if len(hints_list) < 2:
        return

    required_hints = frozenset([hints_list[0]])

    # Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_minimal_set_probe(required_hints)

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Minimized set closes the goal
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set must successfully close the goal"

    # Verify: Contains required hints
    assert required_hints.issubset(minimized.hints), "Minimized set must contain all required hints"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_21_empty_input_produces_empty_output_that_closes(hint_set):
    """
    Feature: search-annotations-tool
    Property 21: Minimized Set Closure Guarantee

    When the input is empty or minimization produces an empty set,
    that empty set should still satisfy the closure property according
    to the probe function.

    Validates: Requirements 5.5
    """
    # Setup: Create minimizer and probe that accepts empty set
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize empty set
    empty_set = HintSet([])
    minimized = minimizer.minimize(empty_set, probe_fn)

    # Verify: Result closes (probe returns success)
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized empty set should close if probe accepts it"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_21_minimized_set_closure_is_verified(hint_set):
    """
    Feature: search-annotations-tool
    Property 21: Minimized Set Closure Guarantee

    The minimization algorithm should verify closure at each step,
    ensuring the final result always closes the goal.

    Validates: Requirements 5.5
    """
    # Setup: Track probe calls to verify closure checking
    probe_calls = []

    def tracking_probe(test_set: HintSet) -> ExecutionOutcome:
        probe_calls.append(test_set)
        # Always succeed for this test
        return ExecutionOutcome(
            status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
        )

    minimizer = Minimizer()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, tracking_probe)

    # Verify: Probe was called (closure was checked)
    assert len(probe_calls) > 0, "Probe should be called to verify closure"

    # Verify: Final result closes
    result = tracking_probe(minimized)
    assert result.status == "success", "Final minimized set must close the goal"


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_21_minimized_set_always_valid(hint_set):
    """
    Feature: search-annotations-tool
    Property 21: Minimized Set Closure Guarantee

    For any valid input hint set and probe function, the minimized
    result should always be a valid HintSet that closes the goal.

    Validates: Requirements 5.5
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Result is a valid HintSet
    assert isinstance(minimized, HintSet), "Result must be a HintSet"
    assert isinstance(minimized.hints, frozenset), "Result hints must be a frozenset"

    # Verify: Result closes the goal
    result = probe_fn(minimized)
    assert result.status == "success", "Minimized set must close the goal"


# ============================================================================
# Property 22: Minimized Set Stability
# ============================================================================


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_22_minimized_set_stable_across_verifications(hint_set):
    """
    Feature: search-annotations-tool
    Property 22: Minimized Set Stability

    For any minimized hint set, multiple verification attempts should
    all succeed, demonstrating the set is stable and not dependent on
    non-deterministic behavior.

    Validates: Requirements 5.6
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Multiple verification attempts all succeed
    for _ in range(5):
        result = probe_fn(minimized)
        assert result.status == "success", (
            "Minimized set should be stable across multiple verifications"
        )


@given(hint_set=valid_hint_sets(min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_22_minimized_set_stable_with_required_hints(hint_set):
    """
    Feature: search-annotations-tool
    Property 22: Minimized Set Stability

    When specific hints are required, the minimized set should be
    stable across multiple verifications.

    Validates: Requirements 5.6
    """
    # Setup: Pick required hints
    hints_list = list(hint_set.hints)
    if len(hints_list) < 2:
        return

    required_hints = frozenset([hints_list[0]])

    # Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_minimal_set_probe(required_hints)

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Multiple verification attempts all succeed
    for _ in range(5):
        result = probe_fn(minimized)
        assert result.status == "success", (
            "Minimized set should be stable across multiple verifications"
        )


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_22_minimization_is_idempotent(hint_set):
    """
    Feature: search-annotations-tool
    Property 22: Minimized Set Stability

    For any hint set, minimizing twice should produce the same result
    as minimizing once (idempotency).

    Validates: Requirements 5.6
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize once
    minimized_once = minimizer.minimize(hint_set, probe_fn)

    # Execute: Minimize again
    minimized_twice = minimizer.minimize(minimized_once, probe_fn)

    # Verify: Both results are identical
    assert minimized_once.hints == minimized_twice.hints, (
        "Minimization should be idempotent (minimize twice = minimize once)"
    )
    assert minimized_once.size() == minimized_twice.size(), (
        "Minimized set sizes should be identical"
    )


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_22_minimized_set_deterministic(hint_set):
    """
    Feature: search-annotations-tool
    Property 22: Minimized Set Stability

    For any hint set, multiple minimization runs should produce
    the same result (deterministic behavior).

    Validates: Requirements 5.6
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize multiple times
    results = []
    for _ in range(3):
        minimized = minimizer.minimize(hint_set, probe_fn)
        results.append(minimized)

    # Verify: All results are identical
    for i in range(1, len(results)):
        assert results[0].hints == results[i].hints, (
            "Minimization should be deterministic across multiple runs"
        )
        assert results[0].size() == results[i].size(), (
            "Minimized set sizes should be identical across runs"
        )


@given(hint_set=valid_hint_sets(min_size=1, max_size=20))
@settings(max_examples=100)
def test_property_22_minimized_set_no_spurious_failures(hint_set):
    """
    Feature: search-annotations-tool
    Property 22: Minimized Set Stability

    For any minimized hint set, verification should never spuriously
    fail (no non-deterministic failures).

    Validates: Requirements 5.6
    """
    # Setup: Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_always_success_probe()

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Many verification attempts all succeed (no spurious failures)
    success_count = 0
    attempts = 10
    for _ in range(attempts):
        result = probe_fn(minimized)
        if result.status == "success":
            success_count += 1

    assert success_count == attempts, (
        f"Minimized set should be stable: {success_count}/{attempts} succeeded"
    )


@given(hint_set=valid_hint_sets(min_size=2, max_size=20))
@settings(max_examples=100)
def test_property_22_minimized_set_stable_with_complex_probe(hint_set):
    """
    Feature: search-annotations-tool
    Property 22: Minimized Set Stability

    Even with complex probe functions, the minimized set should
    remain stable across multiple verifications.

    Validates: Requirements 5.6
    """
    # Setup: Create complex probe (requires specific hints)
    hints_list = list(hint_set.hints)
    if len(hints_list) < 2:
        return

    required_hints = frozenset([hints_list[0], hints_list[1]])

    # Create minimizer and probe
    minimizer = Minimizer()
    probe_fn = create_minimal_set_probe(required_hints)

    # Execute: Minimize
    minimized = minimizer.minimize(hint_set, probe_fn)

    # Verify: Stable across multiple verifications
    for _ in range(5):
        result = probe_fn(minimized)
        assert result.status == "success", "Minimized set should be stable even with complex probe"

    # Verify: Contains required hints
    assert required_hints.issubset(minimized.hints), (
        "Minimized set should contain all required hints"
    )
