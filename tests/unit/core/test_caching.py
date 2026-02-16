"""
Unit tests for the querier-level caching pattern.

With the migration to RangeBasedHarnessConstructor, caching moved from the
constructor (which is now pure/stateless) to the Querier. These tests verify:
- RangeBasedHarnessConstructor determinism (stateless, same input → same output)
- Caller-side caching pattern (shared file_content across theorems)
"""

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessConfig,
    HarnessSuccess,
    RangeBasedHarnessConstructor,
)
from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range


def _decl(
    name: str,
    full_name: str = "",
    kind: str = "theorem",
    start_line: int = 1,
    end_line: int = 2,
    value_start: int = 1,
    value_start_col: int = 22,
    value_end: int = 2,
    value_end_col: int = 8,
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


class TestRangeBasedHarnessConstructorStatelessness:
    """Verify RangeBasedHarnessConstructor is stateless and deterministic."""

    def test_same_input_same_output(self):
        """Identical configs produce identical results — no hidden state."""
        constructor = RangeBasedHarnessConstructor()

        file_content = "import Mathlib\n\ntheorem test : True := by\n  trivial\n"
        declarations = [
            _decl(
                "test",
                start_line=3,
                end_line=4,
                value_start=3,
                value_start_col=23,
                value_end=4,
                value_end_col=9,
            )
        ]

        config = HarnessConfig(
            theorem_id="test",
            file_path="test.lean",
            proof_attempt="aesop",
            file_content=file_content,
            declarations=declarations,
        )

        result1 = constructor.construct(config)
        result2 = constructor.construct(config)

        assert isinstance(result1, HarnessSuccess)
        assert isinstance(result2, HarnessSuccess)
        assert result1.code == result2.code

    def test_different_proof_attempts_differ(self):
        """Different proof attempts on same file produce different harnesses."""
        constructor = RangeBasedHarnessConstructor()

        file_content = "import Mathlib\n\ntheorem test : True := by\n  trivial\n"
        declarations = [
            _decl(
                "test",
                start_line=3,
                end_line=4,
                value_start=3,
                value_start_col=23,
                value_end=4,
                value_end_col=9,
            )
        ]

        config1 = HarnessConfig(
            theorem_id="test", file_path="test.lean", proof_attempt="aesop",
            file_content=file_content, declarations=declarations,
        )
        config2 = HarnessConfig(
            theorem_id="test", file_path="test.lean", proof_attempt="grind",
            file_content=file_content, declarations=declarations,
        )

        result1 = constructor.construct(config1)
        result2 = constructor.construct(config2)

        assert isinstance(result1, HarnessSuccess)
        assert isinstance(result2, HarnessSuccess)
        assert result1.code != result2.code
        assert "aesop" in result1.code
        assert "grind" in result2.code

    def test_no_io_no_side_effects(self):
        """Constructor works with in-memory data only — no filesystem access."""
        constructor = RangeBasedHarnessConstructor()

        file_content = "import Fake.Module\n\nlemma foo : 1 = 1 := by\n  rfl\n"
        declarations = [
            _decl(
                "foo",
                kind="lemma",
                start_line=3,
                end_line=4,
                value_start=3,
                value_start_col=21,
                value_end=4,
                value_end_col=5,
            )
        ]

        config = HarnessConfig(
            theorem_id="foo", file_path="nonexistent/path.lean", proof_attempt="omega",
            file_content=file_content, declarations=declarations,
        )

        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)
        assert "omega" in result.code


class TestCallerCachingPattern:
    """Verify the caller-side caching pattern works correctly."""

    def test_shared_file_content_across_theorems(self):
        """Multiple theorems in same file share the same file_content string."""
        constructor = RangeBasedHarnessConstructor()

        file_content = (
            "import Mathlib\n\n"
            "theorem t1 : True := by\n  trivial\n\n"
            "theorem t2 : True := by\n  trivial\n"
        )
        declarations = [
            _decl(
                "t1",
                start_line=3,
                end_line=4,
                value_start=3,
                value_start_col=21,
                value_end=4,
                value_end_col=9,
            ),
            _decl(
                "t2",
                start_line=6,
                end_line=7,
                value_start=6,
                value_start_col=21,
                value_end=7,
                value_end_col=9,
            ),
        ]

        config1 = HarnessConfig(
            theorem_id="t1", file_path="test.lean", proof_attempt="aesop",
            file_content=file_content, declarations=declarations,
        )
        config2 = HarnessConfig(
            theorem_id="t2", file_path="test.lean", proof_attempt="aesop",
            file_content=file_content, declarations=declarations,
        )

        result1 = constructor.construct(config1)
        result2 = constructor.construct(config2)

        assert isinstance(result1, HarnessSuccess)
        assert isinstance(result2, HarnessSuccess)
        assert result1.code != result2.code

    def test_different_files_isolated(self):
        """Configs from different files produce independent harnesses."""
        constructor = RangeBasedHarnessConstructor()

        file1 = "import A\n\ntheorem t : True := by\n  trivial\n"
        file2 = "import B\n\ntheorem t : False ∨ True := by\n  right; trivial\n"

        decls1 = [
            _decl(
                "t",
                start_line=3,
                end_line=4,
                value_start=3,
                value_start_col=21,
                value_end=4,
                value_end_col=9,
            )
        ]
        decls2 = [
            _decl(
                "t",
                start_line=3,
                end_line=4,
                value_start=3,
                value_start_col=28,
                value_end=4,
                value_end_col=16,
            )
        ]

        config1 = HarnessConfig(
            theorem_id="t", file_path="file1.lean", proof_attempt="aesop",
            file_content=file1, declarations=decls1,
        )
        config2 = HarnessConfig(
            theorem_id="t", file_path="file2.lean", proof_attempt="aesop",
            file_content=file2, declarations=decls2,
        )

        result1 = constructor.construct(config1)
        result2 = constructor.construct(config2)

        assert isinstance(result1, HarnessSuccess)
        assert isinstance(result2, HarnessSuccess)
        assert "import A" in result1.code
        assert "import B" in result2.code
