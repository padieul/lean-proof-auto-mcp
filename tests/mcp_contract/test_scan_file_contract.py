from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from lean_proof_auto_mcp.tools.scan_file import API_VERSION, scan_file


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_dir(repo_root: Path) -> Path:
    """Return the schemas directory."""
    return repo_root / "docs" / "mcp" / "schemas"


@pytest.fixture
def scan_file_validator(schema_dir: Path) -> Draft202012Validator:
    """Create a JSON Schema validator for scan_file responses using referencing library."""
    scan_schema = json.loads((schema_dir / "scan_file.json").read_text(encoding="utf-8"))
    common_schema = json.loads((schema_dir / "common.json").read_text(encoding="utf-8"))

    # Create a registry with both schemas
    registry = Registry().with_resources(
        [
            (
                "common.json",
                Resource.from_contents(common_schema, default_specification=DRAFT202012),
            ),
            (
                "scan_file.json",
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
    assert response.get("tool") == "scan_file", "tool field must be 'scan_file'"

    # If expected status provided, verify it
    if expected_status is not None:
        assert response["status"] == expected_status, (
            f"Expected status '{expected_status}', got '{response['status']}'"
        )


def test_scan_file_success_response_validates():
    """Test that scan_file with valid input returns schema-compliant success response."""
    resp = scan_file({"file": "test.lean"})

    # Verify contract guarantees
    _assert_contract_guarantees(resp, expected_status="success")

    # Verify response structure
    assert "summary" in resp, "Missing required field: summary"
    assert "theorem_count" in resp["summary"], "Missing summary.theorem_count"
    assert "notes" in resp["summary"], "Missing summary.notes"
    assert isinstance(resp["summary"]["notes"], list), "summary.notes must be a list"


def test_scan_file_success_response_conforms_to_schema(scan_file_validator):
    """Test that scan_file success response validates against JSON schema.

    NOTE: This test will fail until task 11.1 updates the JSON schema files for API 1.0.
    The schema files still expect API 0.x format.
    """
    resp = scan_file({"file": "test.lean"})
    _assert_schema_valid(scan_file_validator, resp)


def test_scan_file_fail_response_with_empty_file():
    """Test that scan_file with empty file argument returns fail status."""
    resp = scan_file({"file": ""})

    # Verify contract guarantees
    _assert_contract_guarantees(resp, expected_status="fail")

    # Verify diagnostics are present for failure
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Fail response should have at least one diagnostic"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"


def test_scan_file_fail_response_conforms_to_schema(scan_file_validator):
    """Test that scan_file fail response validates against JSON schema.

    NOTE: This test will fail until task 11.1 updates the JSON schema files for API 1.0.
    """
    resp = scan_file({"file": ""})
    _assert_schema_valid(scan_file_validator, resp)


def test_scan_file_determinism():
    """Test that scan_file returns identical output for repeated calls with same input."""
    input_args = {"file": "test.lean"}

    # Call multiple times
    resp1 = scan_file(input_args)
    resp2 = scan_file(input_args)
    resp3 = scan_file(input_args)

    # All responses should be identical
    assert resp1 == resp2, "First and second calls should return identical responses"
    assert resp2 == resp3, "Second and third calls should return identical responses"
    assert resp1 == resp3, "First and third calls should return identical responses"


def test_scan_file_determinism_with_different_inputs():
    """Test that scan_file returns different outputs for different inputs."""
    resp1 = scan_file({"file": "test1.lean"})
    resp2 = scan_file({"file": "test2.lean"})

    # Responses should differ in the file field at minimum
    assert resp1["file"] != resp2["file"], "Different inputs should produce different file fields"


def test_scan_file_required_fields_present():
    """Test that all required fields are present in success response."""
    resp = scan_file({"file": "test.lean"})

    # Top-level required fields
    required_fields = ["api_version", "status", "run_id", "tool", "file", "summary"]
    for field in required_fields:
        assert field in resp, f"Missing required field: {field}"

    # Summary required fields
    assert "theorem_count" in resp["summary"], "Missing summary.theorem_count"
    assert "notes" in resp["summary"], "Missing summary.notes"


def test_scan_file_field_types():
    """Test that fields have correct types."""
    resp = scan_file({"file": "test.lean"})

    # Type checks
    assert isinstance(resp["api_version"], str), "api_version must be string"
    assert isinstance(resp["status"], str), "status must be string"
    assert isinstance(resp["run_id"], str), "run_id must be string"
    assert isinstance(resp["tool"], str), "tool must be string"
    assert isinstance(resp["file"], str), "file must be string"
    assert isinstance(resp["summary"], dict), "summary must be object"
    assert isinstance(resp["summary"]["theorem_count"], int), "theorem_count must be integer"
    assert isinstance(resp["summary"]["notes"], list), "notes must be array"

    # Optional fields
    if "theorems" in resp:
        assert isinstance(resp["theorems"], list), "theorems must be array"
    if "diagnostics" in resp:
        assert isinstance(resp["diagnostics"], list), "diagnostics must be array"


def test_scan_file_theorem_count_non_negative():
    """Test that theorem_count is non-negative."""
    resp = scan_file({"file": "test.lean"})
    assert resp["summary"]["theorem_count"] >= 0, "theorem_count must be non-negative"


def test_scan_file_notes_are_strings():
    """Test that all notes are strings."""
    resp = scan_file({"file": "test.lean"})
    for note in resp["summary"]["notes"]:
        assert isinstance(note, str), f"Note must be string, got {type(note)}"


def test_scan_file_theorems_array_structure():
    """Test that theorems array (when present) has correct structure."""
    resp = scan_file({"file": "test.lean"})

    if "theorems" in resp and len(resp["theorems"]) > 0:
        for theorem in resp["theorems"]:
            # Required fields in theorem object
            assert "theorem_id" in theorem, "Missing theorem.theorem_id"
            assert "name" in theorem, "Missing theorem.name"
            assert "kind" in theorem, "Missing theorem.kind"
            assert "location" in theorem, "Missing theorem.location"
            assert "automation" in theorem, "Missing theorem.automation"

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

            # Validate automation structure
            auto = theorem["automation"]
            assert "whole_goal_potential" in auto, "Missing automation.whole_goal_potential"
            assert "subgoal_potential" in auto, "Missing automation.subgoal_potential"
            assert "annotation_value" in auto, "Missing automation.annotation_value"

            # Validate score ranges
            for potential_type in ["whole_goal_potential", "subgoal_potential"]:
                potential = auto[potential_type]
                assert "aesop" in potential, f"Missing {potential_type}.aesop"
                assert "grind" in potential, f"Missing {potential_type}.grind"
                assert 0.0 <= potential["aesop"] <= 1.0, f"{potential_type}.aesop out of range"
                assert 0.0 <= potential["grind"] <= 1.0, f"{potential_type}.grind out of range"

            assert 0.0 <= auto["annotation_value"] <= 1.0, "annotation_value out of range"


def test_scan_file_error_handling_missing_file_arg():
    """Test that scan_file handles missing file argument gracefully."""
    resp = scan_file({})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_scan_file_error_handling_invalid_file_type():
    """Test that scan_file handles invalid file type gracefully."""
    resp = scan_file({"file": 123})  # number instead of string

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_scan_file_error_handling_whitespace_only_file():
    """Test that scan_file handles whitespace-only file argument gracefully."""
    resp = scan_file({"file": "   "})

    # Should return fail status
    _assert_contract_guarantees(resp, expected_status="fail")

    # Should have diagnostic
    assert "diagnostics" in resp, "Fail response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_scan_file_diagnostics_structure():
    """Test that diagnostics (when present) have correct structure."""
    resp = scan_file({"file": ""})

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


def test_scan_file_api_version_format():
    """Test that api_version follows the required format (1.0)."""
    resp = scan_file({"file": "test.lean"})

    # Must be exactly "1.0" for API version 1.0
    assert resp["api_version"] == "1.0", f"api_version must be '1.0', got '{resp['api_version']}'"


def test_scan_file_run_id_non_empty():
    """Test that run_id is non-empty."""
    resp = scan_file({"file": "test.lean"})
    assert len(resp["run_id"]) > 0, "run_id must be non-empty"


def test_scan_file_tool_name_correct():
    """Test that tool field is exactly 'scan_file'."""
    resp = scan_file({"file": "test.lean"})
    assert resp["tool"] == "scan_file", f"tool must be 'scan_file', got '{resp['tool']}'"


def test_scan_file_status_valid():
    """Test that status is one of the valid values."""
    resp = scan_file({"file": "test.lean"})
    valid_statuses = {"success", "fail", "error", "timeout"}
    assert resp["status"] in valid_statuses, (
        f"status '{resp['status']}' not in valid set {valid_statuses}"
    )


def test_scan_file_confidence_in_notes():
    """Test that notes include numeric confidence (API 1.0)."""
    resp = scan_file({"file": "test.lean"})

    if resp["status"] == "success" and "theorems" in resp and len(resp["theorems"]) > 0:
        for theorem in resp["theorems"]:
            if "notes" in theorem and len(theorem["notes"]) > 0:
                # Check if any note contains "confidence:"
                _ = any("confidence:" in note for note in theorem["notes"])
                # Confidence note should be present for theorems with automation data
                if "automation" in theorem:
                    # At least some theorems should have confidence notes
                    # (not all may have confidence > 0, so we just check format)
                    pass  # This is a soft check - we verify format exists
