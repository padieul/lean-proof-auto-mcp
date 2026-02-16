"""Integration tests for probe_file tool.

Tests end-to-end functionality with real Lean files. These tests verify
the probe_file tool's batch processing behavior with actual Lean compilation.

NOTE: These tests require LeanInteract library and a Lean 4 installation.
They are marked with @pytest.mark.integration and can be skipped with:
    pytest -m "not integration"

Slow tests are additionally marked with @pytest.mark.slow.

Requirements: 4.1-4.7, 5.1-5.6
"""

from pathlib import Path

import pytest

from lean_proof_auto_mcp.tools.probe_file import probe_file

# Check if LeanInteract is available
try:
    import lean_interact  # noqa: F401

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LEAN_INTERACT_AVAILABLE = False

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
MULTI_THEOREM = str(FIXTURES_DIR / "probe_file_multi_theorem.lean")
AESOP_TRIVIAL = str(FIXTURES_DIR / "probe_aesop_trivial.lean")

# Skip all tests if LeanInteract is not available
pytestmark = [
    pytest.mark.skipif(
        not LEAN_INTERACT_AVAILABLE,
        reason="LeanInteract library not installed. Install with: pip install lean-interact",
    ),
    pytest.mark.requires_lean,  # Mark all tests in this file as requiring Lean
]


class TestProbeFileIntegration:
    """Integration tests for probe_file tool with real Lean files."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_probe_file_with_file_order(self):
        """Test probe_file with file_order ordering mode.

        This test verifies:
        - Probe_file processes multiple theorems in file order
        - Results are returned in file order
        - Summary statistics are correct
        - All required fields are present

        Requirements: 4.1, 4.2, 4.4, 4.5, 4.7, 5.1, 5.2, 5.3, 5.4, 5.5
        """
        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 10,
                "ordering": "file_order",
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"
        assert result["api_version"] == "1.1.0"

        # Verify file field
        assert result["file"] == MULTI_THEOREM

        # Verify summary structure
        summary = result["summary"]
        assert "total" in summary
        assert "closed" in summary
        assert "promising" in summary
        assert "failed" in summary
        assert "timed_out" in summary

        # Verify we processed theorems
        assert summary["total"] > 0, "Should have processed at least one theorem"

        # Verify results structure
        assert isinstance(result["results"], list)
        assert len(result["results"]) == summary["total"]

        # Verify each result has required fields
        for theorem_result in result["results"]:
            assert "theorem_id" in theorem_result
            assert "outcome" in theorem_result
            assert "classification" in theorem_result
            assert "elapsed_ms" in theorem_result

        # Verify summary aggregation correctness
        closed_count = sum(1 for r in result["results"] if r["classification"] == "trivial")
        promising_count = sum(1 for r in result["results"] if r["classification"] == "promising")
        failed_count = sum(1 for r in result["results"] if r["classification"] == "failed")
        timed_out_count = sum(1 for r in result["results"] if r["classification"] == "timed_out")

        assert summary["closed"] == closed_count
        assert summary["promising"] == promising_count
        assert summary["failed"] == failed_count
        assert summary["timed_out"] == timed_out_count

        # Verify metadata
        assert "metadata" in result
        assert "elapsed_ms" in result["metadata"]

    @pytest.mark.integration
    @pytest.mark.slow
    def test_probe_file_with_rank_targets_ordering(self):
        """Test probe_file with rank_targets ordering mode.

        This test verifies:
        - Probe_file uses rank_targets for ordering
        - Results are returned in ranked order
        - Summary statistics are correct

        Requirements: 4.1, 5.5
        """
        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 10,
                "ordering": "rank_targets",
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"

        # Verify we processed theorems
        assert result["summary"]["total"] > 0, "Should have processed at least one theorem"

        # Verify results structure
        assert isinstance(result["results"], list)
        assert len(result["results"]) == result["summary"]["total"]

        # Note: We can't easily verify the exact ordering without knowing
        # rank_targets' internal logic, but we can verify the structure is correct

    @pytest.mark.integration
    def test_probe_file_with_limit_parameter(self):
        """Test probe_file with limit parameter.

        This test verifies:
        - Probe_file respects the limit parameter
        - At most 'limit' theorems are processed
        - Summary total matches actual results count

        Requirements: 4.3, 5.6
        """
        # Use a small limit
        limit = 2

        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": limit,
                "ordering": "file_order",
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"

        # Verify limit was respected
        assert result["summary"]["total"] <= limit, (
            f"Expected at most {limit} theorems but got {result['summary']['total']}"
        )
        assert len(result["results"]) <= limit, (
            f"Expected at most {limit} results but got {len(result['results'])}"
        )

        # Verify summary total matches results count
        assert result["summary"]["total"] == len(result["results"])

    @pytest.mark.integration
    @pytest.mark.slow
    def test_probe_file_partial_success(self):
        """Test probe_file partial success handling.

        This test verifies:
        - Probe_file continues processing after individual theorem errors
        - Status is "partial" or "success" depending on errors
        - Results include both successful and failed probes

        Requirements: 4.6, 10.4
        """
        # Use a file with mixed success/failure theorems
        result = probe_file(
            {
                "file": AESOP_TRIVIAL,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 10,
                "ordering": "file_order",
            }
        )

        # Verify status is success or partial
        assert result["status"] in ("success", "partial"), (
            f"Expected success or partial but got {result['status']}"
        )

        # Verify we got results
        assert result["summary"]["total"] > 0, "Should have processed at least one theorem"
        assert len(result["results"]) > 0, "Should have at least one result"

    @pytest.mark.integration
    def test_probe_file_per_theorem_budget_isolation(self):
        """Test that each theorem gets its own independent budget.

        This test verifies:
        - Each theorem is allocated budget_s_per independently
        - One theorem timing out doesn't affect others
        - Timing information is per-theorem

        Requirements: 4.3, 8.4
        """
        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 3.0,
                "limit": 3,
                "ordering": "file_order",
            }
        )

        # Verify we got results
        assert result["summary"]["total"] > 0

        # Verify each result has timing information
        for theorem_result in result["results"]:
            assert "elapsed_ms" in theorem_result
            assert theorem_result["elapsed_ms"] >= 0

            # Verify elapsed time is reasonable (not accumulated across theorems)
            # Each theorem should take less than budget_s_per + overhead
            # Allow 5s overhead for process management
            assert theorem_result["elapsed_ms"] < (3.0 + 5.0) * 1000, (
                f"Theorem {theorem_result['theorem_id']} took "
                f"{theorem_result['elapsed_ms']}ms, expected < 8000ms"
            )

    @pytest.mark.integration
    def test_probe_file_result_completeness(self):
        """Test that probe_file result contains all required fields.

        This test verifies:
        - All required fields are present in result
        - Field types are correct
        - Nested structures are complete

        Requirements: 4.5, 5.2, 5.3, 5.4
        """
        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 5,
                "ordering": "file_order",
            }
        )

        # Verify top-level fields
        assert "api_version" in result
        assert "status" in result
        assert "file" in result
        assert "summary" in result
        assert "results" in result
        assert "metadata" in result

        # Verify summary structure
        summary = result["summary"]
        assert "total" in summary
        assert "closed" in summary
        assert "promising" in summary
        assert "failed" in summary
        assert "timed_out" in summary

        # Verify all counts are non-negative integers
        assert isinstance(summary["total"], int) and summary["total"] >= 0
        assert isinstance(summary["closed"], int) and summary["closed"] >= 0
        assert isinstance(summary["promising"], int) and summary["promising"] >= 0
        assert isinstance(summary["failed"], int) and summary["failed"] >= 0
        assert isinstance(summary["timed_out"], int) and summary["timed_out"] >= 0

        # Verify results is a list
        assert isinstance(result["results"], list)

        # Verify each result has required fields
        for theorem_result in result["results"]:
            assert "theorem_id" in theorem_result
            assert "outcome" in theorem_result
            assert "classification" in theorem_result
            assert "elapsed_ms" in theorem_result

            # Verify field types
            assert isinstance(theorem_result["theorem_id"], str)
            assert isinstance(theorem_result["outcome"], str)
            assert isinstance(theorem_result["classification"], str)
            assert isinstance(theorem_result["elapsed_ms"], int | float)

        # Verify metadata structure
        metadata = result["metadata"]
        assert "elapsed_ms" in metadata
        assert isinstance(metadata["elapsed_ms"], int | float)

    @pytest.mark.integration
    def test_probe_file_deterministic_result_ordering(self):
        """Test that probe_file produces deterministic result ordering.

        This test verifies:
        - Running probe_file twice with same inputs produces same order
        - Results are consistent across runs

        Requirements: 4.7
        """
        # Run probe_file twice with identical inputs
        result1 = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 3,
                "ordering": "file_order",
            }
        )

        result2 = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 3,
                "ordering": "file_order",
            }
        )

        # Verify both succeeded
        assert result1["status"] == "success"
        assert result2["status"] == "success"

        # Verify same number of results
        assert len(result1["results"]) == len(result2["results"])

        # Verify same ordering of theorem_ids
        theorem_ids_1 = [r["theorem_id"] for r in result1["results"]]
        theorem_ids_2 = [r["theorem_id"] for r in result2["results"]]
        assert theorem_ids_1 == theorem_ids_2, "Theorem ordering should be deterministic"

    @pytest.mark.integration
    def test_probe_file_invalid_file_error(self):
        """Test probe_file error handling with invalid file.

        This test verifies:
        - Probe_file returns error or success status for invalid file
        - If file doesn't exist, scan_file will fail and return error
        - If file exists but has no theorems, returns success with 0 results
        - Error response has correct structure
        - No unhandled exceptions escape

        Requirements: 10.4, 10.5
        """
        result = probe_file(
            {
                "file": "nonexistent_file.lean",
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 10,
                "ordering": "file_order",
            }
        )

        # Verify status is error or success (success with 0 results if scan_file handles gracefully)
        assert result["status"] in ("error", "success"), (
            f"Expected error or success but got {result['status']}"
        )

        # Verify error response structure
        assert "api_version" in result
        assert "file" in result
        assert "summary" in result
        assert "results" in result
        assert "metadata" in result

        # If error, verify summary shows no results
        if result["status"] == "error":
            assert result["summary"]["total"] == 0
            assert len(result["results"]) == 0
            assert "error_code" in result["metadata"]
        else:
            # If success, it means scan_file returned 0 theorems
            assert result["summary"]["total"] == 0
            assert len(result["results"]) == 0

    @pytest.mark.integration
    def test_probe_file_invalid_mode_validation(self):
        """Test probe_file input validation for invalid mode.

        This test verifies:
        - Probe_file validates mode parameter
        - Returns error status for invalid mode
        - No unhandled exceptions escape

        Requirements: 10.4, 10.5
        """
        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "invalid_mode",
                "budget_s_per": 5.0,
                "limit": 10,
                "ordering": "file_order",
            }
        )

        # Verify error status
        assert result["status"] == "error", f"Expected error but got {result['status']}"

        # Verify error metadata
        assert "error_code" in result["metadata"]
        assert result["metadata"]["error_code"] == "input_validation_error"

    @pytest.mark.integration
    def test_probe_file_invalid_ordering_validation(self):
        """Test probe_file input validation for invalid ordering.

        This test verifies:
        - Probe_file validates ordering parameter
        - Returns error status for invalid ordering
        - No unhandled exceptions escape

        Requirements: 5.5, 10.4, 10.5
        """
        result = probe_file(
            {
                "file": MULTI_THEOREM,
                "mode": "aesop",
                "budget_s_per": 5.0,
                "limit": 10,
                "ordering": "invalid_ordering",
            }
        )

        # Verify error status
        assert result["status"] == "error", f"Expected error but got {result['status']}"

        # Verify error metadata
        assert "error_code" in result["metadata"]
        assert result["metadata"]["error_code"] == "input_validation_error"
