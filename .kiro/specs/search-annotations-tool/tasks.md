# Implementation Plan: Search Annotations Tool

## Overview

This implementation plan breaks down the search-annotations-tool feature into discrete coding tasks following hexagonal architecture principles. The implementation will be in Python, **directly reusing existing core services** without additional port wrappers. Tasks are ordered to build incrementally, with testing integrated throughout.

**Key Architectural Decision**: No port abstractions for existing services. Directly use `ProbeCommandHandler`, `VerifyCommandHandler`, `LeanInteractRunner`, `WorkspaceProvider`, `FilesystemArtifactStore`, and core indexer functions.

## Tasks

### Phase 1: Domain Models and Core Logic

- [x] 1. Define core domain models and value objects
  - Create immutable data classes for HintSet, Hint, Candidate, SearchResult, ProofPatch, GlobalSuggestion
  - Create configuration data classes: BudgetConfig, SearchConfig, CandidateConfig, StyleConfig, WorkspaceConfig, AutomationConfig, SkeletonConfig
  - Implement HintSet operations (add, remove, size) maintaining immutability
  - Define HintType and CandidateSource enums
  - _Requirements: 3.1, 3.7, 3.8, 4.1, 4.2, 5.1, 6.1, 7.3, 14.1_

- [x] 1.1 Write property tests for HintSet immutability
  - **Property: HintSet operations preserve immutability**
  - **Validates: Requirements 5.2**

- [x] 2. Implement CandidateGenerator service
  - Create CandidateGenerator class with __init__(source: SourceText, index: TheoremIndex)
  - Implement generate(theorem_decl, sources, config) method
  - Implement _extract_from_goal: parse goal expression, collect constant names
  - Implement _extract_from_context: extract from hypothesis types
  - Implement _extract_from_namespace: gather lemmas in same namespace (use existing index)
  - Implement _extract_nearby: lemmas within ±N lines (use existing index)
  - Implement _extract_from_proof: extract from original proof references
  - Implement _rank_and_deduplicate: prioritize .def lemmas, [simp] lemmas, proof refs
  - Ensure deterministic ordering (sort by fully-qualified name)
  - Respect max_candidates_per_source limit
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

- [x] 2.1 Write property test for candidate source extraction completeness
  - **Property 9: Candidate Source Extraction Completeness**
  - **Validates: Requirements 3.1**

- [x] 2.2 Write property test for candidate limit enforcement
  - **Property 11: Candidate Limit Enforcement**
  - **Validates: Requirements 3.9**

- [x] 2.3 Write property test for candidate ranking priority
  - **Property 12: Candidate Ranking Priority**
  - **Validates: Requirements 3.10**

- [x] 3. Implement SearchStrategy interface and concrete strategies
  - Create SearchStrategy protocol with search method signature
  - Implement GreedySearch: start empty, add best candidate each step
  - Implement BeamSearch: maintain beam_width sets, expand and prune
  - Both strategies respect max_hints, max_steps, stop_on_first_close
  - Both strategies use probe_fn callback (receives HintSet, returns ProbeResult)
  - _Requirements: 4.1, 4.2, 4.5, 4.6, 4.7_

- [x] 3.1 Write property test for greedy search incremental growth
  - **Property 13: Greedy Search Incremental Growth**
  - **Validates: Requirements 4.1**

- [x] 3.2 Write property test for beam search width invariant
  - **Property 14: Beam Search Width Invariant**
  - **Validates: Requirements 4.2**

- [x] 3.3 Write property test for hint set size limit
  - **Property 17: Hint Set Size Limit**
  - **Validates: Requirements 4.7**

- [x] 3.4 Write property test for search termination control
  - **Property 16: Search Termination Control**
  - **Validates: Requirements 4.5, 4.6**

- [x] 3.5 Write property test for hint set scoring consistency
  - **Property 18: Hint Set Scoring Consistency**
  - **Validates: Requirements 4.9**

- [x] 4. Implement Minimizer service
  - Create Minimizer class with minimize method
  - Apply delta-debugging algorithm: iteratively remove hints
  - Use probe_fn callback to verify each reduced set
  - Restore hints that cause failure when removed
  - Iterate until fixed point (no more removals possible)
  - Return minimized stable hint set
  - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6_

- [x] 4.1 Write property test for minimization preservation
  - **Property 19: Minimization Preservation**
  - **Validates: Requirements 5.1, 5.2**

- [x] 4.2 Write property test for minimization restoration
  - **Property 20: Minimization Restoration**
  - **Validates: Requirements 5.3**

- [x] 4.3 Write property test for minimized set closure guarantee
  - **Property 21: Minimized Set Closure Guarantee**
  - **Validates: Requirements 5.5**

- [x] 4.4 Write property test for minimized set stability
  - **Property 22: Minimized Set Stability**
  - **Validates: Requirements 5.6**

- [x] 5. Implement ProofPatchBuilder service
  - Create ProofPatchBuilder class with build method
  - Generate Lean proof code from hint set and automation mode
  - Apply style preferences: prefer_simp_over_aesop, emit_compact, simp_only_list
  - Implement simp-specific formatting (simp_all only [...])
  - Implement aesop-specific formatting (aesop (add safe [...] unfold [...] simp [...]))
  - Detect and preserve definitional proofs (rfl, Iff.rfl, trivial)
  - Ensure syntactically valid Lean code
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 5.1 Write property test for proof patch syntax validity
  - **Property 23: Proof Patch Syntax Validity**
  - **Validates: Requirements 6.1**

- [x] 5.2 Write property test for automation-specific proof formatting
  - **Property 24: Automation-Specific Proof Formatting**
  - **Validates: Requirements 6.2, 6.3**

- [x] 5.3 Write property test for proof formatting style control
  - **Property 25: Proof Formatting Style Control**
  - **Validates: Requirements 6.4, 6.5**

- [x] 5.4 Write property test for definitional proof preservation
  - **Property 27: Definitional Proof Preservation**
  - **Validates: Requirements 6.7, 15.1, 15.2, 15.3**

- [x] 6. Implement GlobalSuggestionAnalyzer service (optional, for suggest_global mode)
  - Create GlobalSuggestionAnalyzer class with analyze method
  - Analyze minimized hint sets for globalization candidates
  - Generate @[aesop] and @[simp] suggestions with rationale
  - Filter suggestions by effectiveness criteria
  - Return list of GlobalSuggestion objects
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 6.1 Write property test for mode-conditional global suggestions
  - **Property 29: Mode-Conditional Global Suggestions**
  - **Validates: Requirements 7.1, 7.2**

- [x] 6.2 Write property test for effective hint suggestion generation
  - **Property 30: Effective Hint Suggestion Generation**
  - **Validates: Requirements 7.3**

### Phase 2: Command Handler and Integration

- [x] 7. Implement SearchAnnotationsCommand and SearchAnnotationsResult
  - Create SearchAnnotationsCommand immutable data class with all input parameters
  - Create SearchAnnotationsResult immutable data class with all output fields
  - Add validation in __post_init__ methods
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

- [x] 8. Implement SearchAnnotationsCommandHandler
  - Create SearchAnnotationsCommandHandler class with dependency injection constructor
  - Accept: probe_handler (ProbeCommandHandler), candidate_generator, search_strategy, minimizer, artifact_store
  - Implement handle(command) method orchestrating complete workflow
  - Phase 1: Viability check using build_index() and find_by_id() from core/indexer
  - Phase 2: Baseline probe using probe_handler.handle()
  - Phase 3: Generate candidates using candidate_generator.generate()
  - Phase 4: Search using search_strategy.search()
  - Phase 5: Minimize using minimizer.minimize()
  - Phase 6: Build proof patch using ProofPatchBuilder
  - Phase 7: Store artifacts using artifact_store.store()
  - Enforce time budgets for each phase
  - Handle errors gracefully, return structured error responses
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

- [x] 8.1 Write property test for file validation correctness
  - **Property 1: File Validation Correctness**
  - **Validates: Requirements 1.1**

- [x] 8.2 Write property test for error descriptiveness
  - **Property 2: Error Descriptiveness**
  - **Validates: Requirements 1.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.8**

- [x] 8.3 Write property test for budget enforcement
  - **Property 3: Budget Enforcement**
  - **Validates: Requirements 1.5, 2.5, 4.8, 5.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7**

- [x] 8.4 Write property test for viability check isolation
  - **Property 4: Viability Check Isolation**
  - **Validates: Requirements 1.6**

- [x] 8.5 Write property test for early termination on baseline success
  - **Property 7: Early Termination on Baseline Success**
  - **Validates: Requirements 2.4**

- [x] 8.6 Write property test for baseline attempt recording
  - **Property 8: Baseline Attempt Recording**
  - **Validates: Requirements 2.6**

- [x] 9. Implement MCP tool entry point (search_annotations function)
  - Create search_annotations(args: dict) function in tools/search_annotations.py
  - Implement _build_command(args) for argument validation and coercion
  - Implement _create_handler(file_path) composition root
  - Wire dependencies: create LeanInteractRunner, WorkspaceProvider, HeuristicClassifier, FilesystemArtifactStore
  - Create ProbeCommandHandler with existing adapters
  - Create search-specific components: CandidateGenerator, SearchStrategy, Minimizer
  - Wire into SearchAnnotationsCommandHandler
  - Implement _build_error_response for consistent error handling
  - Follow exact pattern from probe.py and verify.py
  - _Requirements: 1.1, 1.2, 1.3, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

- [x] 9.1 Write unit tests for argument validation
  - Test invalid file paths
  - Test invalid theorem_ids
  - Test invalid budget values
  - Test invalid configuration values
  - _Requirements: 1.1, 1.3_

- [x] 9.2 Write integration test for complete workflow
  - Test end-to-end search with mock Lean execution
  - Verify all phases execute in order
  - Verify artifacts are stored
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

### Phase 3: Workspace Isolation and Artifacts

- [x] 10. Implement workspace isolation using existing WorkspaceProvider
  - Reuse create_workspace_provider() from adapters/workspace_provider.py
  - Ensure worktree creation for git_worktree mode
  - Ensure cleanup on success, failure, and timeout
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 10.1 Write property test for worktree creation and isolation
  - **Property 33: Worktree Creation and Isolation**
  - **Validates: Requirements 8.1**

- [x] 10.2 Write property test for cleanup guarantee under failure
  - **Property 35: Cleanup Guarantee Under Failure**
  - **Validates: Requirements 8.4**

- [x] 10.3 Write property test for process cleanup guarantee
  - **Property 36: Process Cleanup Guarantee**
  - **Validates: Requirements 8.5**

- [x] 10.4 Write property test for original directory isolation
  - **Property 37: Original Directory Isolation**
  - **Validates: Requirements 8.6**

- [x] 11. Implement artifact storage using existing FilesystemArtifactStore
  - Reuse FilesystemArtifactStore from adapters/artifact_store.py
  - Store request JSON, result JSON, logs under .kiro/runs/{run_id}/
  - Store per-attempt logs for baseline, search trials, minimization
  - Record repo commit, Lean version, Lake version in metadata
  - _Requirements: 9.8, 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 11.1 Write property test for timing completeness
  - **Property 38: Timing Completeness**
  - **Validates: Requirements 9.8**

- [x] 11.2 Write property test for result structure completeness
  - **Property 39: Result Structure Completeness**
  - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8**

- [x] 11.3 Write property test for result determinism
  - **Property 40: Result Determinism**
  - **Validates: Requirements 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5**

### Phase 4: Advanced Features (Optional)

- [ ] 12. Implement skeleton-based search (if skeleton.enabled=true)
  - Create SkeletonExplorer service
  - Implement tactic move exploration (cases, constructor, induction)
  - Respect skeleton.max_depth limit
  - Restrict to skeleton.moves list
  - Combine with hint search in branches
  - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [ ] 12.1 Write property test for skeleton mode conditional behavior
  - **Property 41: Skeleton Mode Conditional Behavior**
  - **Validates: Requirements 14.1, 14.2**

- [ ] 12.2 Write property test for skeleton depth limit
  - **Property 42: Skeleton Depth Limit**
  - **Validates: Requirements 14.3**

### Phase 5: End-to-End Testing

- [ ] 13. Write end-to-end integration tests
  - Test complete workflow with real Lean files (if available)
  - Test local_only mode produces valid proof patches
  - Test suggest_global mode produces advisory suggestions
  - Test timeout handling at each phase
  - Test error handling for missing files, invalid theorems
  - Test deterministic output across multiple runs
  - _Requirements: All requirements_

- [ ] 14. Write property-based tests for all 44 correctness properties
  - Implement remaining properties not covered in earlier tasks
  - Use Hypothesis library with minimum 100 iterations per property
  - Tag each test with "Feature: search-annotations-tool, Property {N}"
  - Enable shrinking to find minimal failing examples
  - _Requirements: All requirements_

## Notes

- **No port abstractions**: Directly use existing `ProbeCommandHandler`, `VerifyCommandHandler`, `LeanInteractRunner`, `WorkspaceProvider`, `FilesystemArtifactStore`
- **Composition root pattern**: Wire dependencies in `_create_handler()` function (same as probe.py, verify.py)
- **Immutability**: All domain models are frozen dataclasses
- **Error handling**: Use structured error responses, no exceptions for expected failures
- **Testing**: Property-based tests for universal properties, unit tests for specific cases
- **Determinism**: Stable JSON ordering, stable hint ordering, deterministic minimization
