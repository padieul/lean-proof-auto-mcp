"""
Property-based tests for probe_file tool domain structures.

These tests verify universal properties that should hold across all valid executions
of the probe_file tool. Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 5.1, 5.5, 5.6
"""

from unittest.mock import Mock

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.probe_domain import (
    ProbeFileCommand,
    ProbeFileCommandHandler,
    ProbeOutcome,
    ProbeResult,
)

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


# ============================================================================
# Handler-Level Property Tests (Properties 15-21)
# ============================================================================


# ============================================================================
# Property 15: Scan_File Integration
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_theorems=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_property_15_scan_file_integration(file_path, mode, num_theorems):
    """
    Feature: probe-and-probe-file-tools
    Property 15: Scan_File Integration

    For any probe_file invocation, the system should call scan_file to enumerate
    theorems and use its output in stable order.

    Validates: Requirements 4.1
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(num_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results
    probe_handler.handle = Mock(
        return_value=ProbeResult(
            api_version="1.1.0",
            status="success",
            run_id="probe-test",
            probe_result=ProbeOutcome(
                mode=mode,
                outcome="closed",
                classification="trivial",
                suggested_script=None,
            ),
            diagnostics=[],
            timing={"elapsed_ms": 100.0, "budget_s": 5.0},
            metadata={},
        )
    )

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=5.0,
        limit=50,
        ordering="file_order",
    )

    # Execute
    result = handler.handle(cmd)

    # Verify: scan_file was called
    assert scan_file_fn.call_count == 1
    assert scan_file_fn.call_args[0][0]["file"] == file_path

    # Verify: Results are in same order as scan_file output
    for i, theorem_result in enumerate(result.results):
        assert theorem_result["theorem_id"] == f"theorem_{i}"


# ============================================================================
# Property 16: Batch Probe Invocation
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_theorems=st.integers(min_value=1, max_value=10),
    budget_s_per=st.floats(min_value=0.1, max_value=10.0),
)
@settings(max_examples=100)
def test_property_16_batch_probe_invocation(file_path, mode, num_theorems, budget_s_per):
    """
    Feature: probe-and-probe-file-tools
    Property 16: Batch Probe Invocation

    For any probe_file invocation with N theorems enumerated, the system should
    call probe exactly N times, once for each theorem with the specified mode
    and budget_s_per.

    Validates: Requirements 4.2
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(num_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results
    probe_handler.handle = Mock(
        return_value=ProbeResult(
            api_version="1.1.0",
            status="success",
            run_id="probe-test",
            probe_result=ProbeOutcome(
                mode=mode,
                outcome="closed",
                classification="trivial",
                suggested_script=None,
            ),
            diagnostics=[],
            timing={"elapsed_ms": 100.0, "budget_s": budget_s_per},
            metadata={},
        )
    )

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=50,
        ordering="file_order",
    )

    # Execute
    handler.handle(cmd)

    # Verify: probe was called exactly N times
    assert probe_handler.handle.call_count == num_theorems

    # Verify: Each call had correct mode and budget
    for call in probe_handler.handle.call_args_list:
        probe_cmd = call[0][0]
        assert probe_cmd.mode == mode
        assert probe_cmd.budget_s == budget_s_per


# ============================================================================
# Property 17: Per-Theorem Budget Isolation
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_theorems=st.integers(min_value=2, max_value=5),
    budget_s_per=st.floats(min_value=1.0, max_value=10.0),
)
@settings(max_examples=100)
def test_property_17_per_theorem_budget_isolation(file_path, mode, num_theorems, budget_s_per):
    """
    Feature: probe-and-probe-file-tools
    Property 17: Per-Theorem Budget Isolation

    For any probe_file invocation with multiple theorems, each theorem should
    receive its own independent budget allocation, and one theorem timing out
    should not affect the budget of subsequent theorems.

    Validates: Requirements 4.3
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(num_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results - first one times out, rest succeed
    def mock_probe_handle(cmd):
        if cmd.theorem_id == "theorem_0":
            return ProbeResult(
                api_version="1.1.0",
                status="timeout",
                run_id="probe-timeout",
                probe_result=ProbeOutcome(
                    mode=mode,
                    outcome="timeout",
                    classification="timed_out",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": budget_s_per * 1000.0, "budget_s": budget_s_per},
                metadata={},
            )
        else:
            return ProbeResult(
                api_version="1.1.0",
                status="success",
                run_id="probe-success",
                probe_result=ProbeOutcome(
                    mode=mode,
                    outcome="closed",
                    classification="trivial",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 100.0, "budget_s": budget_s_per},
                metadata={},
            )

    probe_handler.handle = Mock(side_effect=mock_probe_handle)

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=50,
        ordering="file_order",
    )

    # Execute
    handler.handle(cmd)

    # Verify: All theorems were probed despite first one timing out
    assert probe_handler.handle.call_count == num_theorems

    # Verify: Each theorem got its own budget
    for call in probe_handler.handle.call_args_list:
        probe_cmd = call[0][0]
        assert probe_cmd.budget_s == budget_s_per


# ============================================================================
# Property 18: Summary Aggregation Correctness
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_closed=st.integers(min_value=0, max_value=5),
    num_promising=st.integers(min_value=0, max_value=5),
    num_failed=st.integers(min_value=0, max_value=5),
    num_timed_out=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_property_18_summary_aggregation_correctness(
    file_path, mode, num_closed, num_promising, num_failed, num_timed_out
):
    """
    Feature: probe-and-probe-file-tools
    Property 18: Summary Aggregation Correctness

    For any probe_file invocation, the summary counts (total, closed, promising,
    failed, timed_out) should exactly match the sum of individual theorem results
    with those classifications.

    Validates: Requirements 4.4
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Calculate total theorems
    total_theorems = num_closed + num_promising + num_failed + num_timed_out

    # Skip if no theorems
    if total_theorems == 0:
        return

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(total_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results with specific classifications
    probe_results = []
    for i in range(num_closed):
        probe_results.append(
            ProbeResult(
                api_version="1.1.0",
                status="success",
                run_id=f"probe-{i}",
                probe_result=ProbeOutcome(
                    mode=mode,
                    outcome="closed",
                    classification="trivial",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 100.0, "budget_s": 5.0},
                metadata={},
            )
        )
    for i in range(num_promising):
        probe_results.append(
            ProbeResult(
                api_version="1.1.0",
                status="fail",
                run_id=f"probe-{i}",
                probe_result=ProbeOutcome(
                    mode=mode,
                    outcome="not_closed",
                    classification="promising",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 200.0, "budget_s": 5.0},
                metadata={},
            )
        )
    for i in range(num_failed):
        probe_results.append(
            ProbeResult(
                api_version="1.1.0",
                status="fail",
                run_id=f"probe-{i}",
                probe_result=ProbeOutcome(
                    mode=mode,
                    outcome="not_closed",
                    classification="failed",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 300.0, "budget_s": 5.0},
                metadata={},
            )
        )
    for i in range(num_timed_out):
        probe_results.append(
            ProbeResult(
                api_version="1.1.0",
                status="timeout",
                run_id=f"probe-{i}",
                probe_result=ProbeOutcome(
                    mode=mode,
                    outcome="timeout",
                    classification="timed_out",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 5000.0, "budget_s": 5.0},
                metadata={},
            )
        )

    probe_handler.handle = Mock(side_effect=probe_results)

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=5.0,
        limit=50,
        ordering="file_order",
    )

    # Execute
    result = handler.handle(cmd)

    # Verify: Summary counts match individual results
    assert result.summary["total"] == total_theorems
    assert result.summary["closed"] == num_closed
    assert result.summary["promising"] == num_promising
    assert result.summary["failed"] == num_failed
    assert result.summary["timed_out"] == num_timed_out


# ============================================================================
# Property 19: Probe_File Result Completeness
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_theorems=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100)
def test_property_19_probe_file_result_completeness(file_path, mode, num_theorems):
    """
    Feature: probe-and-probe-file-tools
    Property 19: Probe_File Result Completeness

    For any probe_file invocation, the result should contain all required fields:
    api_version, status, file, summary (with total, closed, promising, failed,
    timed_out), results array (with theorem_id, outcome, classification, elapsed_ms
    for each), and metadata.

    Validates: Requirements 4.5, 5.2, 5.3, 5.4
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(num_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results
    probe_handler.handle = Mock(
        return_value=ProbeResult(
            api_version="1.1.0",
            status="success",
            run_id="probe-test",
            probe_result=ProbeOutcome(
                mode=mode,
                outcome="closed",
                classification="trivial",
                suggested_script=None,
            ),
            diagnostics=[],
            timing={"elapsed_ms": 100.0, "budget_s": 5.0},
            metadata={},
        )
    )

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=5.0,
        limit=50,
        ordering="file_order",
    )

    # Execute
    result = handler.handle(cmd)

    # Verify: All required fields are present
    assert hasattr(result, "api_version")
    assert hasattr(result, "status")
    assert hasattr(result, "file")
    assert hasattr(result, "summary")
    assert hasattr(result, "results")
    assert hasattr(result, "metadata")

    # Verify: Summary has all required fields
    assert "total" in result.summary
    assert "closed" in result.summary
    assert "promising" in result.summary
    assert "failed" in result.summary
    assert "timed_out" in result.summary

    # Verify: Each result has required fields
    for theorem_result in result.results:
        assert "theorem_id" in theorem_result
        assert "outcome" in theorem_result
        assert "classification" in theorem_result
        assert "elapsed_ms" in theorem_result


# ============================================================================
# Property 20: Partial Success Handling
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_theorems=st.integers(min_value=3, max_value=10),
    error_index=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=100)
def test_property_20_partial_success_handling(file_path, mode, num_theorems, error_index):
    """
    Feature: probe-and-probe-file-tools
    Property 20: Partial Success Handling

    For any probe_file invocation where some theorems fail with errors, the system
    should continue processing remaining theorems and return status="partial" with
    all successfully probed results.

    Validates: Requirements 4.6
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(num_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results - one raises exception
    def mock_probe_handle(cmd, lean_server=None):
        if cmd.theorem_id == f"theorem_{error_index}":
            raise RuntimeError(f"Probe failed for {cmd.theorem_id}")
        return ProbeResult(
            api_version="1.1.0",
            status="success",
            run_id="probe-test",
            probe_result=ProbeOutcome(
                mode=mode,
                outcome="closed",
                classification="trivial",
                suggested_script=None,
            ),
            diagnostics=[],
            timing={"elapsed_ms": 100.0, "budget_s": 5.0},
            metadata={},
        )

    probe_handler.handle = Mock(side_effect=mock_probe_handle)

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=5.0,
        limit=50,
        ordering="file_order",
    )

    # Execute
    result = handler.handle(cmd)

    # Verify: Status is partial
    assert result.status == "partial"

    # Verify: Successful results are present
    assert len(result.results) == num_theorems - 1

    # Verify: Error is recorded in metadata
    assert "errors" in result.metadata
    assert len(result.metadata["errors"]) == 1
    assert result.metadata["errors"][0]["theorem_id"] == f"theorem_{error_index}"


# ============================================================================
# Property 21: Deterministic Result Ordering
# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=50),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    num_theorems=st.integers(min_value=2, max_value=10),
)
@settings(max_examples=100)
def test_property_21_deterministic_result_ordering(file_path, mode, num_theorems):
    """
    Feature: probe-and-probe-file-tools
    Property 21: Deterministic Result Ordering

    For any probe_file invocation, running it twice with the same parameters
    should produce results in the same order.

    Validates: Requirements 4.7
    """
    # Setup mocks
    probe_handler = Mock()
    scan_file_fn = Mock()

    # Mock scan_file response
    theorems = [{"theorem_id": f"theorem_{i}"} for i in range(num_theorems)]
    scan_file_fn.return_value = {
        "status": "success",
        "theorems": theorems,
    }

    # Mock probe results
    probe_handler.handle = Mock(
        return_value=ProbeResult(
            api_version="1.1.0",
            status="success",
            run_id="probe-test",
            probe_result=ProbeOutcome(
                mode=mode,
                outcome="closed",
                classification="trivial",
                suggested_script=None,
            ),
            diagnostics=[],
            timing={"elapsed_ms": 100.0, "budget_s": 5.0},
            metadata={},
        )
    )

    # Create handler
    handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

    # Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=5.0,
        limit=50,
        ordering="file_order",
    )

    # Execute twice
    result1 = handler.handle(cmd)

    # Reset mock call counts
    probe_handler.handle.reset_mock()

    result2 = handler.handle(cmd)

    # Verify: Results are in same order
    assert len(result1.results) == len(result2.results)
    for i in range(len(result1.results)):
        assert result1.results[i]["theorem_id"] == result2.results[i]["theorem_id"]
