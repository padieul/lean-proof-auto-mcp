"""Unit tests for rank_targets tool."""

import pytest

from lean_proof_auto_mcp.tools.rank_targets import (
    RankTargetsArgs,
    _coerce_args,
)


class TestRankTargetsArgs:
    """Test cases for RankTargetsArgs dataclass."""

    def test_valid_args(self):
        """Test creating valid RankTargetsArgs."""
        args = RankTargetsArgs(
            file="test.lean",
            objective="balanced",
            limit=30,
            include_components=True,
            include_reasons=True,
            use_deep_structure=False,
            min_confidence=0.0,
        )

        assert args.file == "test.lean"
        assert args.objective == "balanced"
        assert args.limit == 30
        assert args.include_components is True
        assert args.include_reasons is True
        assert args.use_deep_structure is False
        assert args.min_confidence == 0.0

    def test_invalid_empty_file(self):
        """Test validation of empty file."""
        with pytest.raises(ValueError, match="file must be a non-empty string"):
            RankTargetsArgs(
                file="",
                objective="balanced",
                limit=30,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=0.0,
            )

    def test_invalid_whitespace_file(self):
        """Test validation of whitespace-only file."""
        with pytest.raises(ValueError, match="file must be a non-empty string"):
            RankTargetsArgs(
                file="   ",
                objective="balanced",
                limit=30,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=0.0,
            )

    def test_invalid_objective(self):
        """Test validation of invalid objective."""
        with pytest.raises(ValueError, match="objective must be one of"):
            RankTargetsArgs(
                file="test.lean",
                objective="invalid_objective",
                limit=30,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=0.0,
            )

    def test_invalid_limit_too_low(self):
        """Test validation of limit (too low)."""
        with pytest.raises(ValueError, match="limit must be in \\[1, 500\\]"):
            RankTargetsArgs(
                file="test.lean",
                objective="balanced",
                limit=0,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=0.0,
            )

    def test_invalid_limit_too_high(self):
        """Test validation of limit (too high)."""
        with pytest.raises(ValueError, match="limit must be in \\[1, 500\\]"):
            RankTargetsArgs(
                file="test.lean",
                objective="balanced",
                limit=501,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=0.0,
            )

    def test_invalid_min_confidence_low(self):
        """Test validation of min_confidence (too low)."""
        with pytest.raises(ValueError, match="min_confidence must be in \\[0.0, 1.0\\]"):
            RankTargetsArgs(
                file="test.lean",
                objective="balanced",
                limit=30,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=-0.1,
            )

    def test_invalid_min_confidence_high(self):
        """Test validation of min_confidence (too high)."""
        with pytest.raises(ValueError, match="min_confidence must be in \\[0.0, 1.0\\]"):
            RankTargetsArgs(
                file="test.lean",
                objective="balanced",
                limit=30,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=1.1,
            )

    def test_all_objectives_valid(self):
        """Test that all documented objectives are valid."""
        objectives = [
            "maximize_success",
            "maximize_impact",
            "maximize_subgoal_automation",
            "balanced",
        ]

        for objective in objectives:
            args = RankTargetsArgs(
                file="test.lean",
                objective=objective,
                limit=30,
                include_components=True,
                include_reasons=True,
                use_deep_structure=False,
                min_confidence=0.0,
            )
            assert args.objective == objective


class TestCoerceArgs:
    """Test cases for _coerce_args function."""

    def test_valid_minimal_args(self):
        """Test coercing minimal valid arguments."""
        args = {"file": "test.lean"}

        result = _coerce_args(args)

        assert result.file == "test.lean"
        assert result.objective == "balanced"  # Default
        assert result.limit == 30  # Default
        assert result.include_components is True  # Default
        assert result.include_reasons is True  # Default
        assert result.use_deep_structure is False  # Default
        assert result.min_confidence == 0.0  # Default

    def test_valid_full_args(self):
        """Test coercing full arguments."""
        args = {
            "file": "test.lean",
            "objective": "maximize_success",
            "limit": 50,
            "include_components": False,
            "include_reasons": False,
            "use_deep_structure": True,
            "min_confidence": 0.5,
        }

        result = _coerce_args(args)

        assert result.file == "test.lean"
        assert result.objective == "maximize_success"
        assert result.limit == 50
        assert result.include_components is False
        assert result.include_reasons is False
        assert result.use_deep_structure is True
        assert result.min_confidence == 0.5

    def test_missing_file(self):
        """Test error when file is missing."""
        args = {}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _coerce_args(args)

    def test_empty_file(self):
        """Test error when file is empty."""
        args = {"file": ""}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _coerce_args(args)

    def test_whitespace_file(self):
        """Test error when file is whitespace."""
        args = {"file": "   "}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _coerce_args(args)

    def test_non_string_file(self):
        """Test error when file is not a string."""
        args = {"file": 123}

        with pytest.raises(ValueError, match="'file' must be a non-empty string"):
            _coerce_args(args)

    def test_invalid_objective_type(self):
        """Test error when objective is not a string."""
        args = {"file": "test.lean", "objective": 123}

        with pytest.raises(ValueError, match="'objective' must be a string"):
            _coerce_args(args)

    def test_invalid_objective_value(self):
        """Test error when objective value is invalid."""
        args = {"file": "test.lean", "objective": "invalid"}

        with pytest.raises(ValueError, match="objective must be one of"):
            _coerce_args(args)

    def test_invalid_limit_type(self):
        """Test error when limit is not an integer."""
        args = {"file": "test.lean", "limit": "30"}

        with pytest.raises(ValueError, match="'limit' must be an integer"):
            _coerce_args(args)

    def test_invalid_limit_value(self):
        """Test error when limit value is out of range."""
        args = {"file": "test.lean", "limit": 0}

        with pytest.raises(ValueError, match="limit must be in \\[1, 500\\]"):
            _coerce_args(args)

    def test_invalid_include_components_type(self):
        """Test error when include_components is not a boolean."""
        args = {"file": "test.lean", "include_components": "true"}

        with pytest.raises(ValueError, match="'include_components' must be a boolean"):
            _coerce_args(args)

    def test_invalid_include_reasons_type(self):
        """Test error when include_reasons is not a boolean."""
        args = {"file": "test.lean", "include_reasons": 1}

        with pytest.raises(ValueError, match="'include_reasons' must be a boolean"):
            _coerce_args(args)

    def test_invalid_use_deep_structure_type(self):
        """Test error when use_deep_structure is not a boolean."""
        args = {"file": "test.lean", "use_deep_structure": "false"}

        with pytest.raises(ValueError, match="'use_deep_structure' must be a boolean"):
            _coerce_args(args)

    def test_invalid_min_confidence_type(self):
        """Test error when min_confidence is not a number."""
        args = {"file": "test.lean", "min_confidence": "0.5"}

        with pytest.raises(ValueError, match="'min_confidence' must be a number"):
            _coerce_args(args)

    def test_invalid_min_confidence_value(self):
        """Test error when min_confidence value is out of range."""
        args = {"file": "test.lean", "min_confidence": 1.5}

        with pytest.raises(ValueError, match="min_confidence must be in \\[0.0, 1.0\\]"):
            _coerce_args(args)

    def test_min_confidence_integer_coercion(self):
        """Test that integer min_confidence is coerced to float."""
        args = {"file": "test.lean", "min_confidence": 1}

        result = _coerce_args(args)

        assert result.min_confidence == 1.0
        assert isinstance(result.min_confidence, float)


class TestConfidenceFiltering:
    """Test cases for confidence filtering logic."""

    def test_confidence_filtering_in_rank_theorems(self):
        """Test that confidence filtering works correctly in rank_theorems."""
        from lean_proof_auto_mcp.core.ranking import TheoremData, rank_theorems

        theorems = [
            TheoremData(
                theorem_id="high_conf",
                range={"start_line": 10, "end_line": 20},
                signals={
                    "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
                    "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
                    "annotation_value": 0.8,
                    "confidence": 0.9,
                    "proof_lines": 10,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 0,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="medium_conf",
                range={"start_line": 30, "end_line": 40},
                signals={
                    "whole_goal_potential": {"aesop": 0.7, "grind": 0.6},
                    "subgoal_potential": {"aesop": 0.6, "grind": 0.5},
                    "annotation_value": 0.7,
                    "confidence": 0.6,
                    "proof_lines": 12,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 1,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="low_conf",
                range={"start_line": 50, "end_line": 60},
                signals={
                    "whole_goal_potential": {"aesop": 0.9, "grind": 0.8},
                    "subgoal_potential": {"aesop": 0.8, "grind": 0.7},
                    "annotation_value": 0.9,
                    "confidence": 0.3,
                    "proof_lines": 15,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 2,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
        ]

        # Filter with min_confidence=0.5
        ranked = rank_theorems(theorems, "balanced", min_confidence=0.5)

        # Only high_conf and medium_conf should be included
        assert len(ranked) == 2
        theorem_ids = {r.theorem_data.theorem_id for r in ranked}
        assert "high_conf" in theorem_ids
        assert "medium_conf" in theorem_ids
        assert "low_conf" not in theorem_ids

        # All returned theorems should have confidence >= 0.5
        for ranked_theorem in ranked:
            assert ranked_theorem.theorem_data.signals["confidence"] >= 0.5


class TestResponseStructure:
    """Test cases for response structure and required fields."""

    def test_error_response_structure(self):
        """Test that error responses have required structure."""
        from lean_proof_auto_mcp.tools.rank_targets import rank_targets

        # Invalid arguments should return error response
        result = rank_targets({"file": ""})

        # Check required fields
        assert "api_version" in result
        assert "status" in result
        assert "run_id" in result
        assert "tool" in result
        assert "file" in result
        assert "objective" in result
        assert "ranking" in result
        assert "summary" in result
        assert "diagnostics" in result
        assert "metadata" in result

        # Check status is fail
        assert result["status"] == "fail"

        # Check tool name
        assert result["tool"] == "rank_targets"

        # Check ranking is empty
        assert result["ranking"] == []

        # Check diagnostics contains error
        assert len(result["diagnostics"]) > 0
        assert result["diagnostics"][0]["severity"] == "error"

    def test_error_response_with_invalid_objective(self):
        """Test error response with invalid objective."""
        from lean_proof_auto_mcp.tools.rank_targets import rank_targets

        result = rank_targets({"file": "test.lean", "objective": "invalid"})

        assert result["status"] == "fail"
        assert len(result["diagnostics"]) > 0
        assert "objective" in result["diagnostics"][0]["message"].lower()

    def test_error_response_with_invalid_limit(self):
        """Test error response with invalid limit."""
        from lean_proof_auto_mcp.tools.rank_targets import rank_targets

        result = rank_targets({"file": "test.lean", "limit": 0})

        assert result["status"] == "fail"
        assert len(result["diagnostics"]) > 0
        assert "limit" in result["diagnostics"][0]["message"].lower()

    def test_error_response_with_invalid_min_confidence(self):
        """Test error response with invalid min_confidence."""
        from lean_proof_auto_mcp.tools.rank_targets import rank_targets

        result = rank_targets({"file": "test.lean", "min_confidence": 1.5})

        assert result["status"] == "fail"
        assert len(result["diagnostics"]) > 0
        assert "min_confidence" in result["diagnostics"][0]["message"].lower()


class TestGenerateRunId:
    """Test cases for _generate_run_id function."""

    def test_deterministic_run_id(self):
        """Test that run_id is deterministic."""
        from lean_proof_auto_mcp.tools.rank_targets import _generate_run_id

        run_id1 = _generate_run_id("test.lean", "rank")
        run_id2 = _generate_run_id("test.lean", "rank")

        assert run_id1 == run_id2

    def test_different_files_different_run_ids(self):
        """Test that different files produce different run_ids."""
        from lean_proof_auto_mcp.tools.rank_targets import _generate_run_id

        run_id1 = _generate_run_id("test1.lean", "rank")
        run_id2 = _generate_run_id("test2.lean", "rank")

        assert run_id1 != run_id2

    def test_run_id_format(self):
        """Test that run_id has expected format."""
        from lean_proof_auto_mcp.tools.rank_targets import _generate_run_id

        run_id = _generate_run_id("test.lean", "rank")

        # Should start with prefix
        assert run_id.startswith("rank-")

        # Should have hash suffix
        parts = run_id.split("-")
        assert len(parts) == 2
        assert len(parts[1]) == 8  # 8-character hash


class TestIntegrationScenarios:
    """Test integration scenarios with realistic inputs."""

    def test_valid_args_all_defaults(self):
        """Test with valid file and all defaults."""
        args = {"file": "test.lean"}

        result = _coerce_args(args)

        assert result.file == "test.lean"
        assert result.objective == "balanced"
        assert result.limit == 30
        assert result.include_components is True
        assert result.include_reasons is True
        assert result.use_deep_structure is False
        assert result.min_confidence == 0.0

    def test_valid_args_custom_objective(self):
        """Test with custom objective."""
        args = {"file": "test.lean", "objective": "maximize_success"}

        result = _coerce_args(args)

        assert result.objective == "maximize_success"

    def test_valid_args_custom_limit(self):
        """Test with custom limit."""
        args = {"file": "test.lean", "limit": 100}

        result = _coerce_args(args)

        assert result.limit == 100

    def test_valid_args_disable_components_and_reasons(self):
        """Test disabling components and reasons."""
        args = {
            "file": "test.lean",
            "include_components": False,
            "include_reasons": False,
        }

        result = _coerce_args(args)

        assert result.include_components is False
        assert result.include_reasons is False

    def test_valid_args_enable_deep_structure(self):
        """Test enabling deep structure."""
        args = {"file": "test.lean", "use_deep_structure": True}

        result = _coerce_args(args)

        assert result.use_deep_structure is True

    def test_valid_args_custom_min_confidence(self):
        """Test with custom min_confidence."""
        args = {"file": "test.lean", "min_confidence": 0.7}

        result = _coerce_args(args)

        assert result.min_confidence == 0.7

    def test_valid_args_all_custom(self):
        """Test with all custom values."""
        args = {
            "file": "path/to/file.lean",
            "objective": "maximize_impact",
            "limit": 50,
            "include_components": False,
            "include_reasons": True,
            "use_deep_structure": True,
            "min_confidence": 0.6,
        }

        result = _coerce_args(args)

        assert result.file == "path/to/file.lean"
        assert result.objective == "maximize_impact"
        assert result.limit == 50
        assert result.include_components is False
        assert result.include_reasons is True
        assert result.use_deep_structure is True
        assert result.min_confidence == 0.6


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_limit_boundary_min(self):
        """Test limit at minimum boundary."""
        args = {"file": "test.lean", "limit": 1}

        result = _coerce_args(args)

        assert result.limit == 1

    def test_limit_boundary_max(self):
        """Test limit at maximum boundary."""
        args = {"file": "test.lean", "limit": 500}

        result = _coerce_args(args)

        assert result.limit == 500

    def test_min_confidence_boundary_min(self):
        """Test min_confidence at minimum boundary."""
        args = {"file": "test.lean", "min_confidence": 0.0}

        result = _coerce_args(args)

        assert result.min_confidence == 0.0

    def test_min_confidence_boundary_max(self):
        """Test min_confidence at maximum boundary."""
        args = {"file": "test.lean", "min_confidence": 1.0}

        result = _coerce_args(args)

        assert result.min_confidence == 1.0

    def test_file_with_special_characters(self):
        """Test file path with special characters."""
        args = {"file": "path/to/my-file_v2.lean"}

        result = _coerce_args(args)

        assert result.file == "path/to/my-file_v2.lean"

    def test_file_with_spaces(self):
        """Test file path with spaces."""
        args = {"file": "path/to/my file.lean"}

        result = _coerce_args(args)

        assert result.file == "path/to/my file.lean"
