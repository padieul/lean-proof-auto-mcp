"""Property-based tests for rank_targets tool.

**Validates: Requirements US-1, US-2, US-3, US-4, NFR-1, Design P1-P6**

These tests use Hypothesis to verify correctness properties across many random inputs:
1. Determinism: Same input produces identical output (P1)
2. Stable Sorting: Scores are monotonic with consistent tie-breaking (P2, P3)
3. Objective Consistency: Different objectives produce different rankings (P6)
4. Confidence Filtering: All returned theorems meet min_confidence threshold (P4)
5. Score Bounds: All scores are in [0.0, 1.0] range (P5)
"""

from __future__ import annotations

from typing import Any

from hypothesis import assume, given
from hypothesis import strategies as st

from lean_proof_auto_mcp.tools.rank_targets import rank_targets


# Generators for test data
@st.composite
def valid_lean_files(draw) -> str:
    """Generate valid Lean file paths."""
    filename = draw(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=32, max_codepoint=126
            ),
            min_size=1,
            max_size=20,
        ).filter(lambda x: x.strip() and not x.startswith(".") and "/" not in x)
    )
    return f"{filename}.lean"


@st.composite
def objectives(draw) -> str:
    """Generate valid objective names."""
    return draw(
        st.sampled_from(
            [
                "maximize_success",
                "maximize_impact",
                "maximize_subgoal_automation",
                "balanced",
            ]
        )
    )


@st.composite
def rank_targets_args(draw) -> dict[str, Any]:
    """Generate valid rank_targets arguments."""
    file_path = draw(valid_lean_files())
    objective = draw(objectives())
    limit = draw(st.integers(min_value=1, max_value=100))
    include_components = draw(st.booleans())
    include_reasons = draw(st.booleans())
    use_deep_structure = draw(st.booleans())
    min_confidence = draw(st.floats(min_value=0.0, max_value=1.0))

    return {
        "file": file_path,
        "objective": objective,
        "limit": limit,
        "include_components": include_components,
        "include_reasons": include_reasons,
        "use_deep_structure": use_deep_structure,
        "min_confidence": min_confidence,
    }


class TestRankTargetsProperties:
    """Property-based tests for rank_targets tool correctness properties."""

    @given(args=rank_targets_args())
    def test_determinism(self, args: dict[str, Any]) -> None:
        """Property 1: Same input produces identical output across multiple calls.

        **Validates: Requirements US-1 (AC 1.3), NFR-1, Design P1**
        """
        result1 = rank_targets(args)
        result2 = rank_targets(args)
        result3 = rank_targets(args)

        # Remove non-deterministic fields (computation_time_ms) before comparison
        def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
            """Remove non-deterministic fields for comparison."""
            normalized = result.copy()
            if "metadata" in normalized:
                metadata = normalized["metadata"].copy()
                metadata.pop("computation_time_ms", None)
                normalized["metadata"] = metadata
            return normalized

        norm1 = normalize_result(result1)
        norm2 = normalize_result(result2)
        norm3 = normalize_result(result3)

        assert norm1 == norm2, "First and second calls should return identical responses"
        assert norm2 == norm3, "Second and third calls should return identical responses"
        assert norm1 == norm3, "First and third calls should return identical responses"

    @given(file=valid_lean_files(), objective=objectives())
    def test_stable_sorting(self, file: str, objective: str) -> None:
        """Property 2: Scores are monotonic and tie-breaking is consistent.

        **Validates: Requirements US-1 (AC 1.3), NFR-1, Design P2, P3**
        """
        result = rank_targets({"file": file, "objective": objective})

        # Only check if we have theorems
        if "ranking" in result and len(result["ranking"]) > 1:
            ranking = result["ranking"]

            # Check scores are monotonic (descending)
            for i in range(len(ranking) - 1):
                score_i = ranking[i]["score"]
                score_next = ranking[i + 1]["score"]

                assert score_i >= score_next, (
                    f"Scores not monotonic: ranking[{i}].score={score_i} < "
                    f"ranking[{i+1}].score={score_next}"
                )

                # Check tie-breaking: if scores equal, theorem_id should be lexicographically ordered
                if score_i == score_next:
                    theorem_id_i = ranking[i]["theorem_id"]
                    theorem_id_next = ranking[i + 1]["theorem_id"]

                    assert theorem_id_i <= theorem_id_next, (
                        f"Tie-breaking failed: same score {score_i}, but "
                        f"theorem_id '{theorem_id_i}' > '{theorem_id_next}'"
                    )

                    # If theorem_ids also equal, check start_line
                    if theorem_id_i == theorem_id_next:
                        start_i = ranking[i]["range"]["start_line"]
                        start_next = ranking[i + 1]["range"]["start_line"]

                        assert start_i <= start_next, (
                            f"Tie-breaking failed: same score and theorem_id, but "
                            f"start_line {start_i} > {start_next}"
                        )

    @given(file=valid_lean_files())
    def test_objective_consistency(self, file: str) -> None:
        """Property 3: Different objectives produce different rankings (when sufficient theorems).

        **Validates: Requirements US-2 (AC 2.3), Design P6**
        """
        # Get rankings for two different objectives
        success_result = rank_targets({"file": file, "objective": "maximize_success"})
        impact_result = rank_targets({"file": file, "objective": "maximize_impact"})

        # Only test if we have at least 2 theorems in both results
        if (
            "ranking" in success_result
            and "ranking" in impact_result
            and len(success_result["ranking"]) >= 2
            and len(impact_result["ranking"]) >= 2
        ):
            # Rankings should differ (at least in scores, possibly in order)
            success_ranking = success_result["ranking"]
            impact_ranking = impact_result["ranking"]

            # Check if scores differ for at least one theorem
            # (same theorem_id should have different scores under different objectives)
            success_scores = {t["theorem_id"]: t["score"] for t in success_ranking}
            impact_scores = {t["theorem_id"]: t["score"] for t in impact_ranking}

            # Find common theorems
            common_ids = set(success_scores.keys()) & set(impact_scores.keys())

            if common_ids:
                # At least one common theorem should have different scores
                scores_differ = any(
                    success_scores[tid] != impact_scores[tid] for tid in common_ids
                )

                assert scores_differ, (
                    "Different objectives should produce different scores for at least one theorem"
                )

    @given(file=valid_lean_files(), min_conf=st.floats(min_value=0.0, max_value=1.0))
    def test_confidence_filtering(self, file: str, min_conf: float) -> None:
        """Property 4: All returned theorems meet min_confidence threshold.

        **Validates: Requirements US-3 (AC 3.1, 3.2), Design P4**
        """
        result = rank_targets({"file": file, "min_confidence": min_conf})

        # Check all returned theorems have confidence >= min_conf
        if "ranking" in result:
            for theorem in result["ranking"]:
                confidence = theorem["signals"]["confidence"]

                assert confidence >= min_conf, (
                    f"Theorem {theorem['theorem_id']} has confidence {confidence} < "
                    f"min_confidence {min_conf}"
                )

    @given(args=rank_targets_args())
    def test_score_bounds(self, args: dict[str, Any]) -> None:
        """Property 5: All scores are in [0.0, 1.0] range.

        **Validates: Requirements US-4 (AC 4.3), Design P5**
        """
        result = rank_targets(args)

        # Check all scores in ranking
        if "ranking" in result:
            for theorem in result["ranking"]:
                # Check final score
                score = theorem["score"]
                assert 0.0 <= score <= 1.0, (
                    f"Theorem {theorem['theorem_id']} score {score} out of bounds [0.0, 1.0]"
                )

                # Check component scores if present
                if "components" in theorem:
                    components = theorem["components"]

                    for component_name, component_score in components.items():
                        assert 0.0 <= component_score <= 1.0, (
                            f"Theorem {theorem['theorem_id']} component {component_name} "
                            f"score {component_score} out of bounds [0.0, 1.0]"
                        )

    @given(args=rank_targets_args())
    def test_required_fields_always_present(self, args: dict[str, Any]) -> None:
        """Property: All required fields are always present regardless of input."""
        result = rank_targets(args)

        # Top-level required fields
        required_fields = [
            "api_version",
            "status",
            "run_id",
            "tool",
            "file",
            "objective",
            "ranking",
            "summary",
            "diagnostics",
            "metadata",
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Summary required fields
        assert "total" in result["summary"], "Missing summary.total"
        assert "returned" in result["summary"], "Missing summary.returned"
        assert "skipped_low_confidence" in result["summary"], "Missing summary.skipped_low_confidence"

        # Metadata required fields
        assert "deep_structure_used" in result["metadata"], "Missing metadata.deep_structure_used"
        assert "computation_time_ms" in result["metadata"], "Missing metadata.computation_time_ms"

    @given(args=rank_targets_args())
    def test_field_types_invariant(self, args: dict[str, Any]) -> None:
        """Property: Field types are always correct regardless of input."""
        result = rank_targets(args)

        # Type checks for required fields
        assert isinstance(result["api_version"], str), "api_version must be string"
        assert isinstance(result["status"], str), "status must be string"
        assert isinstance(result["run_id"], str), "run_id must be string"
        assert isinstance(result["tool"], str), "tool must be string"
        assert isinstance(result["file"], str), "file must be string"
        assert isinstance(result["objective"], str), "objective must be string"
        assert isinstance(result["ranking"], list), "ranking must be array"
        assert isinstance(result["summary"], dict), "summary must be object"
        assert isinstance(result["diagnostics"], list), "diagnostics must be array"
        assert isinstance(result["metadata"], dict), "metadata must be object"

        # Summary type checks
        assert isinstance(result["summary"]["total"], int), "summary.total must be integer"
        assert isinstance(result["summary"]["returned"], int), "summary.returned must be integer"
        assert isinstance(
            result["summary"]["skipped_low_confidence"], int
        ), "summary.skipped_low_confidence must be integer"

        # Metadata type checks
        assert isinstance(
            result["metadata"]["deep_structure_used"], bool
        ), "metadata.deep_structure_used must be boolean"
        assert isinstance(
            result["metadata"]["computation_time_ms"], (int, float)
        ), "metadata.computation_time_ms must be number"

        # Ranking item type checks
        for theorem in result["ranking"]:
            assert isinstance(theorem, dict), "Each ranking item must be object"
            assert isinstance(theorem["theorem_id"], str), "theorem_id must be string"
            assert isinstance(theorem["range"], dict), "range must be object"
            assert isinstance(theorem["score"], (int, float)), "score must be number"
            assert isinstance(theorem["signals"], dict), "signals must be object"

    @given(args=rank_targets_args())
    def test_tool_name_invariant(self, args: dict[str, Any]) -> None:
        """Property: Tool field is always exactly 'rank_targets'."""
        result = rank_targets(args)

        assert result["tool"] == "rank_targets", (
            f"Tool must be 'rank_targets', got '{result['tool']}'"
        )

    @given(args=rank_targets_args())
    def test_run_id_non_empty(self, args: dict[str, Any]) -> None:
        """Property: run_id is always non-empty."""
        result = rank_targets(args)

        assert len(result["run_id"]) > 0, "run_id must be non-empty"

    @given(args=rank_targets_args())
    def test_summary_consistency(self, args: dict[str, Any]) -> None:
        """Property: Summary counts are consistent with ranking array."""
        result = rank_targets(args)

        summary = result["summary"]
        ranking = result["ranking"]

        # returned should match ranking length
        assert summary["returned"] == len(ranking), (
            f"summary.returned ({summary['returned']}) must match "
            f"ranking length ({len(ranking)})"
        )

        # returned should be <= total
        assert summary["returned"] <= summary["total"], (
            f"summary.returned ({summary['returned']}) must be <= "
            f"summary.total ({summary['total']})"
        )

        # skipped_low_confidence should be non-negative
        assert summary["skipped_low_confidence"] >= 0, (
            "summary.skipped_low_confidence must be non-negative"
        )

        # total = returned + skipped_low_confidence (approximately, may have limit applied)
        # This is only exact if limit >= total
        if "limit" in args and args["limit"] >= summary["total"]:
            assert summary["returned"] + summary["skipped_low_confidence"] == summary["total"], (
                f"summary counts inconsistent: returned ({summary['returned']}) + "
                f"skipped ({summary['skipped_low_confidence']}) != total ({summary['total']})"
            )

    @given(args=rank_targets_args())
    def test_limit_respected(self, args: dict[str, Any]) -> None:
        """Property: Ranking array length never exceeds limit parameter."""
        result = rank_targets(args)

        limit = args.get("limit", 30)
        ranking_length = len(result["ranking"])

        assert ranking_length <= limit, (
            f"Ranking length ({ranking_length}) exceeds limit ({limit})"
        )

    @given(args=rank_targets_args())
    def test_objective_echo(self, args: dict[str, Any]) -> None:
        """Property: Input objective is echoed in response."""
        result = rank_targets(args)

        expected_objective = args.get("objective", "balanced")
        assert result["objective"] == expected_objective, (
            f"Objective not echoed correctly: expected '{expected_objective}', "
            f"got '{result['objective']}'"
        )

    @given(args=rank_targets_args())
    def test_file_echo(self, args: dict[str, Any]) -> None:
        """Property: Input file is echoed in response."""
        result = rank_targets(args)

        assert result["file"] == args["file"], (
            f"File not echoed correctly: expected '{args['file']}', got '{result['file']}'"
        )

    @given(args=rank_targets_args())
    def test_components_conditional(self, args: dict[str, Any]) -> None:
        """Property: Components are included only when include_components=true."""
        result = rank_targets(args)

        include_components = args.get("include_components", True)

        if "ranking" in result and result["ranking"]:
            first_theorem = result["ranking"][0]

            if include_components:
                assert "components" in first_theorem, (
                    "Components should be present when include_components=true"
                )
            else:
                assert "components" not in first_theorem, (
                    "Components should not be present when include_components=false"
                )

    @given(args=rank_targets_args())
    def test_reasons_conditional(self, args: dict[str, Any]) -> None:
        """Property: Reasons are included only when include_reasons=true."""
        result = rank_targets(args)

        include_reasons = args.get("include_reasons", True)

        if "ranking" in result and result["ranking"]:
            first_theorem = result["ranking"][0]

            if include_reasons:
                assert "reasons" in first_theorem, (
                    "Reasons should be present when include_reasons=true"
                )
            else:
                assert "reasons" not in first_theorem, (
                    "Reasons should not be present when include_reasons=false"
                )

    @given(file1=valid_lean_files(), file2=valid_lean_files(), objective=objectives())
    def test_different_files_produce_different_outputs(
        self, file1: str, file2: str, objective: str
    ) -> None:
        """Property: Different file inputs should produce different file fields."""
        assume(file1 != file2)  # Only test when inputs are actually different

        result1 = rank_targets({"file": file1, "objective": objective})
        result2 = rank_targets({"file": file2, "objective": objective})

        # At minimum, the file field should differ
        assert result1["file"] != result2["file"], (
            f"Different file inputs should produce different file fields: "
            f"'{result1['file']}' vs '{result2['file']}'"
        )

    @given(args=rank_targets_args())
    def test_reasons_bounded(self, args: dict[str, Any]) -> None:
        """Property: Reasons are limited to 10 items, each max 200 chars."""
        result = rank_targets(args)

        if "ranking" in result:
            for theorem in result["ranking"]:
                if "reasons" in theorem:
                    reasons = theorem["reasons"]

                    # Max 10 reasons
                    assert len(reasons) <= 10, (
                        f"Theorem {theorem['theorem_id']} has {len(reasons)} reasons, "
                        "max is 10"
                    )

                    # Each reason max 200 chars
                    for i, reason in enumerate(reasons):
                        assert len(reason) <= 200, (
                            f"Theorem {theorem['theorem_id']} reason[{i}] has "
                            f"{len(reason)} chars, max is 200"
                        )

    @given(args=rank_targets_args())
    def test_status_values_valid(self, args: dict[str, Any]) -> None:
        """Property: Status field always contains valid terminal state."""
        result = rank_targets(args)

        valid_statuses = {"success", "fail", "error"}
        assert result["status"] in valid_statuses, (
            f"Invalid status '{result['status']}', must be one of {valid_statuses}"
        )

    @given(args=rank_targets_args())
    def test_location_validity(self, args: dict[str, Any]) -> None:
        """Property: All location line numbers are positive and properly ordered."""
        result = rank_targets(args)

        if "ranking" in result:
            for theorem in result["ranking"]:
                range_obj = theorem["range"]

                # Line numbers must be non-negative
                assert range_obj["start_line"] >= 0, (
                    f"start_line must be >= 0, got {range_obj['start_line']}"
                )
                assert range_obj["end_line"] >= 0, (
                    f"end_line must be >= 0, got {range_obj['end_line']}"
                )

                # start_line <= end_line
                assert range_obj["start_line"] <= range_obj["end_line"], (
                    f"start_line ({range_obj['start_line']}) must be <= "
                    f"end_line ({range_obj['end_line']})"
                )
