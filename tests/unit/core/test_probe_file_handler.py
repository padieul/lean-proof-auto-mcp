"""
Unit tests for ProbeFileCommandHandler.

This module tests the batch probe workflow including theorem enumeration,
ordering, limit enforcement, summary aggregation, and partial success handling.

Requirements: 4.1-4.7, 5.2-5.6, 10.4
"""

from pathlib import Path
from unittest.mock import Mock

from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
from lean_proof_auto_mcp.core.probe_domain import (
    ProbeFileCommand,
    ProbeFileCommandHandler,
    ProbeOutcome,
    ProbeResult,
)


def _make_probe_handler_mock() -> Mock:
    """Create a probe_handler mock with querier, constructor, validator, and workspace wired up.

    ProbeFileCommandHandler.handle() calls _probe_single_theorem which accesses:
    - probe_handler.querier.read_source_file()
    - probe_handler.querier.extract_declarations()
    - probe_handler.harness_constructor.construct()
    - probe_handler._write_harness()
    - probe_handler.validator.verify_file()
    - probe_handler._generate_run_id()
    - probe_handler._process_lean_result()
    - probe_handler.workspace_provider.create_workspace() / cleanup_workspace()
    """
    probe_handler = Mock()

    # Querier returns synthetic data
    probe_handler.querier.read_source_file.return_value = (
        "import Mathlib\n\ntheorem stub : True := by trivial\n"
    )
    probe_handler.querier.extract_declarations.return_value = []

    # Constructor returns success
    probe_handler.harness_constructor.construct.return_value = HarnessSuccess(
        code="import Mathlib\n\ntheorem stub : True := by aesop\n",
        theorem_id="stub",
        file_path="test.lean",
    )

    # Workspace
    mock_workspace = Mock()
    mock_workspace.path = Path("/tmp/fake_workspace")
    mock_workspace.workspace_id = "fake-ws-001"
    probe_handler.workspace_provider.create_workspace.return_value = mock_workspace

    # _write_harness returns a file path string
    probe_handler._write_harness.return_value = "harness_test.lean"

    # _generate_run_id returns a string
    probe_handler._generate_run_id.return_value = "run-001"

    return probe_handler


class TestProbeFileCommandHandler:
    """Test suite for ProbeFileCommandHandler."""

    def test_successful_batch_probing(self):
        """
        Test successful batch probing with mocked dependencies.

        Requirements: 4.1-4.7, 5.2-5.6
        """
        # Setup mocks
        probe_handler = _make_probe_handler_mock()
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

        # Mock validator to return a successful lean result
        mock_lean_result = Mock()
        mock_lean_result.messages = []
        mock_lean_result.sorries = []
        probe_handler.validator.verify_file.return_value = mock_lean_result

        # Mock _process_lean_result to return a closed ProbeResult
        def mock_process(cmd, run_id, lean_result, start_time, workspace=None):
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=run_id,
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

        probe_handler._process_lean_result = Mock(side_effect=mock_process)

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

    def test_theorem_enumeration_file_order(self):
        """
        Test theorem enumeration with file_order.

        Requirements: 4.1, 5.5
        """
        # Setup mocks
        probe_handler = _make_probe_handler_mock()
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

        # Mock validator and _process_lean_result
        mock_lean_result = Mock()
        mock_lean_result.messages = []
        mock_lean_result.sorries = []
        probe_handler.validator.verify_file.return_value = mock_lean_result

        def mock_process(cmd, run_id, lean_result, start_time, workspace=None):
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=run_id,
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

        probe_handler._process_lean_result = Mock(side_effect=mock_process)

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
        probe_handler = _make_probe_handler_mock()
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

        # Mock validator and _process_lean_result
        mock_lean_result = Mock()
        mock_lean_result.messages = []
        mock_lean_result.sorries = []
        probe_handler.validator.verify_file.return_value = mock_lean_result

        def mock_process(cmd, run_id, lean_result, start_time, workspace=None):
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=run_id,
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

        probe_handler._process_lean_result = Mock(side_effect=mock_process)

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
        probe_handler = _make_probe_handler_mock()
        scan_file_fn = Mock()

        # Mock scan_file response with 5 theorems
        scan_file_fn.return_value = {
            "status": "success",
            "theorems": [{"theorem_id": f"theorem{i}"} for i in range(5)],
        }

        # Mock validator and _process_lean_result
        mock_lean_result = Mock()
        mock_lean_result.messages = []
        mock_lean_result.sorries = []
        probe_handler.validator.verify_file.return_value = mock_lean_result

        def mock_process(cmd, run_id, lean_result, start_time, workspace=None):
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=run_id,
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

        probe_handler._process_lean_result = Mock(side_effect=mock_process)

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
        assert result.summary["total"] == 2

    def test_summary_aggregation(self):
        """
        Test summary aggregation.

        Requirements: 4.4, 5.3
        """
        # Setup mocks
        probe_handler = _make_probe_handler_mock()
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

        # Mock validator
        mock_lean_result = Mock()
        mock_lean_result.messages = []
        mock_lean_result.sorries = []
        probe_handler.validator.verify_file.return_value = mock_lean_result

        # Mock _process_lean_result with different classifications per call
        classifications = [
            ("closed", "trivial"),
            ("not_closed", "promising"),
            ("not_closed", "failed"),
            ("timeout", "timed_out"),
        ]
        call_idx = [0]

        def mock_process(cmd, run_id, lean_result, start_time, workspace=None):
            outcome, classification = classifications[call_idx[0]]
            call_idx[0] += 1
            status = (
                "success"
                if outcome == "closed"
                else ("timeout" if outcome == "timeout" else "fail")
            )
            return ProbeResult(
                api_version="0.1.0",
                status=status,
                run_id=run_id,
                probe_result=ProbeOutcome(
                    mode="aesop",
                    outcome=outcome,
                    classification=classification,
                    suggested_script=None,
                ),
                diagnostics=[],
                timing={"elapsed_ms": 100.0, "budget_s": 5.0},
                metadata={},
            )

        probe_handler._process_lean_result = Mock(side_effect=mock_process)

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
        probe_handler = _make_probe_handler_mock()
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

        # Make harness construction fail for theorem2 by returning an error

        call_idx = [0]
        theorem_ids = ["theorem1", "theorem2", "theorem3"]

        def mock_construct(config):
            idx = call_idx[0]
            call_idx[0] += 1
            if config.theorem_id == "theorem2" or (idx == 1):
                raise RuntimeError("Harness construction failed for theorem2")
            return HarnessSuccess(
                code="import Mathlib\n\ntheorem stub : True := by aesop\n",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
            )

        probe_handler.harness_constructor.construct = Mock(side_effect=mock_construct)

        # Mock validator and _process_lean_result for successful theorems
        mock_lean_result = Mock()
        mock_lean_result.messages = []
        mock_lean_result.sorries = []
        probe_handler.validator.verify_file.return_value = mock_lean_result

        def mock_process(cmd, run_id, lean_result, start_time, workspace=None):
            return ProbeResult(
                api_version="0.1.0",
                status="success",
                run_id=run_id,
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

        probe_handler._process_lean_result = Mock(side_effect=mock_process)

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
        probe_handler = _make_probe_handler_mock()
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

    def test_empty_file_handling(self):
        """
        Test empty file handling.

        Requirements: 4.1
        """
        # Setup mocks
        probe_handler = _make_probe_handler_mock()
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

    def test_rank_targets_without_function_raises_error(self):
        """
        Test that rank_targets ordering without rank_targets_fn raises error.

        Requirements: 5.5
        """
        # Setup mocks
        probe_handler = _make_probe_handler_mock()
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
