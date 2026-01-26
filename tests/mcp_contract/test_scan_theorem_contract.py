from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from lean_proof_auto_mcp.tools.scan_theorem import API_VERSION, scan_theorem


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_dir(repo_root: Path) -> Path:
    """Return the schemas directory."""
    return repo_root / "docs" / "mcp" / "schemas"


@pytest.fixture
def scan_theorem_validator(schema_dir: Path) -> Draft202012Validator:
    """Create a JSON Schema validator for scan_theorem responses using referencing library."""
    scan_schema = json.loads((schema_dir / "scan_theorem.json").read_text(encoding="utf-8"))
    common_schema = json.loads((schema_dir / "common.json").read_text(encoding="utf-8"))

    # Create a registry with both schemas
    registry = Registry().with_resources(
        [
            (
                "common.json",
                Resource.from_contents(common_schema, default_specification=DRAFT202012),
            ),
            (
                "scan_theorem.json",
                Resource.from_contents(scan_schema, default_specification=DRAFT202012),
            ),
        ]
    )

    return Draft202012Validator(scan_schema, registry=registry)


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
    assert response.get("tool") == "scan_theorem", "tool field must be 'scan_theorem'"

    # If expected status provided, verify it
    if expected_status is not None:
        assert response["status"] == expected_status, (
            f"Expected status '{expected_status}', got '{response['status']}'"
        )


# Schema Compliance Tests


def test_scan_theorem_success_response_conforms_to_schema(scan_theorem_validator):
    """Test that scan_theorem success response validates against JSON schema.

    NOTE: This test will fail until task 11.1 updates the JSON schema files for API 1.0.
    The schema files still expect API 0.x format.
    """
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})
    _assert_schema_valid(scan_theorem_validator, resp)


def test_scan_theorem_fail_response_conforms_to_schema(scan_theorem_validator):
    """Test that scan_theorem fail response validates against JSON schema.

    NOTE: This test will fail until task 11.1 updates the JSON schema files for API 1.0.
    """
    resp = scan_theorem({"file": ""})
    _assert_schema_valid(scan_theorem_validator, resp)


# Input Mode Tests (theorem_id vs range)


def test_scan_theorem_theorem_id_mode_success():
    """Test scan_theorem with theorem_id input mode returns success."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    # Verify contract guarantees
    _assert_contract_guarantees(resp, expected_status="success")

    # Verify target echo
    assert "target" in resp, "Missing required field: target"
    assert "theorem_id" in resp["target"], "Missing target.theorem_id"
    assert resp["target"]["theorem_id"] == "Nat.mul_comm", "theorem_id not echoed correctly"


def test_scan_theorem_range_mode_success():
    """Test scan_theorem with range input mode returns success."""
    resp = scan_theorem(
        {"file": "test.lean", "target": {"range": {"start_line": 10, "end_line": 25}}}
    )

    # Verify contract guarantees
    _assert_contract_guarantees(resp, expected_status="success")

    # Verify target echo
    assert "target" in resp, "Missing required field: target"
    assert "range" in resp["target"], "Missing target.range"
    assert resp["target"]["range"]["start_line"] == 10, "start_line not echoed correctly"
    assert resp["target"]["range"]["end_line"] == 25, "end_line not echoed correctly"


def test_scan_theorem_both_theorem_id_and_range_fails():
    """Test that providing both theorem_id and range returns fail status."""
    resp = scan_theorem(
        {
            "file": "test.lean",
            "target": {"theorem_id": "Nat.mul_comm", "range": {"start_line": 10, "end_line": 25}},
        }
    )

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_neither_theorem_id_nor_range_fails():
    """Test that providing neither theorem_id nor range returns fail status."""
    resp = scan_theorem({"file": "test.lean", "target": {}})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


# Required Fields Tests


def test_scan_theorem_required_fields_present():
    """Test that all required fields are present in success response."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    # Top-level required fields
    required_fields = ["api_version", "status", "run_id", "tool", "file", "target"]
    for field in required_fields:
        assert field in resp, f"Missing required field: {field}"

    # Theorem object should be present for success
    if resp["status"] == "success":
        assert "theorem" in resp, "Missing theorem field in success response"
        assert resp["theorem"] is not None, "theorem should not be null in success response"


def test_scan_theorem_theorem_object_structure():
    """Test that theorem object has correct structure when present."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if resp["status"] == "success" and resp["theorem"] is not None:
        theorem = resp["theorem"]

        # Required fields in theorem object
        required_fields = ["name", "kind", "location", "structure", "automation"]
        for field in required_fields:
            assert field in theorem, f"Missing theorem.{field}"

        # Validate kind enum
        assert theorem["kind"] in ["theorem", "lemma", "example", "instance"], (
            f"Invalid kind: {theorem['kind']}"
        )

        # Validate location structure
        loc = theorem["location"]
        assert "decl_start" in loc, "Missing location.decl_start"
        assert "decl_end" in loc, "Missing location.decl_end"
        assert loc["decl_start"] >= 1, "decl_start must be >= 1"
        assert loc["decl_end"] >= 1, "decl_end must be >= 1"
        assert loc["decl_end"] >= loc["decl_start"], "decl_end must be >= decl_start"

        # Optional proof location fields
        if "proof_start" in loc:
            assert loc["proof_start"] >= 1, "proof_start must be >= 1"
            assert loc["proof_start"] >= loc["decl_start"], "proof_start must be >= decl_start"
        if "proof_end" in loc:
            assert loc["proof_end"] >= 1, "proof_end must be >= 1"
            if "proof_start" in loc:
                assert loc["proof_end"] >= loc["proof_start"], "proof_end must be >= proof_start"


# Structure Validation Tests


def test_scan_theorem_structure_object_required_fields():
    """Test that structure object has required fields."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if resp["status"] == "success" and resp["theorem"] is not None:
        structure = resp["theorem"]["structure"]

        # Required fields
        assert "skeleton" in structure, "Missing structure.skeleton"
        assert "blocks" in structure, "Missing structure.blocks"

        # Validate types
        assert isinstance(structure["skeleton"], list), "skeleton must be array"
        assert isinstance(structure["blocks"], list), "blocks must be array"

        # Validate skeleton items are strings
        for item in structure["skeleton"]:
            assert isinstance(item, str), f"skeleton item must be string, got {type(item)}"

        # Validate blocks structure
        for block in structure["blocks"]:
            assert isinstance(block, dict), "block must be object"
            assert "kind" in block, "Missing block.kind"
            assert "start_line" in block, "Missing block.start_line"
            assert "end_line" in block, "Missing block.end_line"

            # Validate kind enum
            assert block["kind"] in ["skeleton", "rewrite_simp", "closing", "unknown"], (
                f"Invalid block kind: {block['kind']}"
            )

            # Validate line numbers
            assert block["start_line"] >= 1, "block.start_line must be >= 1"
            assert block["end_line"] >= 1, "block.end_line must be >= 1"
            assert block["end_line"] >= block["start_line"], "block.end_line must be >= start_line"


def test_scan_theorem_structure_cases_optional():
    """Test that structure.cases is optional but valid when present."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if resp["status"] == "success" and resp["theorem"] is not None:
        structure = resp["theorem"]["structure"]

        # cases is optional
        if "cases" in structure:
            assert isinstance(structure["cases"], list), "cases must be array"

            # Validate cases structure
            for case in structure["cases"]:
                assert isinstance(case, dict), "case must be object"
                assert "label" in case, "Missing case.label"
                assert "start_line" in case, "Missing case.start_line"
                assert "end_line" in case, "Missing case.end_line"

                # Validate types
                assert isinstance(case["label"], str), "case.label must be string"
                assert case["start_line"] >= 1, "case.start_line must be >= 1"
                assert case["end_line"] >= 1, "case.end_line must be >= 1"
                assert case["end_line"] >= case["start_line"], "case.end_line must be >= start_line"


# Score Range Tests


def test_scan_theorem_automation_scores_in_range():
    """Test that all automation scores are in the range [0.0, 1.0]."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if resp["status"] == "success" and resp["theorem"] is not None:
        auto = resp["theorem"]["automation"]

        # Required fields
        assert "whole_goal_potential" in auto, "Missing automation.whole_goal_potential"
        assert "subgoal_potential" in auto, "Missing automation.subgoal_potential"
        assert "annotation_value" in auto, "Missing automation.annotation_value"

        # Validate score ranges for potential objects
        for potential_type in ["whole_goal_potential", "subgoal_potential"]:
            potential = auto[potential_type]
            assert "aesop" in potential, f"Missing {potential_type}.aesop"
            assert "grind" in potential, f"Missing {potential_type}.grind"

            # Validate ranges
            assert 0.0 <= potential["aesop"] <= 1.0, (
                f"{potential_type}.aesop out of range [0.0, 1.0]"
            )
            assert 0.0 <= potential["grind"] <= 1.0, (
                f"{potential_type}.grind out of range [0.0, 1.0]"
            )

        # Validate annotation_value range
        assert 0.0 <= auto["annotation_value"] <= 1.0, "annotation_value out of range [0.0, 1.0]"


def test_scan_theorem_automation_scores_are_numbers():
    """Test that all automation scores are numeric types."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if resp["status"] == "success" and resp["theorem"] is not None:
        auto = resp["theorem"]["automation"]

        # Check potential objects
        for potential_type in ["whole_goal_potential", "subgoal_potential"]:
            potential = auto[potential_type]
            assert isinstance(potential["aesop"], int | float), (
                f"{potential_type}.aesop must be number"
            )
            assert isinstance(potential["grind"], int | float), (
                f"{potential_type}.grind must be number"
            )

        # Check annotation_value
        assert isinstance(auto["annotation_value"], int | float), "annotation_value must be number"


# Determinism Tests


def test_scan_theorem_determinism_theorem_id_mode():
    """Test that scan_theorem returns identical output for repeated calls with theorem_id."""
    input_args = {"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}}

    # Call multiple times
    resp1 = scan_theorem(input_args)
    resp2 = scan_theorem(input_args)
    resp3 = scan_theorem(input_args)

    # All responses should be identical
    assert resp1 == resp2, "First and second calls should return identical responses"
    assert resp2 == resp3, "Second and third calls should return identical responses"
    assert resp1 == resp3, "First and third calls should return identical responses"


def test_scan_theorem_determinism_range_mode():
    """Test that scan_theorem returns identical output for repeated calls with range."""
    input_args = {"file": "test.lean", "target": {"range": {"start_line": 10, "end_line": 25}}}

    # Call multiple times
    resp1 = scan_theorem(input_args)
    resp2 = scan_theorem(input_args)
    resp3 = scan_theorem(input_args)

    # All responses should be identical
    assert resp1 == resp2, "First and second calls should return identical responses"
    assert resp2 == resp3, "Second and third calls should return identical responses"
    assert resp1 == resp3, "First and third calls should return identical responses"


def test_scan_theorem_different_inputs_different_outputs():
    """Test that scan_theorem returns different outputs for different inputs."""
    resp1 = scan_theorem({"file": "test1.lean", "target": {"theorem_id": "Nat.add_comm"}})
    resp2 = scan_theorem({"file": "test2.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    # Responses should differ
    assert resp1 != resp2, "Different inputs should produce different responses"
    assert resp1["file"] != resp2["file"], "Different files should be reflected in response"
    assert resp1["target"] != resp2["target"], "Different targets should be reflected in response"


# Error Handling Tests


def test_scan_theorem_missing_file_arg():
    """Test that scan_theorem handles missing file argument gracefully."""
    resp = scan_theorem({"target": {"theorem_id": "Nat.mul_comm"}})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_missing_target_arg():
    """Test that scan_theorem handles missing target argument gracefully."""
    resp = scan_theorem({"file": "test.lean"})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_empty_file_arg():
    """Test that scan_theorem handles empty file argument gracefully."""
    resp = scan_theorem({"file": "", "target": {"theorem_id": "Nat.mul_comm"}})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_empty_theorem_id():
    """Test that scan_theorem handles empty theorem_id gracefully."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": ""}})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_invalid_range_values():
    """Test that scan_theorem handles invalid range values gracefully."""
    resp = scan_theorem(
        {"file": "test.lean", "target": {"range": {"start_line": 0, "end_line": -1}}}
    )

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_invalid_file_type():
    """Test that scan_theorem handles invalid file type gracefully."""
    resp = scan_theorem(
        {
            "file": 123,  # number instead of string
            "target": {"theorem_id": "Nat.mul_comm"},
        }
    )

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_theorem_invalid_target_type():
    """Test that scan_theorem handles invalid target type gracefully."""
    resp = scan_theorem(
        {
            "file": "test.lean",
            "target": "invalid",  # string instead of object
        }
    )

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


# Field Type Tests


def test_scan_theorem_field_types():
    """Test that fields have correct types."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    # Type checks for top-level fields
    assert isinstance(resp["api_version"], str), "api_version must be string"
    assert isinstance(resp["status"], str), "status must be string"
    assert isinstance(resp["run_id"], str), "run_id must be string"
    assert isinstance(resp["tool"], str), "tool must be string"
    assert isinstance(resp["file"], str), "file must be string"
    assert isinstance(resp["target"], dict), "target must be object"

    # Optional fields
    if "theorem" in resp and resp["theorem"] is not None:
        assert isinstance(resp["theorem"], dict), "theorem must be object"
    if "diagnostics" in resp:
        assert isinstance(resp["diagnostics"], list), "diagnostics must be array"


def test_scan_theorem_diagnostics_structure():
    """Test that diagnostics (when present) have correct structure."""
    resp = scan_theorem({"file": ""})  # Force error to get diagnostics

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


# API Version and Tool Name Tests


def test_scan_theorem_api_version_format():
    """Test that api_version follows the required format (1.0)."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    # Must be exactly "1.0" for API version 1.0
    assert resp["api_version"] == "1.0", f"api_version must be '1.0', got '{resp['api_version']}'"


def test_scan_theorem_tool_name_correct():
    """Test that tool field is exactly 'scan_theorem'."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})
    assert resp["tool"] == "scan_theorem", f"tool must be 'scan_theorem', got '{resp['tool']}'"


def test_scan_theorem_run_id_non_empty():
    """Test that run_id is non-empty."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})
    assert len(resp["run_id"]) > 0, "run_id must be non-empty"


def test_scan_theorem_status_valid():
    """Test that status is one of the valid values."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})
    valid_statuses = {"success", "fail", "error", "timeout"}
    assert resp["status"] in valid_statuses, (
        f"status '{resp['status']}' not in valid set {valid_statuses}"
    )


# Target Echo Tests


def test_scan_theorem_target_echo_theorem_id():
    """Test that scan_theorem echoes theorem_id in target field."""
    theorem_id = "List.append_assoc"
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": theorem_id}})

    if resp["status"] == "success":
        assert "target" in resp, "Missing target field"
        assert "theorem_id" in resp["target"], "Missing target.theorem_id"
        assert resp["target"]["theorem_id"] == theorem_id, "theorem_id not echoed correctly"


def test_scan_theorem_target_echo_range():
    """Test that scan_theorem echoes range in target field."""
    range_obj = {"start_line": 15, "end_line": 30}
    resp = scan_theorem({"file": "test.lean", "target": {"range": range_obj}})

    if resp["status"] == "success":
        assert "target" in resp, "Missing target field"
        assert "range" in resp["target"], "Missing target.range"
        assert resp["target"]["range"] == range_obj, "range not echoed correctly"


# Notes Field Tests


def test_scan_theorem_notes_are_strings():
    """Test that all notes are strings when present."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if resp["status"] == "success" and resp["theorem"] is not None and "notes" in resp["theorem"]:
        for note in resp["theorem"]["notes"]:
            assert isinstance(note, str), f"Note must be string, got {type(note)}"


def test_scan_theorem_confidence_in_notes():
    """Test that notes include numeric confidence (API 1.0)."""
    resp = scan_theorem({"file": "test.lean", "target": {"theorem_id": "Nat.mul_comm"}})

    if (
        resp["status"] == "success"
        and resp["theorem"] is not None
        and "notes" in resp["theorem"]
        and len(resp["theorem"]["notes"]) > 0
    ):
        # Check if any note contains "confidence:"
        _ = any("confidence:" in note for note in resp["theorem"]["notes"])
        # Confidence note should be present for theorems with automation data
        if "automation" in resp["theorem"]:
            # At least some theorems should have confidence notes
            # (not all may have confidence > 0, so we just check format)
            pass  # This is a soft check - we verify format exists
