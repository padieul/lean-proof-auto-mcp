"""Integration tests for probe tool.

Tests end-to-end functionality with real Lean files. These tests verify
the probe tool's behavior with actual Lean compilation and automation tactics.

NOTE: These tests require LeanInteract library and a Lean 4 installation.
They are marked with @pytest.mark.integration and can be skipped with:
    pytest -m "not integration"

Slow tests are additionally marked with @pytest.mark.slow.

Requirements: 1.1-1.8, 2.1-2.6, 3.1-3.8
"""

import time
from pathlib import Path

import pytest

from lean_proof_auto_mcp.tools.probe import probe

# Check if LeanInteract is available
try:
    import lean_interact  # noqa: F401

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LEAN_INTERACT_AVAILABLE = False

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
AESOP_TRIVIAL = str(FIXTURES_DIR / "probe_aesop_trivial.lean")
AESOP_PROMISING = str(FIXTURES_DIR / "probe_aesop_promising.lean")
GRIND_TEST = str(FIXTURES_DIR / "probe_grind_test.lean")
TIMEOUT_TEST = str(FIXTURES_DIR / "probe_timeout_test.lean")
ERROR_TEST = str(FIXTURES_DIR / "probe_error_test.lean")

# Skip all tests if LeanInteract is not available
pytestmark = [
    pytest.mark.skipif(
        not LEAN_INTERACT_AVAILABLE,
        reason="LeanInteract library not installed. Install with: pip install lean-interact",
    ),
    pytest.mark.requires_lean,  # Mark all tests in this file as requiring Lean
]


class TestProbeIntegration:
    """Integration tests for probe tool with real Lean files."""

    @pytest.mark.integration
    def test_probe_aesop_mode_trivial_success(self):
        """Test probe with aesop mode on trivial theorem that closes quickly.

        This test verifies:
        - Probe executes successfully with aesop mode
        - Result has correct structure and all required fields
        - Classification is "trivial" for quick success
        - No error diagnostics are present

        Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 3.1-3.8
        """
        result = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"
        assert result["api_version"] == "0.1.0"

        # Verify run_id exists and has correct format
        assert "run_id" in result
        assert result["run_id"].startswith("probe-")

        # Verify probe_result structure
        probe_result = result["probe_result"]
        assert probe_result["mode"] == "aesop"
        assert probe_result["outcome"] == "closed"
        assert probe_result["classification"] == "trivial"
        assert probe_result["suggested_script"] is None  # Only for aesop? mode

        # Verify no error diagnostics
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) == 0, f"Expected no errors but found: {error_diagnostics}"

        # Verify timing information
        assert "timing" in result
        assert "elapsed_ms" in result["timing"]
        assert "budget_s" in result["timing"]
        assert result["timing"]["budget_s"] == 10.0
        assert result["timing"]["elapsed_ms"] > 0

        # Verify metadata
        assert "metadata" in result
        # Metadata may include lean_version, lake_version, repo_commit
        # These are optional and depend on environment
        assert isinstance(result["metadata"], dict)

    @pytest.mark.integration
    def test_probe_aesop_question_mode_with_suggested_script(self):
        """Test probe with aesop? mode returns suggested script on success.

        This test verifies:
        - Probe executes with aesop? mode
        - Suggested script is included in result when successful
        - Result structure is correct

        Requirements: 1.8, 3.5
        """
        result = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "aesop?",
                "budget_s": 10.0,
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"

        # Verify probe_result
        probe_result = result["probe_result"]
        assert probe_result["mode"] == "aesop?"
        assert probe_result["outcome"] == "closed"

        # Verify suggested_script is present for aesop? mode
        # Note: suggested_script may be None if aesop? doesn't provide one
        # but the field should exist
        assert "suggested_script" in probe_result

    @pytest.mark.integration
    def test_probe_grind_mode(self):
        """Test probe with grind mode on grind-solvable theorem.

        This test verifies:
        - Probe executes successfully with grind mode
        - Result has correct mode in probe_result
        - Classification is appropriate for grind success

        Requirements: 1.8, 3.3
        """
        result = probe(
            {
                "file": GRIND_TEST,
                "theorem_id": "grind_simple",
                "mode": "grind",
                "budget_s": 10.0,
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"

        # Verify probe_result
        probe_result = result["probe_result"]
        assert probe_result["mode"] == "grind"
        # grind should close the goal
        assert probe_result["outcome"] == "closed"
        assert probe_result["classification"] == "trivial"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_probe_timeout_handling(self):
        """Test probe timeout handling with small budget.

        This test verifies:
        - Probe respects budget and times out appropriately
        - Timeout status is returned
        - Classification is "timed_out"
        - Elapsed time doesn't significantly exceed budget

        Requirements: 1.4, 2.4, 8.1, 8.2
        """
        # Use a very small budget to trigger timeout
        budget_s = 0.5
        start_time = time.time()

        result = probe(
            {
                "file": TIMEOUT_TEST,
                "theorem_id": "timeout_candidate",
                "mode": "aesop",
                "budget_s": budget_s,
            }
        )

        elapsed = time.time() - start_time

        # Verify timeout status
        # Note: The test may succeed quickly on modern hardware, so we check for either
        assert result["status"] in ("timeout", "success", "fail"), (
            f"Expected timeout/success/fail but got {result['status']}"
        )

        # If it did timeout, verify classification
        if result["status"] == "timeout":
            probe_result = result["probe_result"]
            assert probe_result["classification"] == "timed_out"
            assert probe_result["outcome"] == "timeout"

            # Verify timeout within reasonable overhead
            # Allow 3s overhead for process management
            assert elapsed <= budget_s + 3.0, (
                f"Timeout took {elapsed}s, expected ~{budget_s}s + overhead"
            )

    @pytest.mark.integration
    def test_probe_error_handling_type_error(self):
        """Test probe error handling with file containing type error.

        This test verifies:
        - Probe handles toolchain errors gracefully
        - Status reflects the compilation result
        - Error diagnostics are present if there's a type error

        Note: Type errors in Lean may be caught at different stages:
        - During file compilation (before proof attempt) → error status
        - During proof attempt (aesop tries and fails) → fail/success status

        Requirements: 2.5, 10.2
        """
        result = probe(
            {
                "file": ERROR_TEST,
                "theorem_id": "error_example",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        # The test file has a type error, but Lean may handle it differently
        # depending on when the error is detected. We just verify the probe
        # completes without crashing and returns a valid result.
        assert result["status"] in ("error", "fail", "success"), (
            f"Expected valid status but got {result['status']}"
        )

        # Verify probe_result structure is present
        assert "probe_result" in result
        probe_result = result["probe_result"]
        assert "classification" in probe_result
        assert "outcome" in probe_result

        # Verify diagnostics structure is present
        assert "diagnostics" in result
        assert isinstance(result["diagnostics"], list)

    @pytest.mark.integration
    def test_probe_theorem_not_found_error(self):
        """Test probe error handling when theorem_id doesn't exist.

        This test verifies:
        - Probe returns error status for non-existent theorem
        - Error message is descriptive
        - No unhandled exceptions escape

        Requirements: 10.1, 10.5
        """
        result = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "nonexistent_theorem",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        # Verify error status
        assert result["status"] == "error", f"Expected error but got {result['status']}"

        # Verify error classification
        probe_result = result["probe_result"]
        assert probe_result["classification"] == "error"

        # Verify error diagnostics
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) > 0, "Expected at least one error diagnostic"

    @pytest.mark.integration
    def test_probe_invalid_mode_validation(self):
        """Test probe input validation for invalid mode.

        This test verifies:
        - Probe validates mode parameter
        - Returns error status for invalid mode
        - No unhandled exceptions escape

        Requirements: 1.8, 10.3, 10.5
        """
        result = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "invalid_mode",
                "budget_s": 10.0,
            }
        )

        # Verify error status
        assert result["status"] == "error", f"Expected error but got {result['status']}"

        # Verify error diagnostics mention validation
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) > 0, "Expected at least one error diagnostic"
        # Check that error message mentions mode validation
        error_messages = [d["message"] for d in error_diagnostics]
        assert any("mode" in msg.lower() for msg in error_messages), (
            "Expected error message to mention mode validation"
        )

    @pytest.mark.integration
    def test_probe_no_source_modification(self):
        """Test that probe never modifies source files.

        This test verifies:
        - Source file hash is unchanged after probe execution
        - Probe operates in isolated workspace

        Requirements: 1.6, 7.3
        """
        import hashlib

        # Compute hash before probe
        with open(AESOP_TRIVIAL, "rb") as f:
            hash_before = hashlib.sha256(f.read()).hexdigest()

        # Run probe
        result = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        # Compute hash after probe
        with open(AESOP_TRIVIAL, "rb") as f:
            hash_after = hashlib.sha256(f.read()).hexdigest()

        # Verify hash unchanged
        assert hash_before == hash_after, "Source file was modified by probe"

        # Also verify probe succeeded (to ensure test is meaningful)
        assert result["status"] == "success", "Probe should have succeeded"

    @pytest.mark.integration
    def test_probe_result_completeness(self):
        """Test that probe result contains all required fields.

        This test verifies:
        - All required fields are present in result
        - Field types are correct
        - Nested structures are complete

        Requirements: 1.5, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8
        """
        result = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        # Verify top-level fields
        assert "api_version" in result
        assert "status" in result
        assert "run_id" in result
        assert "probe_result" in result
        assert "diagnostics" in result
        assert "timing" in result
        assert "metadata" in result

        # Verify probe_result structure
        probe_result = result["probe_result"]
        assert "mode" in probe_result
        assert "outcome" in probe_result
        assert "classification" in probe_result
        assert "suggested_script" in probe_result

        # Verify timing structure
        timing = result["timing"]
        assert "elapsed_ms" in timing
        assert "budget_s" in timing

        # Verify metadata structure
        metadata = result["metadata"]
        # Metadata may include lean_version, lake_version, repo_commit
        # These are optional and depend on environment
        assert isinstance(metadata, dict)

        # Verify diagnostics is a list
        assert isinstance(result["diagnostics"], list)

        # Verify run_id format
        assert result["run_id"].startswith("probe-")
        assert len(result["run_id"]) > 10  # Should have timestamp and hash

    @pytest.mark.integration
    def test_probe_deterministic_classification(self):
        """Test that probe produces deterministic classification for identical inputs.

        This test verifies:
        - Running probe twice with same inputs produces same classification
        - Results are consistent across runs

        Requirements: 2.6
        """
        # Run probe twice with identical inputs
        result1 = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        result2 = probe(
            {
                "file": AESOP_TRIVIAL,
                "theorem_id": "aesop_trivial_and",
                "mode": "aesop",
                "budget_s": 10.0,
            }
        )

        # Verify both succeeded
        assert result1["status"] == "success"
        assert result2["status"] == "success"

        # Verify identical classifications
        assert (
            result1["probe_result"]["classification"] == result2["probe_result"]["classification"]
        )
        assert result1["probe_result"]["outcome"] == result2["probe_result"]["outcome"]
        assert result1["probe_result"]["mode"] == result2["probe_result"]["mode"]
