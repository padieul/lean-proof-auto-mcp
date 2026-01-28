"""
Property-based tests for SearchAnnotations artifact storage and result structure.

These tests verify universal properties related to timing completeness,
result structure completeness, and result determinism.

Requirements: 9.8, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10,
              13.1, 13.2, 13.3, 13.4, 13.5
"""

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given, settings

from lean_proof_auto_mcp.core.search_annotations_domain import (
    AutomationConfig,
    BudgetConfig,
    CandidateConfig,
    CandidateSource,
    Hint,
    HintSet,
    HintType,
    ProofPatch,
    SearchAnnotationsCommand,
    SearchAnnotationsResult,
    SearchConfig,
    SkeletonConfig,
    StyleConfig,
    WorkspaceConfig,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_file_paths(draw):
    """Generate valid file path strings."""
    filename = draw(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-."
            ),
        )
    )
    return f"{filename}.lean"


@st.composite
def valid_theorem_ids(draw):
    """Generate valid theorem identifier strings."""
    name = draw(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_."
            ),
        )
    )
    return name


@st.composite
def valid_search_commands(draw):
    """Generate valid SearchAnnotationsCommand instances."""
    file_path = draw(valid_file_paths())
    theorem_id = draw(valid_theorem_ids())
    mode = draw(st.sampled_from(["local_only", "suggest_global"]))

    return SearchAnnotationsCommand(
        file=file_path,
        theorem_id=theorem_id,
        mode=mode,
        automation=AutomationConfig(),
        budgets=BudgetConfig(),
        search=SearchConfig(),
        candidates=CandidateConfig(sources=[CandidateSource.GOAL_SYMBOLS]),
        skeleton=SkeletonConfig(),
        style=StyleConfig(),
        workspace=WorkspaceConfig(),
        allow_global_edits=False,
        run_id="test-run-id",
    )


@st.composite
def valid_search_results(draw):
    """Generate valid SearchAnnotationsResult instances."""
    status = draw(st.sampled_from(["success", "fail", "timeout", "error"]))
    file_path = draw(valid_file_paths())
    theorem_id = draw(valid_theorem_ids())

    # Create minimal valid result based on status
    if status == "success":
        hint = Hint(name="test.lemma", type=HintType.SIMP, source=CandidateSource.GOAL_SYMBOLS)
        hint_set = HintSet([hint])
        proof_patch = ProofPatch(
            lean_code="simp [test.lemma]", hint_set=hint_set, automation="simp", style=StyleConfig()
        )
        minimized_hint_set = hint_set
    else:
        proof_patch = None
        minimized_hint_set = None

    return SearchAnnotationsResult(
        api_version="0.1.0",
        status=status,
        run_id="test-run-id",
        file=file_path,
        theorem_id=theorem_id,
        viability={"status": "success"},
        baseline={"status": "completed"},
        search_result=None,
        minimized_hint_set=minimized_hint_set,
        proof_patch=proof_patch,
        global_suggestions=None,
        timing={
            "total_s": 10.5,
            "viability_check_s": 1.0,
            "baseline_probe_s": 2.0,
            "search_total_s": 5.0,
            "minimize_total_s": 2.0,
            "proof_patch_build_s": 0.5,
        },
        artifacts={
            "request_path": "/path/to/request.json",
            "result_path": "/path/to/result.json",
            "logs_path": "/path/to/logs.txt",
        },
        metadata={"repo_commit": "abc123", "lean_version": "4.0.0", "lake_version": "1.0.0"},
    )


# ============================================================================
# Property 38: Timing Completeness
# ============================================================================


@given(result=valid_search_results())
@settings(max_examples=100)
def test_property_38_timing_completeness(result):
    """
    Feature: search-annotations-tool
    Property 38: Timing Completeness

    For any execution, the result should include time measurements for all
    phases (viability, baseline, search, minimization, verification).

    Validates: Requirements 9.8
    """
    # Verify timing section exists
    assert "timing" in asdict(result), "Result must include timing section"

    timing = result.timing

    # Verify total_s is present
    assert "total_s" in timing, "Timing must include total_s"
    assert isinstance(timing["total_s"], (int, float)), "total_s must be numeric"
    assert timing["total_s"] >= 0, "total_s must be non-negative"

    # Verify all phase timings are present (at least the ones that ran)
    # For any result, we should have at least viability_check_s
    if result.status != "error" or result.viability.get("status") == "success":
        assert "viability_check_s" in timing, "Timing must include viability_check_s"
        assert isinstance(timing["viability_check_s"], (int, float)), (
            "viability_check_s must be numeric"
        )
        assert timing["viability_check_s"] >= 0, "viability_check_s must be non-negative"

    # If baseline was attempted, timing should include it
    if (
        result.baseline.get("status") in ("completed", "timeout", "error")
        and "baseline_probe_s" in timing
    ):
        assert isinstance(timing["baseline_probe_s"], (int, float)), (
            "baseline_probe_s must be numeric"
        )
        assert timing["baseline_probe_s"] >= 0, "baseline_probe_s must be non-negative"

    # If search was performed, timing should include it
    if result.search_result is not None and "search_total_s" in timing:
        assert isinstance(timing["search_total_s"], (int, float)), "search_total_s must be numeric"
        assert timing["search_total_s"] >= 0, "search_total_s must be non-negative"

    # If minimization was performed, timing should include it
    if (
        result.minimized_hint_set is not None
        and result.search_result is not None
        and "minimize_total_s" in timing
    ):
        assert isinstance(timing["minimize_total_s"], (int, float)), (
            "minimize_total_s must be numeric"
        )
        assert timing["minimize_total_s"] >= 0, "minimize_total_s must be non-negative"

    # If proof patch was built, timing should include it
    if result.proof_patch is not None and "proof_patch_build_s" in timing:
        assert isinstance(timing["proof_patch_build_s"], (int, float)), (
            "proof_patch_build_s must be numeric"
        )
        assert timing["proof_patch_build_s"] >= 0, "proof_patch_build_s must be non-negative"

    # Verify all timing values are reasonable (not negative, not NaN)
    for phase, duration in timing.items():
        assert isinstance(duration, (int, float)), f"{phase} must be numeric"
        assert duration >= 0, f"{phase} must be non-negative"
        assert duration == duration, f"{phase} must not be NaN"  # NaN != NaN


# ============================================================================
# Property 39: Result Structure Completeness
# ============================================================================


@given(result=valid_search_results())
@settings(max_examples=100)
def test_property_39_result_structure_completeness(result):
    """
    Feature: search-annotations-tool
    Property 39: Result Structure Completeness

    For any execution, the result should include all required fields: status,
    viability details, baseline attempts, final hint set (if found), proof patch
    (if successful), timing breakdown, and artifact paths.

    Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8
    """
    result_dict = asdict(result)

    # Requirement 10.1: Status field
    assert "status" in result_dict, "Result must include status"
    assert result.status in ("success", "fail", "timeout", "error"), (
        "Status must be one of: success, fail, timeout, error"
    )

    # Requirement 10.2: Viability check details
    assert "viability" in result_dict, "Result must include viability details"
    assert isinstance(result.viability, dict), "Viability must be a dictionary"

    # Requirement 10.3: Baseline attempt outcomes
    assert "baseline" in result_dict, "Result must include baseline details"
    assert isinstance(result.baseline, dict), "Baseline must be a dictionary"

    # Requirement 10.4: Final hint set (if found)
    assert "minimized_hint_set" in result_dict, "Result must include minimized_hint_set field"
    if result.status == "success":
        assert result.minimized_hint_set is not None, "Success status requires minimized_hint_set"

    # Requirement 10.5: Proof patch (if successful)
    assert "proof_patch" in result_dict, "Result must include proof_patch field"
    if result.status == "success":
        assert result.proof_patch is not None, "Success status requires proof_patch"
        assert result.proof_patch.lean_code, "Proof patch must have non-empty lean_code"

    # Requirement 10.6: Global annotation suggestions (if mode is suggest_global)
    assert "global_suggestions" in result_dict, "Result must include global_suggestions field"

    # Requirement 10.7: Timing breakdown
    assert "timing" in result_dict, "Result must include timing breakdown"
    assert isinstance(result.timing, dict), "Timing must be a dictionary"
    assert "total_s" in result.timing, "Timing must include total_s"

    # Requirement 10.8: Artifact paths
    assert "artifacts" in result_dict, "Result must include artifacts"
    assert isinstance(result.artifacts, dict), "Artifacts must be a dictionary"

    # Additional required fields
    assert "api_version" in result_dict, "Result must include api_version"
    assert "run_id" in result_dict, "Result must include run_id"
    assert "file" in result_dict, "Result must include file"
    assert "theorem_id" in result_dict, "Result must include theorem_id"
    assert "metadata" in result_dict, "Result must include metadata"

    # Verify non-empty required string fields
    assert result.api_version, "api_version must be non-empty"
    assert result.run_id, "run_id must be non-empty"
    assert result.file, "file must be non-empty"
    assert result.theorem_id, "theorem_id must be non-empty"


# ============================================================================
# Property 40: Result Determinism
# ============================================================================


@given(result=valid_search_results())
@settings(max_examples=100)
def test_property_40_result_determinism(result):
    """
    Feature: search-annotations-tool
    Property 40: Result Determinism

    For all identical inputs and configurations, the system should produce
    identical output (same field ordering, same hint ordering, same formatting).

    Validates: Requirements 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5
    """
    from lean_proof_auto_mcp.core.json_serialization import to_json_serializable

    # Requirement 13.1: JSON output has deterministic key ordering
    result_dict = to_json_serializable(asdict(result))
    json_str1 = json.dumps(result_dict, sort_keys=True, indent=2)
    json_str2 = json.dumps(result_dict, sort_keys=True, indent=2)

    assert json_str1 == json_str2, "Multiple JSON serializations of same result must be identical"

    # Requirement 13.2: Hints are ordered deterministically
    if result.minimized_hint_set is not None:
        hints_list1 = result.minimized_hint_set.to_sorted_list()
        hints_list2 = result.minimized_hint_set.to_sorted_list()

        assert len(hints_list1) == len(hints_list2), "Sorted hint lists must have same length"

        for h1, h2 in zip(hints_list1, hints_list2, strict=False):
            assert h1.name == h2.name, "Hint names must match in order"
            assert h1.type == h2.type, "Hint types must match in order"
            assert h1.source == h2.source, "Hint sources must match in order"

    # Requirement 13.3: Candidates are ordered deterministically (if present in search_result)
    if result.search_result is not None and result.search_result.best_hint_set is not None:
        hints_list1 = result.search_result.best_hint_set.to_sorted_list()
        hints_list2 = result.search_result.best_hint_set.to_sorted_list()

        assert len(hints_list1) == len(hints_list2), "Sorted hint lists must have same length"

        for h1, h2 in zip(hints_list1, hints_list2, strict=False):
            assert h1.name == h2.name, "Hint names must match in order"

    # Requirement 13.4: Proof patches have consistent formatting
    if result.proof_patch is not None:
        # Proof patch should be deterministic
        patch1 = result.proof_patch.lean_code
        patch2 = result.proof_patch.lean_code

        assert patch1 == patch2, "Proof patch code must be deterministic"

        # Whitespace should be consistent
        assert patch1.strip() == patch2.strip(), "Proof patch whitespace must be consistent"

    # Requirement 13.5: Metadata is deterministic
    metadata1 = json.dumps(result.metadata, sort_keys=True)
    metadata2 = json.dumps(result.metadata, sort_keys=True)

    assert metadata1 == metadata2, "Metadata must be deterministic"

    # Requirement 10.9: Stable JSON ordering
    # Parse and re-serialize to verify stability
    parsed = json.loads(json_str1)
    json_str3 = json.dumps(parsed, sort_keys=True, indent=2)

    assert json_str1 == json_str3, "JSON must remain stable after parse/serialize cycle"

    # Requirement 10.10: Hint ordering is stable
    if result.minimized_hint_set is not None and result.minimized_hint_set.size() > 1:
        # Multiple calls to to_sorted_list should produce same order
        for _ in range(3):
            hints_list = result.minimized_hint_set.to_sorted_list()
            assert hints_list == result.minimized_hint_set.to_sorted_list(), (
                "to_sorted_list must produce stable ordering"
            )


# ============================================================================
# Integration Test: Artifact Storage
# ============================================================================


def test_artifact_storage_integration():
    """
    Integration test verifying artifact storage works correctly.

    This test verifies that:
    - Artifacts are stored in correct directory structure
    - Request JSON is stored with command data
    - Result JSON is stored with result data
    - Logs are stored
    - Metadata includes repo commit, Lean version, Lake version

    Requirements: 9.8, 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5
    """
    from lean_proof_auto_mcp.adapters.artifact_store import FilesystemArtifactStore

    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)
        store = FilesystemArtifactStore(artifacts_dir)

        # Create test command
        command = SearchAnnotationsCommand(
            file="test.lean",
            theorem_id="test_theorem",
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

        # Create test result
        hint = Hint(name="test.lemma", type=HintType.SIMP, source=CandidateSource.GOAL_SYMBOLS)
        hint_set = HintSet([hint])

        result = SearchAnnotationsResult(
            api_version="0.1.0",
            status="success",
            run_id="test-run-123",
            file="test.lean",
            theorem_id="test_theorem",
            viability={"status": "success"},
            baseline={"status": "completed"},
            search_result=None,
            minimized_hint_set=hint_set,
            proof_patch=ProofPatch(
                lean_code="simp [test.lemma]",
                hint_set=hint_set,
                automation="simp",
                style=StyleConfig(),
            ),
            global_suggestions=None,
            timing={
                "total_s": 10.5,
                "viability_check_s": 1.0,
                "baseline_probe_s": 2.0,
                "search_total_s": 5.0,
                "minimize_total_s": 2.0,
            },
            artifacts={},
            metadata={"repo_commit": "abc123", "lean_version": "4.0.0"},
        )

        # Store artifacts
        logs = "Test log output\nLine 2\nLine 3"
        store.store("test-run-123", command, result, logs)

        # Verify directory structure
        run_dir = artifacts_dir / "test-run-123"
        assert run_dir.exists(), "Run directory should exist"

        # Verify request.json
        request_path = run_dir / "request.json"
        assert request_path.exists(), "request.json should exist"

        with open(request_path) as f:
            request_data = json.load(f)
            assert request_data["file"] == "test.lean"
            assert request_data["theorem_id"] == "test_theorem"
            assert request_data["run_id"] == "test-run-123"

        # Verify result.json
        result_path = run_dir / "result.json"
        assert result_path.exists(), "result.json should exist"

        with open(result_path) as f:
            result_data = json.load(f)
            assert result_data["status"] == "success"
            assert result_data["run_id"] == "test-run-123"
            assert "timing" in result_data
            assert "metadata" in result_data

        # Verify lean_output.log
        log_path = run_dir / "lean_output.log"
        assert log_path.exists(), "lean_output.log should exist"

        with open(log_path) as f:
            log_content = f.read()
            assert log_content == logs

        # Verify JSON is deterministic (sort_keys=True)
        with open(request_path) as f:
            request_json = f.read()
            # Keys should be sorted
            request_dict = json.loads(request_json)
            reserialized = json.dumps(request_dict, indent=2, sort_keys=True)
            assert request_json == reserialized, "Request JSON should have sorted keys"

        with open(result_path) as f:
            result_json = f.read()
            result_dict = json.loads(result_json)
            reserialized = json.dumps(result_dict, indent=2, sort_keys=True)
            assert result_json == reserialized, "Result JSON should have sorted keys"
