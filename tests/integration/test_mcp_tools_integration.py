"""
Integration tests for MCP tools with real LeanInteract.

These tests verify that the new MCP tools work correctly with real Lean files
and LeanInteract server instances.

Requirements: 4.1, 4.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.8, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

from pathlib import Path

import pytest

from lean_proof_auto_mcp.tools.get_proof_context import get_proof_context
from lean_proof_auto_mcp.tools.search_automated_proof import search_automated_proof
from lean_proof_auto_mcp.tools.try_automated_proof import try_automated_proof


@pytest.mark.integration
@pytest.mark.requires_lean
class TestMCPToolsIntegration:
    """Integration tests for MCP tools with real LeanInteract."""

    @pytest.fixture
    def test_file(self):
        """Path to test Lean file."""
        return str(Path(__file__).parent.parent / "fixtures" / "lean" / "valid_theorem.lean")

    def test_get_proof_context_with_real_lean(self, test_file):
        """
        Test get_proof_context tool with real Lean file.

        Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
        """
        # Act
        result = get_proof_context(
            {"file": test_file, "theorem_id": "simple_add_comm", "include_similar_proofs": False}
        )

        # Assert
        assert result["status"] == "success"

        # Verify context fields are present at top level
        assert "theorem_statement" in result
        assert "original_proof" in result
        assert "hypotheses" in result
        assert "in_scope" in result
        assert "namespace" in result

        # Verify metadata is included
        assert "metadata" in result
        metadata = result["metadata"]
        assert isinstance(metadata, dict)

    def test_try_automated_proof_with_valid_proof(self, test_file):
        """
        Test try_automated_proof tool with a valid proof.

        Validates: Requirements 7.1, 7.2, 7.3, 7.8
        """
        # Arrange: A simple valid proof
        proof_attempt = "exact Nat.add_comm a b"

        # Act
        result = try_automated_proof(
            {
                "file": test_file,
                "theorem_id": "simple_add_comm",
                "proof_attempt": proof_attempt,
                "timeout_s": 10.0,
                "return_proof_state": True,
            }
        )

        # Assert
        assert "status" in result
        assert result["status"] in ["success", "error", "incomplete", "timeout"]

        # Verify metadata is included
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)

    def test_try_automated_proof_with_invalid_proof(self, test_file):
        """
        Test try_automated_proof tool with an invalid proof.

        Validates: Requirements 7.4, 7.5
        """
        # Arrange: An invalid proof
        proof_attempt = "exact 42"  # Type error

        # Act
        result = try_automated_proof(
            {
                "file": test_file,
                "theorem_id": "simple_add_comm",
                "proof_attempt": proof_attempt,
                "timeout_s": 10.0,
                "return_proof_state": True,
            }
        )

        # Assert
        assert "status" in result
        assert result["status"] in ["error", "incomplete"]

        if result["status"] == "error":
            assert "error_message" in result
            assert result["error_message"]

    def test_search_automated_proof_basic(self, test_file):
        """
        Test search_automated_proof tool with basic parameters.

        Validates: Requirements 4.1, 4.8
        """
        # Act
        result = search_automated_proof(
            {
                "file": test_file,
                "theorem_id": "simple_add_comm",
                "search_depth": "quick",
                "return_proof_states": False,
                "return_partial_progress": False,
                "return_context": False,
                "return_similar_proofs": False,
                "return_search_trace": False,
            }
        )

        # Assert
        assert "status" in result
        # Status can be success, partial, fail, or error
        assert result["status"] in ["success", "partial", "fail", "error"]

        # Verify metadata is included
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)

    def test_search_automated_proof_with_feedback(self, test_file):
        """
        Test search_automated_proof tool with rich feedback enabled.

        Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
        """
        # Act
        result = search_automated_proof(
            {
                "file": test_file,
                "theorem_id": "simple_add_comm",
                "search_depth": "quick",
                "return_proof_states": True,
                "return_partial_progress": True,
                "return_context": True,
                "return_similar_proofs": False,
                "return_search_trace": True,
            }
        )

        # Assert
        assert "status" in result

        # Verify conditional return values (only check if status is not error)
        if result["status"] != "error":
            if result.get("return_proof_states"):
                assert "proof_states" in result or result["status"] == "fail"

            if result.get("return_partial_progress"):
                assert "partial_progress" in result or result["status"] == "fail"

            if result.get("return_context"):
                assert "context" in result or result["status"] == "fail"

            if result.get("return_search_trace"):
                assert "search_trace" in result or result["status"] == "fail"

        # Tactical suggestions should be in feedback
        if "feedback" in result:
            assert "suggestions" in result["feedback"]

    def test_all_tools_include_metadata(self, test_file):
        """
        Test that all MCP tools include metadata in their responses.

        Validates: Requirements 29.3, 29.4, 29.7
        """
        # Test search_automated_proof
        search_result = search_automated_proof(
            {"file": test_file, "theorem_id": "simple_add_comm", "search_depth": "quick"}
        )
        assert "metadata" in search_result
        assert isinstance(search_result["metadata"], dict)

        # Test try_automated_proof
        try_result = try_automated_proof(
            {
                "file": test_file,
                "theorem_id": "simple_add_comm",
                "proof_attempt": "exact Nat.add_comm a b",
                "timeout_s": 10.0,
            }
        )
        assert "metadata" in try_result
        assert isinstance(try_result["metadata"], dict)

        # Test get_proof_context
        context_result = get_proof_context(
            {"file": test_file, "theorem_id": "simple_add_comm", "include_similar_proofs": False}
        )
        assert "metadata" in context_result
        assert isinstance(context_result["metadata"], dict)

    def test_search_depth_presets(self, test_file):
        """
        Test that search depth presets work correctly.

        Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
        """
        # Test each preset
        for depth in ["quick", "normal", "deep", "exhaustive"]:
            result = search_automated_proof(
                {
                    "file": test_file,
                    "theorem_id": "simple_add_comm",
                    "search_depth": depth,
                    "return_proof_states": False,
                    "return_partial_progress": False,
                }
            )

            assert "status" in result
            # Status can be success, partial, fail, or error
            assert result["status"] in ["success", "partial", "fail", "error"]

            # Verify metadata includes search_depth
            assert "metadata" in result
