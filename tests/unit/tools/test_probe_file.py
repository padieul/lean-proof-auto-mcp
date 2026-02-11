"""Unit tests for probe_file tool argument validation and error handling.

Requirements: 10.4-10.5
"""

import pytest

from lean_proof_auto_mcp.tools.probe_file import _build_command, _build_error_response


class TestBuildCommand:
    """Test cases for _build_command function."""

    def test_valid_minimal_args(self):
        """Test building command with minimal valid arguments."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "test.lean"
        assert cmd.mode == "aesop"
        assert cmd.budget_s_per == 30.0  # Default
        assert cmd.limit == 50  # Default
        assert cmd.ordering == "file_order"  # Default

    def test_valid_full_args(self):
        """Test building command with all arguments specified."""
        args = {
            "file": "path/to/file.lean",
            "mode": "aesop?",
            "budget_s_per": 10.0,
            "limit": 100,
            "ordering": "rank_targets",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "path/to/file.lean"
        assert cmd.mode == "aesop?"
        assert cmd.budget_s_per == 10.0
        assert cmd.limit == 100
        assert cmd.ordering == "rank_targets"

    def test_valid_with_grind_mode(self):
        """Test building command with grind mode."""
        args = {
            "file": "test.lean",
            "mode": "grind",
        }

        cmd = _build_command(args)

        assert cmd.mode == "grind"

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "test.lean"

    def test_budget_s_per_integer_coerced_to_float(self):
        """Test that integer budget_s_per is coerced to float."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": 10,
        }

        cmd = _build_command(args)

        assert cmd.budget_s_per == 10.0
        assert isinstance(cmd.budget_s_per, float)

    def test_missing_file(self):
        """Test error when file is missing."""
        args = {
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_empty_file(self):
        """Test error when file is empty string."""
        args = {
            "file": "",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_whitespace_only_file(self):
        """Test error when file is whitespace only."""
        args = {
            "file": "   ",
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_non_string_file(self):
        """Test error when file is not a string."""
        args = {
            "file": 123,
            "mode": "aesop",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_missing_mode(self):
        """Test error when mode is missing."""
        args = {
            "file": "test.lean",
        }

        with pytest.raises(ValueError, match="'mode' must be a string"):
            _build_command(args)

    def test_non_string_mode(self):
        """Test error when mode is not a string."""
        args = {
            "file": "test.lean",
            "mode": 123,
        }

        with pytest.raises(ValueError, match="'mode' must be a string"):
            _build_command(args)

    def test_invalid_mode(self):
        """Test error when mode is invalid."""
        args = {
            "file": "test.lean",
            "mode": "invalid",
        }

        with pytest.raises(ValueError, match="'mode' must be 'aesop', 'aesop\\?', or 'grind'"):
            _build_command(args)

    def test_non_numeric_budget_s_per(self):
        """Test error when budget_s_per is not a number."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": "10",
        }

        with pytest.raises(ValueError, match="'budget_s_per' must be a number"):
            _build_command(args)

    def test_negative_budget_s_per(self):
        """Test error when budget_s_per is negative."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": -5.0,
        }

        with pytest.raises(ValueError, match="'budget_s_per' must be positive"):
            _build_command(args)

    def test_zero_budget_s_per(self):
        """Test error when budget_s_per is zero."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": 0.0,
        }

        with pytest.raises(ValueError, match="'budget_s_per' must be positive"):
            _build_command(args)

    def test_non_integer_limit(self):
        """Test error when limit is not an integer."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "limit": 10.5,
        }

        with pytest.raises(ValueError, match="'limit' must be an integer"):
            _build_command(args)

    def test_negative_limit(self):
        """Test error when limit is negative."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "limit": -10,
        }

        with pytest.raises(ValueError, match="'limit' must be positive"):
            _build_command(args)

    def test_zero_limit(self):
        """Test error when limit is zero."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "limit": 0,
        }

        with pytest.raises(ValueError, match="'limit' must be positive"):
            _build_command(args)

    def test_non_string_ordering(self):
        """Test error when ordering is not a string."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "ordering": 123,
        }

        with pytest.raises(ValueError, match="'ordering' must be a string"):
            _build_command(args)

    def test_invalid_ordering(self):
        """Test error when ordering is invalid."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "ordering": "invalid",
        }

        with pytest.raises(ValueError, match="'ordering' must be 'file_order' or 'rank_targets'"):
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
        assert "file" in response
        assert "summary" in response
        assert "results" in response
        assert "metadata" in response

    def test_error_response_values(self):
        """Test that error response has correct values."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        assert response["api_version"] == "0.1.0"
        assert response["status"] == "error"
        assert response["file"] == "test.lean"

    def test_error_response_summary(self):
        """Test that error response has correct summary."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        summary = response["summary"]
        assert summary["total"] == 0
        assert summary["closed"] == 0
        assert summary["promising"] == 0
        assert summary["failed"] == 0
        assert summary["timed_out"] == 0

    def test_error_response_results_empty(self):
        """Test that error response has empty results."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error",
            error_code="test_error",
        )

        results = response["results"]
        assert isinstance(results, list)
        assert len(results) == 0

    def test_error_response_metadata(self):
        """Test that error response has correct metadata."""
        response = _build_error_response(
            file="test.lean",
            error_message="Test error message",
            error_code="test_error_code",
        )

        metadata = response["metadata"]
        assert metadata["error_code"] == "test_error_code"
        assert metadata["error"] == "Test error message"
        assert metadata["elapsed_ms"] == 0.0

    def test_error_response_invalid_file_handling(self):
        """Test error response with invalid file."""
        response = _build_error_response(
            file="",
            error_message="Test error",
            error_code="test_error",
        )

        # Should use placeholder for invalid file
        assert response["file"] == "<invalid>"

    def test_error_response_none_file_handling(self):
        """Test error response with None file."""
        response = _build_error_response(
            file=None,
            error_message="Test error",
            error_code="test_error",
        )

        # Should use placeholder for None file
        assert response["file"] == "<invalid>"


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_budget_s_per_minimum_positive(self):
        """Test budget_s_per at minimum positive value."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": 0.001,
        }

        cmd = _build_command(args)

        assert cmd.budget_s_per == 0.001

    def test_budget_s_per_large_value(self):
        """Test budget_s_per with large value."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": 3600.0,
        }

        cmd = _build_command(args)

        assert cmd.budget_s_per == 3600.0

    def test_limit_minimum_positive(self):
        """Test limit at minimum positive value."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "limit": 1,
        }

        cmd = _build_command(args)

        assert cmd.limit == 1

    def test_limit_large_value(self):
        """Test limit with large value."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "limit": 10000,
        }

        cmd = _build_command(args)

        assert cmd.limit == 10000

    def test_file_with_special_characters(self):
        """Test file path with special characters."""
        args = {
            "file": "path/to/my-file_v2.lean",
            "mode": "aesop",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "path/to/my-file_v2.lean"


class TestIntegrationScenarios:
    """Test integration scenarios with realistic inputs."""

    def test_file_order_probe_file_args(self):
        """Test arguments for probe_file with file_order."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "mode": "aesop",
            "budget_s_per": 5.0,
            "limit": 50,
            "ordering": "file_order",
        }

        cmd = _build_command(args)

        assert cmd.file_path == "Mathlib/Data/List/Basic.lean"
        assert cmd.mode == "aesop"
        assert cmd.budget_s_per == 5.0
        assert cmd.limit == 50
        assert cmd.ordering == "file_order"

    def test_rank_targets_probe_file_args(self):
        """Test arguments for probe_file with rank_targets."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "mode": "aesop?",
            "budget_s_per": 10.0,
            "limit": 20,
            "ordering": "rank_targets",
        }

        cmd = _build_command(args)

        assert cmd.ordering == "rank_targets"

    def test_quick_probe_file_args(self):
        """Test arguments for quick probe_file with small budget and limit."""
        args = {
            "file": "test.lean",
            "mode": "aesop",
            "budget_s_per": 2.0,
            "limit": 10,
        }

        cmd = _build_command(args)

        assert cmd.budget_s_per == 2.0
        assert cmd.limit == 10

    def test_comprehensive_probe_file_args(self):
        """Test arguments for comprehensive probe_file with large limit."""
        args = {
            "file": "test.lean",
            "mode": "grind",
            "budget_s_per": 15.0,
            "limit": 200,
        }

        cmd = _build_command(args)

        assert cmd.budget_s_per == 15.0
        assert cmd.limit == 200


class TestErrorHandling:
    """Test cases for error handling in probe_file function.

    Requirements: 10.4-10.5
    """

    def test_invalid_args_returns_error_response(self):
        """Test that invalid arguments return error response."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        # Missing file argument
        result = probe_file({"mode": "aesop"})

        assert result["status"] == "error"
        assert result["api_version"] == "0.1.0"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "error" in result["metadata"]

    def test_empty_file_returns_error_response(self):
        """Test that empty file returns error response."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file({"file": "", "mode": "aesop"})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'file' must be a non-empty string" in result["metadata"]["error"]

    def test_invalid_mode_returns_error_response(self):
        """Test that invalid mode returns error response."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file(
            {
                "file": "test.lean",
                "mode": "invalid",
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'mode' must be" in result["metadata"]["error"]

    def test_negative_budget_s_per_returns_error_response(self):
        """Test that negative budget_s_per returns error response."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file(
            {
                "file": "test.lean",
                "mode": "aesop",
                "budget_s_per": -5.0,
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'budget_s_per' must be positive" in result["metadata"]["error"]

    def test_negative_limit_returns_error_response(self):
        """Test that negative limit returns error response."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file(
            {
                "file": "test.lean",
                "mode": "aesop",
                "limit": -10,
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'limit' must be positive" in result["metadata"]["error"]

    def test_invalid_ordering_returns_error_response(self):
        """Test that invalid ordering returns error response."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file(
            {
                "file": "test.lean",
                "mode": "aesop",
                "ordering": "invalid",
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'ordering' must be" in result["metadata"]["error"]

    def test_error_response_has_required_fields(self):
        """Test that error responses have all required fields."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file({"mode": "aesop"})

        # Check all required fields are present
        required_fields = [
            "api_version",
            "status",
            "file",
            "summary",
            "results",
            "metadata",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_error_response_summary_structure(self):
        """Test that error response summary has correct structure."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file({"file": "", "mode": "aesop"})

        summary = result["summary"]
        assert "total" in summary
        assert "closed" in summary
        assert "promising" in summary
        assert "failed" in summary
        assert "timed_out" in summary
        assert summary["total"] == 0

    def test_error_response_results_is_list(self):
        """Test that error response results is a list."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        result = probe_file({"file": "", "mode": "aesop"})

        assert isinstance(result["results"], list)
        assert len(result["results"]) == 0

    def test_multiple_validation_errors_first_caught(self):
        """Test that first validation error is caught and returned."""
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        # Multiple invalid arguments - should catch first one
        result = probe_file(
            {
                "file": "",
                "mode": "invalid",
                "budget_s_per": -5.0,
                "limit": -10,
            }
        )

        assert result["status"] == "error"
        # Should catch the file validation error first
        assert "'file' must be a non-empty string" in result["metadata"]["error"]

    def test_no_unhandled_exceptions_escape(self):
        """Test that no unhandled exceptions escape from probe_file function.

        Requirements: 10.5
        """
        from lean_proof_auto_mcp.tools.probe_file import probe_file

        # Various invalid inputs should all return error responses, not raise exceptions
        test_cases = [
            {},
            {"file": None},
            {"file": 123},
            {"file": "test.lean"},
            {"file": "test.lean", "mode": None},
            {"file": "test.lean", "mode": 123},
            {"file": "test.lean", "mode": "aesop", "budget_s_per": "10"},
            {"file": "test.lean", "mode": "aesop", "limit": 10.5},
            {"file": "test.lean", "mode": "aesop", "ordering": 123},
        ]

        for args in test_cases:
            result = probe_file(args)
            assert isinstance(result, dict)
            assert "status" in result
            assert result["status"] == "error"
