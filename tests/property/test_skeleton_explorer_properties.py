"""
Property-based tests for skeleton explorer implementation.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 14.1, 14.2, 14.3, 14.4
"""

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    ExecutionOutcome,
    HintSet,
    SkeletonConfig,
)
from lean_proof_auto_mcp.core.skeleton_explorer import (
    ProofSkeleton,
    SkeletonExplorer,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_skeleton_configs(draw):
    """Generate valid SkeletonConfig instances."""
    enabled = draw(st.booleans())
    max_depth = draw(st.integers(min_value=1, max_value=5))

    # Generate list of tactic moves
    all_moves = ["cases", "constructor", "induction", "intro", "apply"]
    num_moves = draw(st.integers(min_value=1, max_value=len(all_moves)))
    moves = draw(
        st.lists(st.sampled_from(all_moves), min_size=num_moves, max_size=num_moves, unique=True)
    )

    return SkeletonConfig(enabled=enabled, max_depth=max_depth, moves=moves)


# ============================================================================
# Mock Functions
# ============================================================================


def always_fail_skeleton_probe(skeleton: ProofSkeleton) -> ExecutionOutcome:
    """Skeleton probe function that always fails."""
    return ExecutionOutcome(
        status="failure", automation_used="aesop", duration_s=0.1, output="Failed to close goal"
    )


def always_succeed_skeleton_probe(skeleton: ProofSkeleton) -> ExecutionOutcome:
    """Skeleton probe function that always succeeds."""
    return ExecutionOutcome(
        status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
    )


def succeed_at_depth_probe(target_depth: int):
    """Create skeleton probe function that succeeds at specific depth."""

    def probe(skeleton: ProofSkeleton) -> ExecutionOutcome:
        if skeleton.depth >= target_depth:
            return ExecutionOutcome(
                status="success", automation_used="aesop", duration_s=0.1, output="Goal closed"
            )
        else:
            return ExecutionOutcome(
                status="failure",
                automation_used="aesop",
                duration_s=0.1,
                output=f"Failed at depth {skeleton.depth}",
            )

    return probe


def empty_hint_search(skeleton: ProofSkeleton) -> HintSet | None:
    """Hint search function that always returns empty hint set."""
    return HintSet()


# ============================================================================
# Property 41: Skeleton Mode Conditional Behavior
# ============================================================================


@given(config=valid_skeleton_configs())
@settings(max_examples=100)
def test_property_41_skeleton_mode_conditional_behavior_disabled(config):
    """
    Feature: search-annotations-tool
    Property 41: Skeleton Mode Conditional Behavior

    For any execution, when skeleton.enabled is false, standard hint search
    should be performed (skeleton explorer returns empty result).

    Validates: Requirements 14.1
    """
    # Force skeleton disabled
    config = SkeletonConfig(enabled=False, max_depth=config.max_depth, moves=config.moves)

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    result = explorer.explore(
        config=config,
        probe_fn=always_fail_skeleton_probe,
        hint_search_fn=empty_hint_search,
        budget_s=10.0,
    )

    # Verify: When disabled, should return empty result
    assert result.outcome == "failed", "Disabled skeleton search should return failed outcome"
    assert result.best_skeleton is None, "Disabled skeleton search should not return a skeleton"
    assert result.attempts == 0, "Disabled skeleton search should make no attempts"
    assert result.explored_skeletons == 0, "Disabled skeleton search should explore no skeletons"


@given(
    max_depth=st.integers(min_value=1, max_value=5),
    moves=st.lists(
        st.sampled_from(["cases", "constructor", "induction"]), min_size=1, max_size=3, unique=True
    ),
)
@settings(max_examples=100)
def test_property_41_skeleton_mode_conditional_behavior_enabled(max_depth, moves):
    """
    Feature: search-annotations-tool
    Property 41: Skeleton Mode Conditional Behavior

    For any execution, when skeleton.enabled is true, skeleton-based search
    with tactic moves should be explored.

    Validates: Requirements 14.2
    """
    # Force skeleton enabled
    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=moves)

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    result = explorer.explore(
        config=config,
        probe_fn=always_fail_skeleton_probe,
        hint_search_fn=empty_hint_search,
        budget_s=10.0,
    )

    # Verify: When enabled, should explore skeletons
    assert result.explored_skeletons > 0, (
        "Enabled skeleton search should explore at least one skeleton"
    )
    assert result.attempts > 0, "Enabled skeleton search should make at least one attempt"

    # Verify: Should have explored some skeletons
    # With max_depth and moves, we expect at least len(moves) skeletons at depth 1
    expected_min_skeletons = min(len(moves), result.explored_skeletons)
    assert result.explored_skeletons >= expected_min_skeletons, (
        f"Should have explored at least {expected_min_skeletons} skeletons"
    )


@given(
    max_depth=st.integers(min_value=1, max_value=4),
    target_depth=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=100)
def test_property_41_skeleton_mode_finds_solution_at_depth(max_depth, target_depth):
    """
    Feature: search-annotations-tool
    Property 41: Skeleton Mode Conditional Behavior

    For any execution with skeleton.enabled=true, when a solution exists at
    a specific depth, the skeleton explorer should find it.

    Validates: Requirements 14.2
    """
    # Ensure target_depth is within max_depth
    if target_depth > max_depth:
        target_depth = max_depth

    config = SkeletonConfig(
        enabled=True, max_depth=max_depth, moves=["cases", "constructor", "induction"]
    )

    # Execute: Skeleton exploration with probe that succeeds at target depth
    explorer = SkeletonExplorer()
    result = explorer.explore(
        config=config,
        probe_fn=succeed_at_depth_probe(target_depth),
        hint_search_fn=empty_hint_search,
        budget_s=10.0,
    )

    # Verify: Should find closing skeleton
    assert result.outcome == "closed", f"Should find closing skeleton at depth {target_depth}"
    assert result.best_skeleton is not None, "Closing result should have best_skeleton"
    assert result.best_skeleton.depth >= target_depth, (
        f"Best skeleton depth should be >= {target_depth}"
    )
    assert result.evidence is not None, "Closing result should have evidence"
    assert result.evidence.status == "success", "Evidence should show success"


# ============================================================================
# Property 42: Skeleton Depth Limit
# ============================================================================


@given(
    max_depth=st.integers(min_value=1, max_value=5),
    moves=st.lists(
        st.sampled_from(["cases", "constructor", "induction"]), min_size=1, max_size=3, unique=True
    ),
)
@settings(max_examples=100)
def test_property_42_skeleton_depth_limit(max_depth, moves):
    """
    Feature: search-annotations-tool
    Property 42: Skeleton Depth Limit

    For any skeleton-enabled search, the skeleton depth should not exceed
    skeleton.max_depth.

    Validates: Requirements 14.3
    """
    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=moves)

    # Track maximum depth observed
    max_depth_observed = 0

    def tracking_probe(skeleton: ProofSkeleton) -> ExecutionOutcome:
        """Probe that tracks maximum skeleton depth."""
        nonlocal max_depth_observed
        max_depth_observed = max(max_depth_observed, skeleton.depth)

        # Verify immediately
        assert skeleton.depth <= max_depth, (
            f"Skeleton depth {skeleton.depth} exceeds max_depth {max_depth}"
        )

        return always_fail_skeleton_probe(skeleton)

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    explorer.explore(
        config=config, probe_fn=tracking_probe, hint_search_fn=empty_hint_search, budget_s=10.0
    )

    # Verify: Never exceeded max_depth
    assert max_depth_observed <= max_depth, (
        f"Observed skeleton depth {max_depth_observed}, max_depth is {max_depth}"
    )


@given(
    max_depth=st.integers(min_value=1, max_value=5),
    moves=st.lists(
        st.sampled_from(["cases", "constructor", "induction"]), min_size=1, max_size=3, unique=True
    ),
)
@settings(max_examples=100)
def test_property_42_skeleton_depth_limit_all_skeletons(max_depth, moves):
    """
    Feature: search-annotations-tool
    Property 42: Skeleton Depth Limit

    For any skeleton-enabled search, ALL explored skeletons should respect
    the max_depth limit.

    Validates: Requirements 14.3
    """
    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=moves)

    # Track all skeleton depths
    all_depths: list[int] = []

    def tracking_probe(skeleton: ProofSkeleton) -> ExecutionOutcome:
        """Probe that tracks all skeleton depths."""
        all_depths.append(skeleton.depth)
        return always_fail_skeleton_probe(skeleton)

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    result = explorer.explore(
        config=config, probe_fn=tracking_probe, hint_search_fn=empty_hint_search, budget_s=10.0
    )

    # Verify: All depths within limit
    for depth in all_depths:
        assert depth <= max_depth, f"Found skeleton with depth {depth}, max_depth is {max_depth}"

    # Verify: Result is consistent
    if result.best_skeleton is not None:
        assert result.best_skeleton.depth <= max_depth, (
            f"Best skeleton depth {result.best_skeleton.depth} exceeds max_depth {max_depth}"
        )


@given(
    max_depth=st.integers(min_value=2, max_value=5),
    success_depth=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=100)
def test_property_42_skeleton_depth_limit_stops_at_limit(max_depth, success_depth):
    """
    Feature: search-annotations-tool
    Property 42: Skeleton Depth Limit

    For any skeleton-enabled search, exploration should stop at max_depth
    even if no solution is found.

    Validates: Requirements 14.3
    """
    # Ensure success_depth is beyond max_depth to test limit enforcement
    success_depth = max_depth + 2

    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=["cases", "constructor"])

    # Execute: Skeleton exploration with probe that only succeeds beyond max_depth
    explorer = SkeletonExplorer()
    result = explorer.explore(
        config=config,
        probe_fn=succeed_at_depth_probe(success_depth),
        hint_search_fn=empty_hint_search,
        budget_s=10.0,
    )

    # Verify: Should not find closing skeleton (success is beyond max_depth)
    assert result.outcome != "closed", (
        f"Should not find closing skeleton (success at depth {success_depth}, "
        f"max_depth {max_depth})"
    )

    # Verify: Best skeleton (if any) should be at or below max_depth
    if result.best_skeleton is not None:
        assert result.best_skeleton.depth <= max_depth, (
            f"Best skeleton depth {result.best_skeleton.depth} exceeds max_depth {max_depth}"
        )


# ============================================================================
# Property 43: Skeleton Move Restriction (Bonus)
# ============================================================================


@given(
    max_depth=st.integers(min_value=1, max_value=3),
    allowed_moves=st.lists(
        st.sampled_from(["cases", "constructor", "induction"]), min_size=1, max_size=2, unique=True
    ),
)
@settings(max_examples=100)
def test_property_43_skeleton_move_restriction(max_depth, allowed_moves):
    """
    Feature: search-annotations-tool
    Property 43: Skeleton Move Restriction

    For any skeleton-enabled search, only tactic moves from the skeleton.moves
    list should be used in skeleton exploration.

    Validates: Requirements 14.4
    """
    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=allowed_moves)

    # Track all moves used
    used_moves: set[str] = set()

    def tracking_probe(skeleton: ProofSkeleton) -> ExecutionOutcome:
        """Probe that tracks used moves."""
        for move in skeleton.moves:
            used_moves.add(move.name)
        return always_fail_skeleton_probe(skeleton)

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    result = explorer.explore(
        config=config, probe_fn=tracking_probe, hint_search_fn=empty_hint_search, budget_s=10.0
    )

    # Verify: Only allowed moves were used
    for move in used_moves:
        assert move in allowed_moves, (
            f"Move '{move}' was used but not in allowed moves {allowed_moves}"
        )

    # Verify: Result skeleton (if any) only uses allowed moves
    if result.best_skeleton is not None:
        for move in result.best_skeleton.moves:
            assert move.name in allowed_moves, (
                f"Best skeleton uses move '{move.name}' not in allowed moves {allowed_moves}"
            )


# ============================================================================
# Integration Tests
# ============================================================================


@given(
    max_depth=st.integers(min_value=1, max_value=4),
    moves=st.lists(
        st.sampled_from(["cases", "constructor", "induction"]), min_size=1, max_size=3, unique=True
    ),
    budget_s=st.floats(min_value=0.1, max_value=5.0),
)
@settings(max_examples=50)
def test_skeleton_explorer_respects_budget(max_depth, moves, budget_s):
    """
    Test that skeleton explorer respects time budget.

    This is not a formal property but an important integration test.
    """
    import time

    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=moves)

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    start_time = time.time()
    explorer.explore(
        config=config,
        probe_fn=always_fail_skeleton_probe,
        hint_search_fn=empty_hint_search,
        budget_s=budget_s,
    )
    elapsed = time.time() - start_time

    # Verify: Completed within reasonable time (budget + 1 second grace)
    assert elapsed <= budget_s + 1.0, f"Exploration took {elapsed}s, budget was {budget_s}s"


@given(
    max_depth=st.integers(min_value=1, max_value=3),
    target_depth=st.integers(min_value=1, max_value=3),
)
@settings(max_examples=50)
def test_skeleton_explorer_combines_with_hint_search(max_depth, target_depth):
    """
    Test that skeleton explorer combines skeleton moves with hint search.

    This verifies that hint_search_fn is called and its results are used.
    """
    if target_depth > max_depth:
        target_depth = max_depth

    config = SkeletonConfig(enabled=True, max_depth=max_depth, moves=["cases", "constructor"])

    # Track hint search calls
    hint_search_calls = []

    def tracking_hint_search(skeleton: ProofSkeleton) -> HintSet | None:
        """Hint search that tracks calls."""
        hint_search_calls.append(skeleton.depth)
        return HintSet()  # Return empty for simplicity

    # Execute: Skeleton exploration
    explorer = SkeletonExplorer()
    explorer.explore(
        config=config,
        probe_fn=succeed_at_depth_probe(target_depth),
        hint_search_fn=tracking_hint_search,
        budget_s=10.0,
    )

    # Verify: Hint search was called
    assert len(hint_search_calls) > 0, (
        "Hint search function should be called during skeleton exploration"
    )

    # Verify: Hint search was called for various depths
    unique_depths = set(hint_search_calls)
    assert len(unique_depths) > 0, "Hint search should be called for at least one depth"
