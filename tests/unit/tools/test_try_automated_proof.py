"""
Unit tests for try_automated_proof tool argument validation and error handling.

Requirements: 7.3, 7.4, 7.5, 7.6
"""

import pytest

from lean_proof_auto_mcp.tools.try_automated_proof import (
    _build_error_response,
    _validate_args,
)


class TestValidateArgs:
    """Test cases for _validate_args function."""

    def test_valid_minimal_args(self):
        """Test validating minimal valid arguments."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        file_path, theorem_id, proof_attempt, timeout_s, return_proof_state, run_id = (
            _validate_args(args)
        )

        assert file_path == "test.lean"
        assert theorem_id == "MyTheorem"
        assert proof_attempt == "exact rfl"
        assert timeout_s == 10.0  # Default
        assert return_proof_state is True  # Default
        assert run_id.startswith("try-proof-")

    def test_valid_full_args(self):
        """Test validating all arguments."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "proof_attempt": "simp [add_comm]",
            "timeout_s": 20.0,
            "return_proof_state": False,
        }

        file_path, theorem_id, proof_attempt, timeout_s, return_proof_state, run_id = (
            _validate_args(args)
        )

        assert file_path == "path/to/file.lean"
        assert theorem_id == "MyTheorem.proof"
        assert proof_attempt == "simp [add_comm]"
        assert timeout_s == 20.0
        assert return_proof_state is False

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        file_path, _, _, _, _, _ = _validate_args(args)

        assert file_path == "test.lean"

    def test_theorem_id_whitespace_trimmed(self):
        """Test that theorem_id whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "  MyTheorem  ",
            "proof_attempt": "exact rfl",
        }

        _, theorem_id, _, _, _, _ = _validate_args(args)

        assert theorem_id == "MyTheorem"

    def test_proof_attempt_whitespace_trimmed(self):
        """Test that proof_attempt whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "  exact rfl  ",
        }

        _, _, proof_attempt, _, _, _ = _validate_args(args)

        assert proof_attempt == "exact rfl"

    def test_missing_file_raises_error(self):
        """Test that missing file raises ValueError."""
        args = {
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _validate_args(args)

    def test_empty_file_raises_error(self):
        """Test that empty file raises ValueError."""
        args = {
            "file": "",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _validate_args(args)

    def test_missing_theorem_id_raises_error(self):
        """Test that missing theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _validate_args(args)

    def test_empty_theorem_id_raises_error(self):
        """Test that empty theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _validate_args(args)

    def test_missing_proof_attempt_raises_error(self):
        """Test that missing proof_attempt raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'proof_attempt' must be a non-empty string"):
            _validate_args(args)

    def test_empty_proof_attempt_raises_error(self):
        """Test that empty proof_attempt raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "",
        }

        with pytest.raises(ValueError, match="'proof_attempt' must be a non-empty string"):
            _validate_args(args)

    def test_negative_timeout_raises_error(self):
        """Test that negative timeout raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "timeout_s": -5.0,
        }

        with pytest.raises(ValueError, match="'timeout_s' must be a positive number"):
            _validate_args(args)

    def test_zero_timeout_raises_error(self):
        """Test that zero timeout raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "timeout_s": 0.0,
        }

        with pytest.raises(ValueError, match="'timeout_s' must be a positive number"):
            _validate_args(args)

    def test_non_boolean_return_proof_state_raises_error(self):
        """Test that non-boolean return_proof_state raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "return_proof_state": "yes",  # Should be boolean
        }

        with pytest.raises(ValueError, match="'return_proof_state' must be a boolean"):
            _validate_args(args)


class TestErrorResponse:
    """Test cases for error response formatting."""

    def test_error_response_structure(self):
        """Test error response has correct structure."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        assert response["api_version"] == "0.2.0"
        assert response["status"] == "error"
        assert "run_id" in response
        assert response["run_id"].startswith("try-proof-")
        assert response["file"] == "test.lean"
        assert response["theorem_id"] == "MyTheorem"
        assert response["validation_status"] == "error"
        assert response["error_message"] == "Test error"
        assert response["error_location"] is None
        assert response["proof_state"] is None
        assert "suggestions" in response
        assert "metadata" in response
        assert response["metadata"]["error_code"] == "test_error"
        assert response["metadata"]["error_message"] == "Test error"
        assert "timing" in response

    def test_error_response_with_invalid_file(self):
        """Test error response handles invalid file gracefully."""
        response = _build_error_response(
            file="",
            theorem_id="MyTheorem",
            error_message="Invalid file",
            error_code="input_validation_error",
        )

        assert response["file"] == "<invalid>"
        assert response["status"] == "error"

    def test_error_response_with_invalid_theorem_id(self):
        """Test error response handles invalid theorem_id gracefully."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="",
            error_message="Invalid theorem_id",
            error_code="input_validation_error",
        )

        assert response["theorem_id"] == "<invalid>"
        assert response["status"] == "error"


class TestValidationCases:
    """Test cases for different validation scenarios."""

    def test_timeout_parameter_respected(self):
        """Test that custom timeout is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "timeout_s": 30.0,
        }

        _, _, _, timeout_s, _, _ = _validate_args(args)

        assert timeout_s == 30.0

    def test_return_proof_state_true(self):
        """Test return_proof_state=True is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "return_proof_state": True,
        }

        _, _, _, _, return_proof_state, _ = _validate_args(args)

        assert return_proof_state is True

    def test_return_proof_state_false(self):
        """Test return_proof_state=False is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "return_proof_state": False,
        }

        _, _, _, _, return_proof_state, _ = _validate_args(args)

        assert return_proof_state is False
