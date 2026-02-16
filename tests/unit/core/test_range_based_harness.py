"""
Unit tests for range-based harness construction components.

Tests cover:
- Splice dataclass
- build_splice_plan() pure function
- apply_splices() pure function
- RangeBasedHarnessConstructor
- _prepend_imports() helper

All tests are pure â€” zero mocks, zero I/O. Just data in, data out.
"""

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessConfig,
    HarnessError,
    HarnessSuccess,
    RangeBasedHarnessConstructor,
    Splice,
    _extract_source_at_range,
    _prepend_imports,
    apply_splices,
    build_splice_plan,
    classify_proof_attempt,
)
from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range


def _make_decl(
    name: str,
    full_name: str = "",
    kind: str = "theorem",
    value_range: Range | None = None,
    has_value: bool = True,
) -> Declaration:
    """Helper to create test declarations with minimal boilerplate."""
    if not full_name:
        full_name = name
    value = None
    if has_value and value_range:
        value = DeclValue(pp="sorry", constants=[], range=value_range)
    return Declaration(
        name=name,
        full_name=full_name,
        type="True",
        value=value,
        attributes=[],
        range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
        namespace="",
        kind=kind,
    )


# ============================================================================
# Tests for build_splice_plan
# ============================================================================


class TestBuildSplicePlan:
    """Tests for the pure build_splice_plan() function."""

    def test_single_target_theorem(self):
        """Single theorem â†’ target gets test tactic."""
        decls = [
            _make_decl("my_thm", kind="theorem", value_range=Range(2, 5, 3, 10)),
        ]
        splices = build_splice_plan(decls, "my_thm", "aesop")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  aesop"

    def test_multiple_theorems_target_and_sorry(self):
        """Multiple theorems â†’ target gets test tactic, others get sorry."""
        decls = [
            _make_decl("thm_a", kind="theorem", value_range=Range(2, 0, 3, 5)),
            _make_decl("thm_b", kind="theorem", value_range=Range(5, 0, 6, 5)),
        ]
        splices = build_splice_plan(decls, "thm_a", "grind")
        assert len(splices) == 2
        # Sorted bottom-to-top, so thm_b comes first
        assert splices[0].start_line == 5  # thm_b
        assert splices[0].replacement == "by sorry"
        assert splices[1].start_line == 2  # thm_a (target)
        assert splices[1].replacement == "by\n  grind"

    def test_def_declarations_skipped(self):
        """def declarations are not spliced."""
        decls = [
            _make_decl("my_def", kind="def", value_range=Range(2, 0, 3, 5)),
            _make_decl("my_thm", kind="theorem", value_range=Range(5, 0, 6, 5)),
        ]
        splices = build_splice_plan(decls, "my_thm", "aesop")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  aesop"

    def test_instance_declarations_spliced(self):
        """Non-target instances are preserved (not sorry'd) to keep definitional equality."""
        decls = [
            _make_decl("my_inst", kind="instance", value_range=Range(2, 0, 3, 5)),
            _make_decl("my_thm", kind="theorem", value_range=Range(5, 0, 6, 5)),
        ]
        splices = build_splice_plan(decls, "my_thm", "aesop")
        # Only the target theorem is spliced; the non-target instance is kept intact
        assert len(splices) == 1

    def test_instance_as_target(self):
        """Instance declarations can be the probe target."""
        decls = [
            _make_decl("Monoid.toNatPow", kind="instance", value_range=Range(2, 0, 3, 5)),
        ]
        splices = build_splice_plan(decls, "Monoid.toNatPow", "aesop")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  aesop"

    def test_declarations_without_value_skipped(self):
        """Declarations without value (axioms) are skipped."""
        decls = [
            _make_decl("axiom_decl", kind="theorem", has_value=False),
            _make_decl("my_thm", kind="theorem", value_range=Range(5, 0, 6, 5)),
        ]
        splices = build_splice_plan(decls, "my_thm", "aesop")
        assert len(splices) == 1

    def test_zero_range_declarations_skipped(self):
        """Declarations with zero ranges are skipped."""
        decls = [
            _make_decl("zero_range", kind="theorem", value_range=Range(0, 0, 0, 0)),
            _make_decl("my_thm", kind="theorem", value_range=Range(5, 0, 6, 5)),
        ]
        splices = build_splice_plan(decls, "my_thm", "aesop")
        assert len(splices) == 1

    def test_name_matching_short_name(self):
        """Match by short name."""
        decls = [
            _make_decl(
                "mem_prod",
                full_name="Subgroup.mem_prod",
                kind="theorem",
                value_range=Range(2, 0, 3, 5),
            ),
        ]
        splices = build_splice_plan(decls, "mem_prod", "aesop")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  aesop"

    def test_name_matching_full_name(self):
        """Match by full name."""
        decls = [
            _make_decl(
                "mem_prod",
                full_name="Subgroup.mem_prod",
                kind="theorem",
                value_range=Range(2, 0, 3, 5),
            ),
        ]
        splices = build_splice_plan(decls, "Subgroup.mem_prod", "aesop")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  aesop"

    def test_name_matching_local_name_from_qualified(self):
        """Match by local name extracted from qualified target_theorem_id."""
        decls = [
            _make_decl(
                "mem_prod",
                full_name="Subgroup.mem_prod",
                kind="theorem",
                value_range=Range(2, 0, 3, 5),
            ),
        ]
        # Target is "Subgroup.mem_prod" â†’ local_name = "mem_prod"
        splices = build_splice_plan(decls, "Subgroup.mem_prod", "aesop")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  aesop"

    def test_lemma_kind_is_spliced(self):
        """Lemma declarations are spliced like theorems."""
        decls = [
            _make_decl("my_lemma", kind="lemma", value_range=Range(2, 0, 3, 5)),
        ]
        splices = build_splice_plan(decls, "my_lemma", "aesop")
        assert len(splices) == 1

    def test_range_includes_assign_token(self):
        """When DeclValue.range includes ':=', replacement preserves it."""
        file_content = "import Mathlib\n\ntheorem foo : True := by\n  trivial\n"
        # ':' at col 19, '=' at col 20, 'b' at col 22
        # Range starts at ':' (col 19) â€” includes ':= by ...'
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(3, 19, 4, 9)),
        ]
        splices = build_splice_plan(decls, "foo", "simp", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= by\n  simp"

    def test_range_excludes_assign_token(self):
        """When DeclValue.range starts at 'by', no ':=' prefix added."""
        file_content = "import Mathlib\n\ntheorem foo : True := by\n  trivial\n"
        # 'b' at col 22
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(3, 22, 4, 9)),
        ]
        splices = build_splice_plan(decls, "foo", "simp", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  simp"

    def test_range_includes_assign_sorry_replacement(self):
        """Non-target theorems with ':=' in range get ':= by sorry'."""
        # 'theorem a : True := by trivial'
        # ':' at col 17, '=' at col 18, 'b' at col 20
        file_content = "theorem a : True := by trivial\ntheorem b : True := by trivial\n"
        decls = [
            _make_decl("a", kind="theorem", value_range=Range(1, 17, 1, 30)),
            _make_decl("b", kind="theorem", value_range=Range(2, 17, 2, 30)),
        ]
        splices = build_splice_plan(decls, "a", "simp", file_content=file_content)
        # b is non-target, should get ':= by sorry'
        sorry_splice = next(s for s in splices if s.start_line == 2)
        assert sorry_splice.replacement == ":= by sorry"

    def test_no_file_content_falls_back_to_no_prefix(self):
        """Without file_content, no ':=' prefix detection (backward compat)."""
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(3, 20, 4, 9)),
        ]
        splices = build_splice_plan(decls, "foo", "simp")
        assert len(splices) == 1
        assert splices[0].replacement == "by\n  simp"


# ============================================================================
# Tests for apply_splices
# ============================================================================


class TestApplySplices:
    """Tests for the pure apply_splices() function."""

    def test_single_line_splice(self):
        """Replace a single-line range."""
        content = "line1\ntheorem foo := old_proof\nline3"
        splices = [
            Splice(start_line=2, start_col=17, end_line=2, end_col=26, replacement="by sorry")
        ]
        result = apply_splices(content, splices)
        assert "by sorry" in result
        assert "old_proof" not in result

    def test_multi_line_splice(self):
        """Replace a multi-line range."""
        content = "line1\ntheorem foo := by\n  old_tactic\n  done\nline5"
        splices = [
            Splice(start_line=2, start_col=15, end_line=4, end_col=6, replacement="by sorry")
        ]
        result = apply_splices(content, splices)
        assert "by sorry" in result
        assert "old_tactic" not in result

    def test_multiple_splices_bottom_to_top(self):
        """Multiple splices applied bottom-to-top preserve positions."""
        content = "import X\ntheorem a := proof_a\ntheorem b := proof_b\nend"
        splices = [
            Splice(start_line=3, start_col=13, end_line=3, end_col=20, replacement="by sorry"),
            Splice(start_line=2, start_col=13, end_line=2, end_col=20, replacement="by\n  aesop"),
        ]
        result = apply_splices(content, splices)
        # Both replacements should be present
        assert "by sorry" in result  # theorem b
        assert "aesop" in result  # theorem a
        # theorem b's sorry should come after theorem a's aesop in the output
        assert result.index("aesop") < result.index("by sorry")

    def test_empty_splice_list_unchanged(self):
        """Empty splice list returns content unchanged."""
        content = "import X\ntheorem foo := by sorry"
        result = apply_splices(content, [])
        assert result == content

    def test_unicode_characters(self):
        """Unicode characters in source are preserved."""
        content = "import X\ntheorem foo : âˆ€ x : â„•, x â‰¤ x := by\n  omega"
        splices = [
            Splice(start_line=2, start_col=37, end_line=3, end_col=7, replacement="by\n  aesop")
        ]
        result = apply_splices(content, splices)
        assert "âˆ€ x : â„•, x â‰¤ x" in result
        assert "aesop" in result


# ============================================================================
# Tests for _prepend_imports
# ============================================================================


class TestPrependImports:
    """Tests for the _prepend_imports helper."""

    def test_inserts_after_last_import(self):
        """Additional imports go after the last existing import."""
        code = "import Mathlib\nimport Aesop\n\ntheorem foo := sorry"
        result = _prepend_imports(code, ["Std"])
        lines = result.split("\n")
        assert lines[0] == "import Mathlib"
        assert lines[1] == "import Aesop"
        assert lines[2] == "import Std"

    def test_adds_import_prefix(self):
        """Bare module names get 'import ' prefix."""
        code = "import Mathlib\n\ntheorem foo := sorry"
        result = _prepend_imports(code, ["Aesop"])
        assert "import Aesop" in result

    def test_no_existing_imports(self):
        """When no imports exist, prepend at top."""
        code = "theorem foo := sorry"
        result = _prepend_imports(code, ["import Mathlib"])
        lines = result.split("\n")
        assert lines[0] == "import Mathlib"

    def test_already_has_import_prefix(self):
        """Import strings that already start with 'import ' are not doubled."""
        code = "import Mathlib\n\ntheorem foo := sorry"
        result = _prepend_imports(code, ["import Aesop"])
        assert result.count("import import") == 0


# ============================================================================
# Tests for RangeBasedHarnessConstructor
# ============================================================================


class TestRangeBasedHarnessConstructor:
    """Tests for the RangeBasedHarnessConstructor."""

    def test_successful_construction(self):
        """Successful construction with declarations + file_content."""
        file_content = "import Mathlib\n\ntheorem my_thm : True := by\n  trivial\n"
        decls = [
            _make_decl("my_thm", kind="theorem", value_range=Range(3, 27, 4, 9)),
        ]
        config = HarnessConfig(
            theorem_id="my_thm",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)
        assert "aesop" in result.code
        assert "import Mathlib" in result.code

    def test_theorem_not_found(self):
        """Target theorem not in declarations â†’ HarnessError."""
        file_content = "import Mathlib\n\ntheorem other : True := by trivial\n"
        decls = [
            _make_decl("other", kind="theorem", value_range=Range(3, 24, 3, 34)),
        ]
        config = HarnessConfig(
            theorem_id="nonexistent",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessError)
        assert result.error_type == "theorem_not_found"

    def test_empty_file_content(self):
        """Empty file_content â†’ HarnessError."""
        config = HarnessConfig(
            theorem_id="my_thm",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content="",
            declarations=[_make_decl("my_thm", kind="theorem", value_range=Range(1, 0, 2, 0))],
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessError)
        assert result.error_type == "construction_failed"

    def test_empty_declarations(self):
        """Empty declarations list â†’ HarnessError."""
        config = HarnessConfig(
            theorem_id="my_thm",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content="import Mathlib\ntheorem my_thm := sorry",
            declarations=[],
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessError)
        assert result.error_type == "construction_failed"

    def test_additional_imports_prepended(self):
        """Additional imports are prepended correctly."""
        file_content = "import Mathlib\n\ntheorem my_thm : True := by\n  trivial\n"
        decls = [
            _make_decl("my_thm", kind="theorem", value_range=Range(3, 27, 4, 9)),
        ]
        config = HarnessConfig(
            theorem_id="my_thm",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content=file_content,
            declarations=decls,
            additional_imports=["Aesop", "Std"],
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)
        assert "import Aesop" in result.code
        assert "import Std" in result.code
        assert "import Mathlib" in result.code

    def test_multiple_theorems_others_get_sorry(self):
        """Non-target theorems get sorry'd."""
        file_content = (
            "import Mathlib\n"
            "\n"
            "theorem thm_a : True := by\n"
            "  trivial\n"
            "\n"
            "theorem thm_b : True := by\n"
            "  trivial\n"
        )
        decls = [
            _make_decl("thm_a", kind="theorem", value_range=Range(3, 24, 4, 9)),
            _make_decl("thm_b", kind="theorem", value_range=Range(6, 24, 7, 9)),
        ]
        config = HarnessConfig(
            theorem_id="thm_a",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)
        assert "aesop" in result.code
        assert "by sorry" in result.code

    def test_construction_with_assign_in_range(self):
        """Constructor handles DeclValue.range that includes ':='."""
        file_content = "import Mathlib\n\ntheorem my_thm : True := by\n  trivial\n"
        # 'theorem my_thm : True := by' â€” ':' at col 22, '=' at col 23, 'b' at col 25
        decls = [
            _make_decl("my_thm", kind="theorem", value_range=Range(3, 22, 4, 9)),
        ]
        config = HarnessConfig(
            theorem_id="my_thm",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)
        # Should produce valid Lean: 'theorem my_thm : True := by\n  aesop'
        assert ":= by" in result.code
        assert "aesop" in result.code
        # Should NOT have doubled ':=' or doubled 'by'
        assert ":= :=" not in result.code
        assert "by by" not in result.code

    def test_ambiguous_local_name_returns_error(self):
        """Ambiguous local-name fallback should fail explicitly."""
        file_content = (
            "theorem Ns1.dup : True := by\n  trivial\ntheorem Ns2.dup : True := by\n  trivial\n"
        )
        decls = [
            _make_decl("dup", full_name="Ns1.dup", kind="theorem", value_range=Range(1, 22, 2, 9)),
            _make_decl("dup", full_name="Ns2.dup", kind="theorem", value_range=Range(3, 22, 4, 9)),
        ]
        config = HarnessConfig(
            theorem_id="dup",
            file_path="test.lean",
            proof_attempt="simp",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessError)
        assert result.error_type == "ambiguous_theorem_id"

    def test_empty_cleaned_proof_returns_invalid_proof_attempt(self):
        """Proof attempts that normalize to empty should fail fast."""
        file_content = "theorem t : True := by\n  trivial\n"
        decls = [_make_decl("t", kind="theorem", value_range=Range(1, 18, 2, 9))]
        config = HarnessConfig(
            theorem_id="t",
            file_path="test.lean",
            proof_attempt="by",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessError)
        assert result.error_type == "invalid_proof_attempt"

    def test_unsafe_target_range_returns_error(self):
        """Target ranges that start at declaration syntax should fail fast."""
        file_content = "private def helper : Nat := 42\n"
        decls = [_make_decl("helper", kind="theorem", value_range=Range(1, 0, 1, 30))]
        config = HarnessConfig(
            theorem_id="helper",
            file_path="test.lean",
            proof_attempt="simp",
            file_content=file_content,
            declarations=decls,
        )
        constructor = RangeBasedHarnessConstructor()
        result = constructor.construct(config)
        assert isinstance(result, HarnessError)
        assert result.error_type == "unsafe_target_range"


# ============================================================================
# Tests for _extract_source_at_range
# ============================================================================


class TestExtractSourceAtRange:
    """Tests for the _extract_source_at_range helper."""

    def test_single_line(self):
        content = "theorem foo : True := by trivial"
        # 'b' at col 22, string is 32 chars
        result = _extract_source_at_range(content, 1, 22, 1, 32)
        assert result == "by trivial"

    def test_includes_assign(self):
        content = "theorem foo : True := by trivial"
        # ':' at col 19
        result = _extract_source_at_range(content, 1, 19, 1, 32)
        assert result == ":= by trivial"

    def test_multi_line(self):
        content = "line1\ntheorem foo : True := by\n  trivial\nline4"
        # ':' at col 19 on line 2
        result = _extract_source_at_range(content, 2, 19, 3, 9)
        assert result == ":= by\n  trivial"

    def test_out_of_bounds(self):
        content = "one line"
        result = _extract_source_at_range(content, 5, 0, 6, 0)
        assert result == ""


# ============================================================================
# Tests for classify_proof_attempt
# ============================================================================


class TestClassifyProofAttempt:
    """Tests for the classify_proof_attempt pure function.

    Covers all input forms: tactic-mode, term-mode, with/without
    leading ':=' or 'by' tokens, whitespace variations, edge cases.
    """

    # --- Tactic-mode: bare tactic keywords ---

    def test_bare_simp(self):
        mode, cleaned = classify_proof_attempt("simp")
        assert mode == "tactic"
        assert cleaned == "simp"

    def test_bare_simpa(self):
        mode, cleaned = classify_proof_attempt("simpa")
        assert mode == "tactic"
        assert cleaned == "simpa"

    def test_bare_simp_all(self):
        mode, cleaned = classify_proof_attempt("simp_all")
        assert mode == "tactic"
        assert cleaned == "simp_all"

    def test_bare_rw(self):
        mode, cleaned = classify_proof_attempt("rw [foo]")
        assert mode == "tactic"
        assert cleaned == "rw [foo]"

    def test_bare_aesop(self):
        mode, cleaned = classify_proof_attempt("aesop")
        assert mode == "tactic"
        assert cleaned == "aesop"

    def test_bare_sorry(self):
        mode, cleaned = classify_proof_attempt("sorry")
        assert mode == "tactic"
        assert cleaned == "sorry"

    def test_bare_exact(self):
        mode, cleaned = classify_proof_attempt("exact foo")
        assert mode == "tactic"
        assert cleaned == "exact foo"

    def test_tactic_with_question_mark(self):
        mode, cleaned = classify_proof_attempt("simp?")
        assert mode == "tactic"
        assert cleaned == "simp?"

    def test_tactic_with_question_mark_aesop(self):
        mode, cleaned = classify_proof_attempt("aesop?")
        assert mode == "tactic"
        assert cleaned == "aesop?"

    # --- Tactic-mode: with 'by' prefix ---

    def test_by_simp(self):
        mode, cleaned = classify_proof_attempt("by simp")
        assert mode == "tactic"
        assert cleaned == "simp"

    def test_by_newline_tactic(self):
        mode, cleaned = classify_proof_attempt("by\n  simp\n  ring")
        assert mode == "tactic"
        assert cleaned == "simp\n  ring"

    def test_by_alone(self):
        mode, cleaned = classify_proof_attempt("by")
        assert mode == "tactic"
        assert cleaned == ""

    # --- Tactic-mode: with ':= by' prefix ---

    def test_assign_by_simp(self):
        mode, cleaned = classify_proof_attempt(":= by simp")
        assert mode == "tactic"
        assert cleaned == "simp"

    def test_assign_by_newline(self):
        mode, cleaned = classify_proof_attempt(":= by\n  simp")
        assert mode == "tactic"
        assert cleaned == "simp"

    # --- Tactic-mode: with ':=' prefix and tactic keyword ---

    def test_assign_simp(self):
        """':= simp' â€” strip ':=', detect 'simp' as tactic."""
        mode, cleaned = classify_proof_attempt(":= simp")
        assert mode == "tactic"
        assert cleaned == "simp"

    # --- Term-mode: simple terms ---

    def test_rfl(self):
        mode, cleaned = classify_proof_attempt("rfl")
        assert mode == "term"
        assert cleaned == "rfl"

    def test_term_application(self):
        mode, cleaned = classify_proof_attempt("HasDerivAt.deriv (hasDerivAt_const x c)")
        assert mode == "term"
        assert cleaned == "HasDerivAt.deriv (hasDerivAt_const x c)"

    def test_fun_lambda(self):
        mode, cleaned = classify_proof_attempt("fun x => x")
        assert mode == "term"
        assert cleaned == "fun x => x"

    # --- Term-mode: with ':=' prefix ---

    def test_assign_rfl(self):
        mode, cleaned = classify_proof_attempt(":= rfl")
        assert mode == "term"
        assert cleaned == "rfl"

    def test_assign_no_space_rfl(self):
        mode, cleaned = classify_proof_attempt(":=rfl")
        assert mode == "term"
        assert cleaned == "rfl"

    def test_assign_term_application(self):
        mode, cleaned = classify_proof_attempt(":= HasDerivAt.deriv (hasDerivAt_const x c)")
        assert mode == "term"
        assert cleaned == "HasDerivAt.deriv (hasDerivAt_const x c)"

    # --- Term-mode: where blocks ---

    def test_where_block(self):
        mode, cleaned = classify_proof_attempt("where\n  foo := bar")
        assert mode == "term"
        assert cleaned == "where\n  foo := bar"

    # --- Whitespace handling ---

    def test_leading_whitespace(self):
        mode, cleaned = classify_proof_attempt("  simp  ")
        assert mode == "tactic"
        assert cleaned == "simp"

    def test_leading_whitespace_term(self):
        mode, cleaned = classify_proof_attempt("  rfl  ")
        assert mode == "term"
        assert cleaned == "rfl"

    # --- Multi-line tactic proofs ---

    def test_multi_line_tactic_with_have(self):
        proof = "  have := foo\n  aesop"
        mode, cleaned = classify_proof_attempt(proof)
        assert mode == "tactic"
        assert cleaned == "have := foo\n  aesop"

    def test_intro_then_exact(self):
        proof = "intro h\nexact h"
        mode, cleaned = classify_proof_attempt(proof)
        assert mode == "tactic"
        assert cleaned == "intro h\nexact h"

    def test_ambiguous_bare_proof_uses_term_hint(self):
        mode, cleaned = classify_proof_attempt(
            "(IsLeftCancelMul.mul_left_cancel a ·)", mode_hint="term"
        )
        assert mode == "term"
        assert cleaned == "(IsLeftCancelMul.mul_left_cancel a ·)"

    def test_ambiguous_bare_proof_uses_tactic_hint(self):
        mode, cleaned = classify_proof_attempt("rfl", mode_hint="tactic")
        assert mode == "tactic"
        assert cleaned == "rfl"


# ============================================================================
# Tests for build_splice_plan with term-mode proofs
# ============================================================================


class TestBuildSplicePlanTermMode:
    """Tests for build_splice_plan handling of term-mode proof_attempt values.

    These test the fix for the double-':=' bug where value.pp proofs
    like ':=rfl' were being wrapped in 'by' producing invalid Lean.
    """

    def test_term_mode_rfl_with_assign_in_range(self):
        """Term-mode 'rfl' with ':=' in range produces ':= rfl' (no 'by')."""
        file_content = "import Mathlib\n\ntheorem foo : True := rfl\n"
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(3, 19, 3, 25)),
        ]
        splices = build_splice_plan(decls, "foo", "rfl", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= rfl"

    def test_term_mode_rfl_without_assign_in_range(self):
        """Term-mode 'rfl' without ':=' in range still gets ':= rfl'."""
        file_content = "import Mathlib\n\ntheorem foo : True := rfl\n"
        # Range starts after ':= '
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(3, 22, 3, 25)),
        ]
        splices = build_splice_plan(decls, "foo", "rfl", file_content=file_content)
        assert len(splices) == 1
        # Range excludes ':=' token, so replacement is term body only.
        assert splices[0].replacement == "rfl"

    def test_term_mode_application_with_assign_in_range(self):
        """Term-mode application with ':=' in range."""
        file_content = "theorem foo : Nat := Nat.zero\n"
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(1, 17, 1, 29)),
        ]
        splices = build_splice_plan(decls, "foo", "Nat.succ Nat.zero", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= Nat.succ Nat.zero"

    def test_value_pp_with_assign_prefix_stripped(self):
        """value.pp like ':=rfl' â€” classify strips ':=', splice adds it back."""
        file_content = "theorem foo : True := rfl\n"
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(1, 19, 1, 25)),
        ]
        # Simulating value.pp that includes ':='
        splices = build_splice_plan(decls, "foo", ":=rfl", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= rfl"

    def test_value_pp_with_assign_by_prefix(self):
        """value.pp like ':= by simp' â€” classify strips both, splice rebuilds."""
        file_content = "theorem foo : True := by\n  simp\n"
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(1, 19, 2, 6)),
        ]
        splices = build_splice_plan(decls, "foo", ":= by simp", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= by\n  simp"

    def test_tactic_mode_unchanged(self):
        """Tactic-mode 'simp' still produces 'by\\n  simp' (regression check)."""
        file_content = "theorem foo : True := by\n  trivial\n"
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(1, 19, 2, 9)),
        ]
        splices = build_splice_plan(decls, "foo", "simp", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= by\n  simp"

    def test_non_target_always_sorry(self):
        """Non-target theorems always get 'by sorry' regardless of proof_attempt mode."""
        file_content = "theorem a : True := rfl\ntheorem b : True := rfl\n"
        decls = [
            _make_decl("a", kind="theorem", value_range=Range(1, 17, 1, 23)),
            _make_decl("b", kind="theorem", value_range=Range(2, 17, 2, 23)),
        ]
        splices = build_splice_plan(decls, "a", "rfl", file_content=file_content)
        sorry_splice = next(s for s in splices if s.start_line == 2)
        assert sorry_splice.replacement == ":= by sorry"

    def test_by_prefixed_proof_attempt(self):
        """'by simp' proof_attempt â€” classify strips 'by', splice adds it back."""
        file_content = "theorem foo : True := by\n  trivial\n"
        decls = [
            _make_decl("foo", kind="theorem", value_range=Range(1, 19, 2, 9)),
        ]
        splices = build_splice_plan(decls, "foo", "by simp", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= by\n  simp"


class TestBuildSplicePlanEdgeCases:
    """Tests for edge cases discovered via golden proof diagnostics.

    These cover:
    - Synthetic _def theorems from irreducible_def (shared value ranges)
    - Where-block proofs (no ':=' in source)
    - Match-arm proofs starting at column 0
    """

    def test_irreducible_def_theorem_skipped(self):
        """Synthetic _def theorem range should be skipped when non-target."""
        file_content = (
            "theorem target : True := by trivial\n"
            "private irreducible_def add : R → R → R\n"
            "  | a, b => a + b\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("add_def", kind="theorem", value_range=Range(2, 0, 3, 18)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1

    def test_irreducible_def_with_real_theorem(self):
        """Real theorems in the same file as irreducible_def are still spliced."""
        file_content = (
            "private irreducible_def add : R → R → R\n"
            "  | a, b => a + b\n"
            "theorem add_comm : add a b = add b a := by ring\n"
        )
        decls = [
            _make_decl("add_def", kind="theorem", value_range=Range(1, 0, 2, 18)),
            _make_decl("add_comm", kind="theorem", value_range=Range(3, 42, 3, 49)),
        ]
        splices = build_splice_plan(decls, "add_comm", "ring", file_content=file_content)
        # Only add_comm should be spliced, add_def should be skipped
        assert len(splices) == 1
        assert splices[0].start_line == 3

    def test_where_block_non_target_gets_assign(self):
        """Non-target theorems with where-block proofs get ':= by sorry'."""
        file_content = (
            "theorem target : True := by trivial\n"
            "theorem other : Foo where\n"
            "  mp _ := sorry\n"
            "  mpr _ := sorry\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("other", kind="theorem", value_range=Range(2, 20, 4, 16)),
        ]
        splices = build_splice_plan(decls, "target", "trivial", file_content=file_content)
        other_splice = next(s for s in splices if s.start_line == 2)
        assert other_splice.replacement == ":= by sorry"

    def test_protected_def_theorem_skipped(self):
        """Ranges starting with protected-def syntax are skipped when non-target."""
        file_content = "theorem target : True := by trivial\nprotected def foo : Nat := 42\n"
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("foo_def", kind="theorem", value_range=Range(2, 0, 2, 29)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1

    def test_match_arm_proof_not_skipped(self):
        """Proofs starting with '|' (match arms) are valid proof content."""
        file_content = (
            "theorem target : True := by trivial\n"
            "theorem pow_succ : pow n = x := by\n"
            "  | 0 => rfl\n"
            "  | n + 1 => sorry\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("pow_succ", kind="theorem", value_range=Range(2, 33, 4, 20)),
        ]
        splices = build_splice_plan(decls, "target", "trivial", file_content=file_content)
        pow_splice = next(s for s in splices if s.start_line == 2)
        assert pow_splice.replacement == "by sorry"

    def test_non_target_equation_clauses_skipped(self):
        """Non-target equation-clause ranges are skipped to avoid malformed headers."""
        file_content = (
            "theorem target : True := by\n"
            "  trivial\n"
            "theorem eqn : Nat → Nat\n"
            "  | 0 => 0\n"
            "  | n + 1 => n\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 2, 9)),
            _make_decl("eqn", kind="theorem", value_range=Range(4, 2, 5, 13)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1
        assert all(s.start_line != 4 for s in splices)

    def test_target_equation_clauses_term_rewrite_to_assign(self):
        """Target equation-clause ranges are rewritten as ':= <term>'."""
        file_content = "theorem target : Nat → Nat\n  | 0 => 0\n  | n + 1 => n\n"
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(2, 2, 3, 13)),
        ]
        splices = build_splice_plan(decls, "target", "rfl", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= rfl"

    def test_target_equation_clauses_tactic_rewrite_to_assign_by(self):
        """Tactic target proofs on equation-clause ranges become ':= by ...'."""
        file_content = "theorem target : Nat → Nat\n  | 0 => 0\n  | n + 1 => n\n"
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(2, 2, 3, 13)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1
        assert splices[0].replacement == ":= by\n  simp"

    def test_equation_clause_after_by_stays_tactic_body(self):
        """Equation clauses after an explicit 'by' stay in tactic-body mode."""
        file_content = (
            "theorem target : True := by\n"
            "  trivial\n"
            "theorem by_match : Nat → Nat := by\n"
            "  | 0 => 0\n"
            "  | n + 1 => n\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 2, 9)),
            _make_decl("by_match", kind="theorem", value_range=Range(4, 2, 5, 13)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        by_match_splice = next(s for s in splices if s.start_line == 4)
        assert by_match_splice.replacement == "sorry"

    def test_no_header_followed_by_bare_by_for_equation_skip_case(self):
        """Skipping equation-clause non-targets prevents header + bare 'by sorry' corruption."""
        file_content = (
            "theorem target : True := by\n"
            "  trivial\n"
            "theorem eqn : Nat → Nat\n"
            "  | 0 => 0\n"
            "  | n + 1 => n\n"
            "theorem second : True := by\n"
            "  trivial\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 2, 9)),
            _make_decl("eqn", kind="theorem", value_range=Range(4, 2, 5, 13)),
            _make_decl("second", kind="theorem", value_range=Range(6, 23, 7, 9)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        result = apply_splices(file_content, splices)
        assert "theorem eqn : Nat → Nat\n  by sorry" not in result
        assert "theorem eqn : Nat → Nat\n  | 0 => 0\n  | n + 1 => n" in result

    def test_noncomputable_def_theorem_skipped(self):
        """Ranges starting with noncomputable-def syntax are skipped."""
        file_content = (
            "theorem target : True := by trivial\n"
            "noncomputable def erase (n : ℕ) : R[X] → R[X] := sorry\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("erase_def", kind="theorem", value_range=Range(2, 0, 2, 55)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1

    def test_doc_comment_before_irreducible_def_skipped(self):
        """Doc comments before declaration keywords are stripped before guard."""
        file_content = (
            "theorem target : True := by trivial\n"
            "/-- Some documentation -/\n"
            "private irreducible_def erase : R[X] → R[X]\n"
            "  | p => sorry\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("erase_def", kind="theorem", value_range=Range(2, 0, 4, 14)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1

    def test_doc_comment_before_def_skipped(self):
        """Single-line doc comments before def keyword are stripped."""
        file_content = (
            "theorem target : True := by trivial\n/-- A helper function -/ def helper : Nat := 42\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("helper_def", kind="theorem", value_range=Range(2, 0, 2, 48)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1

    def test_doc_comment_before_real_proof_not_skipped(self):
        """Real proof ranges are still spliced when they do not start with declaration syntax."""
        file_content = (
            "theorem target : True := by trivial\ntheorem other : True := by\n  trivial\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("other", kind="theorem", value_range=Range(2, 23, 3, 9)),
        ]
        splices = build_splice_plan(decls, "target", "trivial", file_content=file_content)
        assert len(splices) == 2

    def test_multiline_doc_comment_before_def_skipped(self):
        """Multi-line doc comments before declaration keywords are stripped."""
        file_content = (
            "theorem target : True := by trivial\n"
            "/-- A long\n"
            "documentation comment\n"
            "-/ noncomputable def foo : Nat := 42\n"
        )
        decls = [
            _make_decl("target", kind="theorem", value_range=Range(1, 23, 1, 35)),
            _make_decl("foo_def", kind="theorem", value_range=Range(2, 0, 4, 37)),
        ]
        splices = build_splice_plan(decls, "target", "simp", file_content=file_content)
        assert len(splices) == 1
