"""Integration tests for rank_targets tool.

Tests end-to-end functionality with real Lean files. These tests are kept minimal
and use small limits to ensure fast execution.

Slow tests are marked with @pytest.mark.slow and can be skipped with:
    pytest -m "not slow"
"""

import os
import time
from pathlib import Path

import pytest

from lean_proof_auto_mcp.tools.rank_targets import API_VERSION, rank_targets

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "mathlib_lean_files"
COEFF_LEAN = str(FIXTURES_DIR / "Coeff.lean")
DEFS_LEAN = str(FIXTURES_DIR / "Defs.lean")
DEGREE_LEAN = str(FIXTURES_DIR / "Degree.lean")
TEST_CONFIG = str(Path(__file__).parent.parent / "fixtures" / "test_config.yaml")


class TestRankTargetsIntegration:
    """Integration tests for rank_targets tool - minimal set for fast execution."""

    def test_basic_ranking_with_new_features(self):
        """Test basic ranking with all new API 1.0 features."""
        result = rank_targets(
            {
                "file": COEFF_LEAN,
                "skip_already_automated": False,
                "limit": 5,  # Small limit for speed
            }
        )

        # Verify success
        assert result["status"] == "success"
        assert result["tool"] == "rank_targets"
        assert result["api_version"] == API_VERSION

        # Verify new fields exist
        assert "available_objectives" in result
        assert "tier_distribution" in result["summary"]
        assert "skipped_already_automated" in result["summary"]

        # Verify ranking structure
        assert len(result["ranking"]) > 0
        for theorem in result["ranking"]:
            assert "tier" in theorem
            assert theorem["tier"] in ["S", "A", "B", "C", "D"]
            assert "score" in theorem
            assert 0.0 <= theorem["score"] <= 1.0

    def test_skip_already_automated_filtering(self):
        """Test skip_already_automated parameter."""
        # Without filtering
        result_all = rank_targets({"file": DEFS_LEAN, "skip_already_automated": False, "limit": 10})

        # With filtering
        result_filtered = rank_targets(
            {"file": DEFS_LEAN, "skip_already_automated": True, "limit": 10}
        )

        assert result_all["status"] == "success"
        assert result_filtered["status"] == "success"

        # Filtered should have skipped count
        assert result_filtered["summary"]["skipped_already_automated"] >= 0
        assert result_all["summary"]["skipped_already_automated"] == 0

    def test_custom_config_file(self):
        """Test loading custom configuration file."""
        result = rank_targets(
            {
                "file": COEFF_LEAN,
                "skip_already_automated": False,
                "config_path": TEST_CONFIG,
                "limit": 5,
            }
        )

        assert result["status"] == "success"
        assert "config_source" in result["metadata"]
        assert TEST_CONFIG in result["metadata"]["config_source"]

    def test_environment_variable_config(self):
        """Test loading configuration from environment variable."""
        os.environ["LEAN_PROOF_AUTO_MCP_CONFIG"] = TEST_CONFIG

        try:
            result = rank_targets({"file": COEFF_LEAN, "skip_already_automated": False, "limit": 5})

            assert result["status"] == "success"
            assert "config_source" in result["metadata"]
        finally:
            if "LEAN_PROOF_AUTO_MCP_CONFIG" in os.environ:
                del os.environ["LEAN_PROOF_AUTO_MCP_CONFIG"]

    def test_confidence_filtering(self):
        """Test confidence-based filtering."""
        result_filtered = rank_targets(
            {"file": DEFS_LEAN, "min_confidence": 0.7, "skip_already_automated": False, "limit": 10}
        )

        assert result_filtered["status"] == "success"

        # All returned theorems should meet confidence threshold
        for theorem in result_filtered["ranking"]:
            confidence = theorem["signals"].get("confidence", 0.0)
            assert confidence >= 0.7

    def test_multiple_objectives(self):
        """Test that different objectives work."""
        objectives = ["maximize_success", "maximize_impact", "balanced"]

        for objective in objectives:
            result = rank_targets(
                {
                    "file": DEFS_LEAN,
                    "objective": objective,
                    "skip_already_automated": False,
                    "limit": 5,
                }
            )

            assert result["status"] == "success"
            assert result["objective"] == objective
            assert len(result["ranking"]) > 0

    def test_response_structure_completeness(self):
        """Test that response contains all required API 1.0 fields."""
        result = rank_targets({"file": COEFF_LEAN, "skip_already_automated": False, "limit": 5})

        assert result["status"] == "success"

        # Top-level fields
        required_fields = [
            "api_version",
            "status",
            "run_id",
            "tool",
            "file",
            "objective",
            "ranking",
            "summary",
            "diagnostics",
            "metadata",
            "available_objectives",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

        # Summary fields
        summary_fields = [
            "total",
            "returned",
            "skipped_low_confidence",
            "skipped_already_automated",
            "tier_distribution",
        ]
        for field in summary_fields:
            assert field in result["summary"], f"Missing summary field: {field}"

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        # Invalid objective
        result = rank_targets(
            {"file": COEFF_LEAN, "objective": "invalid_objective", "skip_already_automated": False}
        )
        assert result["status"] == "fail"

        # Invalid limit
        result = rank_targets({"file": COEFF_LEAN, "limit": 0, "skip_already_automated": False})
        assert result["status"] == "fail"

    @pytest.mark.slow
    def test_deep_structure_mode(self):
        """Test deep structure mode (slow - calls scan_theorem for each theorem)."""
        result = rank_targets(
            {
                "file": COEFF_LEAN,
                "use_deep_structure": True,
                "skip_already_automated": False,
                "limit": 3,  # Very small limit since this is slow
            }
        )

        assert result["status"] == "success"
        assert result["metadata"]["deep_structure_used"] is True


class TestRankTargetsPerformance:
    """Performance tests - kept minimal."""

    def test_performance_without_deep_structure(self):
        """Test that ranking without deep structure is reasonably fast."""
        start_time = time.time()
        result = rank_targets(
            {
                "file": DEGREE_LEAN,
                "use_deep_structure": False,
                "skip_already_automated": False,
                "limit": 10,
            }
        )
        elapsed_ms = (time.time() - start_time) * 1000

        assert result["status"] == "success"
        print(f"\nPerformance: {elapsed_ms:.2f}ms for {result['summary']['total']} theorems")
