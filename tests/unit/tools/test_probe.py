"""Unit tests for probe tool argument validation and error handling.

Requirements: 10.1-10.3, 10.5
"""

import pytest

from lean_proof_auto_mcp.tools.probe import _build_command, _build_error_response


class TestBuildCommand:
    """Test cases for _build_command function."""

    def test_valid_minimal_args(self):
        """Test building command with minimal valid arguments."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "test.lean"
        assert cmd.theorem_id == "MyTheorem"
        assert cmd.mode == "aesop"
        assert cmd.budget_s == 10.0  # Default
        assert cmd.trace_config is None  # Default

    def test_valid_full_args(self):
        """Test building command with all arguments specified."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "mode": "aesop?",
            "budget_s": 30.0,
            "trace_config": {"trace.aesop": True},
        }

        cmd = _build_command(args)

        assert cmd.file_path == "path/to/file.lean"
        assert cmd.theorem_id == "MyTheorem.proof"
        assert cmd.mode == "aesop?"
        assert cmd.budget_s == 30.0
        assert cmd.trace_config == {"trace.aesop": True}

    def test_valid_with_grind_mode(self):
        """Test building command with grind mode."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "grind",
        }

        cmd = _build_command(args)

        assert cmd.mode == "grind"

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "test.lean"

    def test_theorem_id_whitespace_trimmed(self):
        """Test that theorem_id whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "  MyTheorem  ",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.theorem_id == "MyTheorem"

    def test_budget_s_integer_coerced_to_float(self):
        """Test that integer budget_s is coerced to float."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": 20,
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 20.0
        assert isinstance(cmd.budget_s, float)

    def test_missing_file(self):
        """Test error when file is missing."""
        args = {
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_empty_file(self):
        """Test error when file is empty string."""
        args = {
            "file": "",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_whitespace_only_file(self):
        """Test error when file is whitespace only."""
        args = {
            "file": "   ",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_non_string_file(self):
        """Test error when file is not a string."""
        args = {
            "file": 123,
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_missing_theorem_id(self):
        """Test error when theorem_id is missing."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_empty_theorem_id(self):
        """Test error when theorem_id is empty string."""
        args = {
            "file": "test.lean",
            "theorem_id": "",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_whitespace_only_theorem_id(self):
        """Test error when theorem_id is whitespace only."""
        args = {
            "file": "test.lean",
            "theorem_id": "   ",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_non_string_theorem_id(self):
        """Test error when theorem_id is not a string."""
        args = {
            "file": "test.lean",
            "theorem_id": 123,
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_missing_mode(self):
        """Test error when mode is missing."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'mode' must be a string"):
            _build_command(args)

    def test_non_string_mode(self):
        """Test error when mode is not a string."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": 123,
        }

        with pytest.raises(ValueError, match="'mode' must be a string"):
            _build_command(args)

    def test_invalid_mode(self):
        """Test error when mode is invalid."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "invalid",
        }

        with pytest.raises(ValueError, match="'mode' must be 'aesop', 'aesop\\?', or 'grind'"):
            _build_command(args)

    def test_non_numeric_budget_s(self):
        """Test error when budget_s is not a number."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": "30",
        }

        with pytest.raises(ValueError, match="'budget_s' must be a number"):
            _build_command(args)

    def test_negative_budget_s(self):
        """Test error when budget_s is negative."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": -10.0,
        }

        with pytest.raises(ValueError, match="'budget_s' must be positive"):
            _build_command(args)

    def test_zero_budget_s(self):
        """Test error when budget_s is zero."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": 0.0,
        }

        with pytest.raises(ValueError, match="'budget_s' must be positive"):
            _build_command(args)

    def test_non_dict_trace_config(self):
        """Test error when trace_config is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "trace_config": "invalid",
        }

        with pytest.raises(ValueError, match="'trace_config' must be a dict or null"):
            _build_command(args)


class TestBuildErrorResponse:
    """Test cases for _build_error_response function."""

    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error",
        )

        # Check required fields
        assert "api_version" in response
        assert "status" in response
        assert "run_id" in response
        assert "probe_result" in response
        assert "diagnostics" in response
        assert "timing" in response
        assert "metadata" in response

    def test_error_response_values(self):
        """Test that error response has correct values."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error",
        )

        assert response["api_version"] == "0.1.0"
        assert response["status"] == "error"

    def test_error_response_probe_result(self):
        """Test that error response has correct probe_result."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error",
        )

        probe_result = response["probe_result"]
        assert probe_result["mode"] == "aesop"
        assert probe_result["outcome"] == "error"
        assert probe_result["classification"] == "error"
        assert probe_result["suggested_script"] is None

    def test_error_response_diagnostics(self):
        """Test that error response has correct diagnostics."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error message",
            error_code="test_error",
        )

        diagnostics = response["diagnostics"]
        assert len(diagnostics) == 1
        assert diagnostics[0]["severity"] == "error"
        assert diagnostics[0]["message"] == "Test error message"
        assert diagnostics[0]["location"] is None

    def test_error_response_timing(self):
        """Test that error response has correct timing."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error",
        )

        timing = response["timing"]
        assert timing["elapsed_ms"] == 0.0
        assert timing["budget_s"] == 0.0

    def test_error_response_metadata(self):
        """Test that error response has correct metadata."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error_code",
        )

        metadata = response["metadata"]
        assert metadata["error_code"] == "test_error_code"

    def test_error_response_run_id_format(self):
        """Test that error response run_id has correct format."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error",
        )

        run_id = response["run_id"]
        assert run_id.startswith("probe-")
        parts = run_id.split("-")
        assert len(parts) == 5  # probe-YYYYMMDD-HHMMSS-hash-random
        assert len(parts[3]) == 8  # 8-character file hash
        assert len(parts[4]) == 6  # 6-character random suffix

    def test_error_response_invalid_file_handling(self):
        """Test error response with invalid file."""
        response = _build_error_response(
            file="",
            theorem_id="MyTheorem",
            mode="aesop",
            error_message="Test error",
            error_code="test_error",
        )

        # Should use placeholder for invalid file
        assert "run_id" in response
        assert response["run_id"].startswith("probe-")

    def test_error_response_invalid_mode_handling(self):
        """Test error response with invalid mode."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            mode="invalid",
            error_message="Test error",
            error_code="test_error",
        )

        # Should use placeholder for invalid mode
        probe_result = response["probe_result"]
        assert probe_result["mode"] == "<invalid>"


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_budget_s_minimum_positive(self):
        """Test budget_s at minimum positive value."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": 0.001,
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 0.001

    def test_budget_s_large_value(self):
        """Test budget_s with large value."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": 3600.0,
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 3600.0

    def test_file_with_special_characters(self):
        """Test file path with special characters."""
        args = {
            "file": "path/to/my-file_v2.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "path/to/my-file_v2.lean"

    def test_theorem_id_with_dots(self):
        """Test theorem_id with dots (namespace separator)."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyNamespace.MyTheorem.proof",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.theorem_id == "MyNamespace.MyTheorem.proof"

    def test_trace_config_empty_dict(self):
        """Test trace_config with empty dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "trace_config": {},
        }

        cmd = _build_command(args)

        assert cmd.trace_config == {}

    def test_trace_config_multiple_options(self):
        """Test trace_config with multiple options."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "trace_config": {
                "trace.aesop": True,
                "trace.aesop.steps": True,
            },
        }

        cmd = _build_command(args)

        assert cmd.trace_config == {
            "trace.aesop": True,
            "trace.aesop.steps": True,
        }


class TestIntegrationScenarios:
    """Test integration scenarios with realistic inputs."""

    def test_aesop_probe_args(self):
        """Test arguments for aesop probe."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "theorem_id": "List.append_assoc",
            "mode": "aesop",
            "budget_s": 15.0,
        }

        cmd = _build_command(args)

        assert cmd.file_path == "Mathlib/Data/List/Basic.lean"
        assert cmd.theorem_id == "List.append_assoc"
        assert cmd.mode == "aesop"
        assert cmd.budget_s == 15.0

    def test_aesop_question_probe_args(self):
        """Test arguments for aesop? probe."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "theorem_id": "List.append_assoc",
            "mode": "aesop?",
            "budget_s": 20.0,
        }

        cmd = _build_command(args)

        assert cmd.mode == "aesop?"

    def test_grind_probe_args(self):
        """Test arguments for grind probe."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "theorem_id": "List.append_assoc",
            "mode": "grind",
            "budget_s": 10.0,
        }

        cmd = _build_command(args)

        assert cmd.mode == "grind"

    def test_quick_probe_args(self):
        """Test arguments for quick probe with small budget."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": 5.0,
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 5.0

    def test_detailed_probe_with_trace(self):
        """Test arguments for detailed probe with trace configuration."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "mode": "aesop",
            "budget_s": 30.0,
            "trace_config": {
                "trace.aesop": True,
                "trace.aesop.steps": True,
            },
        }

        cmd = _build_command(args)

        assert cmd.budget_s == 30.0
        assert cmd.trace_config is not None
        assert cmd.trace_config["trace.aesop"] is True


class TestErrorHandling:
    """Test cases for error handling in probe function.

    Requirements: 10.1-10.3, 10.5
    """

    def test_invalid_args_returns_error_response(self):
        """Test that invalid arguments return error response."""
        from lean_proof_auto_mcp.tools.probe import probe

        # Missing file argument
        result = probe({"theorem_id": "MyTheorem", "mode": "aesop"})

        assert result["status"] == "error"
        assert result["api_version"] == "0.1.0"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert len(result["diagnostics"]) == 1
        assert result["diagnostics"][0]["severity"] == "error"

    def test_empty_file_returns_error_response(self):
        """Test that empty file returns error response."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe({"file": "", "theorem_id": "MyTheorem", "mode": "aesop"})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'file' must be a non-empty string" in result["diagnostics"][0]["message"]

    def test_empty_theorem_id_returns_error_response(self):
        """Test that empty theorem_id returns error response."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe({"file": "test.lean", "theorem_id": "", "mode": "aesop"})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'theorem_id' must be a non-empty string" in result["diagnostics"][0]["message"]

    def test_invalid_mode_returns_error_response(self):
        """Test that invalid mode returns error response."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe(
            {
                "file": "test.lean",
                "theorem_id": "MyTheorem",
                "mode": "invalid",
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'mode' must be" in result["diagnostics"][0]["message"]

    def test_negative_budget_returns_error_response(self):
        """Test that negative budget returns error response."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe(
            {
                "file": "test.lean",
                "theorem_id": "MyTheorem",
                "mode": "aesop",
                "budget_s": -10.0,
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'budget_s' must be positive" in result["diagnostics"][0]["message"]

    def test_error_response_has_required_fields(self):
        """Test that error responses have all required fields."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe({"theorem_id": "MyTheorem", "mode": "aesop"})

        # Check all required fields are present
        required_fields = [
            "api_version",
            "status",
            "run_id",
            "probe_result",
            "diagnostics",
            "timing",
            "metadata",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_error_response_probe_result_structure(self):
        """Test that error response probe_result has correct structure."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe({"file": "", "theorem_id": "MyTheorem", "mode": "aesop"})

        probe_result = result["probe_result"]
        assert "mode" in probe_result
        assert "outcome" in probe_result
        assert "classification" in probe_result
        assert "suggested_script" in probe_result
        assert probe_result["outcome"] == "error"
        assert probe_result["classification"] == "error"

    def test_multiple_validation_errors_first_caught(self):
        """Test that first validation error is caught and returned."""
        from lean_proof_auto_mcp.tools.probe import probe

        # Multiple invalid arguments - should catch first one
        result = probe(
            {
                "file": "",
                "theorem_id": "",
                "mode": "invalid",
                "budget_s": -10.0,
            }
        )

        assert result["status"] == "error"
        # Should catch the file validation error first
        assert "'file' must be a non-empty string" in result["diagnostics"][0]["message"]

    def test_error_response_has_run_id(self):
        """Test that error response includes a run_id."""
        from lean_proof_auto_mcp.tools.probe import probe

        result = probe({"theorem_id": "MyTheorem", "mode": "aesop"})

        assert "run_id" in result
        assert result["run_id"].startswith("probe-")

    def test_no_unhandled_exceptions_escape(self):
        """Test that no unhandled exceptions escape from probe function.

        Requirements: 10.5
        """
        from lean_proof_auto_mcp.tools.probe import probe

        # Various invalid inputs should all return error responses, not raise exceptions
        test_cases = [
            {},
            {"file": None},
            {"file": 123},
            {"file": "test.lean"},
            {"file": "test.lean", "theorem_id": None},
            {"file": "test.lean", "theorem_id": "MyTheorem"},
            {"file": "test.lean", "theorem_id": "MyTheorem", "mode": None},
            {"file": "test.lean", "theorem_id": "MyTheorem", "mode": 123},
        ]

        for args in test_cases:
            result = probe(args)
            assert isinstance(result, dict)
            assert "status" in result
            assert result["status"] == "error"
