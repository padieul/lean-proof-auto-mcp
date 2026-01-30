"""
Unit tests for get_proof_context tool argument validation and response formatting.

Requirements: 8.2, 8.3, 8.4, 8.5, 8.6
"""

import pytest

from lean_proof_auto_mcp.tools.get_proof_context import (
    _build_error_response,
    _format_response,
    _validate_args,
)
from lean_proof_auto_mcp.core.context_extractor import ProofContext, SimilarProof


class TestValidateArgs:
    """Test cases for _validate_args function."""

    def test_valid_minimal_args(self):
        """Test validating minimal valid arguments."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
        }

        file_path, theorem_id, include_similar, similarity_threshold, run_id = (
            _validate_args(args)
        )

        assert file_path == "test.lean"
        assert theorem_id == "MyTheorem"
        assert include_similar is True  # Default
        assert similarity_threshold == 0.7  # Default
        assert run_id.startswith("context-")

    def test_valid_full_args(self):
        """Test validating all arguments."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "include_similar_proofs": False,
            "similarity_threshold": 0.8,
        }

        file_path, theorem_id, include_similar, similarity_threshold, run_id = (
            _validate_args(args)
        )

        assert file_path == "path/to/file.lean"
        assert theorem_id == "MyTheorem.proof"
        assert include_similar is False
        assert similarity_threshold == 0.8

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "theorem_id": "MyTheorem",
        }

        file_path, _, _, _, _ = _validate_args(args)

        assert file_path == "test.lean"

    def test_theorem_id_whitespace_trimmed(self):
        """Test that theorem_id whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "  MyTheorem  ",
        }

        _, theorem_id, _, _, _ = _validate_args(args)

        assert theorem_id == "MyTheorem"

    def test_missing_file_raises_error(self):
        """Test that missing file raises ValueError."""
        args = {
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _validate_args(args)

    def test_empty_file_raises_error(self):
        """Test that empty file raises ValueError."""
        args = {
            "file": "",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _validate_args(args)

    def test_missing_theorem_id_raises_error(self):
        """Test that missing theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _validate_args(args)

    def test_empty_theorem_id_raises_error(self):
        """Test that empty theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _validate_args(args)

    def test_non_boolean_include_similar_raises_error(self):
        """Test that non-boolean include_similar_proofs raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "include_similar_proofs": "yes",  # Should be boolean
        }

        with pytest.raises(ValueError, match="'include_similar_proofs' must be a boolean"):
            _validate_args(args)

    def test_non_numeric_similarity_threshold_raises_error(self):
        """Test that non-numeric similarity_threshold raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "similarity_threshold": "high",  # Should be numeric
        }

        with pytest.raises(ValueError, match="'similarity_threshold' must be a number"):
            _validate_args(args)

    def test_similarity_threshold_below_zero_raises_error(self):
        """Test that similarity_threshold below 0.0 raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "similarity_threshold": -0.1,
        }

        with pytest.raises(
            ValueError, match="'similarity_threshold' must be between 0.0 and 1.0"
        ):
            _validate_args(args)

    def test_similarity_threshold_above_one_raises_error(self):
        """Test that similarity_threshold above 1.0 raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "similarity_threshold": 1.5,
        }

        with pytest.raises(
            ValueError, match="'similarity_threshold' must be between 0.0 and 1.0"
        ):
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
        assert response["run_id"].startswith("context-")
        assert response["file"] == "test.lean"
        assert response["theorem_id"] == "MyTheorem"
        assert response["theorem_statement"] == ""
        assert response["original_proof"] == ""
        assert response["hypotheses"] == []
        assert response["in_scope"] == []
        assert response["namespace"] == ""
        assert response["similar_proofs"] == []
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


class TestContextExtraction:
    """Test cases for context extraction response formatting."""

    def test_format_response_without_similar_proofs(self):
        """Test formatting response without similar proofs."""
        # Create a ProofContext without similar proofs
        context = ProofContext(
            theorem_statement="theorem add_comm (a b : Nat) : a + b = b + a",
            original_proof="by simp [Nat.add_comm]",
            hypotheses=["a : Nat", "b : Nat"],
            in_scope=["Nat.add_comm", "Nat.add_assoc"],
            namespace="MyNamespace",
            similar_proofs=[],
        )

        metadata = {
            "repo_commit": "abc123",
            "lean_version": "4.0.0",
            "lake_version": "1.0.0",
        }

        response = _format_response(
            context=context,
            file_path="test.lean",
            theorem_id="add_comm",
            run_id="context-20240101-12345678-abcdef",
            metadata=metadata,
        )

        # Verify response structure
        assert response["api_version"] == "0.2.0"
        assert response["status"] == "success"
        assert response["run_id"] == "context-20240101-12345678-abcdef"
        assert response["file"] == "test.lean"
        assert response["theorem_id"] == "add_comm"
        assert response["theorem_statement"] == "theorem add_comm (a b : Nat) : a + b = b + a"
        assert response["original_proof"] == "by simp [Nat.add_comm]"
        assert response["hypotheses"] == ["a : Nat", "b : Nat"]
        assert response["in_scope"] == ["Nat.add_comm", "Nat.add_assoc"]
        assert response["namespace"] == "MyNamespace"
        assert response["similar_proofs"] == []
        assert response["metadata"] == metadata
        assert "timing" in response

    def test_format_response_with_similar_proofs(self):
        """Test formatting response with similar proofs."""
        # Create similar proofs
        similar_proofs = [
            SimilarProof(
                theorem_id="mul_comm",
                similarity=0.85,
                theorem_statement="theorem mul_comm (a b : Nat) : a * b = b * a",
                proof="by simp [Nat.mul_comm]",
                hints_used=["Nat.mul_comm"],
            ),
            SimilarProof(
                theorem_id="sub_comm",
                similarity=0.75,
                theorem_statement="theorem sub_comm (a b : Nat) : a - b = b - a",
                proof="by omega",
                hints_used=[],
            ),
        ]

        # Create a ProofContext with similar proofs
        context = ProofContext(
            theorem_statement="theorem add_comm (a b : Nat) : a + b = b + a",
            original_proof="by simp [Nat.add_comm]",
            hypotheses=["a : Nat", "b : Nat"],
            in_scope=["Nat.add_comm", "Nat.add_assoc"],
            namespace="MyNamespace",
            similar_proofs=similar_proofs,
        )

        metadata = {"repo_commit": "abc123"}

        response = _format_response(
            context=context,
            file_path="test.lean",
            theorem_id="add_comm",
            run_id="context-20240101-12345678-abcdef",
            metadata=metadata,
        )

        # Verify similar proofs are included
        assert len(response["similar_proofs"]) == 2

        # Verify first similar proof
        similar1 = response["similar_proofs"][0]
        assert similar1["theorem_id"] == "mul_comm"
        assert similar1["similarity"] == 0.85
        assert similar1["theorem_statement"] == "theorem mul_comm (a b : Nat) : a * b = b * a"
        assert similar1["proof"] == "by simp [Nat.mul_comm]"
        assert similar1["hints_used"] == ["Nat.mul_comm"]

        # Verify second similar proof
        similar2 = response["similar_proofs"][1]
        assert similar2["theorem_id"] == "sub_comm"
        assert similar2["similarity"] == 0.75
        assert similar2["theorem_statement"] == "theorem sub_comm (a b : Nat) : a - b = b - a"
        assert similar2["proof"] == "by omega"
        assert similar2["hints_used"] == []

    def test_format_response_with_empty_context(self):
        """Test formatting response with minimal context."""
        # Create a minimal ProofContext
        context = ProofContext(
            theorem_statement="theorem trivial : True",
            original_proof="trivial",
            hypotheses=[],
            in_scope=[],
            namespace="",
            similar_proofs=[],
        )

        metadata = {}

        response = _format_response(
            context=context,
            file_path="test.lean",
            theorem_id="trivial",
            run_id="context-20240101-12345678-abcdef",
            metadata=metadata,
        )

        # Verify response handles empty fields
        assert response["theorem_statement"] == "theorem trivial : True"
        assert response["original_proof"] == "trivial"
        assert response["hypotheses"] == []
        assert response["in_scope"] == []
        assert response["namespace"] == ""
        assert response["similar_proofs"] == []
        assert response["metadata"] == {}


class TestJSONResponseFormat:
    """Test cases for JSON response format compliance."""

    def test_response_is_json_serializable(self):
        """Test that response can be serialized to JSON."""
        import json

        context = ProofContext(
            theorem_statement="theorem test : True",
            original_proof="trivial",
            hypotheses=["h : True"],
            in_scope=["True"],
            namespace="Test",
            similar_proofs=[],
        )

        response = _format_response(
            context=context,
            file_path="test.lean",
            theorem_id="test",
            run_id="context-20240101-12345678-abcdef",
            metadata={"key": "value"},
        )

        # Should not raise exception
        json_str = json.dumps(response)
        assert isinstance(json_str, str)

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["status"] == "success"
        assert parsed["theorem_id"] == "test"

    def test_error_response_is_json_serializable(self):
        """Test that error response can be serialized to JSON."""
        import json

        response = _build_error_response(
            file="test.lean",
            theorem_id="test",
            error_message="Test error",
            error_code="test_error",
        )

        # Should not raise exception
        json_str = json.dumps(response)
        assert isinstance(json_str, str)

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["status"] == "error"
        assert parsed["metadata"]["error_code"] == "test_error"


class TestParameterValidation:
    """Test cases for parameter validation edge cases."""

    def test_include_similar_proofs_true(self):
        """Test include_similar_proofs=True is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "include_similar_proofs": True,
        }

        _, _, include_similar, _, _ = _validate_args(args)

        assert include_similar is True

    def test_include_similar_proofs_false(self):
        """Test include_similar_proofs=False is respected."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "include_similar_proofs": False,
        }

        _, _, include_similar, _, _ = _validate_args(args)

        assert include_similar is False

    def test_similarity_threshold_zero(self):
        """Test similarity_threshold=0.0 is valid."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "similarity_threshold": 0.0,
        }

        _, _, _, similarity_threshold, _ = _validate_args(args)

        assert similarity_threshold == 0.0

    def test_similarity_threshold_one(self):
        """Test similarity_threshold=1.0 is valid."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "similarity_threshold": 1.0,
        }

        _, _, _, similarity_threshold, _ = _validate_args(args)

        assert similarity_threshold == 1.0

    def test_similarity_threshold_integer_coerced_to_float(self):
        """Test that integer similarity_threshold is coerced to float."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "similarity_threshold": 1,  # Integer
        }

        _, _, _, similarity_threshold, _ = _validate_args(args)

        assert similarity_threshold == 1.0
        assert isinstance(similarity_threshold, float)
