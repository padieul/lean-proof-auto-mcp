"""
Unit tests for verify domain structures and validation.

Tests the immutable data structures and their validation logic.
"""

import pytest
from pathlib import Path

from lean_proof_auto_mcp.core.verify_domain import (
    VerifyCommand,
    VerifyResult,
    LeanRunResult,
    Workspace,
)


class TestVerifyCommand:
    """Test VerifyCommand validation and immutability."""
    
    def test_valid_command_minimal(self):
        """Test creating command with minimal required fields."""
        cmd = VerifyCommand(file_path="test.lean")
        
        assert cmd.file_path == "test.lean"
        assert cmd.theorem_id is None
        assert cmd.budget_s == 30.0
        assert cmd.max_log_excerpt_chars == 2000
        assert cmd.store_full_logs is True
        assert cmd.workspace_mode is None
    
    def test_valid_command_all_fields(self):
        """Test creating command with all fields specified."""
        cmd = VerifyCommand(
            file_path="test.lean",
            theorem_id="MyTheorem",
            budget_s=60.0,
            max_log_excerpt_chars=5000,
            store_full_logs=False,
            workspace_mode="worktree",
        )
        
        assert cmd.file_path == "test.lean"
        assert cmd.theorem_id == "MyTheorem"
        assert cmd.budget_s == 60.0
        assert cmd.max_log_excerpt_chars == 5000
        assert cmd.store_full_logs is False
        assert cmd.workspace_mode == "worktree"
    
    def test_empty_file_path_raises_error(self):
        """Test that empty file_path raises ValueError."""
        with pytest.raises(ValueError, match="file_path must be non-empty"):
            VerifyCommand(file_path="")
    
    def test_negative_budget_raises_error(self):
        """Test that negative budget_s raises ValueError."""
        with pytest.raises(ValueError, match="budget_s must be positive"):
            VerifyCommand(file_path="test.lean", budget_s=-1.0)
    
    def test_zero_budget_raises_error(self):
        """Test that zero budget_s raises ValueError."""
        with pytest.raises(ValueError, match="budget_s must be positive"):
            VerifyCommand(file_path="test.lean", budget_s=0.0)
    
    def test_negative_max_log_excerpt_raises_error(self):
        """Test that negative max_log_excerpt_chars raises ValueError."""
        with pytest.raises(ValueError, match="max_log_excerpt_chars must be positive"):
            VerifyCommand(file_path="test.lean", max_log_excerpt_chars=-1)
    
    def test_invalid_workspace_mode_raises_error(self):
        """Test that invalid workspace_mode raises ValueError."""
        with pytest.raises(ValueError, match="workspace_mode must be"):
            VerifyCommand(file_path="test.lean", workspace_mode="invalid")
    
    def test_immutability(self):
        """Test that VerifyCommand is immutable."""
        cmd = VerifyCommand(file_path="test.lean")
        
        with pytest.raises(AttributeError):
            cmd.file_path = "other.lean"  # type: ignore


class TestVerifyResult:
    """Test VerifyResult structure."""
    
    def test_create_result(self):
        """Test creating a VerifyResult with all fields."""
        result = VerifyResult(
            api_version="0.2.0",
            status="success",
            run_id="verify-20250126-120000-abc123",
            file="test.lean",
            theorem_id=None,
            verification_scope_used="file",
            diagnostics=[],
            diagnostic_summary={"error_count": 0, "warning_count": 0, "info_count": 0},
            evidence={"stdout_excerpt": "", "stderr_excerpt": "", "notes": []},
            metadata={"workspace_mode": "worktree", "workspace_id": "ws-123"},
            timing={"total_s": 1.5, "lean_execution_s": 1.2, "overhead_s": 0.3},
        )
        
        assert result.api_version == "0.2.0"
        assert result.status == "success"
        assert result.run_id == "verify-20250126-120000-abc123"
        assert result.file == "test.lean"
        assert result.verification_scope_used == "file"
    
    def test_immutability(self):
        """Test that VerifyResult is immutable."""
        result = VerifyResult(
            api_version="0.2.0",
            status="success",
            run_id="verify-20250126-120000-abc123",
            file="test.lean",
            theorem_id=None,
            verification_scope_used="file",
            diagnostics=[],
            diagnostic_summary={},
            evidence={},
            metadata={},
            timing={},
        )
        
        with pytest.raises(AttributeError):
            result.status = "fail"  # type: ignore


class TestLeanRunResult:
    """Test LeanRunResult structure."""
    
    def test_create_lean_run_result(self):
        """Test creating a LeanRunResult."""
        result = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="file",
            full_logs="Lean output...",
            timing={"lean_execution_s": 1.2},
            exit_code=0,
        )
        
        assert result.status == "success"
        assert result.diagnostics == []
        assert result.scope_used == "file"
        assert result.full_logs == "Lean output..."
        assert result.timing == {"lean_execution_s": 1.2}
        assert result.exit_code == 0
    
    def test_immutability(self):
        """Test that LeanRunResult is immutable."""
        result = LeanRunResult(
            status="success",
            diagnostics=[],
            scope_used="file",
            full_logs="",
            timing={},
            exit_code=0,
        )
        
        with pytest.raises(AttributeError):
            result.status = "fail"  # type: ignore


class TestWorkspace:
    """Test Workspace structure."""
    
    def test_create_workspace(self):
        """Test creating a Workspace."""
        workspace = Workspace(
            path=Path("/tmp/workspace-123"),
            workspace_id="workspace-123",
            mode="worktree",
        )
        
        assert workspace.path == Path("/tmp/workspace-123")
        assert workspace.workspace_id == "workspace-123"
        assert workspace.mode == "worktree"
    
    def test_immutability(self):
        """Test that Workspace is immutable."""
        workspace = Workspace(
            path=Path("/tmp/workspace-123"),
            workspace_id="workspace-123",
            mode="worktree",
        )
        
        with pytest.raises(AttributeError):
            workspace.mode = "temp"  # type: ignore
