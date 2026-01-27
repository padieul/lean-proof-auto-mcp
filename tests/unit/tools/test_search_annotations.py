"""Unit tests for search_annotations tool argument validation and error handling.

Requirements: 1.1, 1.3, 11.1, 11.2
"""

import pytest

from lean_proof_auto_mcp.tools.search_annotations import (
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
        }

        cmd = _build_command(args)

        assert cmd.file == "test.lean"
        assert cmd.theorem_id == "MyTheorem"
        assert cmd.mode == "local_only"  # Default
        assert cmd.automation.primary == "aesop"  # Default
        assert cmd.budgets.viability_check_s == 5.0  # Default
        assert cmd.search.strategy == "greedy"  # Default
        assert cmd.allow_global_edits is False  # Default

    def test_valid_full_args(self):
        """Test building command with all arguments specified."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "mode": "suggest_global",
            "automation": {
                "primary": "grind",
                "secondary": "aesop",
            },
            "budgets": {
                "viability_check_s": 10.0,
                "baseline_probe_s": 20.0,
                "search_total_s": 600.0,
                "candidate_trial_s": 10.0,
                "minimize_total_s": 120.0,
                "final_verify_s": 20.0,
            },
            "search": {
                "strategy": "beam",
                "beam_width": 5,
                "max_steps": 200,
                "max_hints": 15,
                "stop_on_first_close": False,
            },
            "candidates": {
                "sources": ["goal_symbols", "local_context"],
                "max_candidates_per_source": 30,
                "allow_simp_hints": False,
                "allow_unfold_hints": False,
            },
            "skeleton": {
                "enabled": True,
                "max_depth": 5,
                "moves": ["cases", "constructor"],
            },
            "style": {
                "prefer_simp_over_aesop": False,
                "emit_compact": True,
                "simp_only_list": True,
            },
            "workspace": {
                "mode": "git_worktree",
                "keep_artifacts": True,
            },
            "allow_global_edits": True,
        }

        cmd = _build_command(args)

        assert cmd.file == "path/to/file.lean"
        assert cmd.theorem_id == "MyTheorem.proof"
        assert cmd.mode == "suggest_global"
        assert cmd.automation.primary == "grind"
        assert cmd.automation.secondary == "aesop"
        assert cmd.budgets.viability_check_s == 10.0
        assert cmd.budgets.baseline_probe_s == 20.0
        assert cmd.search.strategy == "beam"
        assert cmd.search.beam_width == 5
        assert cmd.candidates.max_candidates_per_source == 30
        assert cmd.skeleton.enabled is True
        assert cmd.style.emit_compact is True
        assert cmd.workspace.keep_artifacts is True
        assert cmd.allow_global_edits is True

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "theorem_id": "MyTheorem",
        }

        cmd = _build_command(args)

        assert cmd.file == "test.lean"

    def test_theorem_id_whitespace_trimmed(self):
        """Test that theorem_id whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "  MyTheorem  ",
        }

        cmd = _build_command(args)

        assert cmd.theorem_id == "MyTheorem"

    def test_missing_file(self):
        """Test error when file is missing."""
        args = {
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_empty_file(self):
        """Test error when file is empty string."""
        args = {
            "file": "",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_whitespace_only_file(self):
        """Test error when file is whitespace only."""
        args = {
            "file": "   ",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_non_string_file(self):
        """Test error when file is not a string."""
        args = {
            "file": 123,
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_command(args)

    def test_missing_theorem_id(self):
        """Test error when theorem_id is missing."""
        args = {
            "file": "test.lean",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_empty_theorem_id(self):
        """Test error when theorem_id is empty string."""
        args = {
            "file": "test.lean",
            "theorem_id": "",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_whitespace_only_theorem_id(self):
        """Test error when theorem_id is whitespace only."""
        args = {
            "file": "test.lean",
            "theorem_id": "   ",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_command(args)

    def test_non_string_theorem_id(self):
        """Test error when theorem_id is not a string."""
        args = {
            "file": "test.lean",
            "theorem_id": 123,
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
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

        with pytest.raises(ValueError, match="'mode' must be 'local_only' or 'suggest_global'"):
            _build_command(args)

    def test_non_dict_automation(self):
        """Test error when automation is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "automation": "invalid",
        }

        with pytest.raises(ValueError, match="'automation' must be a dict"):
            _build_command(args)

    def test_non_dict_budgets(self):
        """Test error when budgets is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "budgets": "invalid",
        }

        with pytest.raises(ValueError, match="'budgets' must be a dict"):
            _build_command(args)

    def test_invalid_budget_value(self):
        """Test error when budget value is invalid."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "budgets": {
                "viability_check_s": -5.0,
            },
        }

        with pytest.raises(ValueError, match="viability_check_s must be positive"):
            _build_command(args)

    def test_non_dict_search(self):
        """Test error when search is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search": "invalid",
        }

        with pytest.raises(ValueError, match="'search' must be a dict"):
            _build_command(args)

    def test_invalid_search_strategy(self):
        """Test error when search strategy is invalid."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search": {
                "strategy": "invalid",
            },
        }

        with pytest.raises(ValueError, match="strategy"):
            _build_command(args)

    def test_non_dict_candidates(self):
        """Test error when candidates is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "candidates": "invalid",
        }

        with pytest.raises(ValueError, match="'candidates' must be a dict"):
            _build_command(args)

    def test_non_list_candidate_sources(self):
        """Test error when candidate sources is not a list."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "candidates": {
                "sources": "invalid",
            },
        }

        with pytest.raises(ValueError, match="'candidates.sources' must be a list"):
            _build_command(args)

    def test_invalid_candidate_source(self):
        """Test error when candidate source is invalid."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "candidates": {
                "sources": ["invalid_source"],
            },
        }

        with pytest.raises(ValueError, match="Invalid candidate source"):
            _build_command(args)

    def test_non_dict_skeleton(self):
        """Test error when skeleton is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "skeleton": "invalid",
        }

        with pytest.raises(ValueError, match="'skeleton' must be a dict"):
            _build_command(args)

    def test_non_dict_style(self):
        """Test error when style is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "style": "invalid",
        }

        with pytest.raises(ValueError, match="'style' must be a dict"):
            _build_command(args)

    def test_non_dict_workspace(self):
        """Test error when workspace is not a dict."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "workspace": "invalid",
        }

        with pytest.raises(ValueError, match="'workspace' must be a dict"):
            _build_command(args)

    def test_non_bool_allow_global_edits(self):
        """Test error when allow_global_edits is not a boolean."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "allow_global_edits": "invalid",
        }

        with pytest.raises(ValueError, match="'allow_global_edits' must be a boolean"):
            _build_command(args)


class TestBuildErrorResponse:
    """Test cases for _build_error_response function."""

    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        # Check required fields
        assert "api_version" in response
        assert "status" in response
        assert "run_id" in response
        assert "file" in response
        assert "theorem_id" in response
        assert "viability" in response
        assert "baseline" in response
        assert "search_result" in response
        assert "minimized_hint_set" in response
        assert "proof_patch" in response
        assert "global_suggestions" in response
        assert "timing" in response
        assert "artifacts" in response
        assert "metadata" in response

    def test_error_response_values(self):
        """Test that error response has correct values."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        assert response["api_version"] == "0.1.0"
        assert response["status"] == "error"
        assert response["file"] == "test.lean"
        assert response["theorem_id"] == "MyTheorem"

    def test_error_response_viability(self):
        """Test that error response has correct viability section."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error message",
            error_code="test_error",
        )

        viability = response["viability"]
        assert viability["status"] == "not_started"
        assert viability["error"] == "Test error message"

    def test_error_response_baseline(self):
        """Test that error response has correct baseline section."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        baseline = response["baseline"]
        assert baseline["status"] == "not_started"

    def test_error_response_null_fields(self):
        """Test that error response has null for optional fields."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        assert response["search_result"] is None
        assert response["minimized_hint_set"] is None
        assert response["proof_patch"] is None
        assert response["global_suggestions"] is None

    def test_error_response_timing(self):
        """Test that error response has correct timing."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        timing = response["timing"]
        assert timing["total_s"] == 0.0

    def test_error_response_metadata(self):
        """Test that error response has correct metadata."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error message",
            error_code="test_error_code",
        )

        metadata = response["metadata"]
        assert metadata["error_code"] == "test_error_code"
        assert metadata["error_message"] == "Test error message"

    def test_error_response_run_id_format(self):
        """Test that error response run_id has correct format."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        run_id = response["run_id"]
        assert run_id.startswith("search-")
        parts = run_id.split("-")
        assert len(parts) == 5  # search-YYYYMMDD-HHMMSS-hash-random
        assert len(parts[3]) == 8  # 8-character file hash
        assert len(parts[4]) == 6  # 6-character random suffix

    def test_error_response_invalid_file_handling(self):
        """Test error response with invalid file."""
        response = _build_error_response(
            file="",
            theorem_id="MyTheorem",
            error_message="Test error",
            error_code="test_error",
        )

        # Should use placeholder for invalid file
        assert response["file"] == "<invalid>"
        assert "run_id" in response
        assert response["run_id"].startswith("search-")

    def test_error_response_invalid_theorem_id_handling(self):
        """Test error response with invalid theorem_id."""
        response = _build_error_response(
            file="test.lean",
            theorem_id="",
            error_message="Test error",
            error_code="test_error",
        )

        # Should use placeholder for invalid theorem_id
        assert response["theorem_id"] == "<invalid>"


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_file_with_special_characters(self):
        """Test file path with special characters."""
        args = {
            "file": "path/to/my-file_v2.lean",
            "theorem_id": "MyTheorem",
        }

        cmd = _build_command(args)

        assert cmd.file == "path/to/my-file_v2.lean"

    def test_theorem_id_with_dots(self):
        """Test theorem_id with dots (namespace separator)."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyNamespace.MyTheorem.proof",
        }

        cmd = _build_command(args)

        assert cmd.theorem_id == "MyNamespace.MyTheorem.proof"

    def test_candidate_sources_all_valid(self):
        """Test all valid candidate sources."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "candidates": {
                "sources": [
                    "goal_symbols",
                    "local_context",
                    "same_namespace",
                    "nearby_decls",
                    "original_proof_refs",
                ],
            },
        }

        cmd = _build_command(args)

        assert len(cmd.candidates.sources) == 5

    def test_budget_minimum_positive(self):
        """Test budget at minimum positive value."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "budgets": {
                "viability_check_s": 0.001,
            },
        }

        cmd = _build_command(args)

        assert cmd.budgets.viability_check_s == 0.001

    def test_budget_large_value(self):
        """Test budget with large value."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "budgets": {
                "search_total_s": 3600.0,
            },
        }

        cmd = _build_command(args)

        assert cmd.budgets.search_total_s == 3600.0

    def test_search_max_steps_large(self):
        """Test search with large max_steps."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search": {
                "max_steps": 10000,
            },
        }

        cmd = _build_command(args)

        assert cmd.search.max_steps == 10000

    def test_search_max_hints_large(self):
        """Test search with large max_hints."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search": {
                "max_hints": 100,
            },
        }

        cmd = _build_command(args)

        assert cmd.search.max_hints == 100


class TestIntegrationScenarios:
    """Test integration scenarios with realistic inputs."""

    def test_local_only_search_args(self):
        """Test arguments for local_only search."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "theorem_id": "List.append_assoc",
            "mode": "local_only",
            "automation": {
                "primary": "aesop",
            },
            "budgets": {
                "search_total_s": 300.0,
            },
        }

        cmd = _build_command(args)

        assert cmd.file == "Mathlib/Data/List/Basic.lean"
        assert cmd.theorem_id == "List.append_assoc"
        assert cmd.mode == "local_only"
        assert cmd.automation.primary == "aesop"

    def test_suggest_global_search_args(self):
        """Test arguments for suggest_global search."""
        args = {
            "file": "Mathlib/Data/List/Basic.lean",
            "theorem_id": "List.append_assoc",
            "mode": "suggest_global",
        }

        cmd = _build_command(args)

        assert cmd.mode == "suggest_global"

    def test_beam_search_args(self):
        """Test arguments for beam search."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search": {
                "strategy": "beam",
                "beam_width": 5,
            },
        }

        cmd = _build_command(args)

        assert cmd.search.strategy == "beam"
        assert cmd.search.beam_width == 5

    def test_greedy_search_args(self):
        """Test arguments for greedy search."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search": {
                "strategy": "greedy",
            },
        }

        cmd = _build_command(args)

        assert cmd.search.strategy == "greedy"

    def test_quick_search_small_budgets(self):
        """Test arguments for quick search with small budgets."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "budgets": {
                "viability_check_s": 2.0,
                "baseline_probe_s": 5.0,
                "search_total_s": 60.0,
                "minimize_total_s": 30.0,
            },
        }

        cmd = _build_command(args)

        assert cmd.budgets.viability_check_s == 2.0
        assert cmd.budgets.baseline_probe_s == 5.0
        assert cmd.budgets.search_total_s == 60.0
        assert cmd.budgets.minimize_total_s == 30.0

    def test_comprehensive_search_args(self):
        """Test arguments for comprehensive search with all sources."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "candidates": {
                "sources": [
                    "goal_symbols",
                    "local_context",
                    "same_namespace",
                    "nearby_decls",
                    "original_proof_refs",
                ],
                "max_candidates_per_source": 50,
            },
            "search": {
                "max_steps": 500,
                "max_hints": 20,
            },
        }

        cmd = _build_command(args)

        assert len(cmd.candidates.sources) == 5
        assert cmd.candidates.max_candidates_per_source == 50
        assert cmd.search.max_steps == 500
        assert cmd.search.max_hints == 20


class TestErrorHandling:
    """Test cases for error handling in search_annotations function.

    Requirements: 1.1, 1.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.8
    """

    def test_invalid_args_returns_error_response(self):
        """Test that invalid arguments return error response."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        # Missing file argument
        result = search_annotations({"theorem_id": "MyTheorem"})

        assert result["status"] == "error"
        assert result["api_version"] == "0.1.0"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'file' must be a non-empty string" in result["metadata"]["error_message"]

    def test_empty_file_returns_error_response(self):
        """Test that empty file returns error response."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        result = search_annotations({"file": "", "theorem_id": "MyTheorem"})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'file' must be a non-empty string" in result["metadata"]["error_message"]

    def test_empty_theorem_id_returns_error_response(self):
        """Test that empty theorem_id returns error response."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        result = search_annotations({"file": "test.lean", "theorem_id": ""})

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'theorem_id' must be a non-empty string" in result["metadata"]["error_message"]

    def test_invalid_mode_returns_error_response(self):
        """Test that invalid mode returns error response."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        result = search_annotations(
            {
                "file": "test.lean",
                "theorem_id": "MyTheorem",
                "mode": "invalid",
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "'mode' must be" in result["metadata"]["error_message"]

    def test_invalid_budget_returns_error_response(self):
        """Test that invalid budget returns error response."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        result = search_annotations(
            {
                "file": "test.lean",
                "theorem_id": "MyTheorem",
                "budgets": {
                    "viability_check_s": -5.0,
                },
            }
        )

        assert result["status"] == "error"
        assert result["metadata"]["error_code"] == "input_validation_error"
        assert "viability_check_s must be positive" in result["metadata"]["error_message"]

    def test_error_response_has_required_fields(self):
        """Test that error responses have all required fields."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        result = search_annotations({"theorem_id": "MyTheorem"})

        # Check all required fields are present
        required_fields = [
            "api_version",
            "status",
            "run_id",
            "file",
            "theorem_id",
            "viability",
            "baseline",
            "search_result",
            "minimized_hint_set",
            "proof_patch",
            "global_suggestions",
            "timing",
            "artifacts",
            "metadata",
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_error_response_has_run_id(self):
        """Test that error response includes a run_id."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        result = search_annotations({"theorem_id": "MyTheorem"})

        assert "run_id" in result
        assert result["run_id"].startswith("search-")

    def test_multiple_validation_errors_first_caught(self):
        """Test that first validation error is caught and returned."""
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        # Multiple invalid arguments - should catch first one
        result = search_annotations(
            {
                "file": "",
                "theorem_id": "",
                "mode": "invalid",
            }
        )

        assert result["status"] == "error"
        # Should catch the file validation error first
        assert "'file' must be a non-empty string" in result["metadata"]["error_message"]

    def test_no_unhandled_exceptions_escape(self):
        """Test that no unhandled exceptions escape from search_annotations function.

        Requirements: 12.8
        """
        from lean_proof_auto_mcp.tools.search_annotations import search_annotations

        # Various invalid inputs should all return error responses, not raise exceptions
        test_cases = [
            {},
            {"file": None},
            {"file": 123},
            {"file": "test.lean"},
            {"file": "test.lean", "theorem_id": None},
            {"file": "test.lean", "theorem_id": 123},
            {"file": "test.lean", "theorem_id": "MyTheorem", "mode": 123},
            {"file": "test.lean", "theorem_id": "MyTheorem", "budgets": "invalid"},
        ]

        for args in test_cases:
            result = search_annotations(args)
            assert isinstance(result, dict)
            assert "status" in result
            assert result["status"] == "error"
