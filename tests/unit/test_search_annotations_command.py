"""
Unit tests for SearchAnnotationsCommand and SearchAnnotationsResult.

Tests validation logic and immutability of command and result data structures.
"""

import pytest
from lean_proof_auto_mcp.core.search_annotations_domain import (
    AutomationConfig,
    BudgetConfig,
    CandidateConfig,
    CandidateSource,
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


class TestSearchAnnotationsCommand:
    """Test SearchAnnotationsCommand validation and immutability."""

    def test_valid_command_creation(self):
        """Test creating a valid command with all required fields."""
        cmd = SearchAnnotationsCommand(
            file="test.lean",
            theorem_id="my_theorem",
            mode="local_only",
            automation=AutomationConfig(),
            budgets=BudgetConfig(),
            search=SearchConfig(),
            candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
            skeleton=SkeletonConfig(),
            style=StyleConfig(),
            workspace=WorkspaceConfig(),
            allow_global_edits=False,
            run_id="test-run-123",
        )

        assert cmd.file == "test.lean"
        assert cmd.theorem_id == "my_theorem"
        assert cmd.mode == "local_only"
        assert cmd.run_id == "test-run-123"

    def test_empty_file_raises_error(self):
        """Test that empty file path raises ValueError."""
        with pytest.raises(ValueError, match="file must be non-empty"):
            SearchAnnotationsCommand(
                file="",
                theorem_id="my_theorem",
                mode="local_only",
                automation=AutomationConfig(),
                budgets=BudgetConfig(),
                search=SearchConfig(),
                candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
                skeleton=SkeletonConfig(),
                style=StyleConfig(),
                workspace=WorkspaceConfig(),
                allow_global_edits=False,
                run_id="test-run-123",
            )

    def test_empty_theorem_id_raises_error(self):
        """Test that empty theorem_id raises ValueError."""
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
                run_id="test-run-123",
            )

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="mode must be"):
            SearchAnnotationsCommand(
                file="test.lean",
                theorem_id="my_theorem",
                mode="invalid_mode",  # type: ignore
                automation=AutomationConfig(),
                budgets=BudgetConfig(),
                search=SearchConfig(),
                candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
                skeleton=SkeletonConfig(),
                style=StyleConfig(),
                workspace=WorkspaceConfig(),
                allow_global_edits=False,
                run_id="test-run-123",
            )

    def test_empty_run_id_raises_error(self):
        """Test that empty run_id raises ValueError."""
        with pytest.raises(ValueError, match="run_id must be non-empty"):
            SearchAnnotationsCommand(
                file="test.lean",
                theorem_id="my_theorem",
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

    def test_command_is_immutable(self):
        """Test that command is immutable (frozen dataclass)."""
        cmd = SearchAnnotationsCommand(
            file="test.lean",
            theorem_id="my_theorem",
            mode="local_only",
            automation=AutomationConfig(),
            budgets=BudgetConfig(),
            search=SearchConfig(),
            candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
            skeleton=SkeletonConfig(),
            style=StyleConfig(),
            workspace=WorkspaceConfig(),
            allow_global_edits=False,
            run_id="test-run-123",
        )

        with pytest.raises(AttributeError):
            cmd.file = "modified.lean"  # type: ignore


class TestSearchAnnotationsResult:
    """Test SearchAnnotationsResult validation and immutability."""

    def test_valid_success_result_creation(self):
        """Test creating a valid success result with all required fields."""
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
            run_id="test-run-123",
            file="test.lean",
            theorem_id="my_theorem",
            viability={"status": "ok"},
            baseline={"outcome": "not_closed"},
            search_result=SearchResult(
                outcome="closed",
                best_hint_set=hint_set,
                attempts=10,
                explored_sets=5,
                evidence=None,
            ),
            minimized_hint_set=hint_set,
            proof_patch=proof_patch,
            global_suggestions=None,
            timing={"total_s": 10.5},
            artifacts={"request": "path/to/request.json"},
            metadata={"lean_version": "4.0.0"},
        )

        assert result.status == "success"
        assert result.run_id == "test-run-123"
        assert result.proof_patch is not None

    def test_valid_fail_result_creation(self):
        """Test creating a valid fail result without proof patch."""
        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-123",
            file="test.lean",
            theorem_id="my_theorem",
            viability={"status": "ok"},
            baseline={"outcome": "not_closed"},
            search_result=SearchResult(
                outcome="failed",
                best_hint_set=None,
                attempts=100,
                explored_sets=50,
                evidence=None,
            ),
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={"total_s": 300.0},
            artifacts={"request": "path/to/request.json"},
            metadata={"lean_version": "4.0.0"},
        )

        assert result.status == "fail"
        assert result.proof_patch is None
        assert result.minimized_hint_set is None

    def test_empty_api_version_raises_error(self):
        """Test that empty api_version raises ValueError."""
        with pytest.raises(ValueError, match="api_version must be non-empty"):
            SearchAnnotationsResult(
                api_version="",
                status="success",
                run_id="test-run-123",
                file="test.lean",
                theorem_id="my_theorem",
                viability={"status": "ok"},
                baseline={"outcome": "not_closed"},
                search_result=None,
                minimized_hint_set=HintSet(),
                proof_patch=ProofPatch(
                    lean_code="by aesop",
                    hint_set=HintSet(),
                    automation="aesop",
                    style=StyleConfig(),
                ),
                global_suggestions=None,
                timing={"total_s": 10.5},
                artifacts={"request": "path/to/request.json"},
                metadata={"lean_version": "4.0.0"},
            )

    def test_invalid_status_raises_error(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="status must be"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="invalid",  # type: ignore
                run_id="test-run-123",
                file="test.lean",
                theorem_id="my_theorem",
                viability={"status": "ok"},
                baseline={"outcome": "not_closed"},
                search_result=None,
                minimized_hint_set=None,
                proof_patch=None,
                global_suggestions=None,
                timing={"total_s": 10.5},
                artifacts={"request": "path/to/request.json"},
                metadata={"lean_version": "4.0.0"},
            )

    def test_success_without_proof_patch_raises_error(self):
        """Test that success status without proof_patch raises ValueError."""
        with pytest.raises(ValueError, match="success status requires proof_patch"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="success",
                run_id="test-run-123",
                file="test.lean",
                theorem_id="my_theorem",
                viability={"status": "ok"},
                baseline={"outcome": "not_closed"},
                search_result=None,
                minimized_hint_set=HintSet(),
                proof_patch=None,  # Missing proof_patch for success
                global_suggestions=None,
                timing={"total_s": 10.5},
                artifacts={"request": "path/to/request.json"},
                metadata={"lean_version": "4.0.0"},
            )

    def test_success_without_minimized_hint_set_raises_error(self):
        """Test that success status without minimized_hint_set raises ValueError."""
        with pytest.raises(ValueError, match="success status requires minimized_hint_set"):
            SearchAnnotationsResult(
                api_version="0.1.0",
                status="success",
                run_id="test-run-123",
                file="test.lean",
                theorem_id="my_theorem",
                viability={"status": "ok"},
                baseline={"outcome": "not_closed"},
                search_result=None,
                minimized_hint_set=None,  # Missing minimized_hint_set for success
                proof_patch=ProofPatch(
                    lean_code="by aesop",
                    hint_set=HintSet(),
                    automation="aesop",
                    style=StyleConfig(),
                ),
                global_suggestions=None,
                timing={"total_s": 10.5},
                artifacts={"request": "path/to/request.json"},
                metadata={"lean_version": "4.0.0"},
            )

    def test_result_is_immutable(self):
        """Test that result is immutable (frozen dataclass)."""
        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="fail",
            run_id="test-run-123",
            file="test.lean",
            theorem_id="my_theorem",
            viability={"status": "ok"},
            baseline={"outcome": "not_closed"},
            search_result=None,
            minimized_hint_set=None,
            proof_patch=None,
            global_suggestions=None,
            timing={"total_s": 10.5},
            artifacts={"request": "path/to/request.json"},
            metadata={"lean_version": "4.0.0"},
        )

        with pytest.raises(AttributeError):
            result.status = "success"  # type: ignore
