"""
Property-based tests for probe tool domain structures.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 1.8, 3.1, 10.3, 10.5
"""

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.probe_domain import (
    ProbeCommand,
    ProbeFileCommand,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_probe_commands(draw):
    """Generate valid ProbeCommand instances."""
    file_path = draw(st.text(min_size=1, max_size=100))
    theorem_id = draw(st.text(min_size=1, max_size=100))
    mode = draw(st.sampled_from(["aesop", "aesop?", "grind"]))
    budget_s = draw(st.floats(min_value=0.1, max_value=60.0))
    trace_config = draw(st.none() | st.dictionaries(st.text(), st.booleans()))

    return ProbeCommand(
        file_path=file_path,
        theorem_id=theorem_id,
        mode=mode,
        budget_s=budget_s,
        trace_config=trace_config,
    )


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
# Property 7: Mode Validation
# ============================================================================


@given(
    file_path=st.text(min_size=1),
    theorem_id=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@settings(max_examples=100)
def test_property_7_mode_validation_accepts_valid_modes(
    file_path, theorem_id, mode, budget_s
):
    """
    Feature: probe-and-probe-file-tools
    Property 7: Mode Validation (Valid Modes)

    For any input mode in {"aesop", "aesop?", "grind"}, probe should accept
    the mode without raising a validation error.

    Validates: Requirements 1.8, 3.1
    """
    # Execute: Create command with valid mode
    cmd = ProbeCommand(
        file_path=file_path,
        theorem_id=theorem_id,
        mode=mode,
        budget_s=budget_s,
    )

    # Verify: Command created successfully
    assert cmd.mode == mode
    assert cmd.file_path == file_path
    assert cmd.theorem_id == theorem_id
    assert cmd.budget_s == budget_s


@given(
    file_path=st.text(min_size=1),
    theorem_id=st.text(min_size=1),
    invalid_mode=st.text().filter(lambda x: x not in ("aesop", "aesop?", "grind")),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@settings(max_examples=100)
def test_property_7_mode_validation_rejects_invalid_modes(
    file_path, theorem_id, invalid_mode, budget_s
):
    """
    Feature: probe-and-probe-file-tools
    Property 7: Mode Validation (Invalid Modes)

    For any input mode not in {"aesop", "aesop?", "grind"}, probe should reject
    the mode with a validation error.

    Validates: Requirements 1.8, 3.1
    """
    # Execute & Verify: Creating command with invalid mode raises ValueError
    with pytest.raises(ValueError, match="mode must be"):
        ProbeCommand(
            file_path=file_path,
            theorem_id=theorem_id,
            mode=invalid_mode,
            budget_s=budget_s,
        )


# ============================================================================
# Property 28: Invalid Input Handling
# ============================================================================


@given(
    theorem_id=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@settings(max_examples=100)
def test_property_28_invalid_input_empty_file_path(theorem_id, mode, budget_s):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (Empty file_path)

    For any probe input with empty file_path, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Empty file_path raises ValueError
    with pytest.raises(ValueError, match="file_path must be non-empty"):
        ProbeCommand(
            file_path="",
            theorem_id=theorem_id,
            mode=mode,
            budget_s=budget_s,
        )


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@settings(max_examples=100)
def test_property_28_invalid_input_empty_theorem_id(file_path, mode, budget_s):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (Empty theorem_id)

    For any probe input with empty theorem_id, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Empty theorem_id raises ValueError
    with pytest.raises(ValueError, match="theorem_id must be non-empty"):
        ProbeCommand(
            file_path=file_path,
            theorem_id="",
            mode=mode,
            budget_s=budget_s,
        )


@given(
    file_path=st.text(min_size=1),
    theorem_id=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    invalid_budget=st.floats(max_value=0.0) | st.just(0.0),
)
@settings(max_examples=100)
def test_property_28_invalid_input_non_positive_budget(
    file_path, theorem_id, mode, invalid_budget
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (Non-positive budget)

    For any probe input with non-positive budget_s, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Non-positive budget raises ValueError
    with pytest.raises(ValueError, match="budget_s must be positive"):
        ProbeCommand(
            file_path=file_path,
            theorem_id=theorem_id,
            mode=mode,
            budget_s=invalid_budget,
        )


@given(
    file_path=st.text(min_size=1),
    theorem_id=st.text(min_size=1),
    invalid_mode=st.text().filter(lambda x: x not in ("aesop", "aesop?", "grind")),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@settings(max_examples=100)
def test_property_28_invalid_input_invalid_mode(
    file_path, theorem_id, invalid_mode, budget_s
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (Invalid mode)

    For any probe input with invalid mode, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Invalid mode raises ValueError
    with pytest.raises(ValueError, match="mode must be"):
        ProbeCommand(
            file_path=file_path,
            theorem_id=theorem_id,
            mode=invalid_mode,
            budget_s=budget_s,
        )


# ============================================================================
# ProbeFileCommand Validation Tests
# ============================================================================


@given(
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=100),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_28_probe_file_invalid_input_empty_file_path(
    mode, budget_s_per, limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (ProbeFileCommand empty file_path)

    For any probe_file input with empty file_path, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Empty file_path raises ValueError
    with pytest.raises(ValueError, match="file_path must be non-empty"):
        ProbeFileCommand(
            file_path="",
            mode=mode,
            budget_s_per=budget_s_per,
            limit=limit,
            ordering=ordering,
        )


@given(
    file_path=st.text(min_size=1),
    invalid_mode=st.text().filter(lambda x: x not in ("aesop", "aesop?", "grind")),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=100),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_28_probe_file_invalid_input_invalid_mode(
    file_path, invalid_mode, budget_s_per, limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (ProbeFileCommand invalid mode)

    For any probe_file input with invalid mode, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Invalid mode raises ValueError
    with pytest.raises(ValueError, match="mode must be"):
        ProbeFileCommand(
            file_path=file_path,
            mode=invalid_mode,
            budget_s_per=budget_s_per,
            limit=limit,
            ordering=ordering,
        )


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    invalid_budget=st.floats(max_value=0.0) | st.just(0.0),
    limit=st.integers(min_value=1, max_value=100),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_28_probe_file_invalid_input_non_positive_budget(
    file_path, mode, invalid_budget, limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (ProbeFileCommand non-positive budget)

    For any probe_file input with non-positive budget_s_per, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Non-positive budget raises ValueError
    with pytest.raises(ValueError, match="budget_s_per must be positive"):
        ProbeFileCommand(
            file_path=file_path,
            mode=mode,
            budget_s_per=invalid_budget,
            limit=limit,
            ordering=ordering,
        )


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    invalid_limit=st.integers(max_value=0),
    ordering=st.sampled_from(["file_order", "rank_targets"]),
)
@settings(max_examples=100)
def test_property_28_probe_file_invalid_input_non_positive_limit(
    file_path, mode, budget_s_per, invalid_limit, ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (ProbeFileCommand non-positive limit)

    For any probe_file input with non-positive limit, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Non-positive limit raises ValueError
    with pytest.raises(ValueError, match="limit must be positive"):
        ProbeFileCommand(
            file_path=file_path,
            mode=mode,
            budget_s_per=budget_s_per,
            limit=invalid_limit,
            ordering=ordering,
        )


@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=60.0),
    limit=st.integers(min_value=1, max_value=100),
    invalid_ordering=st.text().filter(lambda x: x not in ("file_order", "rank_targets")),
)
@settings(max_examples=100)
def test_property_28_probe_file_invalid_input_invalid_ordering(
    file_path, mode, budget_s_per, limit, invalid_ordering
):
    """
    Feature: probe-and-probe-file-tools
    Property 28: Invalid Input Handling (ProbeFileCommand invalid ordering)

    For any probe_file input with invalid ordering, the system should raise
    ValueError with validation details.

    Validates: Requirements 10.3, 10.5
    """
    # Execute & Verify: Invalid ordering raises ValueError
    with pytest.raises(ValueError, match="ordering must be"):
        ProbeFileCommand(
            file_path=file_path,
            mode=mode,
            budget_s_per=budget_s_per,
            limit=limit,
            ordering=invalid_ordering,
        )


# ============================================================================
# Valid Input Acceptance Tests
# ============================================================================


@given(cmd=valid_probe_commands())
@settings(max_examples=100)
def test_valid_probe_commands_are_accepted(cmd):
    """
    Feature: probe-and-probe-file-tools
    Property: Valid Input Acceptance

    For any valid ProbeCommand, the system should accept it without
    raising validation errors.

    Validates: Requirements 1.8, 3.1
    """
    # Verify: Command was created successfully
    assert cmd.file_path
    assert cmd.theorem_id
    assert cmd.mode in ("aesop", "aesop?", "grind")
    assert cmd.budget_s > 0


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
