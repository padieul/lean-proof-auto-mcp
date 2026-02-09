"""
Unit tests for ProbeCommandHandler.

Tests the probe handler orchestration logic with mocked dependencies.

Requirements: 1.1-1.6, 7.1-7.4, 10.1-10.5
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from lean_proof_auto_mcp.core.probe_domain import (
    ProbeCommand,
    ProbeCommandHandler,
    ProbeResult,
)
from lean_proof_auto_mcp.core.verify_domain import LeanRunResult, Workspace


class TestProbeCommandHandler:
    """Test ProbeCommandHandler orchestration logic."""

    @pytest.fixture
    def mock_validator(self):
        """Create mock ProofValidator."""
        return Mock()

    @pytest.fixture
    def mock_querier(self):
        """Create mock Querier."""
        return Mock()

    @pytest.fixture
    def mock_workspace_provider(self):
        """Create mock WorkspaceProvider."""
        provider = Mock()
        provider.create_workspace.return_value = Workspace(
            path=Path("/tmp/workspace"),
            workspace_id="ws-test-123",
            mode="temp",
        )
        return provider

    @pytest.fixture
    def mock_classifier(self):
        """Create mock AutomationClassifier."""
        classifier = Mock()
        classifier.classify.return_value = "trivial"
        return classifier

    @pytest.fixture
    def mock_harness_constructor(self):
        """Create mock HarnessConstructor."""
        return Mock()

    @pytest.fixture
    def handler(self, mock_validator, mock_querier, mock_workspace_provider, mock_classifier, mock_harness_constructor):
        """Create ProbeCommandHandler with mocked dependencies."""
        return ProbeCommandHandler(
            validator=mock_validator,
            querier=mock_querier,
            workspace_provider=mock_workspace_provider,
            classifier=mock_classifier,
            harness_constructor=mock_harness_constructor,
        )

    def test_successful_probe_execution(
        self, handler, mock_validator, mock_workspace_provider, mock_classifier, mock_harness_constructor
    ):
        """Test successful probe execution with mocked dependencies."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction
        from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="-- harness code",
            theorem_id="MyTheorem",
            file_path="test.lean",
        )

        # Mock Lean execution result
        mock_validator.verify_file.return_value = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="theorem",
            full_logs="Lean output...",
            timing={"lean_execution_s": 0.5},
            exit_code=0,
        )

        # Mock harness writing to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._write_harness",
            return_value="/tmp/workspace/_probe_harness_MyTheorem.lean",
        ):
            # Execute
            result = handler.handle(cmd)

        # Verify
        assert isinstance(result, ProbeResult)
        assert result.status == "success"
        assert result.probe_result.mode == "aesop"
        assert result.probe_result.outcome == "closed"
        assert result.probe_result.classification == "trivial"
        assert result.timing["budget_s"] == 10.0

        # Verify workspace was created and cleaned up
        mock_workspace_provider.create_workspace.assert_called_once_with("test.lean")
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_workspace_creation_failure(self, handler, mock_workspace_provider):
        """Test error handling for workspace creation failures."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock workspace creation failure
        mock_workspace_provider.create_workspace.side_effect = RuntimeError(
            "Workspace creation failed"
        )

        # Execute
        result = handler.handle(cmd)

        # Verify error result
        assert result.status == "error"
        assert result.probe_result.outcome == "error"
        assert result.probe_result.classification == "error"
        assert "workspace_error" in result.diagnostics[0]["message"]

        # Verify cleanup was not called (workspace was never created)
        mock_workspace_provider.cleanup_workspace.assert_not_called()

    def test_theorem_not_found_error(self, handler, mock_validator, mock_workspace_provider, mock_harness_constructor):
        """Test error handling for theorem not found."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="NonExistentTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction failure
        from lean_proof_auto_mcp.core.harness_construction import HarnessError
        mock_harness_constructor.construct.return_value = HarnessError(
            error_type="theorem_not_found",
            message="Theorem 'NonExistentTheorem' not found",
            theorem_id="NonExistentTheorem",
            file_path="test.lean",
        )

        # Execute
        result = handler.handle(cmd)

        # Verify error result
        assert result.status == "error"
        assert result.probe_result.outcome == "error"
        assert result.probe_result.classification == "error"
        assert "theorem_not_found" in result.diagnostics[0]["message"]

        # Verify cleanup was called
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_toolchain_error_handling(self, handler, mock_validator, mock_workspace_provider, mock_harness_constructor):
        """Test error handling for toolchain failures."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction
        from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="-- harness code",
            theorem_id="MyTheorem",
            file_path="test.lean",
        )

        # Mock harness writing to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._write_harness",
            return_value="/tmp/workspace/_probe_harness_MyTheorem.lean",
        ):
            # Mock Lean execution raising RuntimeError for toolchain failure
            mock_validator.verify_file.side_effect = RuntimeError("Lean process failed")

            # Execute
            result = handler.handle(cmd)

        # Verify error result
        assert result.status == "error"
        assert result.probe_result.outcome == "error"
        assert result.probe_result.classification == "error"
        assert "execution_error" in result.diagnostics[0]["message"]

        # Verify cleanup was called
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_timeout_handling(self, handler, mock_validator, mock_workspace_provider, mock_harness_constructor):
        """Test timeout handling."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction
        from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="-- harness code",
            theorem_id="MyTheorem",
            file_path="test.lean",
        )

        # Mock harness writing to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._write_harness",
            return_value="/tmp/workspace/_probe_harness_MyTheorem.lean",
        ):
            # Mock Lean execution raising TimeoutError
            mock_validator.verify_file.side_effect = TimeoutError("Execution timed out")

            # Execute
            result = handler.handle(cmd)

        # Verify timeout result
        assert result.status == "timeout"
        assert result.probe_result.outcome == "timeout"
        assert result.probe_result.classification == "timed_out"

        # Verify cleanup was called
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_workspace_cleanup_always_runs(
        self, handler, mock_validator, mock_workspace_provider, mock_harness_constructor
    ):
        """Test that workspace cleanup always runs even on errors."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction
        from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="-- harness code",
            theorem_id="MyTheorem",
            file_path="test.lean",
        )

        # Mock Lean execution raising an error
        mock_validator.verify_file.side_effect = RuntimeError("Unexpected error")

        # Execute
        handler.handle(cmd)

        # Verify cleanup was called despite error
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_workspace_cleanup_error_logged_not_propagated(
        self, handler, mock_validator, mock_workspace_provider, mock_harness_constructor
    ):
        """Test that workspace cleanup errors are logged but not propagated."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction
        from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="-- harness code",
            theorem_id="MyTheorem",
            file_path="test.lean",
        )

        # Mock successful Lean execution
        mock_validator.verify_file.return_value = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="theorem",
            full_logs="Lean output...",
            timing={"lean_execution_s": 0.5},
            exit_code=0,
        )

        # Mock cleanup failure
        mock_workspace_provider.cleanup_workspace.side_effect = RuntimeError("Cleanup failed")

        # Mock harness writing to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._write_harness",
            return_value="/tmp/workspace/_probe_harness_MyTheorem.lean",
        ):
            # Execute - should not raise exception
            result = handler.handle(cmd)

        # Verify result is still successful
        assert result.status == "success"

    def test_run_id_generation_uniqueness(self, handler):
        """Test that run_id generation produces unique IDs."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Generate multiple run_ids
        run_ids = set()
        for _ in range(10):
            run_id = handler._generate_run_id(cmd)
            run_ids.add(run_id)

        # Verify all run_ids are unique
        assert len(run_ids) == 10

        # Verify format
        for run_id in run_ids:
            assert run_id.startswith("probe-")
            parts = run_id.split("-")
            assert len(parts) == 5  # probe-YYYYMMDD-HHMMSS-hash-random

    # Tests for _construct_harness removed - method no longer exists
    # Harness construction is now handled by injected HarnessConstructor
    # See test_harness_construction.py for harness construction tests

    def test_diagnostic_normalization(self, handler):
        """Test diagnostic normalization and sorting."""
        # Setup
        raw_diagnostics = [
            {
                "severity": "ERROR",
                "message": "Type mismatch",
                "location": {"file": "test.lean", "line": 10, "col": 5},
            },
            {
                "severity": "warning",
                "message": "Unused variable",
                "location": {"file": "test.lean", "line": 5, "col": 3},
            },
            {
                "severity": "info",
                "message": "Hint",
                "location": None,
            },
        ]

        # Execute
        normalized = handler._normalize_diagnostics(raw_diagnostics)

        # Verify normalization
        assert len(normalized) == 3
        # Diagnostics are sorted by (file, line, col, severity_order, message)
        # Line 5 (warning) comes before line 10 (error)
        assert normalized[0]["severity"] == "warning"
        assert normalized[0]["location"]["line"] == 5
        assert normalized[1]["severity"] == "error"
        assert normalized[1]["location"]["line"] == 10
        # None location comes last
        assert normalized[2]["severity"] == "info"
        assert normalized[2]["location"] is None

    def test_classification_integration(
        self, handler, mock_validator, mock_workspace_provider, mock_classifier, mock_harness_constructor
    ):
        """Test that classification is called with correct parameters."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction
        from lean_proof_auto_mcp.core.harness_construction import HarnessSuccess
        mock_harness_constructor.construct.return_value = HarnessSuccess(
            code="-- harness code",
            theorem_id="MyTheorem",
            file_path="test.lean",
        )

        # Mock Lean execution result
        mock_validator.verify_file.return_value = LeanRunResult(
            status="fail",
            diagnostics=[{"severity": "error", "message": "Unsolved goals", "location": None}],
            scope_used="theorem",
            full_logs="Lean output...",
            timing={"lean_execution_s": 5.0},
            exit_code=1,
        )

        mock_classifier.classify.return_value = "promising"

        # Mock harness writing to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._write_harness",
            return_value="/tmp/workspace/_probe_harness_MyTheorem.lean",
        ):
            # Execute
            result = handler.handle(cmd)

        # Verify classifier was called with correct parameters
        mock_classifier.classify.assert_called_once()
        call_args = mock_classifier.classify.call_args
        assert call_args[0][0] == "not_closed"  # outcome
        assert len(call_args[0][1]) == 1  # diagnostics
        assert call_args[0][3] == 10.0  # budget_s

        # Verify result uses classification
        assert result.probe_result.classification == "promising"
