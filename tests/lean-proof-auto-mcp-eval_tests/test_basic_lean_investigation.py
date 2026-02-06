"""
Comprehensive investigation of MCP tools on Basic.lean theorems.

This test suite empirically investigates whether scoped notation issues
actually exist when using various MCP tools on real Lean code.

Target file: lean-proof-auto-mcp-eval/fixtures/mathlib/Fixtures/Algebra/Group/Subgroup/Basic.lean
Focus: Theorems with `open scoped X in` declarations, particularly `prod_mono`
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

# Mark all tests in this module as eval_investigation
pytestmark = pytest.mark.eval_investigation

# Path to the external eval repository
EVAL_REPO_PATH = Path.home() / "Sources" / "lean-proof-auto-mcp-eval"
BASIC_LEAN_PATH = (
    EVAL_REPO_PATH
    / "fixtures"
    / "mathlib"
    / "Fixtures"
    / "Algebra"
    / "Group"
    / "Subgroup"
    / "Basic.lean"
)

# Path to the MCP server script in current repo
MCP_SERVER_PATH = Path(__file__).parent.parent.parent / "src" / "lean_proof_auto_mcp" / "server.py"


class MCPClient:
    """Simple MCP client for testing."""

    def __init__(self, server_path: Path, working_dir: Path):
        self.server_path = server_path
        self.working_dir = working_dir
        self.process = None

    def __enter__(self):
        """Start the MCP server."""
        self.process = subprocess.Popen(
            ["python", str(self.server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.working_dir),
            text=True,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the MCP server."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool and return the result."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()

        # Read response
        response_line = self.process.stdout.readline()
        response = json.loads(response_line)

        return response


@pytest.fixture
def eval_repo_path():
    """Fixture providing path to eval repository."""
    if not EVAL_REPO_PATH.exists():
        pytest.skip(f"Eval repository not found at {EVAL_REPO_PATH}")
    return EVAL_REPO_PATH


@pytest.fixture
def basic_lean_path(eval_repo_path):
    """Fixture providing path to Basic.lean file."""
    if not BASIC_LEAN_PATH.exists():
        pytest.skip(f"Basic.lean not found at {BASIC_LEAN_PATH}")
    return BASIC_LEAN_PATH


@pytest.fixture
def mcp_client(eval_repo_path):
    """Fixture providing MCP client."""
    with MCPClient(MCP_SERVER_PATH, eval_repo_path) as client:
        yield client


# Theorems to test - focusing on those with scoped notation
THEOREMS_TO_TEST = [
    {
        "name": "Subgroup.prod_mono",
        "has_scoped_notation": True,
        "scoped_modules": ["Relator"],
        "description": "Theorem with 'open scoped Relator in' - the key test case",
    },
    {
        "name": "Subgroup.mem_prod",
        "has_scoped_notation": False,
        "scoped_modules": [],
        "description": "Theorem without scoped notation - control case",
    },
    {
        "name": "Subgroup.top_prod_top",
        "has_scoped_notation": False,
        "scoped_modules": [],
        "description": "Another theorem without scoped notation",
    },
    {
        "name": "Subgroup.bot_prod_bot",
        "has_scoped_notation": False,
        "scoped_modules": [],
        "description": "Another theorem without scoped notation",
    },
]


class TestVerifyTool:
    """Test the verify tool on Basic.lean theorems."""

    @pytest.mark.parametrize("theorem_info", THEOREMS_TO_TEST, ids=lambda t: t["name"])
    def test_verify_theorem(self, mcp_client, basic_lean_path, theorem_info, tmp_path):
        """Test verify tool on a specific theorem."""
        theorem_name = theorem_info["name"]
        print(f"\n{'='*80}")
        print(f"Testing VERIFY on: {theorem_name}")
        print(f"Description: {theorem_info['description']}")
        print(f"Has scoped notation: {theorem_info['has_scoped_notation']}")
        print(f"{'='*80}\n")

        # Call verify tool
        result = mcp_client.call_tool(
            "verify",
            {
                "file_path": str(basic_lean_path),
                "theorem_name": theorem_name,
                "tactic": "aesop",
            },
        )

        # Print detailed results
        print(f"\nRESULT for {theorem_name}:")
        print(json.dumps(result, indent=2))

        # Save results to file for later analysis
        output_file = tmp_path / f"verify_{theorem_name.replace('.', '_')}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {output_file}")

        # Basic assertions
        assert "result" in result or "error" in result, "Response should have result or error"

        if "result" in result:
            # Check if harness was generated
            if "harness" in result["result"]:
                harness = result["result"]["harness"]
                print(f"\nGENERATED HARNESS:\n{harness}\n")

                # Check for scoped notation preservation
                if theorem_info["has_scoped_notation"]:
                    for module in theorem_info["scoped_modules"]:
                        assert (
                            f"open scoped {module}" in harness
                        ), f"Scoped notation 'open scoped {module}' should be preserved in harness"
                        print(f"✓ Scoped notation 'open scoped {module}' found in harness")


class TestProbeTool:
    """Test the probe tool on Basic.lean theorems."""

    @pytest.mark.parametrize("theorem_info", THEOREMS_TO_TEST, ids=lambda t: t["name"])
    def test_probe_theorem(self, mcp_client, basic_lean_path, theorem_info, tmp_path):
        """Test probe tool on a specific theorem."""
        theorem_name = theorem_info["name"]
        print(f"\n{'='*80}")
        print(f"Testing PROBE on: {theorem_name}")
        print(f"Description: {theorem_info['description']}")
        print(f"Has scoped notation: {theorem_info['has_scoped_notation']}")
        print(f"{'='*80}\n")

        # Call probe tool
        result = mcp_client.call_tool(
            "probe",
            {
                "file_path": str(basic_lean_path),
                "theorem_name": theorem_name,
            },
        )

        # Print detailed results
        print(f"\nRESULT for {theorem_name}:")
        print(json.dumps(result, indent=2))

        # Save results to file for later analysis
        output_file = tmp_path / f"probe_{theorem_name.replace('.', '_')}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {output_file}")

        # Basic assertions
        assert "result" in result or "error" in result, "Response should have result or error"

        if "result" in result:
            # Check if harness was generated
            if "harness" in result["result"]:
                harness = result["result"]["harness"]
                print(f"\nGENERATED HARNESS:\n{harness}\n")

                # Check for scoped notation preservation
                if theorem_info["has_scoped_notation"]:
                    for module in theorem_info["scoped_modules"]:
                        assert (
                            f"open scoped {module}" in harness
                        ), f"Scoped notation 'open scoped {module}' should be preserved in harness"
                        print(f"✓ Scoped notation 'open scoped {module}' found in harness")


class TestProbeFileTool:
    """Test the probe_file tool on Basic.lean."""

    def test_probe_file_basic_lean(self, mcp_client, basic_lean_path, tmp_path):
        """Test probe_file tool on entire Basic.lean file."""
        print(f"\n{'='*80}")
        print(f"Testing PROBE_FILE on: {basic_lean_path}")
        print(f"{'='*80}\n")

        # Call probe_file tool
        result = mcp_client.call_tool(
            "probe_file",
            {
                "file_path": str(basic_lean_path),
            },
        )

        # Print detailed results
        print(f"\nRESULT:")
        print(json.dumps(result, indent=2))

        # Save results to file for later analysis
        output_file = tmp_path / "probe_file_basic_lean.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {output_file}")

        # Basic assertions
        assert "result" in result or "error" in result, "Response should have result or error"

        if "result" in result and "theorems" in result["result"]:
            theorems = result["result"]["theorems"]
            print(f"\nFound {len(theorems)} theorems")

            # Check if prod_mono is in the results
            prod_mono_results = [t for t in theorems if "prod_mono" in t.get("name", "")]
            if prod_mono_results:
                print(f"\nFound prod_mono results: {len(prod_mono_results)}")
                for theorem in prod_mono_results:
                    print(f"\nTheorem: {theorem.get('name')}")
                    if "harness" in theorem:
                        harness = theorem["harness"]
                        print(f"Harness preview (first 500 chars):\n{harness[:500]}\n")

                        # Check for scoped notation
                        if "open scoped Relator" in harness:
                            print("✓ Scoped notation 'open scoped Relator' found in harness")
                        else:
                            print("✗ Scoped notation 'open scoped Relator' NOT found in harness")


class TestTryAutomatedProofTool:
    """Test the try_automated_proof tool on Basic.lean theorems."""

    @pytest.mark.parametrize("theorem_info", THEOREMS_TO_TEST[:2], ids=lambda t: t["name"])
    def test_try_automated_proof(self, mcp_client, basic_lean_path, theorem_info, tmp_path):
        """Test try_automated_proof tool on a specific theorem."""
        theorem_name = theorem_info["name"]
        print(f"\n{'='*80}")
        print(f"Testing TRY_AUTOMATED_PROOF on: {theorem_name}")
        print(f"Description: {theorem_info['description']}")
        print(f"Has scoped notation: {theorem_info['has_scoped_notation']}")
        print(f"{'='*80}\n")

        # Call try_automated_proof tool
        result = mcp_client.call_tool(
            "try_automated_proof",
            {
                "file_path": str(basic_lean_path),
                "theorem_name": theorem_name,
            },
        )

        # Print detailed results
        print(f"\nRESULT for {theorem_name}:")
        print(json.dumps(result, indent=2))

        # Save results to file for later analysis
        output_file = tmp_path / f"try_automated_proof_{theorem_name.replace('.', '_')}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {output_file}")

        # Basic assertions
        assert "result" in result or "error" in result, "Response should have result or error"


class TestSearchAutomatedProofTool:
    """Test the search_automated_proof tool on Basic.lean theorems."""

    @pytest.mark.parametrize("theorem_info", THEOREMS_TO_TEST[:2], ids=lambda t: t["name"])
    def test_search_automated_proof(self, mcp_client, basic_lean_path, theorem_info, tmp_path):
        """Test search_automated_proof tool on a specific theorem."""
        theorem_name = theorem_info["name"]
        print(f"\n{'='*80}")
        print(f"Testing SEARCH_AUTOMATED_PROOF on: {theorem_name}")
        print(f"Description: {theorem_info['description']}")
        print(f"Has scoped notation: {theorem_info['has_scoped_notation']}")
        print(f"{'='*80}\n")

        # Call search_automated_proof tool
        result = mcp_client.call_tool(
            "search_automated_proof",
            {
                "file_path": str(basic_lean_path),
                "theorem_name": theorem_name,
            },
        )

        # Print detailed results
        print(f"\nRESULT for {theorem_name}:")
        print(json.dumps(result, indent=2))

        # Save results to file for later analysis
        output_file = tmp_path / f"search_automated_proof_{theorem_name.replace('.', '_')}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {output_file}")

        # Basic assertions
        assert "result" in result or "error" in result, "Response should have result or error"


class TestHarnessGeneration:
    """Direct tests of harness generation logic."""

    def test_harness_preserves_scoped_notation_direct(self, basic_lean_path, tmp_path):
        """
        Direct test of harness construction without going through MCP.

        This tests the core harness construction logic directly to see
        if scoped notation is preserved.
        """
        print(f"\n{'='*80}")
        print("Testing DIRECT HARNESS CONSTRUCTION")
        print(f"{'='*80}\n")

        # Import the harness constructor
        from lean_proof_auto_mcp.core.harness_construction import LeanHarnessConstructor

        # Read the Basic.lean file
        with open(basic_lean_path) as f:
            content = f.read()

        # Create harness constructor
        constructor = LeanHarnessConstructor()

        # Test on prod_mono theorem
        theorem_name = "prod_mono"
        print(f"Constructing harness for: {theorem_name}")

        try:
            harness = constructor.construct_harness(content, theorem_name)
            print(f"\nGENERATED HARNESS:\n{harness}\n")

            # Save harness to file
            output_file = tmp_path / f"direct_harness_{theorem_name}.lean"
            with open(output_file, "w") as f:
                f.write(harness)
            print(f"Harness saved to: {output_file}")

            # Check for scoped notation
            if "open scoped Relator" in harness:
                print("✓ Scoped notation 'open scoped Relator' found in harness")
            else:
                print("✗ Scoped notation 'open scoped Relator' NOT found in harness")
                print("\nSearching for 'Relator' in harness:")
                for i, line in enumerate(harness.split("\n"), 1):
                    if "Relator" in line or "relator" in line.lower():
                        print(f"  Line {i}: {line}")

            # Check for the theorem itself
            if "theorem prod_mono" in harness or "prod_mono" in harness:
                print("✓ Theorem 'prod_mono' found in harness")
            else:
                print("✗ Theorem 'prod_mono' NOT found in harness")

            # Assertions
            assert "open scoped Relator" in harness, (
                "Scoped notation should be preserved in harness"
            )

        except Exception as e:
            print(f"Error constructing harness: {e}")
            import traceback

            traceback.print_exc()
            raise


# Summary test that runs at the end
class TestSummary:
    """Generate a summary of all findings."""

    def test_generate_summary(self, tmp_path):
        """Generate a summary report of all test results."""
        print(f"\n{'='*80}")
        print("INVESTIGATION SUMMARY")
        print(f"{'='*80}\n")

        # This test should run last and summarize findings
        print("All tests completed. Check the output files in:")
        print(f"  {tmp_path}")
        print("\nKey findings:")
        print("1. Check if scoped notation is preserved in verify tool")
        print("2. Check if scoped notation is preserved in probe tool")
        print("3. Check if scoped notation is preserved in probe_file tool")
        print("4. Check if scoped notation is preserved in direct harness construction")
        print("\nIf all tests pass, the scoped notation issue may not exist.")
        print("If tests fail, we have empirical evidence of the issue.")
