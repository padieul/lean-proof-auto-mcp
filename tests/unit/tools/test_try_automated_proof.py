"""
Unit tests for try_automated_proof tool argument validation and error handling.

Requirements: 7.3, 7.4, 7.5, 7.6, 4.3
"""

import pytest

from lean_proof_auto_mcp.tools.try_automated_proof import (
    _build_command,
    _build_error_response,
)


class TestBuildCommand:
    """Test cases for _build_command function."""

    def test_valid_minimal_args(self):
        """Test building command with minimal valid arguments."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        command, run_id = _build_command(args)

        assert command.file_path == "test.lean"
        assert command.theorem_id == "MyTheorem"
        assert command.proof_attempt == "exact rfl"
        assert command.timeout_s == 10.0  # Default
        assert command.return_proof_state is True  # Default
        assert run_id.startswith("try-proof-")

    def test_valid_full_args(self):
        """Test building command with all arguments."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "proof_attempt": "simp [add_comm]",
            "timeout_s": 20.0,
            "return_proof_state": False,
        }

        command, run_id = _build_command(args)

        assert command.file_path == "path/to/file.lean"
        assert command.theorem_id == "MyTheorem.proof"
        assert command.proof_attempt == "simp [add_comm]"
        assert command.timeout_s == 20.0
        assert command.return_proof_state is False

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        command, _ = _build_command(args)

        assert command.file_path == "test.lean"

    def test_theorem_id_whitespace_trimmed(self):
        """Test that theorem_id whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "  MyTheorem  ",
            "proof_attempt": "exact rfl",
        }

        command, _ = _build_command(args)

        assert command.theorem_id == "MyTheorem"

    def test_proof_attempt_whitespace_trimmed(self):
        """Test that proof_attempt whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "  exact rfl  ",
        }

        command, _ = _build_command(args)

        assert command.proof_attempt == "exact rfl"

    def test_missing_file_raises_error(self):
        """Test that missing file raises ValueError."""
        args = {
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_empty_file_raises_error(self):
        """Test that empty file raises ValueError."""
        args = {
            "file": "",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_missing_theorem_id_raises_error(self):
        """Test that missing theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_empty_theorem_id_raises_error(self):
        """Test that empty theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "",
            "proof_attempt": "exact rfl",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_missing_proof_attempt_raises_error(self):
        """Test that missing proof_attempt raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'proof_attempt' must be a non-empty string"):
            _build_command(args)

    def test_empty_proof_attempt_raises_error(self):
        """Test that empty proof_attempt raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "",
        }

        with pytest.raises(ValueError, match="'proof_attempt' must be a non-empty string"):
            _build_command(args)

    def test_negative_timeout_raises_error(self):
        """Test that negative timeout raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "timeout_s": -5.0,
        }

        with pytest.raises(ValueError, match="'timeout_s' must be a positive number"):
            _build_command(args)

    def test_zero_timeout_raises_error(self):
        """Test that zero timeout raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "timeout_s": 0.0,
        }

        with pytest.raises(ValueError, match="'timeout_s' must be a positive number"):
            _build_command(args)

    def test_non_boolean_return_proof_state_raises_error(self):
        """Test that non-boolean return_proof_state raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "return_proof_state": "yes",  # Should be boolean
        }

        with pytest.raises(ValueError, match="'return_proof_state' must be a boolean"):
            _build_command(args)

    def test_command_immutability(self):
        """Test that ValidateProofCommand is immutable (frozen dataclass)."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
        }

        command, _ = _build_command(args)

        # Attempting to modify should raise an error
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            command.file_path = "modified.lean"


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

        assert response["api_version"] == "1.1.0"
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

        command, _ = _build_command(args)

        assert command.timeout_s == 30.0

    def test_return_proof_state_true(self):
        """Test return_proof_state=True is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "return_proof_state": True,
        }

        command, _ = _build_command(args)

        assert command.return_proof_state is True

    def test_return_proof_state_false(self):
        """Test return_proof_state=False is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "proof_attempt": "exact rfl",
            "return_proof_state": False,
        }

        command, _ = _build_command(args)

        assert command.return_proof_state is False
