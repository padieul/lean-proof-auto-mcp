"""
Property-based tests for probe_file tool domain structures.

These tests verify universal properties that should hold across all valid executions
of the probe_file tool. Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 5.1, 5.5, 5.6
"""

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.probe_domain import ProbeFileCommand

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_probe_file_commands(draw):
    """Generate valid ProbeFileCommand instances."""
    file_path = draw(st.text(min_size=1, max_size=100))
    mode = draw(st.sampled_from(["aesop", "aesop?", "grind"]))
    budget_s_per = draw(st.floats(min_value=0.1, max_value=60.0))
    limit = draw(st.integers(min_value=1, max_value=100))
    ordering = draw(st.sampled_from(["file_order", "rank_targets"]))

    return ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=limit,
        ordering=ordering,
    )


# ============================================================================
# Property 22: Ordering Mode Support
# ============================================================================


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=100),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_22_ordering_mode_support_valid_modes(
    file_path, mode, budget_s_per, limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 22: Ordering Mode Support (Valid Modes)

    For any probe_file invocation with ordering in {"file_order", "rank_targets"},
    the system should accept the ordering mode without raising a validation error.

    Validates: Requirements 5.1, 5.5
    """
    # Execute: Create command with valid ordering
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=limit,
        ordering=ordering,
    )

    # Verify: Command created successfully
    assert cmd.ordering == ordering
    assert cmd.ordering in ("file_order", "rank_targets")


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=100),
    invalid_ordering=st.text().filter(lambda x: x not in ("file_order", "rank_targets")),
)
@settings(max_examples=100)
def test_property_22_ordering_mode_support_invalid_modes(
    file_path, mode, budget_s_per, limit, invalid_ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 22: Ordering Mode Support (Invalid Modes)

    For any probe_file invocation with ordering not in {"file_order", "rank_targets"},
    the system should reject the ordering mode with a validation error.

    Validates: Requirements 5.1, 5.5
    """
    # Execute & Verify: Creating command with invalid ordering raises ValueError
    with pytest.raises(ValueError, match="ordering must be"):
        ProbeFileCommand(
            file_path=file_path,
            mode=mode,
            budget_s_per=budget_s_per,
            limit=limit,
            ordering=invalid_ordering,
        )


# ============================================================================
# Property 23: Limit Enforcement
# ============================================================================


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=1000),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_23_limit_enforcement_positive_limits(
    file_path, mode, budget_s_per, limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 23: Limit Enforcement (Positive Limits)

    For any probe_file invocation with limit > 0, the system should accept
    the limit without raising a validation error.

    Validates: Requirements 5.6
    """
    # Execute: Create command with positive limit
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=limit,
        ordering=ordering,
    )

    # Verify: Command created successfully
    assert cmd.limit == limit
    assert cmd.limit > 0


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    invalid_limit=st.integers(max_value=0),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_23_limit_enforcement_non_positive_limits(
    file_path, mode, budget_s_per, invalid_limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 23: Limit Enforcement (Non-Positive Limits)

    For any probe_file invocation with limit <= 0, the system should reject
    the limit with a validation error.

    Validates: Requirements 5.6
    """
    # Execute & Verify: Creating command with non-positive limit raises ValueError
    with pytest.raises(ValueError, match="limit must be positive"):
        ProbeFileCommand(
            file_path=file_path,
            mode=mode,
            budget_s_per=budget_s_per,
            limit=invalid_limit,
            ordering=ordering,
        )


# ============================================================================
# Additional Validation Tests for Completeness
# ============================================================================


@given(cmd=valid_probe_file_commands())
@settings(max_examples=100)
def test_valid_probe_file_commands_are_accepted(cmd):
    """
    Feature: probe-and-probe-file-tools
    Property: Valid Input Acceptance

    For any valid ProbeFileCommand, the system should accept it without
    raising validation errors.

    Validates: Requirements 5.1, 5.5, 5.6
    """
    # Verify: Command was created successfully
    assert cmd.file_path
    assert cmd.mode in ("aesop", "aesop?", "grind")
    assert cmd.budget_s_per > 0
    assert cmd.limit > 0
    assert cmd.ordering in ("file_order", "rank_targets")


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100)
def test_default_ordering_is_file_order(file_path, mode, budget_s_per, limit):
    """
    Feature: probe-and-probe-file-tools
    Property: Default Ordering

    When no ordering is specified, the default should be "file_order".

    Validates: Requirements 5.1, 5.5
    """
    # Execute: Create command without specifying ordering
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=limit,
    )

    # Verify: Default ordering is file_order
    assert cmd.ordering == "file_order"


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    limit=st.integers(min_value=1, max_value=100),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_default_budget_s_per_is_5_0(file_path, mode, limit, ordering):
    """
    Feature: probe-and-probe-file-tools
    Property: Default Budget Per Theorem

    When no budget_s_per is specified, the default should be 5.0 seconds.

    Validates: Requirements 5.1
    """
    # Execute: Create command without specifying budget_s_per
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        limit=limit,
        ordering=ordering,
    )

    # Verify: Default budget_s_per is 5.0
    assert cmd.budget_s_per == 5.0


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_default_limit_is_50(file_path, mode, budget_s_per, ordering):
    """
    Feature: probe-and-probe-file-tools
    Property: Default Limit

    When no limit is specified, the default should be 50 theorems.

    Validates: Requirements 5.6
    """
    # Execute: Create command without specifying limit
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        ordering=ordering,
    )

    # Verify: Default limit is 50
    assert cmd.limit == 50
