"""Integration tests for probe and probe_file MCP tool registration.

Tests that probe and probe_file tools are properly registered with the MCP server
and can be called through the router interface.

Requirements: 1.1, 4.1
"""

import pytest

from lean_proof_auto_mcp.adapters.router import ToolRouter
from lean_proof_auto_mcp.tools.probe import probe
from lean_proof_auto_mcp.tools.probe_file import probe_file


class TestProbeMCPRegistration:
    """Integration tests for probe tool MCP registration."""

    @pytest.mark.integration
    def test_probe_tool_is_registered_and_callable(self):
        """Test that probe tool is registered with router and returns valid JSON.

        Requirements: 1.1
        """
        # Create router and register probe
        router = ToolRouter()
        router.register("probe", probe)

        # Verify probe is registered
        assert "probe" in router.handlers, "probe tool should be registered"

        # Test calling probe with invalid inputs (should return error response)
        result = router.dispatch(
            "probe",
            {
                "file": "",  # Invalid: empty file
                "theorem_id": "test",
                "mode": "aesop",
            },
        )

        # Verify returns valid JSON response
        assert isinstance(result, dict), "probe should return dict"
        assert "api_version" in result, "probe result should have api_version"
        assert "status" in result, "probe result should have status"
        assert result["status"] == "error", "probe should return error for invalid input"

    @pytest.mark.integration
    def test_probe_file_tool_is_registered_and_callable(self):
        """Test that probe_file tool is registered with router and returns valid JSON.

        Requirements: 4.1
        """
        # Create router and register probe_file
        router = ToolRouter()
        router.register("probe_file", probe_file)

        # Verify probe_file is registered
        assert "probe_file" in router.handlers, "probe_file tool should be registered"

        # Test calling probe_file with invalid inputs (should return error response)
        result = router.dispatch(
            "probe_file",
            {
                "file": "",  # Invalid: empty file
                "mode": "aesop",
            },
        )

        # Verify returns valid JSON response
        assert isinstance(result, dict), "probe_file should return dict"
        assert "api_version" in result, "probe_file result should have api_version"
        assert "status" in result, "probe_file result should have status"
        assert result["status"] == "error", "probe_file should return error for invalid input"

    @pytest.mark.integration
    def test_probe_returns_valid_json_structure(self):
        """Test that probe returns valid JSON structure with all required fields.

        Requirements: 1.1
        """
        # Test with invalid inputs to get error response (faster than real execution)
        result = probe(
            {
                "file": "nonexistent.lean",
                "theorem_id": "test_theorem",
                "mode": "aesop",
                "budget_s": 1.0,
            }
        )

        # Verify all required fields are present
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

    @pytest.mark.integration
    def test_probe_file_returns_valid_json_structure(self):
        """Test that probe_file returns valid JSON structure with all required fields.

        Requirements: 4.1
        """
        # Test with invalid inputs to get error response (faster than real execution)
        result = probe_file(
            {
                "file": "nonexistent.lean",
                "mode": "aesop",
                "budget_s_per": 1.0,
                "limit": 10,
                "ordering": "file_order",
            }
        )

        # Verify all required fields are present
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

        # Verify results is a list
        assert isinstance(result["results"], list)
