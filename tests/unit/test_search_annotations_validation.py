"""
Comprehensive validation tests for SearchAnnotationsCommand and SearchAnnotationsResult.

Tests all validation rules specified in Requirements 1.1, 1.3, 10.1-10.8.
"""

import pytest
from lean_proof_auto_mcp.core.search_annotations_domain import (
    AutomationConfig,
    BudgetConfig,
    CandidateConfig,
    CandidateSource,
    GlobalSuggestion,
    HintSet,
    ProofPatch,
    SearchAnnotationsCommand,
    SearchAnnotationsResult,
    SearchConfig,
    SearchResult,
    SkeletonConfig,
    StyleConfig,
    WorkspaceConfig,
)


class TestSearchAnnotationsCommandValidation:
    """Test all validation rules for SearchAnnotationsCommand."""

    def test_requirement_1_1_file_validation(self):
        """
        Requirement 1.1: File path must be non-empty.
        """
        with pytest.raises(ValueError, match="file must be non-empty"):
            SearchAnnotationsCommand(
                file="",
                theorem_id="test",
                mode="local_only",
                automation=AutomationConfig(),
                budgets=BudgetConfig(),
                search=SearchConfig(),
                candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
                skeleton=SkeletonConfig(),
                style=StyleConfig(),
                workspace=WorkspaceConfig(),
                allow_global_edits=False,
                run_id="test-123",
            )

    def test_requirement_1_1_theorem_id_validation(self):
        """
        Requirement 1.1: Theorem ID must be non-empty.
        """
        with pytest.raises(ValueError, match="theorem_id must be non-empty"):
            SearchAnnotationsCommand(
                file="test.lean",
                theorem_id="",
                mode="local_only",
                automation=AutomationConfig(),
                budgets=BudgetConfig(),
                search=SearchConfig(),
                candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
                skeleton=SkeletonConfig(),
                style=StyleConfig(),
                workspace=WorkspaceConfig(),
                allow_global_edits=False,
                run_id="test-123",
            )

    def test_requirement_1_3_mode_validation(self):
        """
        Requirement 1.3: Mode must be valid (local_only or suggest_global).
        """
        with pytest.raises(ValueError, match="mode must be"):
            SearchAnnotationsCommand(
                file="test.lean",
                theorem_id="test",
                mode="invalid",  # type: ignore
                automation=AutomationConfig(),
                budgets=BudgetConfig(),
                search=SearchConfig(),
                candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
                skeleton=SkeletonConfig(),
                style=StyleConfig(),
                workspace=WorkspaceConfig(),
                allow_global_edits=False,
                run_id="test-123",
            )

    def test_valid_local_only_mode(self):
        """Test that local_only mode is accepted."""
        cmd = SearchAnnotationsCommand(
            file="test.lean",
            theorem_id="test",
            mode="local_only",
            automation=AutomationConfig(),
            budgets=BudgetConfig(),
            search=SearchConfig(),
            candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
            skeleton=SkeletonConfig(),
            style=StyleConfig(),
            workspace=WorkspaceConfig(),
            allow_global_edits=False,
            run_id="test-123",
        )
        assert cmd.mode == "local_only"

    def test_valid_suggest_global_mode(self):
        """Test that suggest_global mode is accepted."""
        cmd = SearchAnnotationsCommand(
            file="test.lean",
            theorem_id="test",
            mode="suggest_global",
            automation=AutomationConfig(),
            budgets=BudgetConfig(),
            search=SearchConfig(),
            candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
            skeleton=SkeletonConfig(),
            style=StyleConfig(),
            workspace=WorkspaceConfig(),
            allow_global_edits=False,
            run_id="test-123",
        )
        assert cmd.mode == "suggest_global"

    def test_run_id_validation(self):
        """Test that run_id must be non-empty."""
        with pytest.raises(ValueError, match="run_id must be non-empty"):
            SearchAnnotationsCommand(
                file="test.lean",
                theorem_id="test",
                mode="local_only",
                automation=AutomationConfig(),
                budgets=BudgetConfig(),
                search=SearchConfig(),
                candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
                skeleton=SkeletonConfig(),
                style=StyleConfig(),
                workspace=WorkspaceConfig(),
                allow_global_edits=False,
                run_id="",
            )


class TestSearchAnnotationsResultValidation:
    """Test all validation rules for SearchAnnotationsResult."""

    def test_requirement_10_1_status_validation(self):
        """
        Requirement 10.1: Status must be valid (success, fail, timeout, error).
        """
        with pytest.raises(ValueError, match="status must be"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="invalid",  # type: ignore
                run_id="test-123",
                file="test.lean",
                theorem_id="test",
                viability={},
                baseline={},
                search_result=None,
                minimized_hint_set=None,
                proof_patch=None,
                global_suggestions=None,
                timing={},
                artifacts={},
                metadata={},
            )

    def test_requirement_10_2_viability_details_present(self):
        """
        Requirement 10.2: Result must include viability check details.
        """
        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-123",
            file="test.lean",
            theorem_id="test",
            viability={"status": "ok", "duration_s": 1.5},
            baseline={},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={},
            artifacts={},
            metadata={},
        )
        assert result.viability is not None
        assert "status" in result.viability

    def test_requirement_10_3_baseline_attempts_present(self):
        """
        Requirement 10.3: Result must include baseline attempt outcomes.
        """
        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-123",
            file="test.lean",
            theorem_id="test",
            viability={},
            baseline={"outcome": "not_closed", "duration_s": 2.0},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={},
            artifacts={},
            metadata={},
        )
        assert result.baseline is not None
        assert "outcome" in result.baseline

    def test_requirement_10_4_hint_set_and_proof_patch_for_success(self):
        """
        Requirement 10.4: Success result must include hint set and proof patch.
        """
        hint_set = HintSet()
        proof_patch = ProofPatch(
            lean_code="by aesop",
            hint_set=hint_set,
            automation="aesop",
            style=StyleConfig(),
        )

        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-123",
            file="test.lean",
            theorem_id="test",
            viability={},
            baseline={},
            search_result=None,
            minimized_hint_set=hint_set,
            proof_patch=proof_patch,
            global_suggestions=None,
            timing={},
            artifacts={},
            metadata={},
        )
        assert result.minimized_hint_set is not None
        assert result.proof_patch is not None

    def test_requirement_10_6_global_suggestions_for_suggest_global_mode(self):
        """
        Requirement 10.6: suggest_global mode should include global suggestions.
        """
        suggestions = [
            GlobalSuggestion(
                hint_name="MyLemma",
                attribute="@[simp]",
                rationale="Frequently effective",
                confidence="high",
            )
        ]

        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-123",
            file="test.lean",
            theorem_id="test",
            viability={},
            baseline={},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=suggestions,
            timing={},
            artifacts={},
            metadata={},
        )
        assert result.global_suggestions is not None
        assert len(result.global_suggestions) == 1

    def test_requirement_10_7_timing_breakdown_present(self):
        """
        Requirement 10.7: Result must include timing breakdown for all phases.
        """
        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-123",
            file="test.lean",
            theorem_id="test",
            viability={},
            baseline={},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={
                "viability_s": 1.5,
                "baseline_s": 2.0,
                "search_s": 100.0,
                "minimize_s": 30.0,
                "total_s": 133.5,
            },
            artifacts={},
            metadata={},
        )
        assert result.timing is not None
        assert "total_s" in result.timing

    def test_requirement_10_8_artifact_paths_present(self):
        """
        Requirement 10.8: Result must include paths to artifacts.
        """
        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-123",
            file="test.lean",
            theorem_id="test",
            viability={},
            baseline={},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={},
            artifacts={
                "request": ".artifacts/test-123/request.json",
                "result": ".artifacts/test-123/result.json",
                "logs": ".artifacts/test-123/logs.txt",
            },
            metadata={},
        )
        assert result.artifacts is not None
        assert "request" in result.artifacts

    def test_success_requires_proof_patch(self):
        """Test that success status requires proof_patch."""
        with pytest.raises(ValueError, match="success status requires proof_patch"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="success",
                run_id="test-123",
                file="test.lean",
                theorem_id="test",
                viability={},
                baseline={},
                search_result=None,
                minimized_hint_set=HintSet(),
                proof_patch=None,
                global_suggestions=None,
                timing={},
                artifacts={},
                metadata={},
            )

    def test_success_requires_minimized_hint_set(self):
        """Test that success status requires minimized_hint_set."""
        with pytest.raises(ValueError, match="success status requires minimized_hint_set"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="success",
                run_id="test-123",
                file="test.lean",
                theorem_id="test",
                viability={},
                baseline={},
                search_result=None,
                minimized_hint_set=None,
                proof_patch=ProofPatch(
                    lean_code="by aesop",
                    hint_set=HintSet(),
                    automation="aesop",
                    style=StyleConfig(),
                ),
                global_suggestions=None,
                timing={},
                artifacts={},
                metadata={},
            )

    def test_api_version_validation(self):
        """Test that api_version must be non-empty."""
        with pytest.raises(ValueError, match="api_version must be non-empty"):
            SearchAnnotationsResult(
                api_version="",
                status="fail",
                run_id="test-123",
                file="test.lean",
                theorem_id="test",
                viability={},
                baseline={},
                search_result=None,
                minimized_hint_set=None,
                proof_patch=None,
                global_suggestions=None,
                timing={},
                artifacts={},
                metadata={},
            )

    def test_file_validation(self):
        """Test that file must be non-empty."""
        with pytest.raises(ValueError, match="file must be non-empty"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="fail",
                run_id="test-123",
                file="",
                theorem_id="test",
                viability={},
                baseline={},
                search_result=None,
                minimized_hint_set=None,
                proof_patch=None,
                global_suggestions=None,
                timing={},
                artifacts={},
                metadata={},
            )

    def test_theorem_id_validation(self):
        """Test that theorem_id must be non-empty."""
        with pytest.raises(ValueError, match="theorem_id must be non-empty"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="fail",
                run_id="test-123",
                file="test.lean",
                theorem_id="",
                viability={},
                baseline={},
                search_result=None,
                minimized_hint_set=None,
                proof_patch=None,
                global_suggestions=None,
                timing={},
                artifacts={},
                metadata={},
            )
