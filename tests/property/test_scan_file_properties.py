"""Property-based tests for scan_file tool.

**Validates: Requirements 1.10, 1.2, 1.7, 1.11, 1.4**

These tests use Hypothesis to verify correctness properties across many random inputs:
1. Determinism: Same input produces identical output
2. Schema Compliance: All responses conform to JSON schemas
3. Score Bounds: All automation scores are in [0.0, 1.0] range
4. Stable Ordering: Theorems are consistently ordered by theorem_id
5. Theorem Count Consistency: Summary count matches theorems array length
6. Location Validity: Line numbers are positive and properly ordered
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from lean_proof_auto_mcp.tools.scan_file import scan_file


@pytest.fixture(scope="module")
def scan_file_validator() -> Draft202012Validator:
    """Create a JSON Schema validator for scan_file responses."""
    repo_root = Path(__file__).resolve().parents[2]
    schema_dir = repo_root / "docs" / "mcp" / "schemas"

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


# Generators for test data
@st.composite
def valid_lean_files(draw) -> str:
    """Generate valid Lean file paths."""
    # Generate realistic file paths
    filename = draw(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=32, max_codepoint=126
            ),
            min_size=1,
            max_size=20,
        ).filter(lambda x: x.strip() and not x.startswith(".") and "/" not in x)
    )

    # Add .lean extension
    return f"{filename}.lean"


@st.composite
def lean_like_content(draw) -> str:
    """Generate Lean-like file content for testing."""
    # Generate various Lean constructs
    content_parts = []

    # Optional namespace
    if draw(st.booleans()):
        namespace = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=1, max_size=10
            )
        )
        content_parts.append(f"namespace {namespace}")

    # Generate 0-5 theorems
    num_theorems = draw(st.integers(min_value=0, max_value=5))

    for _i in range(num_theorems):
        theorem_type = draw(st.sampled_from(["theorem", "lemma", "example", "instance"]))
        theorem_name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=1, max_size=15
            )
        )

        # Simple theorem structure
        theorem_content = f"{theorem_type} {theorem_name} (n : Nat) : n + 0 = n := by\n"

        # Add some proof tactics
        tactics = draw(
            st.lists(
                st.sampled_from(
                    ["rfl", "simp", "intro", "cases n", "induction n", "rw [h]", "exact h"]
                ),
                min_size=1,
                max_size=3,
            )
        )

        for tactic in tactics:
            theorem_content += f"  {tactic}\n"

        content_parts.append(theorem_content)

    # Optional comments
    if draw(st.booleans()):
        comment = draw(st.text(min_size=1, max_size=50))
        content_parts.append(f"-- {comment}")

    # Close namespace if opened
    if content_parts and content_parts[0].startswith("namespace"):
        content_parts.append("end " + content_parts[0].split()[1])

    return "\n\n".join(content_parts)


@st.composite
def scan_file_args(draw) -> dict[str, Any]:
    """Generate valid scan_file arguments."""
    file_path = draw(valid_lean_files())
    return {"file": file_path}


class TestScanFileProperties:
    """Property-based tests for scan_file tool correctness properties."""

    @given(args=scan_file_args())
    def test_determinism(self, args: dict[str, Any]) -> None:
        """Property 1: Same input produces identical output across multiple calls.

        **Validates: Requirements 1.10**
        """
        result1 = scan_file(args)
        result2 = scan_file(args)
        result3 = scan_file(args)

        assert result1 == result2, "First and second calls should return identical responses"
        assert result2 == result3, "Second and third calls should return identical responses"
        assert result1 == result3, "First and third calls should return identical responses"

    @given(args=scan_file_args())
    def test_schema_compliance(
        self, args: dict[str, Any], scan_file_validator: Draft202012Validator
    ) -> None:
        """Property 2: All responses conform to JSON schemas.

        **Validates: Requirements 1.2**
        """
        result = scan_file(args)

        # Validate against schema
        errors = list(scan_file_validator.iter_errors(result))
        if errors:
            error_msgs = "\n".join(f"  - {e.json_path}: {e.message}" for e in errors)
            pytest.fail(f"Schema validation failed:\n{error_msgs}")

    @given(args=scan_file_args())
    def test_score_bounds(self, args: dict[str, Any]) -> None:
        """Property 3: All automation scores are in [0.0, 1.0] range.

        **Validates: Requirements 1.7**
        """
        result = scan_file(args)

        # Check theorems array if present
        if "theorems" in result:
            for theorem in result["theorems"]:
                auto = theorem["automation"]

                # Check whole_goal_potential scores
                wgp = auto["whole_goal_potential"]
                assert 0.0 <= wgp["aesop"] <= 1.0, (
                    f"aesop whole_goal_potential out of bounds: {wgp['aesop']}"
                )
                assert 0.0 <= wgp["grind"] <= 1.0, (
                    f"grind whole_goal_potential out of bounds: {wgp['grind']}"
                )

                # Check subgoal_potential scores
                sgp = auto["subgoal_potential"]
                assert 0.0 <= sgp["aesop"] <= 1.0, (
                    f"aesop subgoal_potential out of bounds: {sgp['aesop']}"
                )
                assert 0.0 <= sgp["grind"] <= 1.0, (
                    f"grind subgoal_potential out of bounds: {sgp['grind']}"
                )

                # Check annotation_value
                av = auto["annotation_value"]
                assert 0.0 <= av <= 1.0, f"annotation_value out of bounds: {av}"

    @given(args=scan_file_args())
    def test_stable_ordering(self, args: dict[str, Any]) -> None:
        """Property 4: Theorems are consistently ordered by theorem_id.

        **Validates: Requirements 1.11**
        """
        result = scan_file(args)

        # Check theorems array if present and non-empty
        if "theorems" in result and len(result["theorems"]) > 1:
            theorem_ids = [t["theorem_id"] for t in result["theorems"]]
            sorted_ids = sorted(theorem_ids)

            assert theorem_ids == sorted_ids, (
                f"Theorems not in stable order: {theorem_ids} != {sorted_ids}"
            )

    @given(args=scan_file_args())
    def test_theorem_count_consistency(self, args: dict[str, Any]) -> None:
        """Property 5: Summary theorem_count matches theorems array length.

        **Validates: Requirements 1.4**
        """
        result = scan_file(args)

        summary_count = result["summary"]["theorem_count"]
        actual_count = len(result.get("theorems", []))

        assert summary_count == actual_count, (
            f"Theorem count mismatch: summary says {summary_count}, "
            f"but theorems array has {actual_count} items"
        )

    @given(args=scan_file_args())
    def test_location_validity(self, args: dict[str, Any]) -> None:
        """Property 6: All location line numbers are positive and properly ordered.

        **Validates: Requirements 2.5** (applies to scan_file theorem locations too)
        """
        result = scan_file(args)

        # Check theorems array if present
        if "theorems" in result:
            for theorem in result["theorems"]:
                loc = theorem["location"]

                # Line numbers must be positive
                assert loc["decl_start"] >= 1, f"decl_start must be >= 1, got {loc['decl_start']}"
                assert loc["decl_end"] >= 1, f"decl_end must be >= 1, got {loc['decl_end']}"

                # decl_start <= decl_end
                assert loc["decl_start"] <= loc["decl_end"], (
                    f"decl_start ({loc['decl_start']}) must be <= decl_end ({loc['decl_end']})"
                )

                # If proof locations present, they must be valid
                if "proof_start" in loc and "proof_end" in loc:
                    assert loc["proof_start"] >= 1, (
                        f"proof_start must be >= 1, got {loc['proof_start']}"
                    )
                    assert loc["proof_end"] >= 1, f"proof_end must be >= 1, got {loc['proof_end']}"
                    assert loc["proof_start"] <= loc["proof_end"], (
                        f"proof_start ({loc['proof_start']}) must be <= "
                        f"proof_end ({loc['proof_end']})"
                    )

                    # Proof should be within or after declaration
                    assert loc["proof_start"] >= loc["decl_start"], (
                        f"proof_start ({loc['proof_start']}) must be >= "
                        f"decl_start ({loc['decl_start']})"
                    )

    @given(file1=valid_lean_files(), file2=valid_lean_files())
    def test_different_inputs_produce_different_outputs(self, file1: str, file2: str) -> None:
        """Property: Different inputs should produce different file fields (at minimum)."""
        assume(file1 != file2)  # Only test when inputs are actually different

        result1 = scan_file({"file": file1})
        result2 = scan_file({"file": file2})

        # At minimum, the file field should differ
        assert result1["file"] != result2["file"], (
            f"Different file inputs should produce different file fields: "
            f"'{result1['file']}' vs '{result2['file']}'"
        )

    @given(args=scan_file_args())
    def test_required_fields_always_present(self, args: dict[str, Any]) -> None:
        """Property: All required fields are always present regardless of input."""
        result = scan_file(args)

        # Top-level required fields
        required_fields = ["api_version", "status", "run_id", "tool", "file", "summary"]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Summary required fields
        assert "theorem_count" in result["summary"], "Missing summary.theorem_count"
        assert "notes" in result["summary"], "Missing summary.notes"

    @given(args=scan_file_args())
    def test_field_types_invariant(self, args: dict[str, Any]) -> None:
        """Property: Field types are always correct regardless of input."""
        result = scan_file(args)

        # Type checks for required fields
        assert isinstance(result["api_version"], str), "api_version must be string"
        assert isinstance(result["status"], str), "status must be string"
        assert isinstance(result["run_id"], str), "run_id must be string"
        assert isinstance(result["tool"], str), "tool must be string"
        assert isinstance(result["file"], str), "file must be string"
        assert isinstance(result["summary"], dict), "summary must be object"
        assert isinstance(result["summary"]["theorem_count"], int), "theorem_count must be integer"
        assert isinstance(result["summary"]["notes"], list), "notes must be array"

        # Optional fields type checks
        if "theorems" in result:
            assert isinstance(result["theorems"], list), "theorems must be array"
            for theorem in result["theorems"]:
                assert isinstance(theorem, dict), "Each theorem must be object"
                assert isinstance(theorem["theorem_id"], str), "theorem_id must be string"
                assert isinstance(theorem["name"], str), "name must be string"
                assert isinstance(theorem["kind"], str), "kind must be string"
                assert isinstance(theorem["location"], dict), "location must be object"
                assert isinstance(theorem["automation"], dict), "automation must be object"

        if "diagnostics" in result:
            assert isinstance(result["diagnostics"], list), "diagnostics must be array"

    @given(args=scan_file_args())
    def test_status_values_valid(self, args: dict[str, Any]) -> None:
        """Property: Status field always contains valid terminal state."""
        result = scan_file(args)

        valid_statuses = {"success", "fail", "error", "timeout"}
        assert result["status"] in valid_statuses, (
            f"Invalid status '{result['status']}', must be one of {valid_statuses}"
        )

    @given(args=scan_file_args())
    def test_tool_name_invariant(self, args: dict[str, Any]) -> None:
        """Property: Tool field is always exactly 'scan_file'."""
        result = scan_file(args)

        assert result["tool"] == "scan_file", f"Tool must be 'scan_file', got '{result['tool']}'"

    @given(args=scan_file_args())
    def test_run_id_non_empty(self, args: dict[str, Any]) -> None:
        """Property: run_id is always non-empty."""
        result = scan_file(args)

        assert len(result["run_id"]) > 0, "run_id must be non-empty"

    @given(args=scan_file_args())
    def test_theorem_count_non_negative(self, args: dict[str, Any]) -> None:
        """Property: theorem_count is always non-negative."""
        result = scan_file(args)

        assert result["summary"]["theorem_count"] >= 0, "theorem_count must be non-negative"

    @given(args=scan_file_args())
    def test_notes_are_strings(self, args: dict[str, Any]) -> None:
        """Property: All notes are always strings."""
        result = scan_file(args)

        for note in result["summary"]["notes"]:
            assert isinstance(note, str), f"Note must be string, got {type(note)}: {note}"

        # Check theorem notes if present
        if "theorems" in result:
            for theorem in result["theorems"]:
                if "notes" in theorem:
                    for note in theorem["notes"]:
                        assert isinstance(note, str), (
                            f"Theorem note must be string, got {type(note)}: {note}"
                        )
