# Integration Tests

This directory contains integration tests for the lean-proof-auto-mcp system.

## Test Files

### test_end_to_end_workflow.py

Comprehensive end-to-end integration tests for the complete proof refactoring workflow.

**Test Classes:**

- `TestCompleteWorkflow`: Tests the complete search → validate → iterate cycle
  - `test_search_validate_iterate_cycle`: Tests all three MCP tools working together
  - `test_iterative_refinement_workflow`: Tests multiple search iterations with refinement
  - `test_validation_failure_feedback_loop`: Tests feedback loop when validation fails

- `TestRealMathlibTheorems`: Tests on real mathlib theorems (skipped by default)
  - `test_mathlib_theorem_workflow`: Full workflow on mathlib files

- `TestToolInteraction`: Tests interaction between MCP tools
  - `test_context_informs_search`: Tests that context extraction informs search parameters
  - `test_search_feedback_guides_validation`: Tests that search feedback guides validation

**Requirements Validated:** 27.3

**Running Tests:**
```bash
# Run all end-to-end tests
uv run pytest tests/integration/test_end_to_end_workflow.py -v

# Run specific test
uv run pytest tests/integration/test_end_to_end_workflow.py::TestCompleteWorkflow::test_search_validate_iterate_cycle -v

# Run with markers
uv run pytest tests/integration/test_end_to_end_workflow.py -m e2e -v
```

### Other Integration Tests

- `test_adapter_layer_integration.py`: Tests LeanInteract adapter layer with real Lean files
- `test_mcp_tools_integration.py`: Tests MCP tool registration and execution
- `test_original_proof_refs_accuracy.py`: Tests accuracy of proof reference extraction
- `test_probe_integration.py`: Tests probe tool integration
- `test_probe_file_integration.py`: Tests probe_file tool integration
- `test_verify_integration.py`: Tests verify tool integration
- `test_search_automated_proof_e2e.py`: Tests search_automated_proof tool end-to-end

## Test Markers

- `@pytest.mark.e2e`: End-to-end tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow tests (may take several seconds)
- `@pytest.mark.requires_lean`: Tests that require Lean installation

## Test Fixtures

Test fixtures are located in `tests/fixtures/`:
- `lean/`: Lean test files
- `mathlib_lean_files/`: Mathlib-style test files
- `benchmark_ground_truth.py`: Ground truth data for benchmark tests
