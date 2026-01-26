"""Integration tests for verify tool.

Tests end-to-end functionality with real Lean files. These tests verify
the tool's behavior with actual Lean compilation.

NOTE: These tests require LeanInteract library and a Lean 4 installation.
They are marked with @pytest.mark.integration and can be skipped with:
    pytest -m "not integration"

Slow tests are additionally marked with @pytest.mark.slow.
"""

import time
from pathlib import Path

import pytest

from lean_proof_auto_mcp.tools.verify import verify

# Check if LeanInteract is available
try:
    import lean_interact  # noqa: F401

    LEAN_INTERACT_AVAILABLE = True
except ImportError:
    LEAN_INTERACT_AVAILABLE = False

# Fixture paths
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "lean"
VALID_THEOREM = str(FIXTURES_DIR / "valid_theorem.lean")
TYPE_ERROR = str(FIXTURES_DIR / "type_error.lean")
SORRY_PROOF = str(FIXTURES_DIR / "sorry_proof.lean")
SLOW_VERIFICATION = str(FIXTURES_DIR / "slow_verification.lean")

# Skip all tests if LeanInteract is not available
pytestmark = [
    pytest.mark.skipif(
        not LEAN_INTERACT_AVAILABLE,
        reason="LeanInteract library not installed. Install with: pip install lean-interact",
    ),
    pytest.mark.requires_lean,  # Mark all tests in this file as requiring Lean
]


class TestVerifyIntegration:
    """Integration tests for verify tool with real Lean files."""

    @pytest.mark.integration
    def test_valid_theorem_verification(self):
        """Test verification of valid theorem with no errors.

        Requirements: 1.1
        """
        result = verify(
            {
                "file": VALID_THEOREM,
                "budget_s": 30.0,
                "workspace_mode": "temp",  # Use temp mode to avoid creating worktrees in dev repo
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"
        assert result["api_version"] == "0.2.0"

        # Verify no error diagnostics
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) == 0, f"Expected no errors but found: {error_diagnostics}"

        # Verify diagnostic summary
        assert result["diagnostic_summary"]["error_count"] == 0

        # Verify file field
        assert result["file"] == VALID_THEOREM

        # Verify run_id exists
        assert "run_id" in result
        assert result["run_id"].startswith("verify-")

    @pytest.mark.integration
    def test_type_error_verification(self):
        """Test verification of file with type error.

        Requirements: 1.1, 1.4
        """
        result = verify(
            {
                "file": TYPE_ERROR,
                "budget_s": 30.0,
                "workspace_mode": "temp",  # Use temp mode to avoid creating worktrees in dev repo
            }
        )

        # Verify fail status
        assert result["status"] == "fail", f"Expected fail but got {result['status']}"
        assert result["api_version"] == "0.2.0"

        # Verify error diagnostic is present
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) > 0, "Expected at least one error diagnostic"

        # Verify diagnostic summary
        assert result["diagnostic_summary"]["error_count"] > 0

        # Verify diagnostic structure
        for diag in error_diagnostics:
            assert "severity" in diag
            assert "message" in diag
            assert "location" in diag
            assert "file" in diag["location"]
            assert "line" in diag["location"]
            assert "col" in diag["location"]

        # Verify file field
        assert result["file"] == TYPE_ERROR

    @pytest.mark.integration
    def test_sorry_proof_verification(self):
        """Test verification of file with incomplete proof (sorry).

        Requirements: 1.1, 1.4
        """
        result = verify(
            {
                "file": SORRY_PROOF,
                "budget_s": 30.0,
                "workspace_mode": "temp",  # Use temp mode to avoid creating worktrees in dev repo
            }
        )

        # Verify success status (sorry is a warning, not an error)
        assert result["status"] == "success", f"Expected success but got {result['status']}"
        assert result["api_version"] == "0.2.0"

        # Verify warning diagnostic is present
        warning_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "warning"]
        assert len(warning_diagnostics) > 0, "Expected at least one warning diagnostic for sorry"

        # Verify no error diagnostics
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) == 0, f"Expected no errors but found: {error_diagnostics}"

        # Verify diagnostic summary
        assert result["diagnostic_summary"]["error_count"] == 0
        assert result["diagnostic_summary"]["warning_count"] > 0

        # Verify file field
        assert result["file"] == SORRY_PROOF

    @pytest.mark.integration
    @pytest.mark.slow
    def test_timeout_verification(self):
        """Test verification timeout with slow file and small budget.

        Requirements: 1.3, 4.2, 4.3
        """
        # Use a very small budget to trigger timeout
        budget_s = 0.5
        start_time = time.time()

        result = verify(
            {
                "file": SLOW_VERIFICATION,
                "budget_s": budget_s,
                "workspace_mode": "temp",  # Use temp mode to avoid creating worktrees in dev repo
            }
        )

        elapsed = time.time() - start_time

        # Verify timeout status
        assert result["status"] == "timeout", f"Expected timeout but got {result['status']}"
        assert result["api_version"] == "0.2.0"

        # Verify timeout within reasonable overhead
        # Note: lean_interact has significant process management overhead (~2s)
        # Allow 3s total overhead for process startup/shutdown
        assert elapsed <= budget_s + 3.0, (
            f"Timeout took {elapsed}s, expected ~{budget_s}s + overhead"
        )

        # Verify timing information
        assert "timing" in result
        assert "lean_execution_s" in result["timing"]

        # Verify file field
        assert result["file"] == SLOW_VERIFICATION

    @pytest.mark.integration
    def test_theorem_level_verification(self):
        """Test verification of specific theorem by theorem_id.

        Requirements: 2.1, 2.2
        """
        # Use a theorem_id from the valid_theorem file
        # The theorem_id format should match scan_file output
        result = verify(
            {
                "file": VALID_THEOREM,
                "theorem_id": "simple_add_comm",
                "budget_s": 30.0,
                "workspace_mode": "temp",  # Use temp mode to avoid creating worktrees in dev repo
            }
        )

        # Verify success status
        assert result["status"] == "success", f"Expected success but got {result['status']}"
        assert result["api_version"] == "0.2.0"

        # Verify theorem scope was used
        assert result["verification_scope_used"] == "theorem", (
            f"Expected theorem scope but got {result['verification_scope_used']}"
        )

        # Verify theorem_id is in response
        assert result["theorem_id"] == "simple_add_comm"

        # Verify no error diagnostics
        error_diagnostics = [d for d in result["diagnostics"] if d["severity"] == "error"]
        assert len(error_diagnostics) == 0, f"Expected no errors but found: {error_diagnostics}"

        # Verify file field
        assert result["file"] == VALID_THEOREM
