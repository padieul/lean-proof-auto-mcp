# Implementation Plan: Iterative Orchestration Enhancements

## Overview

This plan implements the migration to LeanInteract as the sole foundation for Lean interaction, enabling LLM-guided proof refactoring with 95%+ hint extraction accuracy and rich feedback mechanisms. The implementation follows a phased approach: Adapter Layer → Core Domain Refactoring → MCP Tool Enhancement → Existing Tool Migration → Test Suite Migration.

## Tasks

- [x] 1. Implement LeanInteract Adapter Layer
  - [x] 1.1 Create LeanInteractQuerier component
    - Implement `extract_declarations()` using `FileCommand(declarations=True)`
    - Implement `get_proof_references()` using value.constants + pp text parsing fallback
    - Implement `get_theorem_context()` with scope and hypothesis extraction
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4_
  
  - [x] 1.2 Write property test for LeanInteractQuerier
    - **Property 1: Complete Declaration Extraction**
    - **Validates: Requirements 1.1, 1.2, 1.3**
  
  - [x] 1.3 Write property test for proof reference extraction
    - **Property 2: Accurate Proof Reference Extraction**
    - **Validates: Requirements 2.3**
  
  - [x] 1.4 Write property test for context extraction
    - **Property 3: Complete Context Extraction**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
  
  - [x] 1.5 Create ProofStateInspector component
    - Implement `get_initial_proof_state()` using Command with sorry
    - Implement `apply_tactic()` using ProofStep
    - Parse proof states to extract goals and hypotheses
    - _Requirements: 16.1, 16.2, 16.3, 16.4_
  
  - [ ]* 1.6 Write property test for proof state inspection
    - **Property 8: Proof State Completeness**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4**
  
  - [x] 1.7 Create ProofValidator component
    - Implement `validate_proof()` using Command with timeout
    - Parse error messages for location and suggestions
    - Extract proof state for incomplete proofs
    - Return structured ValidationResult
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_
  
  - [ ]* 1.8 Write property test for proof validation
    - **Property 7: Validation Result Structure Completeness**
    - **Validates: Requirements 7.3, 7.4, 7.5, 7.6, 7.7, 17.1, 17.2, 17.3, 17.4, 17.5**
  
  - [x] 1.9 Create ServerManager component
    - Implement server instance management (one per file)
    - Implement crash detection and automatic restart
    - Implement request/response logging
    - Use lean-interact-runner as execution wrapper
    - _Requirements: 10.6, 28.3, 28.4, 28.5, 28.6_
  
  - [x] 1.10 Write property test for server management
    - **Property 19: Server Instance Reuse**
    - **Validates: Requirements 10.6, 28.4, 28.5, 28.6**
  
  - [x] 1.11 Write unit tests for error handling
    - Test LeanInteract crash recovery
    - Test timeout handling
    - Test invalid input handling
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 2. Checkpoint - Verify Adapter Layer
  - Ensure all adapter layer tests pass
  - Verify LeanInteract integration works with real Lean files
  - Ask the user if questions arise

- [x] 3. Refactor Core Domain Layer
  - [x] 3.1 Refactor CandidateGenerator to use LeanInteractQuerier
    - Remove all regex-based parsing code
    - Implement goal_symbols extraction using LeanInteract + parsing
    - Implement local_context extraction using proof states
    - Implement same_namespace extraction using declarations
    - Implement original_proof_refs extraction using value.constants
    - Infer hint types from declaration attributes
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 5.2, 5.3, 5.4, 5.5_
  
  - [x] 3.2 Write property test for candidate generation
    - **Property 5: Candidate Source Extraction Accuracy**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.7**
  
  - [ ]* 3.3 Write static analysis test for no regex usage
    - Verify no regex patterns in CandidateGenerator
    - **Validates: Requirements 12.2**
  
  - [x] 3.4 Implement ContextExtractor component
    - Extract theorem statement and original proof
    - Extract hypotheses from proof state
    - Extract in-scope declarations
    - Implement similar proof discovery with similarity scoring
    - Cache context for performance
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.6_
  
  - [ ]* 3.5 Write property test for similar proof discovery
    - **Property 9: Similar Proof Discovery Accuracy**
    - **Validates: Requirements 18.1, 18.2, 18.3, 18.4**
  
  - [x] 3.6 Implement FeedbackBuilder component
    - Track hints that helped and their impact
    - Calculate goal complexity reduction
    - Generate tactical suggestions with confidence scores
    - Provide reasoning for all suggestions
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [x] 3.7 Write property test for feedback building
    - **Property 16: Feedback Builder Completeness**
    - **Validates: Requirements 13.2, 13.3, 13.4, 13.5**
  
  - [x] 3.8 Enhance SearchOrchestrator
    - Support configurable search parameters
    - Implement search depth presets
    - Support all four candidate sources
    - Build rich feedback using FeedbackBuilder
    - Track partial progress during search
    - Accept MetadataCollector as optional parameter
    - Include metadata in SearchResult
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.6, 5.7, 29.2, 29.3_
  
  - [x] 3.9 Write property test for search configuration
    - **Property 4: Search Depth Configuration Consistency**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**
  
  - [x] 3.10 Write property test for search strategies
    - **Property 10: Search Strategy Behavior Consistency**
    - **Validates: Requirements 19.2, 19.3, 19.4**

- [ ] 4. Checkpoint - Verify Core Domain Layer
  - Ensure all core domain tests pass
  - Verify candidate generation achieves 95%+ accuracy on test set
  - Ask the user if questions arise

- [ ] 5. Implement Enhanced MCP Tools
  - [ ] 5.1 Implement search_automated_proof tool
    - Define tool signature with all parameters
    - Validate input parameters
    - Build SearchConfig from parameters
    - Create SubprocessMetadataCollector at composition root
    - Wire MetadataCollector into SearchOrchestrator
    - Delegate to SearchOrchestrator
    - Format response with rich feedback including metadata
    - Support all return options (proof_states, partial_progress, context, similar_proofs, search_trace)
    - _Requirements: 4.1, 4.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 29.5, 29.6_
  
  - [ ]* 5.2 Write property test for conditional return values
    - **Property 6: Conditional Return Value Completeness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**
  
  - [ ]* 5.3 Write unit tests for search_automated_proof
    - Test parameter validation
    - Test JSON response format
    - Test all search depth presets
    - _Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_
  
  - [ ] 5.4 Implement try_automated_proof tool
    - Define tool signature
    - Validate input parameters
    - Create SubprocessMetadataCollector at composition root
    - Wire MetadataCollector into ProofValidator or handler
    - Delegate to ProofValidator
    - Format ValidationResult as JSON including metadata
    - Include tactical suggestions
    - Enforce timeout
    - _Requirements: 7.1, 7.2, 7.8, 29.5, 29.6_
  
  - [ ]* 5.5 Write unit tests for try_automated_proof
    - Test validation success case
    - Test validation error case
    - Test validation incomplete case
    - Test validation timeout case
    - _Requirements: 7.3, 7.4, 7.5, 7.6_
  
  - [ ] 5.6 Implement get_proof_context tool
    - Define tool signature
    - Validate input parameters
    - Create SubprocessMetadataCollector at composition root
    - Wire MetadataCollector into ContextExtractor or handler
    - Delegate to ContextExtractor
    - Format ProofContext as JSON including metadata
    - Include similar proofs if requested
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 29.5, 29.6_
  
  - [ ]* 5.7 Write unit tests for get_proof_context
    - Test context extraction
    - Test similar proof inclusion
    - Test JSON response format
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.6_
  
  - [ ] 5.8 Add deprecation error for search_annotations
    - Remove search_annotations tool entirely
    - Return clear error message directing users to search_automated_proof
    - Do NOT provide backward compatibility or parameter mapping
    - _Requirements: 4.8, 26.5_
  
  - [ ]* 5.9 Write unit test for deprecation error
    - Test that search_annotations is not available
    - Test error message is clear and helpful
    - _Requirements: 4.8, 26.5_
  
  - [ ]* 5.10 Write unit tests for metadata collection
    - Test that all new tools include metadata in responses
    - Test metadata format matches existing tools (probe, verify, search_annotations)
    - Test graceful handling when MetadataCollector is None
    - _Requirements: 29.3, 29.4, 29.7_

- [ ] 6. Checkpoint - Verify MCP Tools
  - Ensure all MCP tool tests pass
  - Test tools with real LeanInteract on sample theorems
  - Ask the user if questions arise

- [ ] 7. Migrate Existing Tools to LeanInteract
  - [ ] 7.1 Migrate probe tool
    - Replace direct Lean CLI calls with LeanInteractQuerier
    - Route all Lean interaction through adapter layer
    - Maintain existing interface and functionality
    - _Requirements: 24.1, 24.4, 24.5_
  
  - [ ] 7.2 Write regression tests for probe
    - Verify existing functionality preserved
    - Test with existing test cases
    - _Requirements: 24.5_
  
  - [ ] 7.3 Migrate probe_file tool
    - Replace direct Lean CLI calls with LeanInteractQuerier
    - Route all Lean interaction through adapter layer
    - Maintain existing interface and functionality
    - _Requirements: 24.2, 24.4, 24.5_
  
  - [ ] 7.4 Write regression tests for probe_file
    - Verify existing functionality preserved
    - Test with existing test cases
    - _Requirements: 24.5_
  
  - [ ] 7.5 Migrate verify tool
    - Replace direct Lean CLI calls with ProofValidator
    - Route all Lean interaction through adapter layer
    - Maintain existing interface and functionality
    - _Requirements: 24.3, 24.4, 24.5_
  
  - [ ] 7.6 Write regression tests for verify
    - Verify existing functionality preserved
    - Test with existing test cases
    - _Requirements: 24.5_
  
  - [ ]* 7.7 Write static analysis test for LeanInteract foundation
    - **Property 18: LeanInteract Foundation Consistency**
    - Verify no direct Lean CLI calls in codebase
    - Verify no regex parsing of Lean output
    - Verify all Lean interaction goes through adapter layer
    - **Validates: Requirements 28.1, 28.2, 28.4**

- [ ] 8. Checkpoint - Verify Tool Migration
  - Ensure all migrated tools pass regression tests
  - Verify no direct Lean CLI calls remain
  - Ask the user if questions arise

- [ ] 9. Migrate Test Suite
  - [ ] 9.1 Update search_annotations tests
    - Update tests to use search_automated_proof
    - Update parameter names and values
    - Update expected response format
    - _Requirements: 25.1_
  
  - [ ] 9.2 Remove regex-based tests
    - Identify tests that rely on regex parsing
    - Remove or update to use LeanInteract
    - _Requirements: 25.2_
  
  - [ ] 9.3 Add LeanInteract-based candidate source tests
    - Test goal_symbols extraction
    - Test local_context extraction
    - Test same_namespace extraction
    - Test original_proof_refs extraction
    - _Requirements: 25.3_
  
  - [ ] 9.4 Add original_proof_refs accuracy tests
    - Create test dataset with known proof references
    - Measure extraction accuracy
    - Verify 95%+ accuracy target
    - _Requirements: 25.4, 2.4_
  
  - [ ] 9.5 Update test mocking strategy
    - Mock LeanInteract Adapter Layer interfaces
    - Remove mocks of Lean CLI
    - Update all tests to use new mocking approach
    - _Requirements: 25.5_
  
  - [ ]* 9.6 Verify test coverage
    - Run coverage analysis
    - Ensure 80%+ coverage maintained
    - Add tests for uncovered code
    - _Requirements: 25.6, 27.4_

- [ ] 10. Add Property-Based Tests for All Properties
  - [ ]* 10.1 Write property test for automation mode selection
    - **Property 11: Automation Mode Selection**
    - **Validates: Requirements 20.2, 20.3, 20.4, 20.5, 20.6**
  
  - [ ]* 10.2 Write property test for hint type filtering
    - **Property 12: Hint Type Filtering**
    - **Validates: Requirements 21.4, 21.5**
  
  - [ ]* 10.3 Write property test for hint minimization
    - **Property 13: Hint Set Minimization Correctness**
    - **Validates: Requirements 22.2, 22.3, 22.5**
  
  - [ ]* 10.4 Write property test for metadata completeness
    - **Property 14: Metadata Completeness**
    - **Validates: Requirements 23.1, 23.2, 23.3**
  
  - [ ]* 10.5 Write property test for error handling
    - **Property 15: Error Handling Without Crashes**
    - **Validates: Requirements 11.2, 11.3**
  
  - [ ]* 10.6 Write property test for original proof preservation
    - **Property 17: Original Proof Preservation**
    - **Validates: Requirements 14.5**
  
  - [ ]* 10.7 Write property test for dependency injection
    - **Property 20: Dependency Injection Architecture**
    - **Validates: Requirements 9.2, 9.5**
  
  - [ ]* 10.8 Write property test for metadata collection consistency
    - **Property 21: Metadata Collection Consistency**
    - **Validates: Requirements 29.2, 29.3, 29.4, 29.7**

- [ ] 11. Add Integration and Benchmark Tests
  - [ ]* 11.1 Create integration test suite
    - Test end-to-end workflow on real mathlib theorems
    - Test search → validate → iterate cycle
    - Test all three MCP tools together
    - _Requirements: 27.3_
  
  - [ ]* 11.2 Create benchmark test for declaration extraction accuracy
    - Create ground truth dataset
    - Measure extraction accuracy
    - Verify 95%+ accuracy target
    - _Requirements: 1.4_
  
  - [ ]* 11.3 Create benchmark test for proof reference extraction accuracy
    - Create ground truth dataset
    - Measure extraction accuracy
    - Verify 95%+ accuracy target
    - _Requirements: 2.4_
  
  - [ ]* 11.4 Create benchmark test for success rates
    - Test on trivial theorems (Tier 1)
    - Test on simple theorems (Tier 2)
    - Test on medium theorems (Tier 3)
    - Measure overall success rate
    - Verify 20-35% overall target
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
  
  - [ ]* 11.5 Create benchmark test for iteration efficiency
    - Measure average iterations per successful refactoring
    - Verify 2-3 iteration average
    - _Requirements: 15.1_
  
  - [ ]* 11.6 Create benchmark test for false positive rate
    - Validate all refactored proofs with Lean
    - Measure false positive rate
    - Verify < 5% target
    - _Requirements: 11.6_
  
  - [ ]* 11.7 Create performance tests
    - Test quick search time (≤ 15s)
    - Test normal search time (≤ 40s)
    - Test deep search time (≤ 90s)
    - Test validation time (≤ 10s)
    - Test full iteration cycle (≤ 50s)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 12. Final Checkpoint - Comprehensive Verification
  - Ensure all tests pass (unit, property, integration, benchmark)
  - Verify 80%+ code coverage
  - Verify 95%+ hint extraction accuracy
  - Verify 20-35% refactoring success rate
  - Verify < 5% false positive rate
  - Verify all performance targets met
  - Ask the user if questions arise

- [ ] 13. Documentation and Deployment Preparation
  - [ ] 13.1 Update API documentation
    - Document all three MCP tools with examples
    - Document removal of search_annotations
    - Document migration guide for users (use search_automated_proof instead)
    - _Requirements: 26.1, 26.5_
  
  - [ ] 13.2 Add logging and monitoring
    - Log all LeanInteract interactions
    - Log performance metrics
    - Log success rates by complexity tier
    - Add alerts for anomalies
    - _Requirements: 11.4, 28.6_
  
  - [ ] 13.3 Prepare deployment configuration
    - Configure feature flags
    - Set up gradual rollout plan
    - Document rollback procedure
    - _Requirements: 26.1, 26.2, 26.3, 26.4_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- Benchmark tests validate accuracy and success rate targets
- All tests use hypothesis library for property-based testing
- All property tests include comment tags: `# Feature: iterative-orchestration-enhancements, Property N: [property text]`
