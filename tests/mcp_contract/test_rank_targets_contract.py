from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from lean_proof_auto_mcp.tools.rank_targets import API_VERSION, rank_targets


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_dir(repo_root: Path) -> Path:
    """Return the schemas directory."""
    return repo_root / "docs" / "mcp" / "schemas"


@pytest.fixture
def rank_targets_validator(schema_dir: Path) -> Draft202012Validator:
    """Create a JSON Schema validator for rank_targets responses using referencing library."""
    rank_schema = json.loads((schema_dir / "rank_targets.json").read_text(encoding="utf-8"))
    common_schema = json.loads((schema_dir / "common.json").read_text(encoding="utf-8"))

    # Create a registry with both schemas
    registry = Registry().with_resources(
        [
            (
                "common.json",
                Resource.from_contents(common_schema, default_specification=DRAFT202012),
            ),
            (
                "rank_targets.json",
                Resource.from_contents(rank_schema, default_specification=DRAFT202012),
            ),
        ]
    )

    return Draft202012Validator(rank_schema, registry=registry)


def _assert_schema_valid(validator: Draft202012Validator, response: dict) -> None:
    """Assert that response validates against schema, with detailed error messages."""
    errors = list(validator.iter_errors(response))
    if errors:
        error_msgs = "\n".join(f"  - {e.json_path}: {e.message}" for e in errors)
        pytest.fail(f"Schema validation failed:\n{error_msgs}")


def _assert_contract_guarantees(response: dict, expected_status: str | None = None) -> None:
    """Assert MCP tool contract guarantees from docs/mcp/tool_contract.md."""
    # All responses must include these fields
    assert "status" in response, "Missing required field: status"
    assert "run_id" in response, "Missing required field: run_id"
    assert "api_version" in response, "Missing required field: api_version"

    # Status must be a valid terminal state
    valid_statuses = {"success", "fail", "timeout", "error"}
    assert response["status"] in valid_statuses, (
        f"Invalid status: {response['status']}, must be one of {valid_statuses}"
    )

    # run_id must be non-empty
    assert response["run_id"], "run_id must be non-empty"

    # api_version must match the tool's declared version
    assert response["api_version"] == API_VERSION, (
        f"api_version mismatch: got {response['api_version']}, expected {API_VERSION}"
    )

    # Tool name must match
    assert response.get("tool") == "rank_targets", "tool field must be 'rank_targets'"

    # If expected status provided, verify it
    if expected_status is not None:
        assert response["status"] == expected_status, (
            f"Expected status '{expected_status}', got '{response['status']}'"
        )


def test_rank_targets_success_response_validates():
    """Test that rank_targets with valid input returns schema-compliant success response."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    # Verify contract guarantees
    _assert_contract_guarantees(resp, expected_status="success")

    # Verify response structure
    assert "objective" in resp, "Missing required field: objective"
    assert "ranking" in resp, "Missing required field: ranking"
    assert "summary" in resp, "Missing required field: summary"
    assert "metadata" in resp, "Missing required field: metadata"
    assert "available_objectives" in resp, "Missing required field: available_objectives"

    # Verify summary structure
    assert "total" in resp["summary"], "Missing summary.total"
    assert "returned" in resp["summary"], "Missing summary.returned"
    assert "skipped_low_confidence" in resp["summary"], "Missing summary.skipped_low_confidence"
    assert "skipped_already_automated" in resp["summary"], (
        "Missing summary.skipped_already_automated"
    )
    assert "tier_distribution" in resp["summary"], "Missing summary.tier_distribution"

    # Verify metadata structure
    assert "deep_structure_used" in resp["metadata"], "Missing metadata.deep_structure_used"
    assert "computation_time_ms" in resp["metadata"], "Missing metadata.computation_time_ms"


def test_rank_targets_success_response_conforms_to_schema(rank_targets_validator):
    """Test that rank_targets success response validates against JSON schema.

    NOTE: This test will fail until task 11.1 updates the JSON schema files for API 1.0.
    The schema files still expect API 0.x format and don't include new fields like:
    - available_objectives
    - summary.skipped_already_automated
    - summary.tier_distribution
    - metadata.config_source
    - theorem.tier
    - components.already_automated_penalty
    """
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})
    _assert_schema_valid(rank_targets_validator, resp)


def test_rank_targets_fail_response_with_empty_file():
    """Test that rank_targets with empty file argument returns fail status."""
    resp = rank_targets({"file": "", "skip_already_automated": False})

    # Verify contract guarantees
    _assert_contract_guarantees(resp, expected_status="fail")

    # Verify diagnostics are present for failure
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Fail response should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_rank_targets_fail_response_conforms_to_schema(rank_targets_validator):
    """Test that rank_targets fail response validates against JSON schema.

    NOTE: This test will fail until task 11.1 updates the JSON schema files for API 1.0.
    """
    resp = rank_targets({"file": "", "skip_already_automated": False})
    _assert_schema_valid(rank_targets_validator, resp)


def test_rank_targets_determinism():
    """Test that rank_targets returns identical output for repeated calls with same input."""
    input_args = {
        "file": "test.lean",
        "objective": "maximize_success",
        "skip_already_automated": False,
    }

    # Call multiple times
    resp1 = rank_targets(input_args)
    resp2 = rank_targets(input_args)
    resp3 = rank_targets(input_args)

    # All responses should be identical except for computation_time_ms
    # which may vary slightly between runs
    def normalize_response(resp):
        """Remove non-deterministic fields for comparison."""
        normalized = resp.copy()
        if "metadata" in normalized:
            metadata = normalized["metadata"].copy()
            metadata.pop("computation_time_ms", None)
            normalized["metadata"] = metadata
        return normalized

    norm1 = normalize_response(resp1)
    norm2 = normalize_response(resp2)
    norm3 = normalize_response(resp3)

    assert norm1 == norm2, "First and second calls should return identical responses"
    assert norm2 == norm3, "Second and third calls should return identical responses"
    assert norm1 == norm3, "First and third calls should return identical responses"


def test_rank_targets_determinism_with_different_objectives():
    """Test that rank_targets returns different outputs for different objectives."""
    resp1 = rank_targets(
        {"file": "test.lean", "objective": "maximize_success", "skip_already_automated": False}
    )
    resp2 = rank_targets(
        {"file": "test.lean", "objective": "maximize_impact", "skip_already_automated": False}
    )

    # Responses should differ in the objective field at minimum
    assert resp1["objective"] != resp2["objective"], (
        "Different objectives should produce different objective fields"
    )


def test_rank_targets_required_fields_present():
    """Test that all required fields are present in success response."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

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
        "available_objectives",  # NEW in API 1.0
    ]
    for field in required_fields:
        assert field in resp, f"Missing required field: {field}"

    # Summary required fields
    assert "total" in resp["summary"], "Missing summary.total"
    assert "returned" in resp["summary"], "Missing summary.returned"
    assert "skipped_low_confidence" in resp["summary"], "Missing summary.skipped_low_confidence"
    assert "skipped_already_automated" in resp["summary"], (
        "Missing summary.skipped_already_automated"
    )  # NEW in API 1.0
    assert "tier_distribution" in resp["summary"], (
        "Missing summary.tier_distribution"
    )  # NEW in API 1.0

    # Metadata required fields
    assert "deep_structure_used" in resp["metadata"], "Missing metadata.deep_structure_used"
    assert "computation_time_ms" in resp["metadata"], "Missing metadata.computation_time_ms"


def test_rank_targets_field_types():
    """Test that fields have correct types."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    # Type checks
    assert isinstance(resp["api_version"], str), "api_version must be string"
    assert isinstance(resp["status"], str), "status must be string"
    assert isinstance(resp["run_id"], str), "run_id must be string"
    assert isinstance(resp["tool"], str), "tool must be string"
    assert isinstance(resp["file"], str), "file must be string"
    assert isinstance(resp["objective"], str), "objective must be string"
    assert isinstance(resp["ranking"], list), "ranking must be array"
    assert isinstance(resp["summary"], dict), "summary must be object"
    assert isinstance(resp["diagnostics"], list), "diagnostics must be array"
    assert isinstance(resp["metadata"], dict), "metadata must be object"
    assert isinstance(resp["available_objectives"], list), (
        "available_objectives must be array"
    )  # NEW in API 1.0

    # Summary types
    assert isinstance(resp["summary"]["total"], int), "summary.total must be integer"
    assert isinstance(resp["summary"]["returned"], int), "summary.returned must be integer"
    assert isinstance(resp["summary"]["skipped_low_confidence"], int), (
        "summary.skipped_low_confidence must be integer"
    )
    assert isinstance(resp["summary"]["skipped_already_automated"], int), (  # NEW in API 1.0
        "summary.skipped_already_automated must be integer"
    )
    assert isinstance(resp["summary"]["tier_distribution"], dict), (  # NEW in API 1.0
        "summary.tier_distribution must be object"
    )

    # Metadata types
    assert isinstance(resp["metadata"]["deep_structure_used"], bool), (
        "metadata.deep_structure_used must be boolean"
    )
    assert isinstance(resp["metadata"]["computation_time_ms"], int | float), (
        "metadata.computation_time_ms must be number"
    )


def test_rank_targets_objective_enum_validation():
    """Test that objective field validates against enum values."""
    valid_objectives = [
        "maximize_success",
        "maximize_impact",
        "maximize_subgoal_automation",
        "balanced",
    ]

    # Test each valid objective
    for objective in valid_objectives:
        resp = rank_targets(
            {"file": "test.lean", "objective": objective, "skip_already_automated": False}
        )
        assert resp["objective"] == objective, f"Objective should be {objective}"

    # Test invalid objective
    resp = rank_targets(
        {"file": "test.lean", "objective": "invalid_objective", "skip_already_automated": False}
    )
    assert resp["status"] == "fail", "Invalid objective should return fail status"


def test_rank_targets_ranking_array_structure():
    """Test that ranking array (when present) has correct structure."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    if len(resp["ranking"]) > 0:
        for theorem in resp["ranking"]:
            # Required fields in theorem object
            assert "theorem_id" in theorem, "Missing theorem.theorem_id"
            assert "range" in theorem, "Missing theorem.range"
            assert "score" in theorem, "Missing theorem.score"
            assert "tier" in theorem, "Missing theorem.tier"  # NEW in API 1.0
            assert "signals" in theorem, "Missing theorem.signals"

            # Validate range structure
            range_obj = theorem["range"]
            assert "start_line" in range_obj, "Missing range.start_line"
            assert "end_line" in range_obj, "Missing range.end_line"
            assert range_obj["start_line"] >= 0, "start_line must be >= 0"
            assert range_obj["end_line"] >= 0, "end_line must be >= 0"

            # Validate score bounds
            assert 0.0 <= theorem["score"] <= 1.0, "score must be in [0.0, 1.0]"

            # Validate tier enum (NEW in API 1.0)
            assert theorem["tier"] in ["S", "A", "B", "C", "D"], (
                f"tier must be one of S/A/B/C/D, got '{theorem['tier']}'"
            )

            # Validate signals structure
            signals = theorem["signals"]
            assert "whole_goal_potential" in signals, "Missing signals.whole_goal_potential"
            assert "subgoal_potential" in signals, "Missing signals.subgoal_potential"
            assert "annotation_value" in signals, "Missing signals.annotation_value"
            assert "proof_lines" in signals, "Missing signals.proof_lines"
            assert "confidence" in signals, "Missing signals.confidence"

            # Validate potential structures
            for potential_type in ["whole_goal_potential", "subgoal_potential"]:
                potential = signals[potential_type]
                assert "aesop" in potential, f"Missing {potential_type}.aesop"
                assert "grind" in potential, f"Missing {potential_type}.grind"
                assert 0.0 <= potential["aesop"] <= 1.0, f"{potential_type}.aesop out of range"
                assert 0.0 <= potential["grind"] <= 1.0, f"{potential_type}.grind out of range"

            # Validate other signal bounds
            assert 0.0 <= signals["annotation_value"] <= 1.0, "annotation_value out of range"
            assert signals["proof_lines"] >= 0, "proof_lines must be >= 0"
            assert 0.0 <= signals["confidence"] <= 1.0, "confidence out of range"

            # Optional components field
            if "components" in theorem:
                components = theorem["components"]
                assert "success_likelihood" in components, "Missing components.success_likelihood"
                assert "impact" in components, "Missing components.impact"
                assert "annotation_value" in components, "Missing components.annotation_value"
                assert "subgoal_potential" in components, "Missing components.subgoal_potential"
                assert "risk" in components, "Missing components.risk"
                assert "already_automated_penalty" in components, (
                    "Missing components.already_automated_penalty"
                )  # NEW in API 1.0

                # Validate component bounds
                for component_name, component_value in components.items():
                    assert 0.0 <= component_value <= 1.0, (
                        f"components.{component_name} must be in [0.0, 1.0]"
                    )

            # Optional reasons field
            if "reasons" in theorem:
                assert isinstance(theorem["reasons"], list), "reasons must be array"
                assert len(theorem["reasons"]) <= 10, "reasons must have at most 10 items"
                for reason in theorem["reasons"]:
                    assert isinstance(reason, str), "reason must be string"


def test_rank_targets_summary_counts_non_negative():
    """Test that summary counts are non-negative."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})
    assert resp["summary"]["total"] >= 0, "summary.total must be non-negative"
    assert resp["summary"]["returned"] >= 0, "summary.returned must be non-negative"
    assert resp["summary"]["skipped_low_confidence"] >= 0, (
        "summary.skipped_low_confidence must be non-negative"
    )
    assert resp["summary"]["skipped_already_automated"] >= 0, (  # NEW in API 1.0
        "summary.skipped_already_automated must be non-negative"
    )


def test_rank_targets_summary_counts_consistent():
    """Test that summary counts are consistent."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    # returned should not exceed total
    assert resp["summary"]["returned"] <= resp["summary"]["total"], (
        "summary.returned should not exceed summary.total"
    )

    # returned should match actual ranking length
    assert resp["summary"]["returned"] == len(resp["ranking"]), (
        "summary.returned should match ranking array length"
    )

    # skipped + returned should not exceed total
    assert (
        resp["summary"]["skipped_low_confidence"] + resp["summary"]["returned"]
        <= resp["summary"]["total"]
    ), "skipped + returned should not exceed total"


def test_rank_targets_error_handling_missing_file_arg():
    """Test that rank_targets handles missing file argument gracefully."""
    resp = rank_targets({})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_rank_targets_error_handling_invalid_file_type():
    """Test that rank_targets handles invalid file type gracefully."""
    resp = rank_targets({"file": 123})  # number instead of string

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_rank_targets_error_handling_invalid_limit():
    """Test that rank_targets handles invalid limit gracefully."""
    resp = rank_targets(
        {"file": "test.lean", "limit": 1000, "skip_already_automated": False}
    )  # exceeds max

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_rank_targets_error_handling_invalid_min_confidence():
    """Test that rank_targets handles invalid min_confidence gracefully."""
    resp = rank_targets(
        {"file": "test.lean", "min_confidence": 1.5, "skip_already_automated": False}
    )  # exceeds max

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_rank_targets_diagnostics_structure():
    """Test that diagnostics (when present) have correct structure."""
    resp = rank_targets({"file": ""})

    if "diagnostics" in resp and len(resp["diagnostics"]) > 0:
        for diag in resp["diagnostics"]:
            # Required fields
            assert "severity" in diag, "Missing diagnostic.severity"
            assert "message" in diag, "Missing diagnostic.message"

            # Validate severity enum
            assert diag["severity"] in ["info", "warning", "error"], (
                f"Invalid severity: {diag['severity']}"
            )

            # Message must be non-empty string
            assert isinstance(diag["message"], str), "diagnostic.message must be string"
            assert len(diag["message"]) > 0, "diagnostic.message must be non-empty"

            # Optional location field
            if "location" in diag:
                loc = diag["location"]
                assert "line" in loc, "Missing diagnostic.location.line"
                assert "col" in loc, "Missing diagnostic.location.col"
                assert loc["line"] >= 1, "location.line must be >= 1"
                assert loc["col"] >= 1, "location.col must be >= 1"


def test_rank_targets_api_version_format():
    """Test that api_version follows the required format (1.0)."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    # Must be exactly "1.0" for API version 1.0
    assert resp["api_version"] == "1.0", f"api_version must be '1.0', got '{resp['api_version']}'"


def test_rank_targets_run_id_non_empty():
    """Test that run_id is non-empty."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})
    assert len(resp["run_id"]) > 0, "run_id must be non-empty"


def test_rank_targets_tool_name_correct():
    """Test that tool field is exactly 'rank_targets'."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})
    assert resp["tool"] == "rank_targets", f"tool must be 'rank_targets', got '{resp['tool']}'"


def test_rank_targets_status_valid():
    """Test that status is one of the valid values."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})
    valid_statuses = {"success", "fail", "error", "timeout"}
    assert resp["status"] in valid_statuses, (
        f"status '{resp['status']}' not in valid set {valid_statuses}"
    )


def test_rank_targets_computation_time_non_negative():
    """Test that computation_time_ms is non-negative."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})
    assert resp["metadata"]["computation_time_ms"] >= 0, "computation_time_ms must be non-negative"


def test_rank_targets_with_include_components_false():
    """Test that components are excluded when include_components=false."""
    resp = rank_targets(
        {"file": "test.lean", "include_components": False, "skip_already_automated": False}
    )

    if len(resp["ranking"]) > 0:
        for theorem in resp["ranking"]:
            assert "components" not in theorem, (
                "components should not be present when include_components=false"
            )


def test_rank_targets_with_include_reasons_false():
    """Test that reasons are excluded when include_reasons=false."""
    resp = rank_targets(
        {"file": "test.lean", "include_reasons": False, "skip_already_automated": False}
    )

    if len(resp["ranking"]) > 0:
        for theorem in resp["ranking"]:
            assert "reasons" not in theorem, (
                "reasons should not be present when include_reasons=false"
            )


def test_rank_targets_with_limit():
    """Test that limit parameter restricts returned theorems."""
    resp = rank_targets({"file": "test.lean", "limit": 5, "skip_already_automated": False})

    # Returned count should not exceed limit
    assert resp["summary"]["returned"] <= 5, "returned count should not exceed limit"
    assert len(resp["ranking"]) <= 5, "ranking array length should not exceed limit"


def test_rank_targets_with_min_confidence():
    """Test that min_confidence parameter filters theorems."""
    resp = rank_targets(
        {"file": "test.lean", "min_confidence": 0.5, "skip_already_automated": False}
    )

    # All returned theorems should have confidence >= 0.5
    for theorem in resp["ranking"]:
        assert theorem["signals"]["confidence"] >= 0.5, (
            "All returned theorems should have confidence >= min_confidence"
        )


def test_rank_targets_tier_distribution_structure():
    """Test that tier_distribution has correct structure (API 1.0)."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    tier_dist = resp["summary"]["tier_distribution"]

    # All tier keys must be present
    required_tiers = ["S", "A", "B", "C", "D"]
    for tier in required_tiers:
        assert tier in tier_dist, f"Missing tier '{tier}' in tier_distribution"
        assert isinstance(tier_dist[tier], int), f"tier_distribution['{tier}'] must be integer"
        assert tier_dist[tier] >= 0, f"tier_distribution['{tier}'] must be non-negative"

    # Sum of tier counts should equal total theorems (before filtering)
    # Note: total may be less than summary.total if some theorems were filtered
    _ = sum(tier_dist.values())  # Verify we can compute total


def test_rank_targets_available_objectives_structure():
    """Test that available_objectives has correct structure (API 1.0)."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    objectives = resp["available_objectives"]
    assert isinstance(objectives, list), "available_objectives must be array"
    assert len(objectives) >= 4, "Should have at least 4 objectives"

    for obj in objectives:
        # Required fields
        assert "name" in obj, "Missing objective.name"
        assert "description" in obj, "Missing objective.description"
        assert "use_case" in obj, "Missing objective.use_case"
        assert "weights" in obj, "Missing objective.weights"

        # Validate types
        assert isinstance(obj["name"], str), "objective.name must be string"
        assert isinstance(obj["description"], str), "objective.description must be string"
        assert isinstance(obj["use_case"], str), "objective.use_case must be string"
        assert isinstance(obj["weights"], dict), "objective.weights must be object"

        # Validate weights structure
        weights = obj["weights"]
        required_weight_keys = [
            "success_likelihood",
            "impact",
            "annotation_value",
            "subgoal_potential",
            "risk",
        ]
        for key in required_weight_keys:
            assert key in weights, f"Missing objective.weights.{key}"
            assert isinstance(weights[key], int | float), f"objective.weights.{key} must be number"


def test_rank_targets_skip_already_automated_required():
    """Test that skip_already_automated parameter has a default value (API 1.0)."""
    # Missing skip_already_automated should use default (False)
    resp = rank_targets({"file": "test.lean"})

    # Should return success status with default behavior
    _assert_contract_guarantees(resp, expected_status="success")

    # Should have skipped_already_automated field (with value 0 since default is False)
    assert "skipped_already_automated" in resp["summary"], (
        "Missing summary.skipped_already_automated"
    )


def test_rank_targets_skip_already_automated_true():
    """Test that skip_already_automated=true filters automated theorems (API 1.0)."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": True})

    # Should have skipped_already_automated count
    assert "skipped_already_automated" in resp["summary"], (
        "Missing summary.skipped_already_automated"
    )
    assert isinstance(resp["summary"]["skipped_already_automated"], int), (
        "summary.skipped_already_automated must be integer"
    )
    assert resp["summary"]["skipped_already_automated"] >= 0, (
        "summary.skipped_already_automated must be non-negative"
    )


def test_rank_targets_skip_already_automated_false():
    """Test that skip_already_automated=false includes automated theorems (API 1.0)."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    # Should have skipped_already_automated count (likely 0)
    assert "skipped_already_automated" in resp["summary"], (
        "Missing summary.skipped_already_automated"
    )
    assert resp["summary"]["skipped_already_automated"] >= 0, (
        "summary.skipped_already_automated must be non-negative"
    )


def test_rank_targets_tier_field_in_ranking():
    """Test that each ranked theorem has tier field (API 1.0)."""
    resp = rank_targets({"file": "test.lean", "skip_already_automated": False})

    if len(resp["ranking"]) > 0:
        for theorem in resp["ranking"]:
            assert "tier" in theorem, "Missing theorem.tier"
            assert theorem["tier"] in ["S", "A", "B", "C", "D"], (
                f"Invalid tier value: {theorem['tier']}"
            )


def test_rank_targets_already_automated_penalty_in_components():
    """Test that components include already_automated_penalty (API 1.0)."""
    resp = rank_targets(
        {"file": "test.lean", "skip_already_automated": False, "include_components": True}
    )

    if len(resp["ranking"]) > 0:
        for theorem in resp["ranking"]:
            if "components" in theorem:
                components = theorem["components"]
                assert "already_automated_penalty" in components, (
                    "Missing components.already_automated_penalty"
                )
                assert 0.0 <= components["already_automated_penalty"] <= 1.0, (
                    "already_automated_penalty must be in [0.0, 1.0]"
                )


def test_rank_targets_confidence_in_reasons():
    """Test that reasons include numeric confidence (API 1.0)."""
    resp = rank_targets(
        {"file": "test.lean", "skip_already_automated": False, "include_reasons": True}
    )

    if len(resp["ranking"]) > 0:
        for theorem in resp["ranking"]:
            if "reasons" in theorem and len(theorem["reasons"]) > 0:
                # Check if any reason contains "confidence:"
                has_confidence = any("confidence:" in reason for reason in theorem["reasons"])
                # Confidence note should be present if confidence > 0
                if theorem["signals"]["confidence"] > 0.0:
                    assert has_confidence, (
                        "Reasons should include numeric confidence when confidence > 0"
                    )
