"""Property-based tests for scan_theorem tool."""

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from lean_proof_auto_mcp.tools.scan_theorem import scan_theorem


@st.composite
def scan_theorem_args(draw) -> dict[str, Any]:
    """Generate scan_theorem arguments."""
    filename = draw(st.text(min_size=1, max_size=10).filter(lambda x: x.strip()))
    theorem_id = draw(st.text(min_size=1, max_size=10).filter(lambda x: x.strip()))
    return {"file": f"{filename}.lean", "target": {"theorem_id": f"Test.{theorem_id}"}}


class TestScanTheoremProperties:
    """Property-based tests for scan_theorem tool correctness properties."""

    @given(args=scan_theorem_args())
    def test_determinism(self, args: dict[str, Any]) -> None:
        """Property 1: Same input produces identical output across multiple calls."""
        result1 = scan_theorem(args)
        result2 = scan_theorem(args)

        assert result1 == result2, "Same input should produce identical output"

    @given(args=scan_theorem_args())
    def test_tool_name_invariant(self, args: dict[str, Any]) -> None:
        """Property: Tool field is always exactly 'scan_theorem'."""
        result = scan_theorem(args)

        assert result["tool"] == "scan_theorem", (
            f"Tool must be 'scan_theorem', got '{result['tool']}'"
        )

    @given(args=scan_theorem_args())
    def test_required_fields_always_present(self, args: dict[str, Any]) -> None:
        """Property: All required fields are always present regardless of input."""
        result = scan_theorem(args)

        # Top-level required fields
        required_fields = ["api_version", "status", "run_id", "tool", "file", "target"]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    @given(args=scan_theorem_args())
    def test_target_echo(self, args: dict[str, Any]) -> None:
        """Property: Input target is echoed in response."""
        result = scan_theorem(args)

        # Target should always be echoed regardless of success/failure
        assert "target" in result, "Response must include target field"
        assert "theorem_id" in result["target"], "Target must include theorem_id when provided"
        assert result["target"]["theorem_id"] == args["target"]["theorem_id"], (
            f"Target theorem_id not echoed correctly: "
            f"expected '{args['target']['theorem_id']}', got '{result['target']['theorem_id']}'"
        )

    @given(args=scan_theorem_args())
    def test_score_bounds(self, args: dict[str, Any]) -> None:
        """Property: All automation scores are in [0.0, 1.0] range when theorem is found."""
        result = scan_theorem(args)

        # Only check scores if theorem was found (success status)
        if result["status"] == "success" and "theorem" in result and result["theorem"]:
            auto = result["theorem"]["automation"]

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
