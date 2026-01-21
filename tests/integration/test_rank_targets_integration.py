"""Integration tests for rank_targets tool.

Tests end-to-end functionality with real Lean files, including all objectives,
deep structure mode, and error scenarios.
"""

import time
from pathlib import Path

from lean_proof_auto_mcp.tools.rank_targets import rank_targets

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "mathlib_lean_files"
COEFF_LEAN = str(FIXTURES_DIR / "Coeff.lean")
DEFS_LEAN = str(FIXTURES_DIR / "Defs.lean")
DEGREE_LEAN = str(FIXTURES_DIR / "Degree.lean")


class TestRankTargetsIntegration:
    """Integration tests for rank_targets tool."""

    def test_basic_ranking_with_coeff_lean(self):
        """Test basic ranking with Coeff.lean fixture."""
        result = rank_targets({"file": COEFF_LEAN})

        # Verify success
        assert result["status"] == "success"
        assert result["tool"] == "rank_targets"
        assert result["file"] == COEFF_LEAN
        assert result["objective"] == "balanced"  # Default

        # Verify structure
        assert "ranking" in result
        assert "summary" in result
        assert "diagnostics" in result
        assert "metadata" in result

        # Verify ranking is non-empty (Coeff.lean has theorems)
        assert len(result["ranking"]) > 0

        # Verify each ranked theorem has required fields
        for theorem in result["ranking"]:
            assert "theorem_id" in theorem
            assert "range" in theorem
            assert "score" in theorem
            assert "signals" in theorem

            # Verify range structure
            assert "start_line" in theorem["range"]
            assert "end_line" in theorem["range"]

            # Verify score bounds
            assert 0.0 <= theorem["score"] <= 1.0

    def test_all_objectives_produce_valid_rankings(self):
        """Test that all four objectives produce valid rankings."""
        objectives = [
            "maximize_success",
            "maximize_impact",
            "maximize_subgoal_automation",
            "balanced",
        ]

        for objective in objectives:
            result = rank_targets({"file": DEFS_LEAN, "objective": objective})

            # Verify success
            assert result["status"] == "success", f"Failed for objective: {objective}"
            assert result["objective"] == objective

            # Verify ranking is valid
            assert "ranking" in result
            assert len(result["ranking"]) > 0

            # Verify scores are monotonic (descending)
            scores = [t["score"] for t in result["ranking"]]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], (
                    f"Scores not monotonic for {objective}: "
                    f"{scores[i]} < {scores[i + 1]} at index {i}"
                )

    def test_different_objectives_produce_different_rankings(self):
        """Test that different objectives produce different rankings."""
        success_result = rank_targets({"file": DEGREE_LEAN, "objective": "maximize_success"})
        impact_result = rank_targets({"file": DEGREE_LEAN, "objective": "maximize_impact"})

        # Both should succeed
        assert success_result["status"] == "success"
        assert impact_result["status"] == "success"

        # Extract theorem IDs in order
        success_ids = [t["theorem_id"] for t in success_result["ranking"]]
        impact_ids = [t["theorem_id"] for t in impact_result["ranking"]]

        # Rankings should differ (unless file has < 2 theorems)
        if len(success_ids) >= 2:
            assert success_ids != impact_ids, (
                "Different objectives should produce different rankings"
            )

    def test_deep_structure_mode(self):
        """Test deep structure mode integration with scan_theorem."""
        # Test without deep structure
        result_shallow = rank_targets({"file": COEFF_LEAN, "use_deep_structure": False})

        # Test with deep structure
        result_deep = rank_targets({"file": COEFF_LEAN, "use_deep_structure": True})

        # Both should succeed
        assert result_shallow["status"] == "success"
        assert result_deep["status"] == "success"

        # Verify metadata reflects deep structure usage
        assert result_shallow["metadata"]["deep_structure_used"] is False
        assert result_deep["metadata"]["deep_structure_used"] is True

        # Deep structure may produce different scores (due to structure bonus)
        # but both should have valid rankings
        assert len(result_shallow["ranking"]) > 0
        assert len(result_deep["ranking"]) > 0

    def test_confidence_filtering(self):
        """Test confidence-based filtering."""
        # Get all theorems (no filtering)
        result_all = rank_targets({"file": DEFS_LEAN, "min_confidence": 0.0})

        # Get high-confidence theorems only
        result_filtered = rank_targets({"file": DEFS_LEAN, "min_confidence": 0.7})

        # Both should succeed
        assert result_all["status"] == "success"
        assert result_filtered["status"] == "success"

        # Filtered result should have fewer or equal theorems
        assert len(result_filtered["ranking"]) <= len(result_all["ranking"])

        # All returned theorems should meet confidence threshold
        for theorem in result_filtered["ranking"]:
            confidence = theorem["signals"].get("confidence", 0.0)
            assert confidence >= 0.7, (
                f"Theorem {theorem['theorem_id']} has confidence {confidence} < 0.7"
            )

        # Summary should report skipped theorems
        total = result_filtered["summary"]["total"]
        returned = result_filtered["summary"]["returned"]
        skipped = result_filtered["summary"]["skipped_low_confidence"]
        assert total == returned + skipped

    def test_limit_parameter(self):
        """Test limit parameter controls number of returned theorems."""
        # Request only top 5 theorems
        result = rank_targets({"file": DEGREE_LEAN, "limit": 5})

        assert result["status"] == "success"

        # Should return at most 5 theorems
        assert len(result["ranking"]) <= 5

        # Summary should reflect this
        assert result["summary"]["returned"] <= 5

    def test_include_components_flag(self):
        """Test include_components flag controls component output."""
        # With components
        result_with = rank_targets({"file": COEFF_LEAN, "include_components": True})

        # Without components
        result_without = rank_targets({"file": COEFF_LEAN, "include_components": False})

        # Both should succeed
        assert result_with["status"] == "success"
        assert result_without["status"] == "success"

        # Verify components presence
        if len(result_with["ranking"]) > 0:
            assert "components" in result_with["ranking"][0]

        if len(result_without["ranking"]) > 0:
            assert "components" not in result_without["ranking"][0]

    def test_include_reasons_flag(self):
        """Test include_reasons flag controls reason output."""
        # With reasons
        result_with = rank_targets({"file": DEFS_LEAN, "include_reasons": True})

        # Without reasons
        result_without = rank_targets({"file": DEFS_LEAN, "include_reasons": False})

        # Both should succeed
        assert result_with["status"] == "success"
        assert result_without["status"] == "success"

        # Verify reasons presence
        if len(result_with["ranking"]) > 0:
            assert "reasons" in result_with["ranking"][0]
            assert isinstance(result_with["ranking"][0]["reasons"], list)

        if len(result_without["ranking"]) > 0:
            assert "reasons" not in result_without["ranking"][0]

    def test_missing_file_error(self):
        """Test error handling for missing file."""
        result = rank_targets({"file": "nonexistent_file.lean"})

        # Should either fail or succeed with empty results
        # (scan_file may handle missing files gracefully)
        assert result["status"] in ["fail", "success"]

        if result["status"] == "fail":
            # Should have error diagnostic
            assert "diagnostics" in result
            error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
            assert len(error_diagnostics) > 0
        else:
            # If success, should have empty ranking
            assert len(result["ranking"]) == 0

    def test_invalid_objective_error(self):
        """Test error handling for invalid objective."""
        result = rank_targets({"file": COEFF_LEAN, "objective": "invalid_objective"})

        # Should fail gracefully
        assert result["status"] == "fail"
        assert "diagnostics" in result

        # Should have error diagnostic mentioning objective
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) > 0
        assert any("objective" in d["message"].lower() for d in error_diagnostics)

    def test_invalid_limit_error(self):
        """Test error handling for invalid limit."""
        # Limit too low
        result_low = rank_targets({"file": COEFF_LEAN, "limit": 0})
        assert result_low["status"] == "fail"

        # Limit too high
        result_high = rank_targets({"file": COEFF_LEAN, "limit": 1000})
        assert result_high["status"] == "fail"

    def test_invalid_confidence_error(self):
        """Test error handling for invalid min_confidence."""
        # Confidence too low
        result_low = rank_targets({"file": COEFF_LEAN, "min_confidence": -0.1})
        assert result_low["status"] == "fail"

        # Confidence too high
        result_high = rank_targets({"file": COEFF_LEAN, "min_confidence": 1.5})
        assert result_high["status"] == "fail"

    def test_deterministic_output(self):
        """Test that multiple invocations produce identical output."""
        result1 = rank_targets({"file": DEFS_LEAN, "objective": "balanced"})
        result2 = rank_targets({"file": DEFS_LEAN, "objective": "balanced"})

        # Both should succeed
        assert result1["status"] == "success"
        assert result2["status"] == "success"

        # Rankings should be identical
        assert len(result1["ranking"]) == len(result2["ranking"])

        for i, (t1, t2) in enumerate(zip(result1["ranking"], result2["ranking"], strict=True)):
            assert t1["theorem_id"] == t2["theorem_id"], f"Theorem IDs differ at index {i}"
            assert t1["score"] == t2["score"], f"Scores differ at index {i}"

    def test_performance_target_without_deep_structure(self):
        """Test performance target: < 50ms for 200 theorems without deep structure.

        Note: This is a soft target and may vary by system.
        """
        # Use largest fixture file
        result = rank_targets({"file": DEGREE_LEAN, "use_deep_structure": False})

        assert result["status"] == "success"

        # Check computation time
        computation_time_ms = result["metadata"]["computation_time_ms"]

        # Log performance for visibility
        print(f"\nPerformance (no deep structure): {computation_time_ms:.2f}ms")

        # Soft assertion - warn if exceeds target but don't fail
        if computation_time_ms > 50:
            print(f"WARNING: Performance target exceeded: {computation_time_ms:.2f}ms > 50ms")

    def test_response_structure_completeness(self):
        """Test that response contains all required fields."""
        result = rank_targets({"file": COEFF_LEAN})

        assert result["status"] == "success"

        # Top-level fields
        assert "api_version" in result
        assert "status" in result
        assert "run_id" in result
        assert "tool" in result
        assert "file" in result
        assert "objective" in result
        assert "ranking" in result
        assert "summary" in result
        assert "diagnostics" in result
        assert "metadata" in result

        # Summary fields
        assert "total" in result["summary"]
        assert "returned" in result["summary"]
        assert "skipped_low_confidence" in result["summary"]

        # Metadata fields
        assert "deep_structure_used" in result["metadata"]
        assert "computation_time_ms" in result["metadata"]

        # Ranking structure (if non-empty)
        if len(result["ranking"]) > 0:
            theorem = result["ranking"][0]
            assert "theorem_id" in theorem
            assert "range" in theorem
            assert "score" in theorem
            assert "signals" in theorem

    def test_run_id_generation(self):
        """Test that run_id is generated and deterministic."""
        result1 = rank_targets({"file": COEFF_LEAN})
        result2 = rank_targets({"file": COEFF_LEAN})

        # Both should have run_id
        assert "run_id" in result1
        assert "run_id" in result2

        # Run IDs should be deterministic (same file = same run_id)
        assert result1["run_id"] == result2["run_id"]

        # Run ID should have expected format
        assert result1["run_id"].startswith("rank-")

    def test_scan_file_run_id_correlation(self):
        """Test that scan_file_run_id is included in metadata."""
        result = rank_targets({"file": DEFS_LEAN})

        assert result["status"] == "success"

        # Should have scan_file_run_id in metadata
        assert "scan_file_run_id" in result["metadata"]
        assert isinstance(result["metadata"]["scan_file_run_id"], str)


class TestRankTargetsPerformance:
    """Performance benchmark tests for rank_targets."""

    def test_performance_benchmark_no_deep_structure(self):
        """Benchmark: < 50ms for 200 theorems without deep structure."""
        # Use largest fixture
        start_time = time.time()
        result = rank_targets({"file": DEGREE_LEAN, "use_deep_structure": False})
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000

        assert result["status"] == "success"

        # Log results
        theorem_count = result["summary"]["total"]
        print("\nBenchmark (no deep structure):")
        print(f"  Theorems: {theorem_count}")
        print(f"  Time: {elapsed_ms:.2f}ms")
        print("  Target: < 50ms")

        # Metadata should also report time
        reported_time = result["metadata"]["computation_time_ms"]
        print(f"  Reported time: {reported_time:.2f}ms")

    def test_performance_benchmark_with_deep_structure(self):
        """Benchmark: < 200ms for 200 theorems with deep structure.

        Note: This test may be slow as it calls scan_theorem for each theorem.
        """
        # Use smaller fixture for deep structure test
        start_time = time.time()
        result = rank_targets({"file": COEFF_LEAN, "use_deep_structure": True, "limit": 10})
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000

        assert result["status"] == "success"

        # Log results
        theorem_count = result["summary"]["total"]
        print("\nBenchmark (with deep structure):")
        print(f"  Theorems: {theorem_count}")
        print(f"  Time: {elapsed_ms:.2f}ms")
        print("  Target: < 200ms (for 200 theorems)")

        # Metadata should report deep structure usage
        assert result["metadata"]["deep_structure_used"] is True

    def test_computation_time_metadata(self):
        """Test that computation_time_ms is included in metadata."""
        result = rank_targets({"file": DEFS_LEAN})

        assert result["status"] == "success"
        assert "computation_time_ms" in result["metadata"]
        assert isinstance(result["metadata"]["computation_time_ms"], (int, float))
        assert result["metadata"]["computation_time_ms"] >= 0
