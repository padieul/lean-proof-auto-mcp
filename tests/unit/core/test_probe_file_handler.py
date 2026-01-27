"""
Unit tests for ProbeFileCommandHandler.

This module tests the batch probe workflow including theorem enumeration,
ordering, limit enforcement, summary aggregation, and partial success handling.

Requirements: 4.1-4.7, 5.2-5.6, 10.4
"""

from unittest.mock import Mock

from lean_proof_auto_mcp.core.probe_domain import (
    ProbeFileCommand,
    ProbeFileCommandHandler,
    ProbeOutcome,
    ProbeResult,
)


class TestProbeFileCommandHandler:
    """Test suite for ProbeFileCommandHandler."""

    def test_successful_batch_probing(self):
        """
        Test successful batch probing with mocked dependencies.

        Requirements: 4.1-4.7, 5.2-5.6
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()
        rank_targets_fn = None

        # Mock scan_file response
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [
                {"theorem_id": "theorem1"},
                {"theorem_id": "theorem2"},
                {"theorem_id": "theorem3"},
            ],
        }

        # Mock probe results
        def mock_probe_handle(cmd):
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=f"probe-{cmd.theorem_id}",
                probe_result=ProbeOutcome(
                    mode=cmd.mode,
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
        handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, rank_targets_fn)

        # Create command
        cmd = ProbeFileCommand(
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify
        assert result.status == "success"
        assert result.file == "test.lean"
        assert result.summary["total"] == 3
        assert result.summary["closed"] == 3
        assert len(result.results) == 3
        assert scan_file_fn.call_count == 1
        assert probe_handler.handle.call_count == 3

    def test_theorem_enumeration_file_order(self):
        """
        Test theorem enumeration with file_order.

        Requirements: 4.1, 5.5
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file response with specific order
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [
                {"theorem_id": "theorem_c"},
                {"theorem_id": "theorem_a"},
                {"theorem_id": "theorem_b"},
            ],
        }

        # Mock probe results
        probe_handler.handle = Mock(
            return_value=ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id="probe-test",
                probe_result=ProbeOutcome(
                    mode="aesop",
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

        # Create command with file_order
        cmd = ProbeFileCommand(
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify order matches scan_file order
        assert result.results[0]["theorem_id"] == "theorem_c"
        assert result.results[1]["theorem_id"] == "theorem_a"
        assert result.results[2]["theorem_id"] == "theorem_b"

    def test_theorem_enumeration_rank_targets(self):
        """
        Test theorem enumeration with rank_targets.

        Requirements: 4.1, 5.5
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()
        rank_targets_fn = Mock()

        # Mock scan_file response
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [
                {"theorem_id": "theorem1"},
                {"theorem_id": "theorem2"},
                {"theorem_id": "theorem3"},
            ],
        }

        # Mock rank_targets response with different order
        rank_targets_fn.return_value = {
            "status": "success",
            "ranking": [
                {"theorem_id": "theorem3"},
                {"theorem_id": "theorem1"},
                {"theorem_id": "theorem2"},
            ],
        }

        # Mock probe results
        probe_handler.handle = Mock(
            return_value=ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id="probe-test",
                probe_result=ProbeOutcome(
                    mode="aesop",
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
        handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, rank_targets_fn)

        # Create command with rank_targets ordering
        cmd = ProbeFileCommand(
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="rank_targets",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify order matches rank_targets order
        assert result.results[0]["theorem_id"] == "theorem3"
        assert result.results[1]["theorem_id"] == "theorem1"
        assert result.results[2]["theorem_id"] == "theorem2"
        assert rank_targets_fn.call_count == 1

    def test_limit_enforcement(self):
        """
        Test limit enforcement.

        Requirements: 5.6
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file response with 5 theorems
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [{"theorem_id": f"theorem{i}"} for i in range(5)],
        }

        # Mock probe results
        probe_handler.handle = Mock(
            return_value=ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id="probe-test",
                probe_result=ProbeOutcome(
                    mode="aesop",
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

        # Create command with limit=2
        cmd = ProbeFileCommand(
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=2,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify only 2 theorems were probed
        assert len(result.results) == 2
        assert probe_handler.handle.call_count == 2
        assert result.summary["total"] == 2

    def test_summary_aggregation(self):
        """
        Test summary aggregation.

        Requirements: 4.4, 5.3
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file response
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [
                {"theorem_id": "theorem1"},
                {"theorem_id": "theorem2"},
                {"theorem_id": "theorem3"},
                {"theorem_id": "theorem4"},
            ],
        }

        # Mock probe results with different classifications
        probe_results = [
            ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id="probe-1",
                probe_result=ProbeOutcome(
                    mode="aesop",
                    outcome="closed",
                    classification="trivial",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 100.0, "budget_s": 5.0},
                metadata={},
            ),
            ProbeResult(
                api_version="0.1.0",
                status="fail",
                run_id="probe-2",
                probe_result=ProbeOutcome(
                    mode="aesop",
                    outcome="not_closed",
                    classification="promising",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 200.0, "budget_s": 5.0},
                metadata={},
            ),
            ProbeResult(
                api_version="0.1.0",
                status="fail",
                run_id="probe-3",
                probe_result=ProbeOutcome(
                    mode="aesop",
                    outcome="not_closed",
                    classification="failed",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 300.0, "budget_s": 5.0},
                metadata={},
            ),
            ProbeResult(
                api_version="0.1.0",
                status="timeout",
                run_id="probe-4",
                probe_result=ProbeOutcome(
                    mode="aesop",
                    outcome="timeout",
                    classification="timed_out",
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 5000.0, "budget_s": 5.0},
                metadata={},
            ),
        ]

        probe_handler.handle = Mock(side_effect=probe_results)

        # Create handler
        handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

        # Create command
        cmd = ProbeFileCommand(
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify summary counts
        assert result.summary["total"] == 4
        assert result.summary["closed"] == 1
        assert result.summary["promising"] == 1
        assert result.summary["failed"] == 1
        assert result.summary["timed_out"] == 1

    def test_partial_success_handling(self):
        """
        Test partial success handling (some theorems fail).

        Requirements: 4.6, 10.4
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file response
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [
                {"theorem_id": "theorem1"},
                {"theorem_id": "theorem2"},
                {"theorem_id": "theorem3"},
            ],
        }

        # Mock probe results - second one raises exception
        def mock_probe_handle(cmd):
            if cmd.theorem_id == "theorem2":
                raise RuntimeError("Probe failed for theorem2")
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=f"probe-{cmd.theorem_id}",
                probe_result=ProbeOutcome(
                    mode=cmd.mode,
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
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify partial success
        assert result.status == "partial"
        assert len(result.results) == 2  # Only successful probes
        assert result.metadata["successful_probes"] == 2
        assert result.metadata["failed_probes"] == 1
        assert "errors" in result.metadata
        assert len(result.metadata["errors"]) == 1
        assert result.metadata["errors"][0]["theorem_id"] == "theorem2"

    def test_scan_file_failure_handling(self):
        """
        Test scan_file failure handling.

        Requirements: 10.4
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file failure
        scan_file_fn.return_value = {
            "status": "error",
            "error": "File not found",
        }

        # Create handler
        handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

        # Create command
        cmd = ProbeFileCommand(
            file_path="nonexistent.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify error result
        assert result.status == "error"
        assert result.summary["total"] == 0
        assert len(result.results) == 0
        assert "error" in result.metadata
        assert probe_handler.handle.call_count == 0  # Should not probe any theorems

    def test_empty_file_handling(self):
        """
        Test empty file handling.

        Requirements: 4.1
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file response with no theorems
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [],
        }

        # Create handler
        handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

        # Create command
        cmd = ProbeFileCommand(
            file_path="empty.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="file_order",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify empty result
        assert result.status == "success"
        assert result.summary["total"] == 0
        assert len(result.results) == 0
        assert probe_handler.handle.call_count == 0

    def test_rank_targets_without_function_raises_error(self):
        """
        Test that rank_targets ordering without rank_targets_fn raises error.

        Requirements: 5.5
        """
        # Setup mocks
        probe_handler = Mock()
        scan_file_fn = Mock()

        # Mock scan_file response
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [
                {"theorem_id": "theorem1"},
            ],
        }

        # Create handler WITHOUT rank_targets_fn
        handler = ProbeFileCommandHandler(probe_handler, scan_file_fn, None)

        # Create command with rank_targets ordering
        cmd = ProbeFileCommand(
            file_path="test.lean",
            mode="aesop",
            budget_s_per=5.0,
            limit=50,
            ordering="rank_targets",
        )

        # Execute and expect error
        result = handler.handle(cmd)

        # Verify error result
        assert result.status == "error"
        assert "rank_targets_fn required" in result.metadata["error"]
