# Implementation Plan: verify MCP Tool

## Overview

This plan implements the `verify` tool as the foundational Lean execution primitive for the repository. The implementation follows hexagonal architecture with clear separation between core domain logic, ports (abstract interfaces), and adapters (concrete implementations). The tool provides deterministic, sandboxed, budget-bounded verification of Lean files and theorems using LeanInteract as the execution backend.

## Tasks

- [x] 1. Set up core domain structures and ports
  - Create `VerifyCommand` immutable data class with validation
  - Create `VerifyResult` immutable data class
  - Define `LeanRunner` port (Protocol)
  - Define `WorkspaceProvider` port (Protocol)
  - Define `ArtifactStore` port (Protocol)
  - Create internal data structures: `LeanRunResult`, `Workspace`
  - _Requirements: 1.1, 1.2, 1.5, 6.1, 7.1_

- [x] 2. Implement VerifyCommandHandler (core orchestrator)
  - [x] 2.1 Implement handler initialization with dependency injection
    - Accept LeanRunner, WorkspaceProvider, ArtifactStore as constructor parameters
    - Store dependencies as instance variables
    - _Requirements: 1.1_

  - [x] 2.2 Implement main handle() method orchestration
    - Generate run_id with timestamp and file hash
    - Create isolated workspace via WorkspaceProvider
    - Call LeanRunner.verify_file() with timeout
    - Parse and normalize diagnostics
    - Determine status from LeanRunResult
    - Build VerifyResult with all sections
    - Store artifacts if store_full_logs=true
    - Ensure workspace cleanup in finally block
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 6.3_

  - [x] 2.3 Write property test for handler orchestration
    - **Property 1: Response Schema Compliance**
    - **Validates: Requirements 1.1, 8.3**

  - [x] 2.4 Implement diagnostic normalization
    - Sort diagnostics by (file, line, col, severity, message)
    - Ensure all diagnostics have required fields
    - Map severity strings to standard values
    - _Requirements: 1.4, 3.1, 3.2, 5.1, 5.2_

  - [x] 2.5 Write property test for diagnostic sorting
    - **Property 7: Deterministic Diagnostic Sorting**
    - **Validates: Requirements 3.1, 3.2**

  - [x] 2.6 Implement deterministic output formatting
    - Apply deterministic truncation to log excerpts
    - Ensure JSON key ordering (sort_keys=True)
    - Round floating point values consistently
    - Reuse core.format.ensure_deterministic()
    - _Requirements: 3.3, 3.4, 3.5_

  - [x] 2.7 Write property test for deterministic output
    - **Property 8: Deterministic Output**
    - **Validates: Requirements 3.3, 3.4, 3.5, 8.5**

  - [x] 2.8 Implement diagnostic summary builder
    - Count diagnostics by severity
    - Return dict with error_count, warning_count, info_count
    - _Requirements: 5.4_

  - [x] 2.9 Write property test for diagnostic summary consistency
    - **Property 12: Diagnostic Summary Consistency**
    - **Validates: Requirements 5.4**

  - [x] 2.10 Implement evidence section builder
    - Truncate stdout/stderr to max_log_excerpt_chars
    - Add notes array with error codes and context
    - _Requirements: 5.5_

  - [x] 2.11 Implement metadata section builder
    - Include workspace_mode and workspace_id
    - Detect repo_commit via git rev-parse HEAD
    - Detect lean_version and lake_version
    - _Requirements: 6.5, 8.4_

  - [x] 2.12 Implement timing section builder
    - Calculate total_s, lean_execution_s, overhead_s
    - Ensure overhead < 500ms for performance requirement
    - _Requirements: 4.5_

- [ ] 3. Checkpoint - Core domain complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement LeanInteractRunner adapter
  - [x] 4.1 Implement LeanInteractRunner class
    - Initialize with timeout_buffer_ms parameter
    - Implement verify_file() method
    - Handle both file-level and theorem-level verification
    - _Requirements: 1.1, 1.3, 2.1, 2.2_

  - [x] 4.2 Implement file-level verification
    - Initialize LeanServer with project_path and timeout
    - Call server.run_file() with file path
    - Parse response for diagnostics
    - Capture stdout/stderr logs
    - Handle TimeoutError and return timeout status
    - Always close server in finally block
    - _Requirements: 1.1, 1.3, 4.2, 4.3_

  - [x] 4.3 Write property test for timeout enforcement
    - **Property 4: Timeout Enforcement**
    - **Validates: Requirements 1.3, 4.2, 4.3**

  - [x] 4.4 Implement theorem-level verification
    - Parse file with SourceText and build_index
    - Find theorem by theorem_id
    - Extract lines up to theorem.decl_span.end_line
    - Create temporary abridged file in workspace
    - Verify abridged file with LeanInteract
    - Map diagnostics back to original file path
    - Clean up temporary file
    - Return scope_used="theorem"
    - _Requirements: 2.1, 2.2_

  - [x] 4.5 Write property test for theorem scope support
    - **Property 16: Theorem Scope Support**
    - **Validates: Requirements 2.1, 2.2**

  - [x] 4.6 Implement theorem not found error handling
    - Raise ValueError if theorem_id not found in index
    - Include helpful error message
    - _Requirements: 2.3_

  - [x] 4.7 Write unit test for theorem not found handling
    - Test with invalid theorem_id
    - Verify error diagnostic returned
    - _Requirements: 2.3_

  - [x] 4.8 Implement diagnostic parsing from LeanInteract response
    - Parse messages array for errors/warnings
    - Parse sorries array for incomplete proofs
    - Normalize to standard diagnostic format
    - Extract location (file, line, col)
    - _Requirements: 1.4, 5.1, 5.2, 5.3_

  - [x] 4.9 Write unit test for diagnostic parsing
    - Test with various LeanInteract response formats
    - Verify all diagnostic fields populated correctly
    - _Requirements: 1.4, 5.1, 5.2, 5.3_

  - [x] 4.10 Implement process cleanup guarantees
    - Ensure server.close() called in finally block
    - Verify no orphaned Lean processes
    - _Requirements: 4.4_

  - [x] 4.11 Write property test for process cleanup
    - **Property 5: Process and Workspace Cleanup**
    - **Validates: Requirements 4.4, 6.3**

- [ ] 5. Checkpoint - LeanInteract adapter complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement GitWorktreeProvider adapter
  - [x] 6.1 Implement GitWorktreeProvider class
    - Initialize with worktree_dir parameter
    - Implement create_workspace() method
    - Implement cleanup_workspace() method
    - _Requirements: 1.2, 6.1, 6.3_

  - [x] 6.2 Implement workspace creation with git worktree
    - Generate unique workspace_id (timestamp + random suffix)
    - Run: git worktree add <path> HEAD
    - Return Workspace with path, workspace_id, mode="worktree"
    - Handle git command errors gracefully
    - _Requirements: 1.2, 6.1_

  - [x] 6.3 Write property test for workspace isolation
    - **Property 3: Workspace Isolation**
    - **Validates: Requirements 1.2, 6.1, 6.2**

  - [x] 6.4 Implement workspace cleanup
    - Run: git worktree remove <path> --force
    - Handle cleanup errors (log but don't fail)
    - _Requirements: 6.3_

  - [x] 6.5 Implement TempCopyProvider as fallback
    - Copy project directory to temp location
    - Return Workspace with mode="temp"
    - Clean up temp directory on cleanup_workspace()
    - _Requirements: 1.2, 6.1_

  - [x] 6.6 Implement workspace mode auto-detection
    - Check if .git directory exists
    - Return "worktree" if git repo, "temp" otherwise
    - _Requirements: 6.5_

  - [x] 6.7 Write unit test for workspace mode detection
    - Test with git repository
    - Test without git repository
    - Verify correct mode selected
    - _Requirements: 6.5_

- [ ] 7. Implement FilesystemArtifactStore adapter
  - [ ] 7.1 Implement FilesystemArtifactStore class
    - Initialize with artifacts_dir parameter
    - Implement store() method
    - _Requirements: 1.5, 7.1_

  - [ ] 7.2 Implement artifact storage
    - Create run_id directory under artifacts_dir
    - Write request.json with command data
    - Write result.json with result data
    - Write lean_output.log with full logs
    - Use json.dump with indent=2 and sort_keys=True
    - _Requirements: 1.5, 7.1_

  - [ ] 7.3 Write property test for artifact storage completeness
    - **Property 10: Artifact Storage Completeness**
    - **Validates: Requirements 1.5, 7.1**

  - [ ] 7.4 Implement conditional artifact storage
    - Only store if store_full_logs=true
    - Skip storage if store_full_logs=false
    - _Requirements: 7.5_

  - [ ] 7.5 Write property test for artifact storage control
    - **Property 11: Artifact Storage Control**
    - **Validates: Requirements 7.5**

  - [ ] 7.6 Implement artifact persistence
    - Ensure artifacts exist after tool returns
    - Handle disk space errors gracefully
    - _Requirements: 7.4_

  - [ ] 7.7 Write property test for artifact persistence
    - **Property 19: Artifact Persistence**
    - **Validates: Requirements 7.4**

- [ ] 8. Checkpoint - All adapters complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement MCP tool entry point
  - [ ] 9.1 Create verify() function in tools/verify.py
    - Accept args dict with file, theorem_id, budget_s, etc.
    - Coerce and validate arguments
    - Build VerifyCommand from args
    - Create handler with real adapters (composition root)
    - Call handler.handle(command)
    - Return VerifyResult as dict
    - _Requirements: 1.1, 8.3_

  - [ ] 9.2 Implement argument validation and coercion
    - Validate file is non-empty string
    - Validate budget_s is positive number
    - Validate max_log_excerpt_chars is positive integer
    - Provide defaults for optional parameters
    - Return error response for invalid inputs
    - _Requirements: 1.1_

  - [ ] 9.3 Write unit test for argument validation
    - Test with valid inputs
    - Test with invalid inputs (missing file, negative budget)
    - Verify error responses
    - _Requirements: 1.1_

  - [ ] 9.4 Implement composition root
    - Create LeanInteractRunner instance
    - Create GitWorktreeProvider instance (with fallback to TempCopyProvider)
    - Create FilesystemArtifactStore instance
    - Wire dependencies into VerifyCommandHandler
    - _Requirements: 1.1_

  - [ ] 9.5 Implement error handling wrapper
    - Catch all exceptions in try/except
    - Return error response with diagnostic
    - Include error code in notes
    - Ensure cleanup happens even on exception
    - _Requirements: 1.1_

  - [ ] 9.6 Write unit test for error handling
    - Test with various error conditions
    - Verify error responses have correct structure
    - Verify cleanup happens
    - _Requirements: 1.1_

- [ ] 10. Register verify tool with MCP router
  - [ ] 10.1 Register verify handler in adapters/router.py
    - Import verify function
    - Register with router.register("verify", verify)
    - _Requirements: 8.3_

  - [ ] 10.2 Add verify tool to MCP server tool list
    - Update server.py to include verify in list_tools()
    - Add tool description and input schema
    - _Requirements: 8.3_

  - [ ] 10.3 Write MCP contract test for verify tool
    - Test tool registration
    - Test input schema validation
    - Test output schema validation
    - _Requirements: 8.3_

- [ ] 11. Integration testing with mathlib fixtures
  - [ ] 11.1 Create mathlib test fixtures
    - Create tests/fixtures/lean/valid_theorem.lean
    - Create tests/fixtures/lean/type_error.lean
    - Create tests/fixtures/lean/sorry_proof.lean
    - Create tests/fixtures/lean/slow_verification.lean
    - _Requirements: 1.1, 1.3_

  - [ ] 11.2 Write integration test for valid theorem
    - Verify file with no errors
    - Verify status="success"
    - Verify no error diagnostics
    - _Requirements: 1.1_

  - [ ] 11.3 Write integration test for type error
    - Verify file with type error
    - Verify status="fail"
    - Verify error diagnostic present
    - _Requirements: 1.1, 1.4_

  - [ ] 11.4 Write integration test for sorry proof
    - Verify file with incomplete proof
    - Verify status="success" (sorry is warning, not error)
    - Verify warning diagnostic present
    - _Requirements: 1.1, 1.4_

  - [ ] 11.5 Write integration test for timeout
    - Verify slow file with small budget
    - Verify status="timeout"
    - Verify timeout within 100ms of budget
    - _Requirements: 1.3, 4.2, 4.3_

  - [ ] 11.6 Write integration test for theorem-level verification
    - Verify specific theorem by theorem_id
    - Verify scope_used="theorem"
    - Verify diagnostics scoped to theorem
    - _Requirements: 2.1, 2.2_

- [ ] 12. Concurrent execution testing
  - [ ] 12.1 Write property test for concurrent execution safety
    - **Property 15: Concurrent Execution Safety**
    - Run N verifications concurrently (N=2-10)
    - Verify all complete successfully
    - Verify no workspace collisions
    - **Validates: Requirements 6.4**

- [ ] 13. Create API documentation
  - [ ] 13.1 Create docs/mcp/tools/verify.md
    - Document tool purpose and use cases
    - Document input schema with all parameters
    - Document output schema with all fields
    - Provide usage examples (file-level and theorem-level)
    - Document error codes and handling
    - Document performance characteristics and timeouts
    - _Requirements: 8.3_

  - [ ] 13.2 Add verify tool to docs/mcp/README.md
    - Add verify to tool list with brief description
    - Link to detailed verify.md documentation
    - _Requirements: 8.3_

  - [ ] 13.3 Create JSON schema files
    - Create docs/mcp/schemas/verify_input.json
    - Create docs/mcp/schemas/verify_output.json
    - Include all fields with types and descriptions
    - _Requirements: 8.3_

- [ ] 14. Final checkpoint - All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations)
- Unit tests validate specific examples and edge cases
- Integration tests validate with real Lean files
- All code follows hexagonal architecture with ports and adapters
- All data structures are immutable (frozen dataclasses)
- All dependencies injected via constructor (no global state)
