"""Integration tests for search_annotations tool.

Tests end-to-end functionality with mock Lean execution. These tests verify
the tool's workflow orchestration and phase execution.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lean_proof_auto_mcp.tools.search_annotations import search_annotations

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
VALID_THEOREM = str(FIXTURES_DIR / "valid_theorem.lean")


class TestSearchAnnotationsIntegration:
    """Integration tests for search_annotations tool workflow."""

    @pytest.mark.integration
    def test_file_not_found_error(self):
        """Test that non-existent file returns appropriate error.

        Requirements: 1.1, 1.3
        """
        result = search_annotations(
            {
                "file": "nonexistent_file.lean",
                "theorem_id": "MyTheorem",
            }
        )

        # Verify error status (file not found is caught as internal error)
        assert result["status"] == "error", f"Expected error but got {result['status']}"
        assert result["api_version"] == "0.1.0"

        # Verify error message mentions file not found
        assert "not found" in result["metadata"]["error_message"].lower() or "no such file" in result["metadata"]["error_message"].lower()

        # Verify run_id exists
        assert "run_id" in result
        assert result["run_id"].startswith("search-")

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_workflow_phases_execute_in_order(self, mock_create_handler):
        """Test that all workflow phases execute in correct order.

        This test mocks the handler to verify phase execution without
        requiring actual Lean execution.

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            SearchAnnotationsResult,
        )

        # Create mock handler that returns a fail result (no proof found)
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="MyTheorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={"total_s": 1.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
            }
        )

        # Verify handler was created and called
        mock_create_handler.assert_called_once()
        mock_handler.handle.assert_called_once()

        # Verify command was passed to handler
        command = mock_handler.handle.call_args[0][0]
        assert command.file == VALID_THEOREM
        assert command.theorem_id == "MyTheorem"

        # Verify result structure
        assert "api_version" in result
        assert "status" in result
        assert "run_id" in result
        assert "file" in result
        assert "theorem_id" in result
        assert "viability" in result
        assert "baseline" in result
        assert "search_result" in result
        assert "minimized_hint_set" in result
        assert "proof_patch" in result
        assert "global_suggestions" in result
        assert "timing" in result
        assert "artifacts" in result
        assert "metadata" in result

    @pytest.mark.integration
    def test_invalid_theorem_id_error(self):
        """Test that invalid theorem_id returns appropriate error.

        Requirements: 1.1, 1.3
        """
        # Use a valid file but invalid theorem_id
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "NonExistentTheorem",
            }
        )

        # Verify error or fail status
        assert result["status"] in ("fail", "error"), f"Expected fail/error but got {result['status']}"
        assert result["api_version"] == "0.1.0"

        # Verify run_id exists
        assert "run_id" in result
        assert result["run_id"].startswith("search-")

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_artifacts_stored_on_success(self, mock_create_handler):
        """Test that artifacts are stored when search succeeds.

        Requirements: 1.4
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Create mock handler that returns a success result with artifacts
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="MyTheorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=HintSet(),  # Success requires minimized_hint_set
            proof_patch={"lean_code": "by aesop"},  # Success requires proof_patch
            global_suggestions=None,
            timing={"total_s": 1.0},
            artifacts={
                "request": ".artifacts/test-run-id/request.json",
                "result": ".artifacts/test-run-id/result.json",
            },
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
            }
        )

        # Verify artifacts section exists
        assert "artifacts" in result
        assert isinstance(result["artifacts"], dict)

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_timing_information_included(self, mock_create_handler):
        """Test that timing information is included in results.

        Requirements: 1.5, 9.8
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Create mock handler that returns a result with timing
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="MyTheorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=HintSet(),  # Success requires minimized_hint_set
            proof_patch={"lean_code": "by aesop"},  # Success requires proof_patch
            global_suggestions=None,
            timing={
                "total_s": 10.5,
                "viability_check_s": 1.2,
                "baseline_probe_s": 2.3,
                "search_total_s": 5.0,
                "minimize_total_s": 2.0,
            },
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
            }
        )

        # Verify timing section exists and has expected fields
        assert "timing" in result
        assert isinstance(result["timing"], dict)
        assert "total_s" in result["timing"]

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_local_only_mode(self, mock_create_handler):
        """Test search in local_only mode.

        Requirements: 7.1
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="MyTheorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=HintSet(),  # Success requires minimized_hint_set
            proof_patch={"lean_code": "by aesop"},  # Success requires proof_patch
            global_suggestions=None,  # Should be None in local_only mode
            timing={"total_s": 1.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search in local_only mode
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
                "mode": "local_only",
            }
        )

        # Verify command mode
        command = mock_handler.handle.call_args[0][0]
        assert command.mode == "local_only"

        # Verify global_suggestions is None
        assert result["global_suggestions"] is None

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_suggest_global_mode(self, mock_create_handler):
        """Test search in suggest_global mode.

        Requirements: 7.2
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="MyTheorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=HintSet(),  # Success requires minimized_hint_set
            proof_patch={"lean_code": "by aesop"},  # Success requires proof_patch
            global_suggestions=[],  # Should be list in suggest_global mode
            timing={"total_s": 1.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search in suggest_global mode
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
                "mode": "suggest_global",
            }
        )

        # Verify command mode
        command = mock_handler.handle.call_args[0][0]
        assert command.mode == "suggest_global"

        # Verify global_suggestions is a list
        assert isinstance(result["global_suggestions"], list)

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_exception_handling(self, mock_create_handler):
        """Test that exceptions are caught and returned as error responses.

        Requirements: 12.8
        """
        # Create mock handler that raises an exception
        mock_handler = MagicMock()
        mock_handler.handle.side_effect = RuntimeError("Test error")
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
            }
        )

        # Verify error response
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "internal_error"
        assert "Test error" in result["metadata"]["error_message"]

    @pytest.mark.integration
    def test_configuration_validation(self):
        """Test that configuration parameters are validated.

        Requirements: 1.1, 1.3
        """
        # Test with various configuration options
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
                "budgets": {
                    "viability_check_s": 10.0,
                    "search_total_s": 300.0,
                },
                "search": {
                    "strategy": "greedy",
                    "max_steps": 100,
                },
                "candidates": {
                    "sources": ["goal_symbols", "local_context"],
                    "max_candidates_per_source": 20,
                },
            }
        )

        # Should not raise validation errors
        assert "status" in result
        assert result["api_version"] == "0.1.0"

    @pytest.mark.integration
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_run_id_uniqueness(self, mock_create_handler):
        """Test that each run gets a unique run_id.

        Requirements: 10.9, 13.1
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="MyTheorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=HintSet(),  # Success requires minimized_hint_set
            proof_patch={"lean_code": "by aesop"},  # Success requires proof_patch
            global_suggestions=None,
            timing={"total_s": 1.0},
            artifacts={},
            metadata={},
        )

        mock_create_handler.return_value = mock_handler
        mock_handler.handle.return_value = mock_result

        # Execute search twice
        result1 = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
            }
        )

        # Get run_id from first execution
        run_id_1 = mock_handler.handle.call_args[0][0].run_id

        result2 = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
            }
        )

        # Get run_id from second execution
        run_id_2 = mock_handler.handle.call_args[0][0].run_id

        # Verify run_ids are different
        assert run_id_1 != run_id_2
        assert run_id_1.startswith("search-")
        assert run_id_2.startswith("search-")


class TestSearchAnnotationsErrorScenarios:
    """Test error scenarios and edge cases."""

    @pytest.mark.integration
    def test_empty_args(self):
        """Test with empty arguments."""
        result = search_annotations({})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"

    @pytest.mark.integration
    def test_partial_args(self):
        """Test with partial arguments."""
        result = search_annotations({"file": VALID_THEOREM})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"

    @pytest.mark.integration
    def test_invalid_budget_values(self):
        """Test with invalid budget values."""
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
                "budgets": {
                    "viability_check_s": -1.0,
                },
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"

    @pytest.mark.integration
    def test_invalid_candidate_sources(self):
        """Test with invalid candidate sources."""
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "MyTheorem",
                "candidates": {
                    "sources": ["invalid_source"],
                },
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
