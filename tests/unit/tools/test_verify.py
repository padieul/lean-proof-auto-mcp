"""Unit tests for verify tool argument validation and error handling."""

import pytest

from lean_proof_auto_mcp.tools.verify import _build_command, _build_error_response


class TestBuildCommand:
    """Test cases for _build_command function."""

    def test_valid_minimal_args(self):
        """Test building command with minimal valid arguments."""
        args = {"file": "test.lean"}

        cmd = _build_command(args)

        assert cmd.file_path == "test.lean"
        assert cmd.theorem_id is None
        assert cmd.budget_s == 30.0  # Default
        assert cmd.max_log_excerpt_chars == 2000  # Default
        assert cmd.store_full_logs is True  # Default
        assert cmd.workspace_mode is None  # Default

    def test_valid_full_args(self):
        """Test building command with all arguments specified."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "budget_s": 60.0,
            "max_log_excerpt_chars": 5000,
            "store_full_logs": False,
            "workspace_mode": "worktree",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "path/to/file.lean"
        assert cmd.theorem_id == "MyTheorem.proof"
        assert cmd.budget_s == 60.0
        assert cmd.max_log_excerpt_chars == 5000
        assert cmd.store_full_logs is False
        assert cmd.workspace_mode == "worktree"

    def test_valid_with_temp_workspace_mode(self):
        """Test building command with temp workspace mode."""
        args = {"file": "test.lean", "workspace_mode": "temp"}

        cmd = _build_command(args)

        assert cmd.workspace_mode == "temp"

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {"file": "  test.lean  "}

        cmd = _build_command(args)

        assert cmd.file_path == "test.lean"

    def test_budget_s_integer_coerced_to_float(self):
        """Test that integer budget_s is coerced to float."""
        args = {"file": "test.lean", "budget_s": 45}

        cmd = _build_command(args)

        assert cmd.budget_s == 45.0
        assert isinstance(cmd.budget_s, float)

    def test_missing_file(self):
        """Test error when file is missing."""
        args = {}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_empty_file(self):
        """Test error when file is empty string."""
        args = {"file": ""}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_whitespace_only_file(self):
        """Test error when file is whitespace only."""
        args = {"file": "   "}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_non_string_file(self):
        """Test error when file is not a string."""
        args = {"file": 123}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_non_string_theorem_id(self):
        """Test error when theorem_id is not a string."""
        args = {"file": "test.lean", "theorem_id": 123}

        with pytest.raises(ValueError, match="'theorem_id' must be a string or null"):
            _build_command(args)

    def test_non_numeric_budget_s(self):
        """Test error when budget_s is not a number."""
        args = {"file": "test.lean", "budget_s": "30"}

        with pytest.raises(ValueError, match="'budget_s' must be a number"):
            _build_command(args)

    def test_negative_budget_s(self):
        """Test error when budget_s is negative."""
        args = {"file": "test.lean", "budget_s": -10.0}

        with pytest.raises(ValueError, match="'budget_s' must be positive"):
            _build_command(args)

    def test_zero_budget_s(self):
        """Test error when budget_s is zero."""
        args = {"file": "test.lean", "budget_s": 0.0}

        with pytest.raises(ValueError, match="'budget_s' must be positive"):
            _build_command(args)

    def test_non_integer_max_log_excerpt_chars(self):
        """Test error when max_log_excerpt_chars is not an integer."""
        args = {"file": "test.lean", "max_log_excerpt_chars": "2000"}

        with pytest.raises(ValueError, match="'max_log_excerpt_chars' must be an integer"):
            _build_command(args)

    def test_negative_max_log_excerpt_chars(self):
        """Test error when max_log_excerpt_chars is negative."""
        args = {"file": "test.lean", "max_log_excerpt_chars": -100}

        with pytest.raises(ValueError, match="'max_log_excerpt_chars' must be positive"):
            _build_command(args)

    def test_zero_max_log_excerpt_chars(self):
        """Test error when max_log_excerpt_chars is zero."""
        args = {"file": "test.lean", "max_log_excerpt_chars": 0}

        with pytest.raises(ValueError, match="'max_log_excerpt_chars' must be positive"):
            _build_command(args)

    def test_non_boolean_store_full_logs(self):
        """Test error when store_full_logs is not a boolean."""
        args = {"file": "test.lean", "store_full_logs": "true"}

        with pytest.raises(ValueError, match="'store_full_logs' must be a boolean"):
            _build_command(args)

    def test_non_string_workspace_mode(self):
        """Test error when workspace_mode is not a string."""
        args = {"file": "test.lean", "workspace_mode": 123}

        with pytest.raises(ValueError, match="'workspace_mode' must be a string or null"):
            _build_command(args)

    def test_invalid_workspace_mode(self):
        """Test error when workspace_mode is invalid."""
        args = {"file": "test.lean", "workspace_mode": "invalid"}

        with pytest.raises(
            ValueError, match="'workspace_mode' must be 'worktree', 'temp', or null"
        ):
            _build_command(args)


class TestBuildErrorResponse:
    """Test cases for _build_error_response function."""

    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        # Check required fields
        assert "api_version" in response
        assert "status" in response
        assert "run_id" in response
        assert "file" in response
        assert "theorem_id" in response
        assert "verification_scope_used" in response
        assert "diagnostics" in response
        assert "diagnostic_summary" in response
        assert "evidence" in response
        assert "metadata" in response
        assert "timing" in response

    def test_error_response_values(self):
        """Test that error response has correct values."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        assert response["api_version"] == "0.2.0"
        assert response["status"] == "error"
        assert response["file"] == "test.lean"
        assert response["theorem_id"] is None
        assert response["verification_scope_used"] == "none"

    def test_error_response_with_theorem_id(self):
        """Test error response with theorem_id."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
            theorem_id="MyTheorem.proof",
        )

        assert response["theorem_id"] == "MyTheorem.proof"

    def test_error_response_diagnostics(self):
        """Test that error response has correct diagnostics."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error message",
            error_code="test_error",
        )

        diagnostics = response["diagnostics"]
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "error"
        assert diagnostics[0]["message"] == "Test error message"
        # Location should be null for error diagnostics (per schema)
        assert diagnostics[0]["location"] is None

    def test_error_response_diagnostic_summary(self):
        """Test that error response has correct diagnostic summary."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        summary = response["diagnostic_summary"]
        assert summary["error_count"] == 1
        assert summary["warning_count"] == 0
        assert summary["info_count"] == 0

    def test_error_response_evidence(self):
        """Test that error response has correct evidence."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error_code",
        )

        evidence = response["evidence"]
        assert evidence["stdout_excerpt"] == ""
        assert evidence["stderr_excerpt"] == ""
        assert "error_code: test_error_code" in evidence["notes"]

    def test_error_response_run_id_format(self):
        """Test that error response run_id has correct format."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        run_id = response["run_id"]
        assert run_id.startswith("verify-")
        parts = run_id.split("-")
        assert len(parts) == 5  # verify-YYYYMMDD-HHMMSS-hash-random
        assert len(parts[3]) == 8  # 8-character file hash
        assert len(parts[4]) == 6  # 6-character random suffix


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_budget_s_minimum_positive(self):
        """Test budget_s at minimum positive value."""
        args = {"file": "test.lean", "budget_s": 0.001}

        cmd = _build_command(args)

        assert cmd.budget_s == 0.001

    def test_budget_s_large_value(self):
        """Test budget_s with large value."""
        args = {"file": "test.lean", "budget_s": 3600.0}

        cmd = _build_command(args)

        assert cmd.budget_s == 3600.0

    def test_max_log_excerpt_chars_minimum(self):
        """Test max_log_excerpt_chars at minimum value."""
        args = {"file": "test.lean", "max_log_excerpt_chars": 1}

        cmd = _build_command(args)

        assert cmd.max_log_excerpt_chars == 1

    def test_max_log_excerpt_chars_large_value(self):
        """Test max_log_excerpt_chars with large value."""
        args = {"file": "test.lean", "max_log_excerpt_chars": 1000000}

        cmd = _build_command(args)

        assert cmd.max_log_excerpt_chars == 1000000

    def test_file_with_special_characters(self):
        """Test file path with special characters."""
        args = {"file": "path/to/my-file_v2.lean"}

        cmd = _build_command(args)

        assert cmd.file_path == "path/to/my-file_v2.lean"

    def test_theorem_id_with_dots(self):
        """Test theorem_id with dots (namespace separator)."""
        args = {"file": "test.lean", "theorem_id": "MyNamespace.MyTheorem.proof"}

        cmd = _build_command(args)

        assert cmd.theorem_id == "MyNamespace.MyTheorem.proof"


class TestIntegrationScenarios:
    """Test integration scenarios with realistic inputs."""

    def test_file_level_verification_args(self):
        """Test arguments for file-level verification."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "budget_s": 60.0,
            "store_full_logs": True,
        }

        cmd = _build_command(args)

        assert cmd.file_path == "Mathlib/Data/List/Basic.lean"
        assert cmd.theorem_id is None
        assert cmd.budget_s == 60.0
        assert cmd.store_full_logs is True

    def test_theorem_level_verification_args(self):
        """Test arguments for theorem-level verification."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "theorem_id": "List.append_assoc",
            "budget_s": 30.0,
            "workspace_mode": "worktree",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "Mathlib/Data/List/Basic.lean"
        assert cmd.theorem_id == "List.append_assoc"
        assert cmd.budget_s == 30.0
        assert cmd.workspace_mode == "worktree"

    def test_quick_verification_args(self):
        """Test arguments for quick verification with small budget."""
        args = {
            "file": "test.lean",
            "budget_s": 5.0,
            "max_log_excerpt_chars": 500,
            "store_full_logs": False,
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 5.0
        assert cmd.max_log_excerpt_chars == 500
        assert cmd.store_full_logs is False

    def test_detailed_verification_args(self):
        """Test arguments for detailed verification with large log excerpts."""
        args = {
            "file": "test.lean",
            "budget_s": 120.0,
            "max_log_excerpt_chars": 10000,
            "store_full_logs": True,
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 120.0
        assert cmd.max_log_excerpt_chars == 10000
        assert cmd.store_full_logs is True


class TestErrorHandling:
    """Test cases for error handling in verify function."""

    def test_invalid_args_returns_error_response(self):
        """Test that invalid arguments return error response."""
        from lean_proof_auto_mcp.tools.verify import verify

        # Missing file argument
        result = verify({})

        assert result["status"] == "error"
        assert result["api_version"] == "0.2.0"
        assert "error_code: input_validation_error" in result["evidence"]["notes"]
        assert len(result["diagnostics"]) == 1
        assert result["diagnostics"][0]["severity"] == "error"

    def test_empty_file_returns_error_response(self):
        """Test that empty file returns error response."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({"file": ""})

        assert result["status"] == "error"
        assert "error_code: input_validation_error" in result["evidence"]["notes"]
        assert "'file' must be a non-empty string" in result["diagnostics"][0]["message"]

    def test_negative_budget_returns_error_response(self):
        """Test that negative budget returns error response."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({"file": "test.lean", "budget_s": -10.0})

        assert result["status"] == "error"
        assert "error_code: input_validation_error" in result["evidence"]["notes"]
        assert "'budget_s' must be positive" in result["diagnostics"][0]["message"]

    def test_invalid_workspace_mode_returns_error_response(self):
        """Test that invalid workspace_mode returns error response."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({"file": "test.lean", "workspace_mode": "invalid"})

        assert result["status"] == "error"
        assert "error_code: input_validation_error" in result["evidence"]["notes"]
        assert "workspace_mode" in result["diagnostics"][0]["message"]

    def test_error_response_has_required_fields(self):
        """Test that error responses have all required fields."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({})

        # Check all required fields are present
        required_fields = [
            "api_version",
            "status",
            "run_id",
            "file",
            "theorem_id",
            "verification_scope_used",
            "diagnostics",
            "diagnostic_summary",
            "evidence",
            "metadata",
            "timing",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_error_response_diagnostic_summary(self):
        """Test that error response has correct diagnostic summary."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({"file": ""})

        summary = result["diagnostic_summary"]
        assert summary["error_count"] == 1
        assert summary["warning_count"] == 0
        assert summary["info_count"] == 0

    def test_error_response_verification_scope_none(self):
        """Test that error response has verification_scope_used='none'."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({"file": ""})

        assert result["verification_scope_used"] == "none"

    def test_error_response_preserves_file_path(self):
        """Test that error response preserves the file path from request."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({"file": "path/to/test.lean", "budget_s": -5.0})

        assert result["file"] == "path/to/test.lean"

    def test_error_response_preserves_theorem_id(self):
        """Test that error response preserves theorem_id if provided."""

        # Note: This will fail validation before theorem_id is used,
        # but we can test the error response builder directly
        from lean_proof_auto_mcp.tools.verify import _build_error_response

        result = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
            theorem_id="MyTheorem.proof",
        )

        assert result["theorem_id"] == "MyTheorem.proof"

    def test_multiple_validation_errors_first_caught(self):
        """Test that first validation error is caught and returned."""
        from lean_proof_auto_mcp.tools.verify import verify

        # Multiple invalid arguments - should catch first one
        result = verify({"file": "", "budget_s": -10.0})

        assert result["status"] == "error"
        # Should catch the file validation error first
        assert "'file' must be a non-empty string" in result["diagnostics"][0]["message"]

    def test_error_response_has_run_id(self):
        """Test that error response includes a run_id."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({})

        assert "run_id" in result
        assert result["run_id"].startswith("verify-")

    def test_error_response_empty_metadata_and_timing(self):
        """Test that error response has empty metadata and timing."""
        from lean_proof_auto_mcp.tools.verify import verify

        result = verify({})

        assert result["metadata"] == {}
        assert result["timing"] == {}
