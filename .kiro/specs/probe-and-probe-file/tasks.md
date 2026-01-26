# Implementation Plan: Probe and Probe_File Tools

## Overview

This implementation plan breaks down the probe and probe_file tools into discrete coding tasks. The tools extend verify's execution infrastructure into empirical measurement of automation behavior, following hexagonal architecture with dependency injection, command pattern, and result/either pattern.

The implementation reuses verify's infrastructure (LeanInteractRunner, WorkspaceProvider) and adds new components for automation classification and batch processing.

## Tasks

- [x] 1. Set up core domain structures for probe
  - Create `src/lean_proof_auto_mcp/core/probe_domain.py` with immutable command and result types
  - Define ProbeCommand dataclass with file_path, theorem_id, mode, budget_s, trace_config
  - Define ProbeResult dataclass with api_version, status, run_id, probe_result, diagnostics, timing, metadata
  - Define ProbeOutcome dataclass with mode, outcome, classification, suggested_script
  - Define AutomationClassifier port interface (Protocol)
  - Add validation in `__post_init__` methods for all commands
  - _Requirements: 1.1, 1.8, 2.1-2.6, 3.1-3.8_

- [x] 1.1 Write property tests for probe domain structures
  - **Property 7: Mode Validation** - Test mode validation accepts valid modes and rejects invalid ones
  - **Property 28: Invalid Input Handling** - Test validation errors for invalid inputs
  - **Validates: Requirements 1.8, 3.1, 10.3, 10.5**

- [x] 2. Implement automation classifier
  - [x] 2.1 Create `src/lean_proof_auto_mcp/core/probe_classifier.py` with HeuristicClassifier
    - Implement classify method with deterministic rules
    - Add trivial classification (< 20% budget)
    - Add promising classification (shallow subgoals ≤ 3 levels)
    - Add failed classification (deep subgoals > 3 levels)
    - Add timeout and error classifications
    - Implement `_estimate_subgoal_depth` helper
    - _Requirements: 2.1-2.6_

  - [x] 2.2 Write unit tests for classifier
    - Test trivial classification with quick success examples
    - Test promising classification with shallow subgoal examples
    - Test failed classification with deep subgoal examples
    - Test timeout classification
    - Test error classification
    - Test boundary cases (exactly 20% budget, exactly 3 levels)
    - _Requirements: 2.1-2.6_

  - [x] 2.3 Write property tests for classifier
    - **Property 8: Trivial Classification** - Test quick success → trivial
    - **Property 9: Promising Classification** - Test shallow subgoals → promising
    - **Property 10: Failed Classification** - Test deep subgoals → failed
    - **Property 11: Timeout Classification** - Test budget exhausted → timed_out
    - **Property 12: Error Classification** - Test toolchain error → error
    - **Property 13: Deterministic Classification** - Test identical inputs → identical outputs
    - **Validates: Requirements 2.1-2.6**

- [x] 3. Implement probe command handler
  - [x] 3.1 Create ProbeCommandHandler in `src/lean_proof_auto_mcp/core/probe_domain.py`
    - Implement `__init__` with dependency injection (lean_runner, workspace_provider, classifier)
    - Implement `handle` method orchestrating probe workflow
    - Add `_generate_run_id` method (format: probe-YYYYMMDD-HHMMSS-<hash>-<random>)
    - Add `_construct_harness` method to build automation test harness (import file, theorem signature, automation tactic)
    - Add `_build_result` method to construct ProbeResult with all required fields
    - Add `_build_error_result` method for error cases (validation, theorem not found, toolchain, workspace)
    - Add `_build_timeout_result` method for timeout cases
    - Ensure workspace cleanup in finally block (always runs, errors logged but not propagated)
    - Implement error handling strategy from design (validation → workspace → execution → classification)
    - _Requirements: 1.1-1.6, 3.2-3.8, 6.1-6.4, 7.1-7.4, 8.1-8.2, 10.1-10.5_

  - [x] 3.2 Write unit tests for probe handler
    - Test successful probe execution with mocked dependencies
    - Test workspace creation and cleanup
    - Test harness construction for different modes
    - Test error handling for theorem not found
    - Test error handling for workspace failures
    - Test error handling for toolchain failures
    - Test timeout handling
    - Test run_id generation uniqueness
    - _Requirements: 1.1-1.6, 7.1-7.4, 10.1-10.5_

  - [x] 3.3 Write property tests for probe handler
    - **Property 1: Workspace Isolation** - Test workspace creation and cleanup
    - **Property 2: Harness Structure Validity** - Test harness has correct structure
    - **Property 3: Infrastructure Reuse** - Test uses same runner as verify
    - **Property 4: Hard Timeout Enforcement** - Test timeout terminates within budget
    - **Property 5: Result Completeness** - Test result has all required fields
    - **Property 6: No Source Modification** - Test source file hash unchanged
    - **Property 24: No External Filesystem Mutation** - Test no files outside workspace modified
    - **Property 25: Stateless Execution** - Test consecutive runs are independent
    - **Validates: Requirements 1.1-1.6, 3.2-3.8, 6.1-6.4, 7.1-7.4, 8.1-8.2**

- [ ] 4. Checkpoint - Ensure probe handler tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement MCP tool entry point for probe
  - [x] 5.1 Create `src/lean_proof_auto_mcp/tools/probe.py`
    - Implement `probe(args: dict) -> dict` function
    - Add `_coerce_args` for argument validation and coercion
    - Add `_build_command` to construct ProbeCommand from args
    - Add `_create_handler` composition root (wire dependencies)
    - Add `_build_error_response` for validation errors
    - Handle all exceptions and return error responses
    - _Requirements: 1.1, 3.1-3.8, 10.1-10.3, 10.5_

  - [x] 5.2 Write unit tests for probe tool entry point
    - Test valid inputs are accepted
    - Test invalid inputs return error responses
    - Test theorem not found returns error
    - Test toolchain errors are handled
    - Test no unhandled exceptions escape
    - _Requirements: 10.1-10.3, 10.5_

- [x] 6. Implement probe_file domain structures
  - Create ProbeFileCommand dataclass with file_path, mode, budget_s_per, limit, ordering
  - Create ProbeFileResult dataclass with api_version, status, file, summary, results, metadata
  - Add validation for ordering modes (file_order, rank_targets)
  - Add validation for limit and budget_s_per (must be positive)
  - Add validation for mode (aesop, aesop?, grind)
  - _Requirements: 4.1-4.7, 5.1-5.6_

- [x] 6.1 Write property tests for probe_file domain structures
  - **Property 22: Ordering Mode Support** - Test ordering mode validation
  - **Property 23: Limit Enforcement** - Test limit validation
  - **Validates: Requirements 5.1, 5.5, 5.6**

- [x] 7. Implement probe_file command handler
  - [x] 7.1 Create ProbeFileCommandHandler in `src/lean_proof_auto_mcp/core/probe_domain.py`
    - Implement `__init__` with dependency injection (probe_handler, scan_file_fn, rank_targets_fn)
    - Implement `handle` method orchestrating batch probe workflow
    - Add `_enumerate_theorems` method using scan_file and optionally rank_targets (stable ordering)
    - Add `_aggregate_results` method to build summary statistics (total, closed, promising, failed, timed_out)
    - Add `_build_result` method to construct ProbeFileResult with per-theorem and file-level stats
    - Add `_build_error_result` method for scan_file failures
    - Add `_extract_summary` method to extract summary from individual probe results
    - Implement partial success handling (collect errors but continue processing remaining theorems)
    - Determine status: error if no results, partial if some errors, success if no errors
    - _Requirements: 4.1-4.7, 5.2-5.6, 10.4_

  - [x] 7.2 Write unit tests for probe_file handler
    - Test successful batch probing with mocked dependencies
    - Test theorem enumeration with file_order
    - Test theorem enumeration with rank_targets
    - Test limit enforcement
    - Test summary aggregation
    - Test partial success handling (some theorems fail)
    - Test scan_file failure handling
    - Test empty file handling
    - _Requirements: 4.1-4.7, 5.2-5.6, 10.4_

  - [x] 7.3 Write property tests for probe_file handler
    - **Property 15: Scan_File Integration** - Test calls scan_file and uses output
    - **Property 16: Batch Probe Invocation** - Test calls probe for each theorem
    - **Property 17: Per-Theorem Budget Isolation** - Test each theorem gets own budget
    - **Property 18: Summary Aggregation Correctness** - Test summary matches individual results
    - **Property 19: Probe_File Result Completeness** - Test result has all required fields
    - **Property 20: Partial Success Handling** - Test continues on errors
    - **Property 21: Deterministic Result Ordering** - Test results in same order
    - **Validates: Requirements 4.1-4.7, 5.2-5.6**

- [ ] 8. Checkpoint - Ensure probe_file handler tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement MCP tool entry point for probe_file
  - [x] 9.1 Create `src/lean_proof_auto_mcp/tools/probe_file.py`
    - Implement `probe_file(args: dict) -> dict` function
    - Add `_coerce_args` for argument validation and coercion
    - Add `_build_command` to construct ProbeFileCommand from args
    - Add `_create_handler` composition root (wire dependencies)
    - Add `_build_error_response` for validation errors
    - Handle all exceptions and return error responses
    - _Requirements: 5.1-5.6, 10.4-10.5_

  - [x] 9.2 Write unit tests for probe_file tool entry point
    - Test valid inputs are accepted
    - Test invalid inputs return error responses
    - Test scan_file failures are handled
    - Test partial success scenarios
    - Test no unhandled exceptions escape
    - _Requirements: 10.4-10.5_

- [x] 10. Implement diagnostic normalization and sorting
  - [x] 10.1 Add diagnostic utilities to probe_domain.py
    - Implement `_normalize_diagnostics` method (reuse from verify)
    - Implement `_sort_diagnostics` method (reuse from verify)
    - Implement `_normalize_severity` method (reuse from verify)
    - _Requirements: 9.1-9.3_

  - [x] 10.2 Write property tests for diagnostic handling
    - **Property 26: Diagnostic Ordering** - Test diagnostics sorted correctly
    - **Property 27: Severity Normalization** - Test severity values normalized
    - **Validates: Requirements 9.1, 9.3**

- [x] 11. Implement aesop? suggested script extraction
  - [x] 11.1 Add script extraction logic to ProbeCommandHandler
    - Parse aesop? output for suggested script
    - Extract script from LeanInteract response
    - Include in ProbeOutcome when mode="aesop?" and successful
    - _Requirements: 3.5_

  - [x] 11.2 Write property tests for suggested script
    - **Property 14: Aesop? Suggested Script** - Test aesop? success includes script
    - **Validates: Requirements 3.5**

- [x] 12. Register probe tools with MCP server
  - [x] 12.1 Update `src/lean_proof_auto_mcp/server.py`
    - Import probe and probe_file functions
    - Register probe tool with MCP server
    - Register probe_file tool with MCP server
    - Add tool descriptions and schemas
    - _Requirements: 1.1, 4.1_

  - [x] 12.2 Write integration tests for MCP registration
    - Test probe tool is registered and callable
    - Test probe_file tool is registered and callable
    - Test tools return valid JSON responses
    - _Requirements: 1.1, 4.1_

- [x] 13. Create JSON schemas for probe tools
  - Create `docs/mcp/schemas/probe.json` with input/output schemas
    - Input: api_version, scope (file, theorem_id), mode, budget_s, runner configuration
    - Output: api_version, status, run_id, probe_result, diagnostics, timing, metadata
  - Create `docs/mcp/schemas/probe_file.json` with input/output schemas
    - Input: api_version, file, mode, budget_s_per, limit, ordering
    - Output: api_version, status, file, summary, results, metadata
  - Ensure schemas match design document specifications
  - _Requirements: 3.1-3.8, 5.1-5.6_

- [x] 14. Final checkpoint - End-to-end integration tests
  - [x] 14.1 Write end-to-end tests for probe
    - Test probe on real Lean file with aesop mode
    - Test probe on real Lean file with aesop? mode
    - Test probe on real Lean file with grind mode
    - Test probe timeout handling
    - Test probe error handling
    - _Requirements: 1.1-1.8, 2.1-2.6, 3.1-3.8_

  - [x] 14.2 Write end-to-end tests for probe_file
    - Test probe_file with file_order ordering
    - Test probe_file with rank_targets ordering
    - Test probe_file with limit parameter
    - Test probe_file partial success
    - _Requirements: 4.1-4.7, 5.1-5.6_

- [x] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- The implementation reuses verify's infrastructure (LeanInteractRunner, WorkspaceProvider) for consistency
- All code follows hexagonal architecture with dependency injection and command pattern

### Test Organization

Tests should be organized as follows:
```
tests/
├── unit/
│   ├── test_probe_command.py          # Command validation (Task 1.1)
│   ├── test_probe_handler.py          # Handler logic (Task 3.2)
│   ├── test_classifier.py             # Classification logic (Task 2.2)
│   ├── test_probe_file_handler.py     # Batch handler logic (Task 7.2)
│   └── test_error_handling.py         # Error scenarios (Tasks 5.2, 9.2)
├── property/
│   ├── test_probe_properties.py       # Properties 1-14, 24-28 (Tasks 1.1, 2.3, 3.3, 10.2, 11.2)
│   └── test_probe_file_properties.py  # Properties 15-23 (Tasks 6.1, 7.3)
└── integration/
    ├── test_probe_integration.py      # End-to-end probe tests (Task 14.1)
    └── test_probe_file_integration.py # End-to-end probe_file tests (Task 14.2)
```

### Coverage Goals

- **Line Coverage**: Minimum 90% for core domain logic
- **Branch Coverage**: Minimum 85% for error handling paths
- **Property Coverage**: All 28 properties implemented as property tests
- **Integration Coverage**: All MCP tool entry points tested end-to-end