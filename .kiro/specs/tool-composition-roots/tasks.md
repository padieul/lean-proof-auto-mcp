# Implementation Plan: Tool Composition Roots Refactor

## Overview

This implementation plan refactors all MCP tool composition roots to eliminate dependency injection violations, add caching for performance, establish Command/Handler pattern for try_automated_proof, and wire SearchOrchestrator to use ProofValidator. The implementation follows hexagonal architecture principles and the established code conventions.

## Tasks

- [x] 1. Add caching infrastructure to ImportBasedHarnessConstructor
  - Add three cache dictionaries: _file_cache, _decl_cache, _theorem_verified
  - Implement cache lookup logic in construct() method
  - Implement clear_cache() method to reset all caches
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ]* 1.1 Write property test for file content caching
  - **Property 5: File content caching**
  - **Validates: Requirements 3.1, 3.4**

- [ ]* 1.2 Write property test for declaration extraction caching
  - **Property 6: Declaration extraction caching**
  - **Validates: Requirements 3.2, 3.4**

- [ ]* 1.3 Write property test for theorem verification caching
  - **Property 7: Theorem verification caching**
  - **Validates: Requirements 3.3, 3.4**

- [ ]* 1.4 Write property test for cache clearing
  - **Property 9: Cache clearing**
  - **Validates: Requirements 3.5, 6.5**

- [x] 2. Refactor ProbeCommandHandler to use dependency injection
  - Change constructor signature: add querier parameter, change lean_runner to validator, make harness_constructor required
  - Remove _construct_harness() method (use injected constructor instead)
  - Update handle() method to use injected querier and validator
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 9.1, 9.2, 9.3_

- [ ]* 2.1 Write property test for no infrastructure creation in handlers
  - **Property 2: No infrastructure creation in handlers**
  - **Validates: Requirements 1.3, 2.2, 2.3, 9.1, 9.2, 9.3**

- [ ]* 2.2 Write property test for constructor injection
  - **Property 3: Constructor injection for all dependencies**
  - **Validates: Requirements 2.1, 9.6**

- [ ]* 2.3 Write property test for injected constructor usage
  - **Property 4: Injected constructor usage**
  - **Validates: Requirements 2.4**

- [x] 3. Update probe.py composition root
  - Create single LeanInteractServerManager instance
  - Create LeanInteractQuerier with ServerManager
  - Create LeanInteractProofValidator with ServerManager
  - Create ImportBasedHarnessConstructor with caching
  - Wire all dependencies into ProbeCommandHandler
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 7.5, 7.6_

- [ ]* 3.1 Write property test for single ServerManager per tool invocation
  - **Property 1: Single ServerManager per tool invocation**
  - **Validates: Requirements 1.1, 1.2**

- [ ]* 3.2 Write property test for correct adapter types
  - **Property 19: Correct adapter types**
  - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

- [ ]* 3.3 Write property test for no deprecated adapter references
  - **Property 20: No deprecated adapter references**
  - **Validates: Requirements 7.5, 7.6**

- [x] 4. Checkpoint - Ensure probe tool tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update probe_file.py composition root
  - Create single LeanInteractServerManager instance (shared across all theorems)
  - Create single ImportBasedHarnessConstructor with caching (shared across all theorems)
  - Wire dependencies into ProbeCommandHandler
  - Add constructor.clear_cache() call after batch completes
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.3_

- [ ]* 5.1 Write property test for single ServerManager in batch operations
  - **Property 17: Single ServerManager in batch operations**
  - **Validates: Requirements 6.1, 6.3, 8.3**

- [ ]* 5.2 Write property test for single HarnessConstructor in batch operations
  - **Property 18: Single HarnessConstructor in batch operations**
  - **Validates: Requirements 6.2**

- [ ]* 5.3 Write property test for batch operation caching
  - **Property 8: Batch operation caching**
  - **Validates: Requirements 6.4, 8.1, 8.2**

- [ ] 6. Create ValidateProofCommand and ValidateProofCommandHandler
  - Create new file: core/validate_proof_domain.py
  - Define ValidateProofCommand as frozen dataclass with file_path, theorem_id, proof_attempt, timeout_s, return_proof_state
  - Define ValidateProofCommandHandler with querier, validator, constructor, proof_state_inspector, metadata_collector
  - Implement handle() method: extract theorem, construct harness, validate proof, enrich with proof state
  - _Requirements: 4.1, 4.2, 4.6_

- [ ]* 6.1 Write unit test for ValidateProofCommand immutability
  - Test that ValidateProofCommand is frozen
  - Test that modifying fields raises error
  - _Requirements: 4.1_

- [ ]* 6.2 Write property test for ValidateProofCommand immutability
  - **Property 10: ValidateProofCommand immutability**
  - **Validates: Requirements 4.1**

- [ ]* 6.3 Write unit test for ValidateProofCommandHandler workflow
  - Test that handler extracts theorem using querier
  - Test that handler constructs harness using constructor
  - Test that handler validates using validator
  - _Requirements: 4.2, 4.6_

- [ ] 7. Refactor try_automated_proof.py to use Command/Handler pattern
  - Implement _build_command() to create ValidateProofCommand from args
  - Implement _create_handler() composition root
  - Update try_automated_proof() to use command/handler workflow
  - Remove _create_validator() and monkey-patching code
  - _Requirements: 4.3, 4.4, 4.5, 4.7, 9.4_

- [ ]* 7.1 Write property test for try_automated_proof workflow
  - **Property 11: try_automated_proof workflow**
  - **Validates: Requirements 4.3, 4.4, 4.5**

- [ ]* 7.2 Write property test for no monkey-patching
  - **Property 12: No monkey-patching**
  - **Validates: Requirements 4.7, 9.4**

- [ ] 8. Checkpoint - Ensure try_automated_proof tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Refactor SearchOrchestrator to use ProofValidator
  - Change constructor signature: replace lean_runner with validator, make constructor required
  - Update _test_hint_combination() to use validator.validate_proof()
  - Implement harness construction with caching
  - Implement result status mapping (success → True, others → False)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ]* 9.1 Write property test for SearchOrchestrator uses ProofValidator
  - **Property 13: SearchOrchestrator uses ProofValidator**
  - **Validates: Requirements 5.1, 5.2**

- [ ]* 9.2 Write property test for probe_fn uses validator
  - **Property 14: probe_fn uses validator**
  - **Validates: Requirements 5.3**

- [ ]* 9.3 Write property test for probe_fn uses injected constructor
  - **Property 15: probe_fn uses injected constructor**
  - **Validates: Requirements 5.4**

- [ ]* 9.4 Write property test for probe_fn result mapping
  - **Property 16: probe_fn result mapping**
  - **Validates: Requirements 5.6**

- [ ] 10. Update search_automated_proof.py composition root
  - Create LeanInteractProofValidator with ServerManager
  - Create ImportBasedHarnessConstructor with caching
  - Wire validator and constructor into SearchOrchestrator
  - Remove LeanInteractRunner references
  - _Requirements: 5.1, 5.2, 7.3, 7.5_

- [ ] 11. Update verify.py composition root
  - Change from LeanInteractRunner to LeanInteractProofValidator
  - Update VerifyCommandHandler to use ProofValidator port
  - _Requirements: 7.3, 7.5_

- [ ]* 11.1 Write property test for domain components receive ports only
  - **Property 21: Domain components receive ports only**
  - **Validates: Requirements 9.5**

- [ ] 12. Checkpoint - Ensure all tool tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Write integration tests for refactored workflows
  - Test probe with single theorem
  - Test probe_file with multiple theorems (verify caching)
  - Test try_automated_proof with valid proof
  - Test search_automated_proof with candidates
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ]* 13.1 Write property test for API compatibility
  - **Property 22: API compatibility**
  - **Validates: Requirements 10.4**

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Run full test suite
  - Verify no resource leaks
  - Verify performance improvements in probe_file
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end workflows
- The refactoring maintains backward compatibility with existing APIs
