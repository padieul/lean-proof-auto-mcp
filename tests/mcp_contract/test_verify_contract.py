"""
MCP contract tests for the verify tool.

These tests validate that the verify tool conforms to the MCP tool contract
as defined in docs/mcp/tool_contract.md, including:
- Tool registration
- Input schema validation
- Output schema validation
- Response structure and field types
- Error handling

Requirements: 8.3

NOTE: These tests call the verify tool which requires Lean 4 installation.
They are marked with @pytest.mark.requires_lean and can be skipped with:
    pytest -m "not requires_lean"
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from lean_proof_auto_mcp.tools.verify import API_VERSION, verify

# Mark all tests in this file as requiring Lean
pytestmark = pytest.mark.requires_lean


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_dir(repo_root: Path) -> Path:
    """Return the schemas directory."""
    return repo_root / "docs" / "mcp" / "schemas"


@pytest.fixture
def verify_validator(schema_dir: Path) -> Draft202012Validator:
    """Create a JSON Schema validator for verify responses using referencing library."""
    # Check if schema files exist
    verify_schema_path = schema_dir / "verify_output.json"
    common_schema_path = schema_dir / "common.json"

    if not verify_schema_path.exists() or not common_schema_path.exists():
        pytest.skip("Schema files not yet created (will be created in task 13.3)")

    verify_schema = json.loads(verify_schema_path.read_text(encoding="utf-8"))
    common_schema = json.loads(common_schema_path.read_text(encoding="utf-8"))

    # Create a registry with both schemas
    registry = Registry().with_resources(
        [
            (
                "common.json",
                Resource.from_contents(common_schema, default_specification=DRAFT202012),
            ),
            (
                "verify_output.json",
                Resource.from_contents(verify_schema, default_specification=DRAFT202012),
            ),
        ]
    )

    return Draft202012Validator(verify_schema, registry=registry)


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

    # If expected status provided, verify it
    if expected_status is not None:
        assert response["status"] == expected_status, (
            f"Expected status '{expected_status}', got '{response['status']}'"
        )


# ============================================================================
# Test: Tool Registration
# ============================================================================


def test_verify_tool_is_registered():
    """Test that verify tool can be called (is registered)."""
    # This test verifies that the verify function exists and is callable
    assert callable(verify), "verify function must be callable"


# ============================================================================
# Test: Input Schema Validation
# ============================================================================


def test_verify_accepts_valid_file_only_input():
    """Test that verify accepts minimal valid input (file only)."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    # Should return valid response (error is ok, we're testing input acceptance)
    _assert_contract_guarantees(resp)


def test_verify_accepts_all_optional_parameters():
    """Test that verify accepts all optional parameters."""
    resp = verify(
        {
            "file": "test.lean",
            "theorem_id": "MyTheorem",
            "budget_s": 60.0,
            "max_log_excerpt_chars": 5000,
            "store_full_logs": False,
            "workspace_mode": "temp",
        }
    )

    # Should return valid response
    _assert_contract_guarantees(resp)


def test_verify_rejects_missing_file():
    """Test that verify rejects input without file parameter."""
    resp = verify({"workspace_mode": "temp"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")

    # Should have diagnostic explaining the error
    assert "diagnostics" in resp, "Error response should include diagnostics"
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_verify_rejects_empty_file():
    """Test that verify rejects empty file parameter."""
    resp = verify({"file": "", "workspace_mode": "temp"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")


def test_verify_rejects_invalid_budget_s():
    """Test that verify rejects negative budget_s."""
    resp = verify({"file": "test.lean", "budget_s": -10.0, "workspace_mode": "temp"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")


def test_verify_rejects_zero_budget_s():
    """Test that verify rejects zero budget_s."""
    resp = verify({"file": "test.lean", "budget_s": 0.0, "workspace_mode": "temp"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")


def test_verify_rejects_invalid_max_log_excerpt_chars():
    """Test that verify rejects negative max_log_excerpt_chars."""
    resp = verify({"file": "test.lean", "max_log_excerpt_chars": -100, "workspace_mode": "temp"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")


def test_verify_rejects_invalid_workspace_mode():
    """Test that verify rejects invalid workspace_mode."""
    resp = verify({"file": "test.lean", "workspace_mode": "invalid"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")


# ============================================================================
# Test: Output Schema Validation
# ============================================================================


def test_verify_response_validates_against_schema(verify_validator):
    """Test that verify response validates against JSON schema."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})
    _assert_schema_valid(verify_validator, resp)


def test_verify_error_response_validates_against_schema(verify_validator):
    """Test that verify error response validates against JSON schema."""
    resp = verify({"file": "", "workspace_mode": "temp"})
    _assert_schema_valid(verify_validator, resp)


# ============================================================================
# Test: Response Structure
# ============================================================================


def test_verify_required_fields_present():
    """Test that all required fields are present in response."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    # Top-level required fields
    required_fields = [
        "api_version",
        "status",
        "run_id",
        "file",
        "theorem_id",
        "verification_scope_used",
        "diagnostics",
        "diagnostic_summary",
        "evidence",
        "metadata",
        "timing",
    ]
    for field in required_fields:
        assert field in resp, f"Missing required field: {field}"

    # diagnostic_summary required fields
    assert "error_count" in resp["diagnostic_summary"], "Missing diagnostic_summary.error_count"
    assert "warning_count" in resp["diagnostic_summary"], "Missing diagnostic_summary.warning_count"
    assert "info_count" in resp["diagnostic_summary"], "Missing diagnostic_summary.info_count"

    # evidence required fields
    assert "stdout_excerpt" in resp["evidence"], "Missing evidence.stdout_excerpt"
    assert "stderr_excerpt" in resp["evidence"], "Missing evidence.stderr_excerpt"
    assert "notes" in resp["evidence"], "Missing evidence.notes"


def test_verify_field_types():
    """Test that fields have correct types."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    # Type checks for top-level fields
    assert isinstance(resp["api_version"], str), "api_version must be string"
    assert isinstance(resp["status"], str), "status must be string"
    assert isinstance(resp["run_id"], str), "run_id must be string"
    assert isinstance(resp["file"], str), "file must be string"
    assert resp["theorem_id"] is None or isinstance(resp["theorem_id"], str), (
        "theorem_id must be string or null"
    )
    assert isinstance(resp["verification_scope_used"], str), (
        "verification_scope_used must be string"
    )
    assert isinstance(resp["diagnostics"], list), "diagnostics must be array"
    assert isinstance(resp["diagnostic_summary"], dict), "diagnostic_summary must be object"
    assert isinstance(resp["evidence"], dict), "evidence must be object"
    assert isinstance(resp["metadata"], dict), "metadata must be object"
    assert isinstance(resp["timing"], dict), "timing must be object"

    # Type checks for diagnostic_summary
    assert isinstance(resp["diagnostic_summary"]["error_count"], int), "error_count must be integer"
    assert isinstance(resp["diagnostic_summary"]["warning_count"], int), (
        "warning_count must be integer"
    )
    assert isinstance(resp["diagnostic_summary"]["info_count"], int), "info_count must be integer"

    # Type checks for evidence
    assert isinstance(resp["evidence"]["stdout_excerpt"], str), "stdout_excerpt must be string"
    assert isinstance(resp["evidence"]["stderr_excerpt"], str), "stderr_excerpt must be string"
    assert isinstance(resp["evidence"]["notes"], list), "notes must be array"


def test_verify_diagnostics_structure():
    """Test that diagnostics (when present) have correct structure."""
    resp = verify({"file": "", "workspace_mode": "temp"})  # Use invalid input to get diagnostics

    if len(resp["diagnostics"]) > 0:
        for diag in resp["diagnostics"]:
            # Required fields
            assert "severity" in diag, "Missing diagnostic.severity"
            assert "message" in diag, "Missing diagnostic.message"
            assert "location" in diag, "Missing diagnostic.location"

            # Validate severity enum
            assert diag["severity"] in ["info", "warning", "error"], (
                f"Invalid severity: {diag['severity']}"
            )

            # Message must be non-empty string
            assert isinstance(diag["message"], str), "diagnostic.message must be string"
            assert len(diag["message"]) > 0, "diagnostic.message must be non-empty"

            # Location structure (can be null for error diagnostics)
            loc = diag["location"]
            if loc is not None:
                assert "file" in loc, "Missing diagnostic.location.file"
                assert "line" in loc, "Missing diagnostic.location.line"
                assert "col" in loc, "Missing diagnostic.location.col"
                assert "end_line" in loc, "Missing diagnostic.location.end_line"
                assert "end_col" in loc, "Missing diagnostic.location.end_col"


def test_verify_verification_scope_used_valid():
    """Test that verification_scope_used is one of valid values."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    valid_scopes = {"file", "theorem", "file_fallback", "none"}
    assert resp["verification_scope_used"] in valid_scopes, (
        f"verification_scope_used '{resp['verification_scope_used']}' "
        f"not in valid set {valid_scopes}"
    )


def test_verify_status_valid():
    """Test that status is one of the valid values."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    valid_statuses = {"success", "fail", "timeout", "error"}
    assert resp["status"] in valid_statuses, (
        f"status '{resp['status']}' not in valid set {valid_statuses}"
    )


def test_verify_api_version_format():
    """Test that api_version follows the required format (0.2.0)."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    # Must be exactly "0.2.0" for API version 0.2.0
    assert resp["api_version"] == "0.2.0", (
        f"api_version must be '0.2.0', got '{resp['api_version']}'"
    )


def test_verify_run_id_non_empty():
    """Test that run_id is non-empty."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})
    assert len(resp["run_id"]) > 0, "run_id must be non-empty"


def test_verify_run_id_format():
    """Test that run_id follows expected format (verify-timestamp-hash)."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    # run_id should start with "verify-"
    assert resp["run_id"].startswith("verify-"), "run_id should start with 'verify-'"

    # run_id should have at least 3 parts separated by hyphens
    parts = resp["run_id"].split("-")
    assert len(parts) >= 3, "run_id should have format 'verify-timestamp-hash'"


# ============================================================================
# Test: Error Handling
# ============================================================================


def test_verify_error_response_structure():
    """Test that error responses have correct structure."""
    resp = verify({"file": "", "workspace_mode": "temp"})

    # Should be error status
    _assert_contract_guarantees(resp, expected_status="error")

    # Should have error diagnostic
    assert len(resp["diagnostics"]) > 0, "Error response should have diagnostics"
    assert resp["diagnostics"][0]["severity"] == "error", "Should have error diagnostic"

    # Should have error code in notes
    assert len(resp["evidence"]["notes"]) > 0, "Error response should have notes"
    assert any("error_code:" in note for note in resp["evidence"]["notes"]), (
        "Error response should include error_code in notes"
    )


def test_verify_error_handling_invalid_file_type():
    """Test that verify handles invalid file type gracefully."""
    resp = verify({"file": 123, "workspace_mode": "temp"})  # number instead of string

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")

    # Should have diagnostic
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


def test_verify_error_handling_whitespace_only_file():
    """Test that verify handles whitespace-only file argument gracefully."""
    resp = verify({"file": "   ", "workspace_mode": "temp"})

    # Should return error status
    _assert_contract_guarantees(resp, expected_status="error")

    # Should have diagnostic
    assert len(resp["diagnostics"]) > 0, "Should have at least one diagnostic"


# ============================================================================
# Test: Determinism
# ============================================================================


def test_verify_determinism_with_same_input():
    """Test that verify returns identical output for repeated calls with same input."""
    input_args = {"file": "test.lean", "workspace_mode": "temp"}

    # Call multiple times
    resp1 = verify(input_args)
    resp2 = verify(input_args)

    # Responses should be identical except for:
    # - run_id (includes timestamp and random suffix)
    # - metadata.workspace_id (unique for each temp workspace)
    # - timing (varies based on system load)
    # Compare all fields except these
    for key in resp1:
        if key == "run_id":
            continue  # run_id includes timestamp and random suffix
        if key == "timing":
            continue  # timing varies based on system load
        if key == "metadata":
            # Compare metadata fields except workspace_id
            for meta_key in resp1["metadata"]:
                if meta_key != "workspace_id":
                    assert resp1["metadata"][meta_key] == resp2["metadata"][meta_key], (
                        f"Metadata field '{meta_key}' differs between calls: "
                        f"{resp1['metadata'][meta_key]} != {resp2['metadata'][meta_key]}"
                    )
        else:
            assert resp1[key] == resp2[key], (
                f"Field '{key}' differs between calls: {resp1[key]} != {resp2[key]}"
            )


def test_verify_determinism_with_different_files():
    """Test that verify returns different outputs for different files."""
    resp1 = verify({"file": "test1.lean", "workspace_mode": "temp"})
    resp2 = verify({"file": "test2.lean", "workspace_mode": "temp"})

    # Responses should differ in the file field at minimum
    assert resp1["file"] != resp2["file"], "Different inputs should produce different file fields"


# ============================================================================
# Test: Diagnostic Counts
# ============================================================================


def test_verify_diagnostic_counts_non_negative():
    """Test that diagnostic counts are non-negative."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    assert resp["diagnostic_summary"]["error_count"] >= 0, "error_count must be non-negative"
    assert resp["diagnostic_summary"]["warning_count"] >= 0, "warning_count must be non-negative"
    assert resp["diagnostic_summary"]["info_count"] >= 0, "info_count must be non-negative"


def test_verify_diagnostic_counts_match_diagnostics():
    """Test that diagnostic counts match actual diagnostics array."""
    resp = verify({"file": "", "workspace_mode": "temp"})  # Use invalid input to get diagnostics

    # Count diagnostics by severity
    error_count = sum(1 for d in resp["diagnostics"] if d["severity"] == "error")
    warning_count = sum(1 for d in resp["diagnostics"] if d["severity"] == "warning")
    info_count = sum(1 for d in resp["diagnostics"] if d["severity"] == "info")

    # Verify counts match
    assert resp["diagnostic_summary"]["error_count"] == error_count, (
        "error_count should match actual error diagnostics"
    )
    assert resp["diagnostic_summary"]["warning_count"] == warning_count, (
        "warning_count should match actual warning diagnostics"
    )
    assert resp["diagnostic_summary"]["info_count"] == info_count, (
        "info_count should match actual info diagnostics"
    )


# ============================================================================
# Test: Notes Array
# ============================================================================


def test_verify_notes_are_strings():
    """Test that all notes are strings."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    for note in resp["evidence"]["notes"]:
        assert isinstance(note, str), f"Note must be string, got {type(note)}"


def test_verify_notes_non_empty():
    """Test that notes are non-empty strings."""
    resp = verify({"file": "test.lean", "workspace_mode": "temp"})

    for note in resp["evidence"]["notes"]:
        assert len(note) > 0, "Note must be non-empty string"
