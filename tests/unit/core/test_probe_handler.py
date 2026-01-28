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
    def mock_lean_runner(self):
        """Create mock LeanRunner."""
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
    def handler(self, mock_lean_runner, mock_workspace_provider, mock_classifier):
        """Create ProbeCommandHandler with mocked dependencies."""
        return ProbeCommandHandler(
            lean_runner=mock_lean_runner,
            workspace_provider=mock_workspace_provider,
            classifier=mock_classifier,
        )

    def test_successful_probe_execution(
        self, handler, mock_lean_runner, mock_workspace_provider, mock_classifier
    ):
        """Test successful probe execution with mocked dependencies."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock Lean execution result
        mock_lean_runner.verify_file.return_value = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="theorem",
            full_logs="Lean output...",
            timing={"lean_execution_s": 0.5},
            exit_code=0,
        )

        # Mock harness construction to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._construct_harness",
            return_value="mocked harness",
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

    def test_theorem_not_found_error(self, handler, mock_lean_runner, mock_workspace_provider):
        """Test error handling for theorem not found."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="NonExistentTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock Lean execution raising ValueError for theorem not found
        mock_lean_runner.verify_file.side_effect = ValueError(
            "Theorem 'NonExistentTheorem' not found"
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

    def test_toolchain_error_handling(self, handler, mock_lean_runner, mock_workspace_provider):
        """Test error handling for toolchain failures."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._construct_harness",
            return_value="mocked harness",
        ):
            # Mock Lean execution raising RuntimeError for toolchain failure
            mock_lean_runner.verify_file.side_effect = RuntimeError("Lean process failed")

            # Execute
            result = handler.handle(cmd)

        # Verify error result
        assert result.status == "error"
        assert result.probe_result.outcome == "error"
        assert result.probe_result.classification == "error"
        assert "execution_error" in result.diagnostics[0]["message"]

        # Verify cleanup was called
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_timeout_handling(self, handler, mock_lean_runner, mock_workspace_provider):
        """Test timeout handling."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock harness construction to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._construct_harness",
            return_value="mocked harness",
        ):
            # Mock Lean execution raising TimeoutError
            mock_lean_runner.verify_file.side_effect = TimeoutError("Execution timed out")

            # Execute
            result = handler.handle(cmd)

        # Verify timeout result
        assert result.status == "timeout"
        assert result.probe_result.outcome == "timeout"
        assert result.probe_result.classification == "timed_out"

        # Verify cleanup was called
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_workspace_cleanup_always_runs(
        self, handler, mock_lean_runner, mock_workspace_provider
    ):
        """Test that workspace cleanup always runs even on errors."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock Lean execution raising an error
        mock_lean_runner.verify_file.side_effect = RuntimeError("Unexpected error")

        # Execute
        handler.handle(cmd)

        # Verify cleanup was called despite error
        mock_workspace_provider.cleanup_workspace.assert_called_once()

    def test_workspace_cleanup_error_logged_not_propagated(
        self, handler, mock_lean_runner, mock_workspace_provider
    ):
        """Test that workspace cleanup errors are logged but not propagated."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock successful Lean execution
        mock_lean_runner.verify_file.return_value = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="theorem",
            full_logs="Lean output...",
            timing={"lean_execution_s": 0.5},
            exit_code=0,
        )

        # Mock cleanup failure
        mock_workspace_provider.cleanup_workspace.side_effect = RuntimeError("Cleanup failed")

        # Mock harness construction to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._construct_harness",
            return_value="mocked harness",
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

    @pytest.mark.requires_lean
    def test_harness_construction_for_aesop(self, handler, mock_workspace_provider):
        """Test harness construction for aesop mode."""
        # Setup
        cmd = ProbeCommand(
            file_path="MyModule/Test.lean",
            theorem_id="my_theorem",
            mode="aesop",
            budget_s=10.0,
        )

        workspace_path = Path("/tmp/workspace")

        # Create a test file with a theorem
        test_file_content = """
theorem my_theorem : True := by
  trivial
"""
        test_file = workspace_path / "MyModule" / "Test.lean"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(test_file_content)

        # Execute
        harness = handler._construct_harness(cmd, workspace_path)

        # Verify harness structure
        assert "import MyModule.Test" in harness
        assert "theorem my_theorem" in harness
        assert ":= by" in harness
        assert "aesop" in harness

        # Cleanup
        test_file.unlink()
        test_file.parent.rmdir()

    @pytest.mark.requires_lean
    def test_harness_construction_for_grind(self, handler, mock_workspace_provider):
        """Test harness construction for grind mode."""
        # Setup
        cmd = ProbeCommand(
            file_path="Test.lean",
            theorem_id="my_theorem",
            mode="grind",
            budget_s=10.0,
        )

        workspace_path = Path("/tmp/workspace")

        # Create a test file with a theorem
        test_file_content = """
theorem my_theorem : True := by
  trivial
"""
        test_file = workspace_path / "Test.lean"
        test_file.write_text(test_file_content)

        # Execute
        harness = handler._construct_harness(cmd, workspace_path)

        # Verify harness structure
        assert "import Test" in harness
        assert "theorem my_theorem" in harness
        assert ":= by" in harness
        assert "grind" in harness

        # Cleanup
        test_file.unlink()

    def test_harness_construction_with_trace_config(
        self, handler, mock_workspace_provider, tmp_path
    ):
        """Test harness construction with trace configuration."""
        # Setup
        cmd = ProbeCommand(
            file_path="Test.lean",
            theorem_id="my_theorem",
            mode="aesop",
            budget_s=10.0,
            trace_config={"trace.aesop": True},
        )

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()

        # Create a test file with a theorem
        test_file_content = """
theorem my_theorem : True := by
  trivial
"""
        test_file = workspace_path / "Test.lean"
        test_file.write_text(test_file_content)

        # Execute
        harness = handler._construct_harness(cmd, workspace_path)

        # Verify trace configuration is included
        assert "set_option trace.aesop true" in harness

    def test_harness_construction_theorem_not_found(
        self, handler, mock_workspace_provider, tmp_path
    ):
        """Test harness construction raises error when theorem not found."""
        # Setup
        cmd = ProbeCommand(
            file_path="Test.lean",
            theorem_id="nonexistent_theorem",
            mode="aesop",
            budget_s=10.0,
        )

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()

        # Create a test file without the theorem
        test_file_content = """
theorem other_theorem : True := by
  trivial
"""
        test_file = workspace_path / "Test.lean"
        test_file.write_text(test_file_content)

        # Execute and verify error
        with pytest.raises(ValueError, match="Theorem 'nonexistent_theorem' not found"):
            handler._construct_harness(cmd, workspace_path)

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
        self, handler, mock_lean_runner, mock_workspace_provider, mock_classifier
    ):
        """Test that classification is called with correct parameters."""
        # Setup
        cmd = ProbeCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            budget_s=10.0,
        )

        # Mock Lean execution result
        mock_lean_runner.verify_file.return_value = LeanRunResult(
            status="fail",
            diagnostics=[{"severity": "error", "message": "Unsolved goals", "location": None}],
            scope_used="theorem",
            full_logs="Lean output...",
            timing={"lean_execution_s": 5.0},
            exit_code=1,
        )

        mock_classifier.classify.return_value = "promising"

        # Mock harness construction to avoid file I/O
        with patch(
            "lean_proof_auto_mcp.core.probe_domain.ProbeCommandHandler._construct_harness",
            return_value="mocked harness",
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
