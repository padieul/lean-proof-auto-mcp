"""
Property-based tests for ProofPatchBuilder service.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 15.1, 15.2, 15.3, 15.4, 15.5
"""

import re

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.core.proof_patch_builder import ProofPatchBuilder
from lean_proof_auto_mcp.core.search_annotations_domain import (
    CandidateSource,
    Hint,
    HintSet,
    HintType,
    StyleConfig,
)

# ============================================================================
# Hypothesis Strategies
# ============================================================================


@st.composite
def valid_hints(draw):
    """Generate valid Hint instances."""
    # Use valid Lean identifiers
    name = draw(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="._"
            ),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s[0].isalpha())
    )

    hint_type = draw(st.sampled_from(list(HintType)))
    source = draw(st.sampled_from(list(CandidateSource)))

    return Hint(name=name, type=hint_type, source=source)


@st.composite
def valid_hint_sets(draw):
    """Generate valid HintSet instances."""
    hints = draw(st.lists(valid_hints(), min_size=0, max_size=10))
    return HintSet(hints)


@st.composite
def valid_style_configs(draw):
    """Generate valid StyleConfig instances."""
    prefer_simp = draw(st.booleans())
    emit_compact = draw(st.booleans())
    simp_only = draw(st.booleans())

    return StyleConfig(
        prefer_simp_over_aesop=prefer_simp, emit_compact=emit_compact, simp_only_list=simp_only
    )


@st.composite
def valid_automation_tools(draw):
    """Generate valid automation tool names."""
    return draw(st.sampled_from(["aesop", "grind", "simp"]))


# ============================================================================
# Property 23: Proof Patch Syntax Validity
# ============================================================================


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_23_proof_patch_syntax_validity(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 23: Proof Patch Syntax Validity

    For any generated proof patch, the Lean code should parse as
    syntactically valid Lean syntax.

    Validates: Requirements 6.1
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute
    patch = builder.build(hint_set, automation, style)

    # Verify: Lean code is non-empty
    assert patch.lean_code
    assert len(patch.lean_code) > 0

    # Verify: No invalid characters
    assert "\x00" not in patch.lean_code

    # Verify: Basic Lean syntax patterns
    lean_code = patch.lean_code.strip()

    # Should start with a valid Lean keyword or identifier
    assert re.match(r"^[a-zA-Z_]", lean_code) or lean_code.startswith("(")

    # Should have balanced brackets if any
    assert lean_code.count("[") == lean_code.count("]")
    assert lean_code.count("(") == lean_code.count(")")

    # Verify: Contains expected automation keyword
    # Note: prefer_simp_over_aesop can change aesop to simp
    if automation == "simp":
        assert "simp" in lean_code.lower()
    elif automation == "aesop":
        if style.prefer_simp_over_aesop:
            assert "simp" in lean_code.lower()
        else:
            assert "aesop" in lean_code.lower()
    elif automation == "grind":
        assert "grind" in lean_code.lower()


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_23_proof_patch_no_syntax_errors(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 23: Proof Patch Syntax Validity

    For any generated proof patch, the Lean code should not contain
    obvious syntax errors like unmatched brackets or invalid tokens.

    Validates: Requirements 6.1
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute
    patch = builder.build(hint_set, automation, style)
    lean_code = patch.lean_code

    # Verify: No unmatched brackets
    bracket_stack = []
    for char in lean_code:
        if char in "([{":
            bracket_stack.append(char)
        elif char in ")]}":
            if not bracket_stack:
                pytest.fail(f"Unmatched closing bracket: {char}")
            opening = bracket_stack.pop()
            expected = {"(": ")", "[": "]", "{": "}"}
            if expected[opening] != char:
                pytest.fail(f"Mismatched brackets: {opening} vs {char}")

    assert len(bracket_stack) == 0, f"Unmatched opening brackets: {bracket_stack}"

    # Verify: No double spaces (clean formatting)
    assert "  " not in lean_code or not style.emit_compact

    # Verify: No trailing whitespace on lines
    for line in lean_code.split("\n"):
        assert line == line.rstrip() or line.strip() == ""


# ============================================================================
# Property 24: Automation-Specific Proof Formatting
# ============================================================================


@given(hint_set=valid_hint_sets(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_24_simp_proof_formatting(hint_set, style):
    """
    Feature: search-annotations-tool
    Property 24: Automation-Specific Proof Formatting

    For any proof patch with simp automation and prefer_simp_over_aesop=True,
    the proof should use simp syntax.

    Validates: Requirements 6.2
    """
    # Setup
    builder = ProofPatchBuilder()
    style_with_simp_pref = StyleConfig(
        prefer_simp_over_aesop=True,
        emit_compact=style.emit_compact,
        simp_only_list=style.simp_only_list,
    )

    # Execute
    patch = builder.build(hint_set, "simp", style_with_simp_pref)

    # Verify: Uses simp syntax
    assert "simp" in patch.lean_code.lower()

    # Verify: If hints present, they are in brackets
    if not hint_set.is_empty():
        simp_hints = [h for h in hint_set.hints if h.type == HintType.SIMP]
        if simp_hints:
            assert "[" in patch.lean_code
            assert "]" in patch.lean_code


@given(hint_set=valid_hint_sets(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_24_aesop_proof_formatting(hint_set, style):
    """
    Feature: search-annotations-tool
    Property 24: Automation-Specific Proof Formatting

    For any proof patch with aesop automation, the proof should use
    aesop syntax with local hints (unless prefer_simp_over_aesop is True).

    Validates: Requirements 6.3
    """
    # Setup
    builder = ProofPatchBuilder()

    # Force prefer_simp_over_aesop to False to test aesop formatting
    style_aesop = StyleConfig(
        prefer_simp_over_aesop=False,
        emit_compact=style.emit_compact,
        simp_only_list=style.simp_only_list,
    )

    # Execute
    patch = builder.build(hint_set, "aesop", style_aesop)

    # Verify: Uses aesop syntax
    assert "aesop" in patch.lean_code.lower()

    # Verify: If hints present, they are in configuration
    if not hint_set.is_empty():
        # Should have parentheses for configuration
        assert "(" in patch.lean_code or patch.lean_code.strip() == "aesop"


@given(hint_set=valid_hint_sets(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_24_prefer_simp_over_aesop(hint_set, style):
    """
    Feature: search-annotations-tool
    Property 24: Automation-Specific Proof Formatting

    For any proof patch with aesop automation and prefer_simp_over_aesop=True,
    the proof should use simp syntax instead of aesop.

    Validates: Requirements 6.2
    """
    # Setup
    builder = ProofPatchBuilder()
    style_with_simp_pref = StyleConfig(
        prefer_simp_over_aesop=True,
        emit_compact=style.emit_compact,
        simp_only_list=style.simp_only_list,
    )

    # Execute
    patch = builder.build(hint_set, "aesop", style_with_simp_pref)

    # Verify: Uses simp syntax when prefer_simp_over_aesop is True
    assert "simp" in patch.lean_code.lower()


# ============================================================================
# Property 25: Proof Formatting Style Control
# ============================================================================


@given(
    hint_set=valid_hint_sets().filter(lambda hs: not hs.is_empty()),
    automation=valid_automation_tools(),
)
@settings(max_examples=100)
def test_property_25_compact_formatting(hint_set, automation):
    """
    Feature: search-annotations-tool
    Property 25: Proof Formatting Style Control

    For any proof patch with emit_compact=True, hints should be
    formatted on a single line.

    Validates: Requirements 6.4
    """
    # Setup
    builder = ProofPatchBuilder()
    style_compact = StyleConfig(
        prefer_simp_over_aesop=False, emit_compact=True, simp_only_list=False
    )

    # Execute
    patch = builder.build(hint_set, automation, style_compact)

    # Verify: Single line format (no internal newlines in hint list)
    # The proof might have newlines for structure, but hints should be compact
    if "[" in patch.lean_code:
        # Extract content between brackets
        bracket_content = re.search(r"\[(.*?)\]", patch.lean_code, re.DOTALL)
        if bracket_content:
            content = bracket_content.group(1)
            # Compact format should not have newlines in hint list
            assert "\n" not in content or content.strip() == ""


@given(
    hint_set=valid_hint_sets().filter(lambda hs: not hs.is_empty() and len(hs.hints) > 1),
    automation=valid_automation_tools(),
)
@settings(max_examples=100)
def test_property_25_multiline_formatting(hint_set, automation):
    """
    Feature: search-annotations-tool
    Property 25: Proof Formatting Style Control

    For any proof patch with emit_compact=False and multiple hints,
    hints should be formatted with one per line.

    Validates: Requirements 6.5
    """
    # Setup
    builder = ProofPatchBuilder()
    style_multiline = StyleConfig(
        prefer_simp_over_aesop=False, emit_compact=False, simp_only_list=False
    )

    # Execute
    patch = builder.build(hint_set, automation, style_multiline)

    # Verify: Multi-line format (has newlines)
    if "[" in patch.lean_code and len(hint_set.hints) > 1:
        # Should have newlines for multi-line format
        assert "\n" in patch.lean_code


@given(hint_set=valid_hint_sets().filter(lambda hs: any(h.type == HintType.SIMP for h in hs.hints)))
@settings(max_examples=100)
def test_property_25_simp_only_variant(hint_set):
    """
    Feature: search-annotations-tool
    Property 25: Proof Formatting Style Control

    For any simp proof patch with simp_only_list=True, the proof should
    use "simp only" syntax instead of "simp_all".

    Validates: Requirements 6.6
    """
    # Setup
    builder = ProofPatchBuilder()
    style_simp_only = StyleConfig(
        prefer_simp_over_aesop=True, emit_compact=True, simp_only_list=True
    )

    # Execute
    patch = builder.build(hint_set, "simp", style_simp_only)

    # Verify: Uses "simp only" syntax
    assert "simp only" in patch.lean_code.lower()


@given(hint_set=valid_hint_sets().filter(lambda hs: any(h.type == HintType.SIMP for h in hs.hints)))
@settings(max_examples=100)
def test_property_25_simp_all_variant(hint_set):
    """
    Feature: search-annotations-tool
    Property 25: Proof Formatting Style Control

    For any simp proof patch with simp_only_list=False, the proof should
    use "simp_all only" syntax.

    Validates: Requirements 6.6
    """
    # Setup
    builder = ProofPatchBuilder()
    style_simp_all = StyleConfig(
        prefer_simp_over_aesop=True, emit_compact=True, simp_only_list=False
    )

    # Execute
    patch = builder.build(hint_set, "simp", style_simp_all)

    # Verify: Uses "simp_all only" syntax
    assert "simp_all only" in patch.lean_code.lower()


# ============================================================================
# Property 27: Definitional Proof Preservation
# ============================================================================


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_27_rfl_preservation(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 27: Definitional Proof Preservation

    For any theorem with original proof "rfl", the system should not
    replace it with automation.

    Validates: Requirements 6.7, 15.1
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute
    patch = builder.build(hint_set, automation, style, original_proof="rfl")

    # Verify: Preserves rfl
    assert patch.lean_code.strip() == "rfl"


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_27_iff_rfl_preservation(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 27: Definitional Proof Preservation

    For any theorem with original proof "Iff.rfl", the system should not
    replace it with automation.

    Validates: Requirements 6.7, 15.2
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute
    patch = builder.build(hint_set, automation, style, original_proof="Iff.rfl")

    # Verify: Preserves Iff.rfl
    assert patch.lean_code.strip() == "Iff.rfl"


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_27_trivial_preservation(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 27: Definitional Proof Preservation

    For any theorem with original proof "trivial", the system should not
    replace it with automation.

    Validates: Requirements 6.7, 15.3
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute
    patch = builder.build(hint_set, automation, style, original_proof="trivial")

    # Verify: Preserves trivial
    assert patch.lean_code.strip() == "trivial"


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_27_non_definitional_replacement(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 27: Definitional Proof Preservation

    For any theorem with non-definitional original proof, the system
    should generate automation-based proof.

    Validates: Requirements 6.7
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute with non-definitional proof
    patch = builder.build(hint_set, automation, style, original_proof="by omega")

    # Verify: Does not preserve non-definitional proof
    assert patch.lean_code.strip() != "by omega"

    # Verify: Generates automation-based proof
    assert automation in patch.lean_code.lower() or "simp" in patch.lean_code.lower()


@given(hint_set=valid_hint_sets(), automation=valid_automation_tools(), style=valid_style_configs())
@settings(max_examples=100)
def test_property_27_definitional_with_whitespace(hint_set, automation, style):
    """
    Feature: search-annotations-tool
    Property 27: Definitional Proof Preservation

    For any theorem with definitional proof with surrounding whitespace,
    the system should still preserve it.

    Validates: Requirements 6.7, 15.1, 15.2, 15.3
    """
    # Setup
    builder = ProofPatchBuilder()

    # Execute with whitespace
    patch1 = builder.build(hint_set, automation, style, original_proof="  rfl  ")
    patch2 = builder.build(hint_set, automation, style, original_proof="\nIff.rfl\n")
    patch3 = builder.build(hint_set, automation, style, original_proof="\t trivial \t")

    # Verify: Preserves definitional proofs (stripped)
    assert patch1.lean_code.strip() == "rfl"
    assert patch2.lean_code.strip() == "Iff.rfl"
    assert patch3.lean_code.strip() == "trivial"
