"""
Unit tests for search_automated_proof tool argument validation and error handling.

Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

import pytest

from lean_proof_auto_mcp.tools.search_automated_proof import (
    _build_error_response,
    _build_search_config,
)


class TestBuildSearchConfig:
    """Test cases for _build_search_config function."""

    def test_valid_minimal_args(self):
        """Test building config with minimal valid arguments."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
        }

        config, file_path, theorem_id, run_id = _build_search_config(args)

        assert file_path == "test.lean"
        assert theorem_id == "MyTheorem"
        assert config.search_depth == "normal"  # Default
        assert config.automation_mode == "aesop"  # Default
        assert config.search_strategy == "greedy"  # Default
        assert config.return_proof_states is True  # Default
        assert config.return_partial_progress is True  # Default
        assert run_id.startswith("search-auto-")

    def test_valid_full_args_with_overrides(self):
        """Test building config with all arguments and overrides."""
        args = {
            "file": "path/to/file.lean",
            "theorem_id": "MyTheorem.proof",
            "search_depth": "deep",
            "search_budget_s": 100.0,
            "max_candidates": 150,
            "candidate_sources": ["goal_symbols", "original_proof_refs"],
            "max_candidates_per_source": 40,
            "automation_mode": "simp",
            "automation_secondary": "aesop",
            "search_strategy": "beam",
            "beam_width": 5,
            "max_search_steps": 250,
            "max_hints_in_set": 15,
            "allow_simp_hints": False,
            "allow_unfold_hints": False,
            "allow_unsafe_hints": True,
            "minimize_hints": False,
            "minimize_budget_s": 50.0,
            "return_proof_states": False,
            "return_partial_progress": False,
            "return_context": True,
            "return_similar_proofs": True,
            "return_search_trace": True,
        }

        config, file_path, theorem_id, run_id = _build_search_config(args)

        assert file_path == "path/to/file.lean"
        assert theorem_id == "MyTheorem.proof"
        assert config.search_depth == "deep"
        assert config.search_budget_s == 100.0  # Override
        assert config.max_candidates == 150  # Override
        assert len(config.candidate_sources) == 2
        assert config.max_candidates_per_source == 40  # Override
        assert config.automation_mode == "simp"
        assert config.automation_secondary == "aesop"
        assert config.search_strategy == "beam"
        assert config.beam_width == 5
        assert config.max_search_steps == 250  # Override
        assert config.max_hints_in_set == 15
        assert config.allow_simp_hints is False
        assert config.allow_unfold_hints is False
        assert config.allow_unsafe_hints is True
        assert config.minimize_hints is False
        assert config.minimize_budget_s == 50.0  # Override
        assert config.return_proof_states is False
        assert config.return_partial_progress is False
        assert config.return_context is True
        assert config.return_similar_proofs is True
        assert config.return_search_trace is True

    def test_file_whitespace_trimmed(self):
        """Test that file path whitespace is trimmed."""
        args = {
            "file": "  test.lean  ",
            "theorem_id": "MyTheorem",
        }

        config, file_path, theorem_id, run_id = _build_search_config(args)

        assert file_path == "test.lean"

    def test_theorem_id_whitespace_trimmed(self):
        """Test that theorem_id whitespace is trimmed."""
        args = {
            "file": "test.lean",
            "theorem_id": "  MyTheorem  ",
        }

        config, file_path, theorem_id, run_id = _build_search_config(args)

        assert theorem_id == "MyTheorem"

    def test_missing_file_raises_error(self):
        """Test that missing file raises ValueError."""
        args = {
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_search_config(args)

    def test_empty_file_raises_error(self):
        """Test that empty file raises ValueError."""
        args = {
            "file": "",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_search_config(args)

    def test_whitespace_only_file_raises_error(self):
        """Test that whitespace-only file raises ValueError."""
        args = {
            "file": "   ",
            "theorem_id": "MyTheorem",
        }

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _build_search_config(args)

    def test_missing_theorem_id_raises_error(self):
        """Test that missing theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_search_config(args)

    def test_empty_theorem_id_raises_error(self):
        """Test that empty theorem_id raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "",
        }

        with pytest.raises(ValueError, match="'theorem_id' must be a non-empty string"):
            _build_search_config(args)

    def test_invalid_search_depth_raises_error(self):
        """Test that invalid search_depth raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "invalid",
        }

        with pytest.raises(
            ValueError,
            match="'search_depth' must be 'quick', 'normal', 'deep', or 'exhaustive'",
        ):
            _build_search_config(args)

    def test_invalid_automation_mode_raises_error(self):
        """Test that invalid automation_mode raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "automation_mode": "invalid",
        }

        with pytest.raises(
            ValueError,
            match="'automation_mode' must be 'aesop', 'simp', 'omega', or 'grind'",
        ):
            _build_search_config(args)

    def test_invalid_search_strategy_raises_error(self):
        """Test that invalid search_strategy raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_strategy": "invalid",
        }

        with pytest.raises(
            ValueError,
            match="'search_strategy' must be 'greedy', 'beam', or 'exhaustive'",
        ):
            _build_search_config(args)

    def test_negative_search_budget_raises_error(self):
        """Test that negative search_budget_s raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_budget_s": -10.0,
        }

        with pytest.raises(ValueError, match="'search_budget_s' must be a positive number"):
            _build_search_config(args)

    def test_zero_max_candidates_raises_error(self):
        """Test that zero max_candidates raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "max_candidates": 0,
        }

        with pytest.raises(ValueError, match="'max_candidates' must be a positive integer"):
            _build_search_config(args)

    def test_invalid_candidate_source_raises_error(self):
        """Test that invalid candidate source raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "candidate_sources": ["invalid_source"],
        }

        with pytest.raises(ValueError, match="Invalid candidate source"):
            _build_search_config(args)

    def test_non_boolean_flag_raises_error(self):
        """Test that non-boolean flag raises ValueError."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "allow_simp_hints": "yes",  # Should be boolean
        }

        with pytest.raises(ValueError, match="'allow_simp_hints' must be a boolean"):
            _build_search_config(args)


class TestSearchDepthPresets:
    """Test cases for search depth preset configurations."""

    def test_quick_preset_parameters(self):
        """Test quick preset has correct parameters."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "quick",
        }

        config, _, _, _ = _build_search_config(args)

        assert config.search_depth == "quick"
        assert config.search_budget_s == 10.0
        assert config.max_candidates == 20
        assert config.max_search_steps == 50
        assert config.minimize_budget_s == 5.0

    def test_normal_preset_parameters(self):
        """Test normal preset has correct parameters."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "normal",
        }

        config, _, _, _ = _build_search_config(args)

        assert config.search_depth == "normal"
        assert config.search_budget_s == 30.0
        assert config.max_candidates == 50
        assert config.max_search_steps == 100
        assert config.minimize_budget_s == 30.0

    def test_deep_preset_parameters(self):
        """Test deep preset has correct parameters."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "deep",
        }

        config, _, _, _ = _build_search_config(args)

        assert config.search_depth == "deep"
        assert config.search_budget_s == 60.0
        assert config.max_candidates == 100
        assert config.max_search_steps == 200
        assert config.minimize_budget_s == 60.0

    def test_exhaustive_preset_parameters(self):
        """Test exhaustive preset has correct parameters."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "exhaustive",
        }

        config, _, _, _ = _build_search_config(args)

        assert config.search_depth == "exhaustive"
        assert config.search_budget_s == 120.0
        assert config.max_candidates == 200
        assert config.max_search_steps == 500
        assert config.minimize_budget_s == 120.0

    def test_preset_override_with_custom_budget(self):
        """Test that custom budget overrides preset."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "quick",
            "search_budget_s": 50.0,  # Override
        }

        config, _, _, _ = _build_search_config(args)

        assert config.search_depth == "quick"
        assert config.search_budget_s == 50.0  # Custom value
        assert config.max_candidates == 20  # Preset value

    def test_preset_override_with_custom_candidates(self):
        """Test that custom max_candidates overrides preset."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "search_depth": "normal",
            "max_candidates": 200,  # Override
        }

        config, _, _, _ = _build_search_config(args)

        assert config.search_depth == "normal"
        assert config.search_budget_s == 30.0  # Preset value
        assert config.max_candidates == 200  # Custom value


class TestJSONResponseFormat:
    """Test cases for JSON response formatting."""

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
        assert response["run_id"].startswith("search-auto-")
        assert response["file"] == "test.lean"
        assert response["theorem_id"] == "MyTheorem"
        assert response["outcome"] == "failed"
        assert response["best_hint_set"] is None
        assert response["attempts"] == 0
        assert response["explored_sets"] == 0
        assert "feedback" in response
        assert response["feedback"]["status"] == "error"
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


class TestReturnOptions:
    """Test cases for return option configurations."""

    def test_all_return_options_enabled(self):
        """Test config with all return options enabled."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "return_proof_states": True,
            "return_partial_progress": True,
            "return_context": True,
            "return_similar_proofs": True,
            "return_search_trace": True,
        }

        config, _, _, _ = _build_search_config(args)

        assert config.return_proof_states is True
        assert config.return_partial_progress is True
        assert config.return_context is True
        assert config.return_similar_proofs is True
        assert config.return_search_trace is True

    def test_all_return_options_disabled(self):
        """Test config with all return options disabled."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "return_proof_states": False,
            "return_partial_progress": False,
            "return_context": False,
            "return_similar_proofs": False,
            "return_search_trace": False,
        }

        config, _, _, _ = _build_search_config(args)

        assert config.return_proof_states is False
        assert config.return_partial_progress is False
        assert config.return_context is False
        assert config.return_similar_proofs is False
        assert config.return_search_trace is False

    def test_mixed_return_options(self):
        """Test config with mixed return options."""
        args = {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "return_proof_states": True,
            "return_partial_progress": False,
            "return_context": True,
            "return_similar_proofs": False,
            "return_search_trace": True,
        }

        config, _, _, _ = _build_search_config(args)

        assert config.return_proof_states is True
        assert config.return_partial_progress is False
        assert config.return_context is True
        assert config.return_similar_proofs is False
        assert config.return_search_trace is True
