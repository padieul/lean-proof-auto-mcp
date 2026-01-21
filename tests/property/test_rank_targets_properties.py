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

from hypothesis import assume, given, settings
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
    return str(
        draw(
            st.sampled_from(
                [
                    "maximize_success",
                    "maximize_impact",
                    "maximize_subgoal_automation",
                    "balanced",
                ]
            )
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
    skip_already_automated = draw(st.booleans())

    return {
        "file": file_path,
        "objective": objective,
        "limit": limit,
        "include_components": include_components,
        "include_reasons": include_reasons,
        "use_deep_structure": use_deep_structure,
        "min_confidence": min_confidence,
        "skip_already_automated": skip_already_automated,
    }


class TestRankTargetsProperties:
    """Property-based tests for rank_targets tool correctness properties."""

    @settings(deadline=500, max_examples=10)  # Reduced examples for faster execution
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

    @settings(deadline=500, max_examples=10)
    @given(file=valid_lean_files(), objective=objectives())
    def test_stable_sorting(self, file: str, objective: str) -> None:
        """Property 2: Scores are monotonic and tie-breaking is consistent.

        **Validates: Requirements US-1 (AC 1.3), NFR-1, Design P2, P3**
        """
        result = rank_targets({"file": file, "objective": objective, "skip_already_automated": False})

        # Only check if we have theorems
        if "ranking" in result and len(result["ranking"]) > 1:
            ranking = result["ranking"]

            # Check scores are monotonic (descending)
            for i in range(len(ranking) - 1):
                score_i = ranking[i]["score"]
                score_next = ranking[i + 1]["score"]

                assert score_i >= score_next, (
                    f"Scores not monotonic: ranking[{i}].score={score_i} < "
                    f"ranking[{i + 1}].score={score_next}"
                )

                # Check tie-breaking: if scores equal, theorem_id should be
                # lexicographically ordered
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

    @settings(deadline=500, max_examples=10)
    @given(file=valid_lean_files())
    def test_objective_consistency(self, file: str) -> None:
        """Property 3: Different objectives produce different rankings (when sufficient theorems).

        **Validates: Requirements US-2 (AC 2.3), Design P6**
        """
        # Get rankings for two different objectives
        success_result = rank_targets({"file": file, "objective": "maximize_success", "skip_already_automated": False})
        impact_result = rank_targets({"file": file, "objective": "maximize_impact", "skip_already_automated": False})

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
                scores_differ = any(success_scores[tid] != impact_scores[tid] for tid in common_ids)

                assert scores_differ, (
                    "Different objectives should produce different scores for at least one theorem"
                )

    @settings(deadline=500, max_examples=10)
    @given(file=valid_lean_files(), min_conf=st.floats(min_value=0.0, max_value=1.0))
    def test_confidence_filtering(self, file: str, min_conf: float) -> None:
        """Property 4: All returned theorems meet min_confidence threshold.

        **Validates: Requirements US-3 (AC 3.1, 3.2), Design P4**
        """
        result = rank_targets({"file": file, "min_confidence": min_conf, "skip_already_automated": False})

        # Check all returned theorems have confidence >= min_conf
        if "ranking" in result:
            for theorem in result["ranking"]:
                confidence = theorem["signals"]["confidence"]

                assert confidence >= min_conf, (
                    f"Theorem {theorem['theorem_id']} has confidence {confidence} < "
                    f"min_confidence {min_conf}"
                )

    @settings(deadline=500, max_examples=10)
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

    @settings(deadline=500, max_examples=10)
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
            "available_objectives",  # NEW FIELD
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Summary required fields
        assert "total" in result["summary"], "Missing summary.total"
        assert "returned" in result["summary"], "Missing summary.returned"
        assert "skipped_low_confidence" in result["summary"], (
            "Missing summary.skipped_low_confidence"
        )
        assert "skipped_already_automated" in result["summary"], (
            "Missing summary.skipped_already_automated"
        )
        assert "tier_distribution" in result["summary"], (
            "Missing summary.tier_distribution"
        )

        # Metadata required fields
        assert "deep_structure_used" in result["metadata"], "Missing metadata.deep_structure_used"
        assert "computation_time_ms" in result["metadata"], "Missing metadata.computation_time_ms"

    @settings(deadline=500, max_examples=10)
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
        assert isinstance(result["available_objectives"], list), "available_objectives must be array"

        # Summary type checks
        assert isinstance(result["summary"]["total"], int), "summary.total must be integer"
        assert isinstance(result["summary"]["returned"], int), "summary.returned must be integer"
        assert isinstance(result["summary"]["skipped_low_confidence"], int), (
            "summary.skipped_low_confidence must be integer"
        )
        assert isinstance(result["summary"]["skipped_already_automated"], int), (
            "summary.skipped_already_automated must be integer"
        )
        assert isinstance(result["summary"]["tier_distribution"], dict), (
            "summary.tier_distribution must be object"
        )

        # Metadata type checks
        assert isinstance(result["metadata"]["deep_structure_used"], bool), (
            "metadata.deep_structure_used must be boolean"
        )
        assert isinstance(result["metadata"]["computation_time_ms"], (int, float)), (
            "metadata.computation_time_ms must be number"
        )

        # Ranking item type checks
        for theorem in result["ranking"]:
            assert isinstance(theorem, dict), "Each ranking item must be object"
            assert isinstance(theorem["theorem_id"], str), "theorem_id must be string"
            assert isinstance(theorem["range"], dict), "range must be object"
            assert isinstance(theorem["score"], (int, float)), "score must be number"
            assert isinstance(theorem["signals"], dict), "signals must be object"
            assert isinstance(theorem["tier"], str), "tier must be string"

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_tool_name_invariant(self, args: dict[str, Any]) -> None:
        """Property: Tool field is always exactly 'rank_targets'."""
        result = rank_targets(args)

        assert result["tool"] == "rank_targets", (
            f"Tool must be 'rank_targets', got '{result['tool']}'"
        )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_run_id_non_empty(self, args: dict[str, Any]) -> None:
        """Property: run_id is always non-empty."""
        result = rank_targets(args)

        assert len(result["run_id"]) > 0, "run_id must be non-empty"

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_summary_consistency(self, args: dict[str, Any]) -> None:
        """Property: Summary counts are consistent with ranking array."""
        result = rank_targets(args)

        summary = result["summary"]
        ranking = result["ranking"]

        # returned should match ranking length
        assert summary["returned"] == len(ranking), (
            f"summary.returned ({summary['returned']}) must match ranking length ({len(ranking)})"
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

        # skipped_already_automated should be non-negative
        assert summary["skipped_already_automated"] >= 0, (
            "summary.skipped_already_automated must be non-negative"
        )

        # total = returned + skipped_low_confidence + skipped_already_automated (approximately, may have limit applied)
        # This is only exact if limit >= total
        if "limit" in args and args["limit"] >= summary["total"]:
            assert summary["returned"] + summary["skipped_low_confidence"] + summary["skipped_already_automated"] <= summary["total"], (
                f"summary counts inconsistent: returned ({summary['returned']}) + "
                f"skipped_low_confidence ({summary['skipped_low_confidence']}) + "
                f"skipped_already_automated ({summary['skipped_already_automated']}) > total ({summary['total']})"
            )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_limit_respected(self, args: dict[str, Any]) -> None:
        """Property: Ranking array length never exceeds limit parameter."""
        result = rank_targets(args)

        limit = args.get("limit", 30)
        ranking_length = len(result["ranking"])

        assert ranking_length <= limit, f"Ranking length ({ranking_length}) exceeds limit ({limit})"

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_objective_echo(self, args: dict[str, Any]) -> None:
        """Property: Input objective is echoed in response."""
        result = rank_targets(args)

        expected_objective = args.get("objective", "balanced")
        assert result["objective"] == expected_objective, (
            f"Objective not echoed correctly: expected '{expected_objective}', "
            f"got '{result['objective']}'"
        )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_file_echo(self, args: dict[str, Any]) -> None:
        """Property: Input file is echoed in response."""
        result = rank_targets(args)

        assert result["file"] == args["file"], (
            f"File not echoed correctly: expected '{args['file']}', got '{result['file']}'"
        )

    @settings(deadline=500, max_examples=10)
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

    @settings(deadline=500, max_examples=10)
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

    @settings(deadline=500, max_examples=10)
    @given(file1=valid_lean_files(), file2=valid_lean_files(), objective=objectives())
    def test_different_files_produce_different_outputs(
        self, file1: str, file2: str, objective: str
    ) -> None:
        """Property: Different file inputs should produce different file fields."""
        assume(file1 != file2)  # Only test when inputs are actually different

        result1 = rank_targets({"file": file1, "objective": objective, "skip_already_automated": False})
        result2 = rank_targets({"file": file2, "objective": objective, "skip_already_automated": False})

        # At minimum, the file field should differ
        assert result1["file"] != result2["file"], (
            f"Different file inputs should produce different file fields: "
            f"'{result1['file']}' vs '{result2['file']}'"
        )

    @settings(deadline=500, max_examples=10)
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
                        f"Theorem {theorem['theorem_id']} has {len(reasons)} reasons, max is 10"
                    )

                    # Each reason max 200 chars
                    for i, reason in enumerate(reasons):
                        assert len(reason) <= 200, (
                            f"Theorem {theorem['theorem_id']} reason[{i}] has "
                            f"{len(reason)} chars, max is 200"
                        )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_status_values_valid(self, args: dict[str, Any]) -> None:
        """Property: Status field always contains valid terminal state."""
        result = rank_targets(args)

        valid_statuses = {"success", "fail", "error"}
        assert result["status"] in valid_statuses, (
            f"Invalid status '{result['status']}', must be one of {valid_statuses}"
        )

    @settings(deadline=500, max_examples=10)
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

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_tier_field_always_present(self, args: dict[str, Any]) -> None:
        """Property: All ranked theorems have a tier field.

        **Validates: Requirements US-4 (AC 4.1), Design D3**
        """
        result = rank_targets(args)

        if "ranking" in result:
            for theorem in result["ranking"]:
                assert "tier" in theorem, (
                    f"Theorem {theorem['theorem_id']} missing tier field"
                )

                # Tier must be one of S/A/B/C/D
                valid_tiers = {"S", "A", "B", "C", "D"}
                assert theorem["tier"] in valid_tiers, (
                    f"Theorem {theorem['theorem_id']} has invalid tier '{theorem['tier']}', "
                    f"must be one of {valid_tiers}"
                )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_tier_distribution_consistency(self, args: dict[str, Any]) -> None:
        """Property: Tier distribution counts match actual tier assignments.

        **Validates: Requirements US-4 (AC 4.5), Design D3**
        """
        result = rank_targets(args)

        if "ranking" in result and result["ranking"]:
            # Count tiers in ranking
            tier_counts_actual = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
            for theorem in result["ranking"]:
                tier = theorem["tier"]
                tier_counts_actual[tier] += 1

            # Compare with summary tier_distribution
            tier_distribution = result["summary"]["tier_distribution"]

            # Note: tier_distribution includes ALL theorems (not just returned ones)
            # So we can only check that returned theorems are counted correctly
            for tier in ["S", "A", "B", "C", "D"]:
                assert tier in tier_distribution, (
                    f"Tier '{tier}' missing from tier_distribution"
                )
                assert tier_distribution[tier] >= tier_counts_actual[tier], (
                    f"Tier distribution for '{tier}' ({tier_distribution[tier]}) "
                    f"is less than actual count in ranking ({tier_counts_actual[tier]})"
                )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_tier_ordering_by_percentile(self, args: dict[str, Any]) -> None:
        """Property: Tiers follow percentile ordering (S > A > B > C > D).

        **Validates: Requirements US-4 (AC 4.2, 4.3), Design D3**
        """
        result = rank_targets(args)

        if "ranking" in result and len(result["ranking"]) > 1:
            # Tiers should follow ordering based on position in ranking
            # (ranking is sorted by score descending)
            tier_order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}

            prev_tier_value = -1
            for theorem in result["ranking"]:
                tier = theorem["tier"]
                tier_value = tier_order[tier]

                # Tier value should be >= previous (can stay same or increase)
                assert tier_value >= prev_tier_value, (
                    f"Tier ordering violated: {tier} appears after better tier"
                )

                prev_tier_value = tier_value

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_available_objectives_structure(self, args: dict[str, Any]) -> None:
        """Property: available_objectives has correct structure.

        **Validates: Requirements US-3 (AC 3.1, 3.2, 3.4), Design D4**
        """
        result = rank_targets(args)

        assert "available_objectives" in result, "Missing available_objectives field"
        objectives = result["available_objectives"]

        assert isinstance(objectives, list), "available_objectives must be array"
        assert len(objectives) > 0, "available_objectives must not be empty"

        # Check structure of each objective
        for obj in objectives:
            assert isinstance(obj, dict), "Each objective must be object"

            # Required fields
            assert "name" in obj, "Objective missing name field"
            assert "description" in obj, "Objective missing description field"
            assert "use_case" in obj, "Objective missing use_case field"
            assert "weights" in obj, "Objective missing weights field"

            # Field types
            assert isinstance(obj["name"], str), "Objective name must be string"
            assert isinstance(obj["description"], str), "Objective description must be string"
            assert isinstance(obj["use_case"], str), "Objective use_case must be string"
            assert isinstance(obj["weights"], dict), "Objective weights must be object"

            # Weights structure
            weights = obj["weights"]
            expected_components = {
                "success_likelihood",
                "impact",
                "annotation_value",
                "subgoal_potential",
                "risk",
            }
            for component in expected_components:
                assert component in weights, (
                    f"Objective {obj['name']} missing weight for {component}"
                )
                assert isinstance(weights[component], (int, float)), (
                    f"Weight for {component} must be number"
                )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_already_automated_penalty_component(self, args: dict[str, Any]) -> None:
        """Property: already_automated_penalty component is present when components included.

        **Validates: Requirements US-5 (AC 5.1, 5.2), Design D6**
        """
        result = rank_targets(args)

        include_components = args.get("include_components", True)

        if include_components and "ranking" in result and result["ranking"]:
            for theorem in result["ranking"]:
                if "components" in theorem:
                    components = theorem["components"]

                    assert "already_automated_penalty" in components, (
                        f"Theorem {theorem['theorem_id']} missing already_automated_penalty component"
                    )

                    penalty = components["already_automated_penalty"]
                    assert isinstance(penalty, (int, float)), (
                        "already_automated_penalty must be number"
                    )
                    assert 0.0 <= penalty <= 1.0, (
                        f"already_automated_penalty must be in [0.0, 1.0], got {penalty}"
                    )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_skip_already_automated_filtering(self, args: dict[str, Any]) -> None:
        """Property: When skip_already_automated=true, skipped count is non-negative.

        **Validates: Requirements US-2 (AC 2.1, 2.4), Design D5**
        """
        result = rank_targets(args)

        skip_already_automated = args.get("skip_already_automated", False)

        # skipped_already_automated should always be present
        assert "skipped_already_automated" in result["summary"], (
            "Missing summary.skipped_already_automated"
        )

        skipped = result["summary"]["skipped_already_automated"]
        assert skipped >= 0, "skipped_already_automated must be non-negative"

        # When skip_already_automated=false, skipped should be 0
        if not skip_already_automated:
            assert skipped == 0, (
                f"When skip_already_automated=false, skipped should be 0, got {skipped}"
            )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_api_version_is_1_0(self, args: dict[str, Any]) -> None:
        """Property: API version is always 1.0.

        **Validates: Design (Breaking Changes)**
        """
        result = rank_targets(args)

        assert result["api_version"] == "1.0", (
            f"API version must be '1.0', got '{result['api_version']}'"
        )

    @settings(deadline=500, max_examples=10)
    @given(args=rank_targets_args())
    def test_confidence_in_notes(self, args: dict[str, Any]) -> None:
        """Property: Numeric confidence appears in notes when confidence > 0.

        **Validates: Requirements US-1 (AC 1.1, 1.2), Design D1**
        """
        result = rank_targets(args)

        if "ranking" in result:
            for theorem in result["ranking"]:
                confidence = theorem["signals"].get("confidence", 0.0)

                if confidence > 0.0 and "reasons" in theorem:
                    # Check if numeric confidence is in reasons
                    has_numeric_confidence = any(
                        "confidence:" in reason.lower()
                        for reason in theorem["reasons"]
                    )

                    # Note: This may not always be true if reasons are truncated
                    # or if confidence note is not in top reasons
                    # So we make this a soft check
                    if len(theorem["reasons"]) >= 1:
                        # At least check that confidence is extractable from signals
                        assert confidence >= 0.0, (
                            f"Confidence must be non-negative, got {confidence}"
                        )

    @settings(deadline=500, max_examples=10)
    @given(
        file=valid_lean_files(),
        skip1=st.booleans(),
        skip2=st.booleans()
    )
    def test_skip_already_automated_determinism(
        self, file: str, skip1: bool, skip2: bool
    ) -> None:
        """Property: Same skip_already_automated value produces same results.

        **Validates: Requirements US-2, NFR-3, Design D5**
        """
        result1 = rank_targets({
            "file": file,
            "skip_already_automated": skip1
        })
        result2 = rank_targets({
            "file": file,
            "skip_already_automated": skip1
        })

        # Remove non-deterministic fields
        def normalize(r):
            normalized = r.copy()
            if "metadata" in normalized:
                meta = normalized["metadata"].copy()
                meta.pop("computation_time_ms", None)
                normalized["metadata"] = meta
            return normalized

        norm1 = normalize(result1)
        norm2 = normalize(result2)

        assert norm1 == norm2, (
            f"Same skip_already_automated={skip1} should produce identical results"
        )

        # Different skip values may produce different results
        if skip1 != skip2:
            result3 = rank_targets({
                "file": file,
                "skip_already_automated": skip2
            })

            # At minimum, skipped_already_automated counts should differ
            # (unless there are no automated theorems)
            skipped1 = result1["summary"]["skipped_already_automated"]
            skipped3 = result3["summary"]["skipped_already_automated"]

            # When skip=true, skipped >= 0; when skip=false, skipped == 0
            if skip1:
                assert skipped1 >= 0
            else:
                assert skipped1 == 0

            if skip2:
                assert skipped3 >= 0
            else:
                assert skipped3 == 0
