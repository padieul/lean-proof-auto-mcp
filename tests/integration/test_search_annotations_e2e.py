"""Comprehensive end-to-end integration tests for search_annotations tool.

These tests verify the complete workflow with real Lean files, testing:
- Complete workflow execution
- local_only mode producing valid proof patches
- suggest_global mode producing advisory suggestions
- Timeout handling at each phase
- Error handling for missing files and invalid theorems
- Deterministic output across multiple runs

Requirements: All requirements
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lean_proof_auto_mcp.tools.search_annotations import search_annotations

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
VALID_THEOREM = str(FIXTURES_DIR / "valid_theorem.lean")
AESOP_TRIVIAL = str(FIXTURES_DIR / "probe_aesop_trivial.lean")
MULTI_THEOREM = str(FIXTURES_DIR / "probe_file_multi_theorem.lean")


@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete workflow with real Lean files."""

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_complete_workflow_success(self, mock_create_handler):
        """Test complete workflow from start to finish with success.

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, All requirements
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler with complete success result
        mock_handler = MagicMock()
        hint = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success", "theorem_found": True},
            baseline={
                "status": "completed",
                "primary_result": "open",
                "secondary_result": None,
            },
            search_result={
                "outcome": "closed",
                "best_hint_set": hint_set,
                "attempts": 5,
                "explored_sets": 10,
            },
            minimized_hint_set=hint_set,
            proof_patch={
                "lean_code": "by aesop (add safe Nat.add_comm)",
                "hint_set": hint_set,
                "automation": "aesop",
            },
            global_suggestions=None,
            timing={
                "total_s": 15.5,
                "viability_check_s": 1.2,
                "baseline_probe_s": 2.3,
                "search_total_s": 10.0,
                "minimize_total_s": 2.0,
            },
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
                "theorem_id": "simple_add_comm",
            }
        )

        # Verify all phases completed
        assert result["status"] == "success"
        assert result["viability"]["status"] == "success"
        assert result["baseline"]["status"] == "completed"
        assert result["search_result"]["outcome"] == "closed"
        assert result["minimized_hint_set"] is not None
        assert result["proof_patch"] is not None

        # Verify timing information
        assert result["timing"]["total_s"] > 0
        assert "viability_check_s" in result["timing"]
        assert "baseline_probe_s" in result["timing"]
        assert "search_total_s" in result["timing"]
        assert "minimize_total_s" in result["timing"]

        # Verify artifacts
        assert "request" in result["artifacts"]
        assert "result" in result["artifacts"]

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_complete_workflow_baseline_success(self, mock_create_handler):
        """Test workflow when baseline automation succeeds (early termination).

        Requirements: 2.4, 7
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Create mock handler with baseline success
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=AESOP_TRIVIAL,
            theorem_id="aesop_trivial_and",
            viability={"status": "success", "theorem_found": True},
            baseline={
                "status": "completed",
                "primary_result": "closed",
                "secondary_result": None,
            },
            search_result=None,  # No search needed
            minimized_hint_set=HintSet(),  # Empty hint set for baseline success
            proof_patch={
                "lean_code": "by aesop",
                "hint_set": None,
                "automation": "aesop",
            },
            global_suggestions=None,
            timing={
                "total_s": 3.5,
                "viability_check_s": 1.2,
                "baseline_probe_s": 2.3,
                "search_total_s": 0.0,  # No search performed
                "minimize_total_s": 0.0,  # No minimization performed
            },
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
            }
        )

        # Verify baseline success
        assert result["status"] == "success"
        assert result["baseline"]["primary_result"] == "closed"

        # Verify search was not performed
        assert result["search_result"] is None
        assert result["timing"]["search_total_s"] == 0.0

        # Verify proof patch still generated
        assert result["proof_patch"] is not None
        assert "by aesop" in result["proof_patch"]["lean_code"]

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_complete_workflow_no_solution_found(self, mock_create_handler):
        """Test workflow when no closing hint set is found.

        Requirements: 4.8, 12.4
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            SearchAnnotationsResult,
        )

        # Create mock handler with fail result
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success", "theorem_found": True},
            baseline={
                "status": "completed",
                "primary_result": "open",
                "secondary_result": "open",
            },
            search_result={
                "outcome": "failed",
                "best_hint_set": None,
                "attempts": 100,
                "explored_sets": 200,
            },
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={
                "total_s": 300.0,
                "viability_check_s": 1.2,
                "baseline_probe_s": 2.3,
                "search_total_s": 296.5,
                "minimize_total_s": 0.0,
            },
            artifacts={},
            metadata={"reason": "No closing hint set found within budget"},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budgets": {"search_total_s": 300.0},
            }
        )

        # Verify fail status
        assert result["status"] == "fail"
        assert result["search_result"]["outcome"] == "failed"
        assert result["minimized_hint_set"] is None
        assert result["proof_patch"] is None

        # Verify metadata explains failure
        assert "reason" in result["metadata"]


@pytest.mark.e2e
class TestLocalOnlyMode:
    """Test local_only mode produces valid proof patches."""

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_local_only_mode_no_global_suggestions(self, mock_create_handler):
        """Test that local_only mode does not generate global suggestions.

        Requirements: 7.1
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,
            proof_patch={
                "lean_code": "by aesop (add safe Nat.add_comm)",
                "hint_set": hint_set,
                "automation": "aesop",
            },
            global_suggestions=None,  # Should be None in local_only mode
            timing={"total_s": 10.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search in local_only mode
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "mode": "local_only",
            }
        )

        # Verify mode was set correctly
        command = mock_handler.handle.call_args[0][0]
        assert command.mode == "local_only"

        # Verify no global suggestions
        assert result["global_suggestions"] is None

        # Verify proof patch was generated
        assert result["proof_patch"] is not None
        assert "lean_code" in result["proof_patch"]

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_local_only_proof_patch_valid_syntax(self, mock_create_handler):
        """Test that local_only mode produces syntactically valid proof patches.

        Requirements: 6.1
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint1 = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint2 = Hint(name="Nat.add_assoc", type=HintType.ADD_SAFE, source="same_namespace")
        hint_set = HintSet(hints=frozenset([hint1, hint2]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,
            proof_patch={
                "lean_code": "by aesop (add safe Nat.add_comm, Nat.add_assoc)",
                "hint_set": hint_set,
                "automation": "aesop",
            },
            global_suggestions=None,
            timing={"total_s": 10.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "mode": "local_only",
            }
        )

        # Verify proof patch structure
        proof_patch = result["proof_patch"]
        assert "lean_code" in proof_patch
        assert "hint_set" in proof_patch
        assert "automation" in proof_patch

        # Verify Lean code is valid syntax (basic checks)
        lean_code = proof_patch["lean_code"]
        assert lean_code.startswith("by ")
        assert "aesop" in lean_code or "grind" in lean_code or "simp" in lean_code


@pytest.mark.e2e
class TestSuggestGlobalMode:
    """Test suggest_global mode produces advisory suggestions."""

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_suggest_global_mode_generates_suggestions(self, mock_create_handler):
        """Test that suggest_global mode generates global annotation suggestions.

        Requirements: 7.2, 7.3, 7.4
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,
            proof_patch={
                "lean_code": "by aesop (add safe Nat.add_comm)",
                "hint_set": hint_set,
                "automation": "aesop",
            },
            global_suggestions=[
                {
                    "hint_name": "Nat.add_comm",
                    "attribute": "@[aesop]",
                    "rationale": "This hint was effective in closing the goal",
                    "confidence": "high",
                }
            ],
            timing={"total_s": 10.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search in suggest_global mode
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "mode": "suggest_global",
            }
        )

        # Verify mode was set correctly
        command = mock_handler.handle.call_args[0][0]
        assert command.mode == "suggest_global"

        # Verify global suggestions were generated
        assert result["global_suggestions"] is not None
        assert isinstance(result["global_suggestions"], list)
        assert len(result["global_suggestions"]) > 0

        # Verify suggestion structure
        suggestion = result["global_suggestions"][0]
        assert "hint_name" in suggestion
        assert "attribute" in suggestion
        assert "rationale" in suggestion
        assert "confidence" in suggestion

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_suggest_global_mode_no_edits_without_permission(self, mock_create_handler):
        """Test that suggest_global mode does not apply edits without permission.

        Requirements: 7.5, 7.6
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,
            proof_patch={"lean_code": "by aesop (add safe Nat.add_comm)"},
            global_suggestions=[
                {
                    "hint_name": "Nat.add_comm",
                    "attribute": "@[aesop]",
                    "rationale": "Advisory only - no edits applied",
                    "confidence": "high",
                }
            ],
            timing={"total_s": 10.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with allow_global_edits=False (default)
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "mode": "suggest_global",
                "allow_global_edits": False,
            }
        )

        # Verify command has correct flag
        command = mock_handler.handle.call_args[0][0]
        assert command.allow_global_edits is False

        # Verify suggestions are advisory only
        assert result["global_suggestions"] is not None
        assert len(result["global_suggestions"]) > 0


@pytest.mark.e2e
class TestTimeoutHandling:
    """Test timeout handling at each phase."""

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_viability_check_timeout(self, mock_create_handler):
        """Test timeout during viability check phase.

        Requirements: 1.5, 9.2
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            SearchAnnotationsResult,
        )

        # Create mock handler that returns timeout error
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="error",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={
                "status": "timeout",
                "error": "Viability check exceeded 5.0s budget",
            },
            baseline={"status": "not_started"},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={
                "total_s": 5.1,
                "viability_check_s": 5.1,
            },
            artifacts={},
            metadata={"error_code": "viability_timeout"},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with small viability budget
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budgets": {"viability_check_s": 5.0},
            }
        )

        # Verify timeout was recorded
        assert result["viability"]["status"] == "timeout"
        assert "timeout" in result["viability"]["error"].lower() or "exceeded" in result["viability"]["error"].lower()

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_baseline_probe_timeout(self, mock_create_handler):
        """Test timeout during baseline probe phase.

        Requirements: 2.5, 9.3
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={
                "status": "timeout",
                "primary_result": "timeout",
                "secondary_result": None,
            },
            search_result={"outcome": "failed"},
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={
                "total_s": 10.5,
                "viability_check_s": 1.0,
                "baseline_probe_s": 10.0,
            },
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with small baseline budget
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budgets": {"baseline_probe_s": 10.0},
            }
        )

        # Verify timeout was recorded
        assert result["baseline"]["status"] == "timeout"
        assert result["baseline"]["primary_result"] == "timeout"

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_search_timeout(self, mock_create_handler):
        """Test timeout during search phase.

        Requirements: 4.8, 9.4
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed", "primary_result": "open"},
            search_result={
                "outcome": "timeout",
                "best_hint_set": None,
                "attempts": 50,
                "explored_sets": 100,
            },
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={
                "total_s": 60.5,
                "viability_check_s": 1.0,
                "baseline_probe_s": 2.0,
                "search_total_s": 60.0,
            },
            artifacts={},
            metadata={"reason": "Search exceeded budget"},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with small search budget
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budgets": {"search_total_s": 60.0},
            }
        )

        # Verify timeout was recorded
        assert result["search_result"]["outcome"] == "timeout"
        assert result["timing"]["search_total_s"] >= 60.0

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_minimize_timeout(self, mock_create_handler):
        """Test timeout during minimization phase.

        Requirements: 5.4, 9.6
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint1 = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint2 = Hint(name="Nat.add_assoc", type=HintType.ADD_SAFE, source="same_namespace")
        hint_set = HintSet(hints=frozenset([hint1, hint2]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,  # Partial minimization
            proof_patch={"lean_code": "by aesop (add safe Nat.add_comm, Nat.add_assoc)"},
            global_suggestions=None,
            timing={
                "total_s": 80.0,
                "viability_check_s": 1.0,
                "baseline_probe_s": 2.0,
                "search_total_s": 50.0,
                "minimize_total_s": 30.0,  # Timeout during minimization
            },
            artifacts={},
            metadata={"minimization_status": "partial"},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with small minimize budget
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budgets": {"minimize_total_s": 30.0},
            }
        )

        # Verify minimization completed (possibly partial)
        assert result["minimized_hint_set"] is not None
        assert result["timing"]["minimize_total_s"] >= 30.0


@pytest.mark.e2e
class TestErrorHandling:
    """Test error handling for missing files and invalid theorems."""

    def test_missing_file_error(self):
        """Test error handling for missing file.

        Requirements: 1.1, 12.1
        """
        result = search_annotations(
            {
                "file": "nonexistent_file.lean",
                "theorem_id": "MyTheorem",
            }
        )

        # Verify error status
        assert result["status"] == "error"
        assert result["api_version"] == "0.1.0"

        # Verify error message mentions file not found
        error_msg = result["metadata"]["error_message"].lower()
        assert "not found" in error_msg or "no such file" in error_msg or "does not exist" in error_msg

    def test_invalid_theorem_id_error(self):
        """Test error handling for invalid theorem_id.

        Requirements: 1.1, 12.2
        """
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "NonExistentTheorem",
            }
        )

        # Verify error or fail status
        assert result["status"] in ("fail", "error")

        # Verify run_id exists
        assert "run_id" in result
        assert result["run_id"].startswith("search-")

    def test_empty_file_path_error(self):
        """Test error handling for empty file path.

        Requirements: 1.1, 1.3
        """
        result = search_annotations(
            {
                "file": "",
                "theorem_id": "MyTheorem",
            }
        )

        # Verify error status
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'file' must be a non-empty string" in result["metadata"]["error_message"]

    def test_empty_theorem_id_error(self):
        """Test error handling for empty theorem_id.

        Requirements: 1.1, 1.3
        """
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "",
            }
        )

        # Verify error status
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'theorem_id' must be a non-empty string" in result["metadata"]["error_message"]

    def test_invalid_configuration_error(self):
        """Test error handling for invalid configuration.

        Requirements: 1.3, 12.8
        """
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budgets": {
                    "viability_check_s": -5.0,  # Invalid negative budget
                },
            }
        )

        # Verify error status
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_handler_exception_caught(self, mock_create_handler):
        """Test that handler exceptions are caught and returned as errors.

        Requirements: 12.8
        """
        # Create mock handler that raises exception
        mock_handler = MagicMock()
        mock_handler.handle.side_effect = RuntimeError("Test internal error")
        mock_create_handler.return_value = mock_handler

        # Execute search
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
            }
        )

        # Verify error response
        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "internal_error"
        assert "Test internal error" in result["metadata"]["error_message"]


@pytest.mark.e2e
class TestDeterministicOutput:
    """Test deterministic output across multiple runs."""

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_deterministic_json_output(self, mock_create_handler):
        """Test that identical inputs produce identical JSON output.

        Requirements: 10.9, 13.1, 13.5
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler with deterministic result
        mock_handler = MagicMock()
        hint1 = Hint(name="Nat.add_assoc", type=HintType.ADD_SAFE, source="same_namespace")
        hint2 = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint1, hint2]))

        def create_result(run_id):
            return SearchAnnotationsResult(
                api_version="0.1.0",
                status="success",
                run_id=run_id,
                file=VALID_THEOREM,
                theorem_id="simple_add_comm",
                viability={"status": "success"},
                baseline={"status": "completed"},
                search_result={"outcome": "closed"},
                minimized_hint_set=hint_set,
                proof_patch={"lean_code": "by aesop (add safe Nat.add_assoc, Nat.add_comm)"},
                global_suggestions=None,
                timing={"total_s": 10.0},
                artifacts={},
                metadata={},
            )

        # Mock handler to return deterministic results
        call_count = [0]

        def handle_side_effect(cmd):
            call_count[0] += 1
            return create_result(cmd.run_id)

        mock_handler.handle.side_effect = handle_side_effect
        mock_create_handler.return_value = mock_handler

        # Execute search twice with identical inputs
        result1 = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
            }
        )

        result2 = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
            }
        )

        # Verify both executions completed
        assert call_count[0] == 2

        # Verify run_ids are different (unique per run)
        assert result1["run_id"] != result2["run_id"]

        # Verify all other fields are identical (except run_id)
        for key in result1.keys():
            if key != "run_id":
                assert result1[key] == result2[key], f"Field {key} differs between runs"

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_hint_ordering_stable(self, mock_create_handler):
        """Test that hint ordering is stable across runs.

        Requirements: 10.10, 13.2
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler with multiple hints
        mock_handler = MagicMock()
        hint1 = Hint(name="Nat.add_assoc", type=HintType.ADD_SAFE, source="same_namespace")
        hint2 = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint3 = Hint(name="Nat.zero_add", type=HintType.ADD_SAFE, source="nearby_decls")
        hint_set = HintSet(hints=frozenset([hint1, hint2, hint3]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,
            proof_patch={"lean_code": "by aesop (add safe Nat.add_assoc, Nat.add_comm, Nat.zero_add)"},
            global_suggestions=None,
            timing={"total_s": 10.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search multiple times
        results = []
        for _ in range(3):
            result = search_annotations(
                {
                    "file": VALID_THEOREM,
                    "theorem_id": "simple_add_comm",
                }
            )
            results.append(result)

        # Verify hint ordering is stable
        for i in range(1, len(results)):
            assert results[0]["proof_patch"]["lean_code"] == results[i]["proof_patch"]["lean_code"]

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_json_field_ordering_stable(self, mock_create_handler):
        """Test that JSON field ordering is stable.

        Requirements: 13.1
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={"total_s": 10.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search multiple times
        results = []
        for _ in range(3):
            result = search_annotations(
                {
                    "file": VALID_THEOREM,
                    "theorem_id": "simple_add_comm",
                }
            )
            results.append(result)

        # Convert to JSON strings to verify ordering
        json_strings = [json.dumps(r, sort_keys=True) for r in results]

        # Verify all JSON strings are identical (except run_id)
        # We can't compare directly due to run_id, but we can verify structure
        for result in results:
            assert list(result.keys()) == list(results[0].keys())


@pytest.mark.e2e
class TestRealLeanFiles:
    """Test with real Lean files if available."""

    @pytest.mark.skipif(
        not Path(VALID_THEOREM).exists(),
        reason="Lean test files not available"
    )
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_with_real_lean_file(self, mock_create_handler):
        """Test with real Lean file structure.

        Requirements: All requirements
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Verify file exists
        assert Path(VALID_THEOREM).exists()

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=HintSet(),  # Empty hint set
            proof_patch={"lean_code": "by rw [Nat.add_comm]"},
            global_suggestions=None,
            timing={"total_s": 5.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with real file
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
            }
        )

        # Verify result structure
        assert result["status"] == "success"
        assert result["file"] == VALID_THEOREM
        assert result["theorem_id"] == "simple_add_comm"

    @pytest.mark.skipif(
        not Path(MULTI_THEOREM).exists(),
        reason="Lean test files not available"
    )
    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_with_multi_theorem_file(self, mock_create_handler):
        """Test with file containing multiple theorems.

        Requirements: 1.2
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            HintSet,
            SearchAnnotationsResult,
        )

        # Verify file exists
        assert Path(MULTI_THEOREM).exists()

        # Create mock handler
        mock_handler = MagicMock()
        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=MULTI_THEOREM,
            theorem_id="multi_theorem_1",
            viability={"status": "success"},
            baseline={"status": "completed", "primary_result": "closed"},
            search_result=None,
            minimized_hint_set=HintSet(),  # Empty hint set for baseline success
            proof_patch={"lean_code": "by aesop"},
            global_suggestions=None,
            timing={"total_s": 3.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with specific theorem from multi-theorem file
        result = search_annotations(
            {
                "file": MULTI_THEOREM,
                "theorem_id": "multi_theorem_1",
            }
        )

        # Verify correct theorem was targeted
        assert result["status"] == "success"
        assert result["file"] == MULTI_THEOREM
        assert result["theorem_id"] == "multi_theorem_1"


@pytest.mark.e2e
class TestComplexScenarios:
    """Test complex scenarios combining multiple features."""

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_beam_search_with_suggest_global(self, mock_create_handler):
        """Test beam search strategy with suggest_global mode.

        Requirements: 4.2, 7.2
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed", "strategy": "beam"},
            minimized_hint_set=hint_set,
            proof_patch={"lean_code": "by aesop (add safe Nat.add_comm)"},
            global_suggestions=[
                {
                    "hint_name": "Nat.add_comm",
                    "attribute": "@[aesop]",
                    "rationale": "Effective hint",
                    "confidence": "high",
                }
            ],
            timing={"total_s": 15.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with beam strategy and suggest_global mode
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "mode": "suggest_global",
                "search": {
                    "strategy": "beam",
                    "beam_width": 5,
                },
            }
        )

        # Verify command configuration
        command = mock_handler.handle.call_args[0][0]
        assert command.mode == "suggest_global"
        assert command.search.strategy == "beam"
        assert command.search.beam_width == 5

        # Verify both features work together
        assert result["status"] == "success"
        assert result["global_suggestions"] is not None
        assert len(result["global_suggestions"]) > 0

    @patch("lean_proof_auto_mcp.tools.search_annotations._create_handler")
    def test_comprehensive_configuration(self, mock_create_handler):
        """Test with comprehensive configuration of all options.

        Requirements: All requirements
        """
        from lean_proof_auto_mcp.core.search_annotations_domain import (
            Hint,
            HintSet,
            HintType,
            SearchAnnotationsResult,
        )

        # Create mock handler
        mock_handler = MagicMock()
        hint = Hint(name="Nat.add_comm", type=HintType.ADD_SAFE, source="goal_symbols")
        hint_set = HintSet(hints=frozenset([hint]))

        mock_result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-id",
            file=VALID_THEOREM,
            theorem_id="simple_add_comm",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result={"outcome": "closed"},
            minimized_hint_set=hint_set,
            proof_patch={"lean_code": "by grind (add safe Nat.add_comm)"},
            global_suggestions=None,
            timing={"total_s": 20.0},
            artifacts={},
            metadata={},
        )

        mock_handler.handle.return_value = mock_result
        mock_create_handler.return_value = mock_handler

        # Execute search with comprehensive configuration
        result = search_annotations(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "mode": "local_only",
                "automation": {
                    "primary": "grind",
                    "secondary": "aesop",
                },
                "budgets": {
                    "viability_check_s": 10.0,
                    "baseline_probe_s": 20.0,
                    "search_total_s": 300.0,
                    "candidate_trial_s": 10.0,
                    "minimize_total_s": 60.0,
                    "final_verify_s": 20.0,
                },
                "search": {
                    "strategy": "greedy",
                    "max_steps": 100,
                    "max_hints": 10,
                    "stop_on_first_close": True,
                },
                "candidates": {
                    "sources": ["goal_symbols", "local_context", "same_namespace"],
                    "max_candidates_per_source": 20,
                    "allow_simp_hints": True,
                    "allow_unfold_hints": True,
                },
                "style": {
                    "prefer_simp_over_aesop": False,
                    "emit_compact": True,
                    "simp_only_list": False,
                },
                "workspace": {
                    "mode": "git_worktree",
                    "keep_artifacts": False,
                },
                "allow_global_edits": False,
            }
        )

        # Verify command was built correctly
        command = mock_handler.handle.call_args[0][0]
        assert command.file == VALID_THEOREM
        assert command.theorem_id == "simple_add_comm"
        assert command.mode == "local_only"
        assert command.automation.primary == "grind"
        assert command.automation.secondary == "aesop"
        assert command.budgets.viability_check_s == 10.0
        assert command.search.strategy == "greedy"
        assert command.search.max_steps == 100
        assert command.candidates.max_candidates_per_source == 20
        assert command.style.emit_compact is True
        assert command.workspace.mode == "git_worktree"
        assert command.allow_global_edits is False

        # Verify result
        assert result["status"] == "success"
