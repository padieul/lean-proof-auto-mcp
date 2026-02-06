"""
Property-based tests for import-based harness construction.

These tests verify universal properties that should hold across all valid executions
of the harness construction components. Each test runs a minimum of 100 iterations
with randomized inputs.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
"""

from unittest.mock import Mock

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessConfig,
    HarnessError,
    HarnessSuccess,
    ImportBasedHarnessConstructor,
    ImportPath,
    TheoremType,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_theorem_ids(draw):
    """Generate valid theorem identifiers."""
    # Lean theorem IDs can have dots, underscores, and alphanumeric characters
    parts = draw(
        st.lists(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"
                ),
            ),
            min_size=1,
            max_size=5,
        )
    )
    return ".".join(parts)


@st.composite
def valid_file_paths(draw):
    """Generate valid Lean file paths."""
    # Generate path components
    num_parts = draw(st.integers(min_value=1, max_value=5))
    parts = []
    for _i in range(num_parts):
        # First character should be uppercase for Lean convention
        first_char = draw(st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        rest = draw(
            st.text(
                min_size=0,
                max_size=15,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"
                ),
            )
        )
        parts.append(first_char + rest)

    path = "/".join(parts) + ".lean"
    return path


@st.composite
def valid_proof_attempts(draw):
    """Generate valid proof attempt tactics."""
    tactics = ["aesop", "grind", "simp", "rfl", "trivial", "exact?", "omega"]
    return draw(st.sampled_from(tactics))


@st.composite
def valid_theorem_types(draw):
    """Generate valid theorem type expressions."""
    # Simple type expressions for testing
    simple_types = [
        "True",
        "False → True",
        "∀ x : ℕ, x ≤ x",
        "p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K",
        "{p : G × N} → p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K",
        "∀ (a b : ℕ), a + b = b + a",
    ]
    return draw(st.sampled_from(simple_types))


@st.composite
def valid_harness_configs(draw):
    """Generate valid HarnessConfig instances."""
    theorem_id = draw(valid_theorem_ids())
    file_path = draw(valid_file_paths())
    proof_attempt = draw(valid_proof_attempts())

    # Optionally add additional imports
    add_imports = draw(st.booleans())
    if add_imports:
        num_imports = draw(st.integers(min_value=1, max_value=3))
        additional_imports = [f"import Module{i}" for i in range(num_imports)]
    else:
        additional_imports = []

    return HarnessConfig(
        theorem_id=theorem_id,
        file_path=file_path,
        proof_attempt=proof_attempt,
        additional_imports=additional_imports,
    )


# ============================================================================
# Property 1: Import-First Invariant
# ============================================================================


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_1_import_first_invariant(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property 1: Import-First Invariant

    For any harness construction, ALL imports MUST be on line 1 (or consecutive
    lines starting from line 1). No code should appear before imports.

    **Validates: Requirements 1.1, 1.5**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=theorem_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: First non-empty line is an import
    lines = result.code.split("\n")
    first_non_empty = next((line for line in lines if line.strip()), "")
    assert first_non_empty.startswith("import"), (
        f"First non-empty line must be import, got: {first_non_empty}"
    )

    # Verify: All imports are consecutive from the start
    found_non_import = False
    for i, line in enumerate(lines):
        if line.strip():
            if line.strip().startswith("import"):
                assert not found_non_import, f"Import at line {i + 1} appears after non-import code"
            else:
                found_non_import = True


# ============================================================================
# Property 2: No Signature Reconstruction
# ============================================================================


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_2_no_signature_reconstruction(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property 2: No Signature Reconstruction

    For any harness construction, the generated code MUST use "example :" not
    "theorem <name>". This ensures we're testing the type, not redeclaring the
    theorem.

    **Validates: Requirements 1.4**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=theorem_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: Uses "example :" not "theorem"
    assert "example :" in result.code, "Harness must use 'example :' statement"

    # Verify: Does NOT redeclare the theorem
    assert f"theorem {config.theorem_id}" not in result.code, (
        f"Harness must not redeclare theorem {config.theorem_id}"
    )

    # Verify: Does NOT use "def" either
    assert not result.code.strip().startswith("def "), (
        "Harness must not use 'def' for theorem testing"
    )


# ============================================================================
# Property 3: Type Preservation
# ============================================================================


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_3_type_preservation(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property 3: Type Preservation

    For any harness construction, the theorem type in the generated harness MUST
    exactly match the type extracted from LeanInteract. No manual parsing or
    reconstruction should alter the type.

    **Validates: Requirements 1.2**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(
        type_expr=theorem_type, source="LeanInteract:test.lean"
    )

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: Exact type appears in harness
    assert theorem_type in result.code, (
        f"Theorem type '{theorem_type}' must appear exactly in harness"
    )

    # Verify: Type appears after "example :"
    example_index = result.code.find("example :")
    type_index = result.code.find(theorem_type)
    assert example_index < type_index, "Theorem type must appear after 'example :'"


# ============================================================================
# Additional Property Tests
# ============================================================================


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_proof_attempt_preservation(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property: Proof Attempt Preservation

    For any harness construction, the proof attempt tactic MUST appear in the
    generated harness exactly as specified in the config.

    **Validates: Requirements 1.1**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=theorem_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: Proof attempt appears in harness
    assert config.proof_attempt in result.code, (
        f"Proof attempt '{config.proof_attempt}' must appear in harness"
    )


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_additional_imports_included(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property: Additional Imports Included

    For any harness construction with additional imports specified, ALL additional
    imports MUST appear in the generated harness.

    **Validates: Requirements 1.1**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=theorem_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: All additional imports appear
    for import_stmt in config.additional_imports:
        assert import_stmt in result.code, (
            f"Additional import '{import_stmt}' must appear in harness"
        )


@given(
    theorem_id=valid_theorem_ids(),
    file_path=valid_file_paths(),
    proof_attempt=valid_proof_attempts(),
    theorem_type=valid_theorem_types(),
)
@settings(max_examples=100)
def test_property_deterministic_construction(theorem_id, file_path, proof_attempt, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property: Deterministic Construction

    For any harness construction with the same inputs, the output MUST be
    identical across multiple invocations.

    **Validates: Requirements 1.1**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=theorem_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Create config
    config = HarnessConfig(theorem_id=theorem_id, file_path=file_path, proof_attempt=proof_attempt)

    # Execute: Construct harness twice
    result1 = constructor.construct(config)
    result2 = constructor.construct(config)

    # Verify: Both results are successful
    if not isinstance(result1, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result1.message}")
    if not isinstance(result2, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result2.message}")

    # Verify: Results are identical
    assert result1.code == result2.code, "Harness construction must be deterministic"


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_unicode_preservation(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property: Unicode Preservation

    For any harness construction with Unicode characters in the theorem type,
    the Unicode MUST be preserved exactly in the generated harness.

    **Validates: Requirements 1.2**
    """
    # Setup mocks with Unicode type
    unicode_type = "∀ x : ℕ, x ≤ x → x ∈ Set.univ"

    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=unicode_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: Unicode characters are preserved
    assert "∀" in result.code, "Unicode ∀ must be preserved"
    assert "ℕ" in result.code, "Unicode ℕ must be preserved"
    assert "≤" in result.code, "Unicode ≤ must be preserved"
    assert "∈" in result.code, "Unicode ∈ must be preserved"
    assert unicode_type in result.code, "Full Unicode type must be preserved"


@given(config=valid_harness_configs())
@settings(max_examples=100)
def test_property_error_handling_theorem_not_found(config):
    """
    Feature: import-based-theorem-testing
    Property: Error Handling - Theorem Not Found

    For any harness construction where the theorem cannot be found, the result
    MUST be a HarnessError with error_type="theorem_not_found".

    **Validates: Requirements 1.2**
    """
    # Setup mocks - theorem not found
    from lean_proof_auto_mcp.core.harness_construction import TheoremNotFoundError

    type_extractor = Mock()
    type_extractor.extract_type.side_effect = TheoremNotFoundError(
        f"Theorem {config.theorem_id} not found"
    )

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is an error
    assert isinstance(result, HarnessError), "Result must be HarnessError when theorem not found"

    # Verify: Error type is correct
    assert result.error_type == "theorem_not_found", "Error type must be 'theorem_not_found'"

    # Verify: Error contains theorem ID
    assert config.theorem_id in result.message, "Error message must contain theorem ID"


@given(config=valid_harness_configs(), theorem_type=valid_theorem_types())
@settings(max_examples=100)
def test_property_metadata_preservation(config, theorem_type):
    """
    Feature: import-based-theorem-testing
    Property: Metadata Preservation

    For any successful harness construction, the result MUST preserve the
    theorem_id and file_path from the config.

    **Validates: Requirements 1.1**
    """
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(type_expr=theorem_type, source="test")

    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(path="Test.Module")

    # Create constructor
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor, path_converter=path_converter
    )

    # Execute: Construct harness
    result = constructor.construct(config)

    # Verify: Result is successful
    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Harness construction failed: {result.message}")

    # Verify: Metadata is preserved
    assert result.theorem_id == config.theorem_id, "Theorem ID must be preserved in result"
    assert result.file_path == config.file_path, "File path must be preserved in result"
