# Eval Investigation Tests

This directory contains tests for investigating potential issues with the MCP server tools when working with real Lean code from the `lean-proof-auto-mcp-eval` repository.

## Purpose

These tests are designed to:
1. Empirically verify whether reported issues actually exist
2. Test all MCP tools (verify, probe, probe_file, try_automated_proof, search_automated_proof) on real Lean code
3. Generate detailed output for analysis
4. Provide evidence for or against implementing fixes

## Key Characteristics

- **Excluded from CI/CD**: These tests are marked with `@pytest.mark.eval_investigation` and are excluded from CI/CD pipelines
- **Manual execution only**: Run these tests manually when investigating issues
- **Requires external repository**: Tests require the `lean-proof-auto-mcp-eval` repository to be cloned at `~/Sources/lean-proof-auto-mcp-eval`
- **Requires Lean 4**: Tests require a working Lean 4 installation

## Running the Tests

### Run all eval investigation tests:
```bash
pytest tests/lean-proof-auto-mcp-eval_tests/ -v -s
```

### Run specific test class:
```bash
pytest tests/lean-proof-auto-mcp-eval_tests/test_basic_lean_investigation.py::TestVerifyTool -v -s
```

### Run specific test:
```bash
pytest tests/lean-proof-auto-mcp-eval_tests/test_basic_lean_investigation.py::TestVerifyTool::test_verify_theorem -v -s
```

## Test Structure

### `test_basic_lean_investigation.py`

Comprehensive investigation of MCP tools on `Basic.lean` theorems, focusing on:
- **Scoped notation preservation**: Does `open scoped X in` get preserved in generated harnesses?
- **Tool behavior**: How do different tools handle the same theorem?
- **Edge cases**: Theorems with and without scoped notation

#### Test Classes:
1. **TestVerifyTool**: Tests the `verify` tool
2. **TestProbeTool**: Tests the `probe` tool
3. **TestProbeFileTool**: Tests the `probe_file` tool
4. **TestTryAutomatedProofTool**: Tests the `try_automated_proof` tool
5. **TestSearchAutomatedProofTool**: Tests the `search_automated_proof` tool
6. **TestHarnessGeneration**: Direct tests of harness construction logic
7. **TestSummary**: Generates a summary report

#### Target Theorems:
- `Subgroup.prod_mono` - Has `open scoped Relator in` (key test case)
- `Subgroup.mem_prod` - No scoped notation (control case)
- `Subgroup.top_prod_top` - No scoped notation
- `Subgroup.bot_prod_bot` - No scoped notation

## Output

Tests generate detailed JSON output files in the pytest `tmp_path` directory, including:
- Tool responses
- Generated harnesses
- Error messages
- Diagnostic information

Check the test output for the location of these files.

## Current Investigation

**Issue**: Scoped notation harness fix spec
**Question**: Does the import-based harness construction actually fail to preserve `open scoped X in` declarations?
**Approach**: Run all tools on theorems with and without scoped notation to gather empirical evidence

## Adding New Tests

When adding new investigation tests:
1. Mark them with `@pytest.mark.eval_investigation`
2. Add detailed print statements for analysis
3. Save results to files for later review
4. Document what you're investigating in the test docstring
