from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
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
    """Test that scan_file success response validates against JSON schema."""
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
    """Test that scan_file fail response validates against JSON schema."""
    resp = scan_file({"file": ""})
    _assert_schema_valid(scan_file_validator, resp)
