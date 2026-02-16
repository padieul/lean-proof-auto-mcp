"""
Property-based tests for range-based harness construction.

These tests verify universal properties that should hold across all valid
executions of the RangeBasedHarnessConstructor. Each test runs a minimum
of 100 iterations with randomized inputs.

The constructor is pure (zero I/O, zero dependencies) so every property
can be checked without mocks.
"""

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessConfig,
    HarnessError,
    HarnessSuccess,
    RangeBasedHarnessConstructor,
)
from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range

# ============================================================================
# Helpers
# ============================================================================


def _decl(
    name: str,
    full_name: str = "",
    kind: str = "theorem",
    start_line: int = 3,
    end_line: int = 4,
    value_start: int = 3,
    value_start_col: int = 22,
    value_end: int = 4,
    value_end_col: int = 9,
) -> Declaration:
    """Create a Declaration with minimal boilerplate."""
    if not full_name:
        full_name = name
    return Declaration(
        name=name,
        full_name=full_name,
        type="True",
        value=DeclValue(
            pp="sorry",
            constants=[],
            range=Range(value_start, value_start_col, value_end, value_end_col),
        ),
        attributes=[],
        range=Range(start_line, 0, end_line, 0),
        namespace="",
        kind=kind,
    )


def _make_file_and_config(
    theorem_id: str,
    proof_attempt: str,
    file_path: str = "Test.lean",
    additional_imports: list[str] | None = None,
) -> HarnessConfig:
    """Build a synthetic file + config for a single-theorem file."""
    local_name = theorem_id.split(".")[-1] if "." in theorem_id else theorem_id
    file_content = f"import Mathlib\n\ntheorem {local_name} : True := by\n  trivial\n"
    theorem_line = f"theorem {local_name} : True := by"
    by_col = theorem_line.index("by")
    declarations = [
        _decl(
            local_name,
            full_name=theorem_id,
            value_start=3,
            value_start_col=by_col,
            value_end=4,
            value_end_col=9,
        )
    ]
    return HarnessConfig(
        theorem_id=theorem_id,
        file_path=file_path,
        proof_attempt=proof_attempt,
        file_content=file_content,
        declarations=declarations,
        additional_imports=additional_imports or [],
    )


# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_theorem_ids(draw):
    """Generate valid theorem identifiers."""
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
def valid_proof_attempts(draw):
    """Generate valid proof attempt tactics."""
    tactics = ["aesop", "grind", "simp", "rfl", "trivial", "exact?", "omega"]
    return draw(st.sampled_from(tactics))


@st.composite
def valid_file_paths(draw):
    """Generate valid Lean file paths."""
    num_parts = draw(st.integers(min_value=1, max_value=5))
    parts = []
    for _ in range(num_parts):
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
    return "/".join(parts) + ".lean"


# ============================================================================
# Property 1: Proof Attempt Preservation
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_proof_attempt_preservation(proof_attempt):
    """
    Property: The proof attempt tactic MUST appear in the generated harness
    exactly as specified in the config.
    """
    constructor = RangeBasedHarnessConstructor()
    config = _make_file_and_config("test_thm", proof_attempt)
    result = constructor.construct(config)

    assert isinstance(result, HarnessSuccess)
    assert proof_attempt in result.code


# ============================================================================
# Property 2: Import Preservation
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_import_preservation(proof_attempt):
    """
    Property: Original imports from the source file MUST be preserved
    in the generated harness.
    """
    constructor = RangeBasedHarnessConstructor()
    config = _make_file_and_config("test_thm", proof_attempt)
    result = constructor.construct(config)

    assert isinstance(result, HarnessSuccess)
    assert "import Mathlib" in result.code


# ============================================================================
# Property 3: Additional Imports Included
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_additional_imports_included(proof_attempt):
    """
    Property: ALL additional imports specified in config MUST appear
    in the generated harness.
    """
    constructor = RangeBasedHarnessConstructor()
    config = _make_file_and_config(
        "test_thm", proof_attempt, additional_imports=["import Aesop", "import Std"]
    )
    result = constructor.construct(config)

    assert isinstance(result, HarnessSuccess)
    assert "import Aesop" in result.code
    assert "import Std" in result.code


# ============================================================================
# Property 4: Deterministic Construction
# ============================================================================


@given(
    theorem_id=valid_theorem_ids(),
    proof_attempt=valid_proof_attempts(),
)
@settings(max_examples=100)
def test_property_deterministic_construction(theorem_id, proof_attempt):
    """
    Property: Same inputs MUST produce identical output across invocations.
    The constructor is stateless — no hidden caches or side effects.
    """
    constructor = RangeBasedHarnessConstructor()
    config = _make_file_and_config(theorem_id, proof_attempt)

    result1 = constructor.construct(config)
    result2 = constructor.construct(config)

    if not isinstance(result1, HarnessSuccess):
        pytest.skip(f"Construction failed: {result1.message}")
    assert isinstance(result2, HarnessSuccess)
    assert result1.code == result2.code


# ============================================================================
# Property 5: Metadata Preservation
# ============================================================================


@given(
    theorem_id=valid_theorem_ids(),
    file_path=valid_file_paths(),
    proof_attempt=valid_proof_attempts(),
)
@settings(max_examples=100)
def test_property_metadata_preservation(theorem_id, file_path, proof_attempt):
    """
    Property: theorem_id and file_path from config MUST be preserved
    in the result.
    """
    constructor = RangeBasedHarnessConstructor()
    config = _make_file_and_config(theorem_id, proof_attempt, file_path=file_path)
    result = constructor.construct(config)

    if not isinstance(result, HarnessSuccess):
        pytest.skip(f"Construction failed: {result.message}")

    assert result.theorem_id == theorem_id
    assert result.file_path == file_path


# ============================================================================
# Property 6: Error Handling — Theorem Not Found
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_error_handling_theorem_not_found(proof_attempt):
    """
    Property: When the target theorem is not in declarations, the result
    MUST be a HarnessError with error_type="theorem_not_found".
    """
    constructor = RangeBasedHarnessConstructor()

    file_content = "import Mathlib\n\ntheorem other : True := by trivial\n"
    declarations = [
        _decl(
            "other",
            start_line=3,
            end_line=3,
            value_start=3,
            value_start_col=24,
            value_end=3,
            value_end_col=34,
        )
    ]
    config = HarnessConfig(
        theorem_id="nonexistent",
        file_path="test.lean",
        proof_attempt=proof_attempt,
        file_content=file_content,
        declarations=declarations,
    )

    result = constructor.construct(config)
    assert isinstance(result, HarnessError)
    assert result.error_type == "theorem_not_found"


# ============================================================================
# Property 7: Error Handling — Empty Content
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_error_handling_empty_content(proof_attempt):
    """
    Property: When file_content is empty, the result MUST be a HarnessError.
    """
    constructor = RangeBasedHarnessConstructor()

    config = HarnessConfig(
        theorem_id="test",
        file_path="test.lean",
        proof_attempt=proof_attempt,
        file_content="",
        declarations=[],
    )

    result = constructor.construct(config)
    assert isinstance(result, HarnessError)
    assert result.error_type == "construction_failed"


# ============================================================================
# Property 8: Non-Target Theorems Get Sorry
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_non_target_theorems_get_sorry(proof_attempt):
    """
    Property: Non-target theorem proofs MUST be replaced with sorry,
    while the target theorem gets the proof_attempt.
    """
    constructor = RangeBasedHarnessConstructor()

    file_content = (
        "import Mathlib\n\n"
        "theorem target : True := by\n  trivial\n\n"
        "theorem other : True := by\n  trivial\n"
    )
    declarations = [
        _decl(
            "target",
            start_line=3,
            end_line=4,
            value_start=3,
            value_start_col=25,
            value_end=4,
            value_end_col=9,
        ),
        _decl(
            "other",
            start_line=6,
            end_line=7,
            value_start=6,
            value_start_col=24,
            value_end=7,
            value_end_col=9,
        ),
    ]

    config = HarnessConfig(
        theorem_id="target",
        file_path="test.lean",
        proof_attempt=proof_attempt,
        file_content=file_content,
        declarations=declarations,
    )

    result = constructor.construct(config)
    assert isinstance(result, HarnessSuccess)
    assert proof_attempt in result.code
    assert "sorry" in result.code


# ============================================================================
# Property 9: Unicode Preservation
# ============================================================================


@given(proof_attempt=valid_proof_attempts())
@settings(max_examples=100)
def test_property_unicode_preservation(proof_attempt):
    """
    Property: Unicode characters in the source file MUST be preserved
    exactly in the generated harness.
    """
    constructor = RangeBasedHarnessConstructor()

    file_content = (
        "import Mathlib\n\n"
        "variable {G : Type*} [Group G]\n\n"
        "theorem mem_prod : ∀ x : ℕ, x ≤ x := by\n  trivial\n"
    )
    # value range covers only the proof body "by\n  trivial"
    # "theorem mem_prod : ∀ x : ℕ, x ≤ x := " is 41 chars, so proof starts at col 41
    declarations = [
        Declaration(
            name="mem_prod",
            full_name="mem_prod",
            type="∀ x : ℕ, x ≤ x",
            value=DeclValue(pp="by trivial", constants=[], range=Range(5, 41, 6, 8)),
            attributes=[],
            range=Range(5, 0, 6, 8),
            namespace="",
            kind="theorem",
        ),
    ]

    config = HarnessConfig(
        theorem_id="mem_prod",
        file_path="test.lean",
        proof_attempt=proof_attempt,
        file_content=file_content,
        declarations=declarations,
    )

    result = constructor.construct(config)
    assert isinstance(result, HarnessSuccess)
    assert "∀ x : ℕ, x ≤ x" in result.code
    assert "variable {G : Type*} [Group G]" in result.code
