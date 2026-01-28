# Implementation Plan: Iterative Orchestration Enhancements

## Overview

This implementation plan breaks down the iterative orchestration enhancements into discrete, incremental coding tasks. Each task builds on previous work and includes testing to validate functionality early. The plan follows the phased approach outlined in the design document, prioritizing high-impact features first.

## Tasks

- [ ] 1. Set up core data models and serialization
  - [ ] 1.1 Create `SubgoalState` dataclass with validation
    - Implement frozen dataclass with fields: remaining_goals, applied_hints, complexity_before, complexity_after
    - Add `__post_init__` validation for non-negative complexity and monotonicity
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [ ] 1.2 Create `CaseInfo` and `CaseAnalysis` dataclasses
    - Implement `CaseInfo` with case_label, goal_expression, recommended_hints, complexity
    - Implement `CaseAnalysis` with has_induction, cases, induction_variable
    - Add validation for consistency (has_induction implies non-empty cases)
    - _Requirements: 2.2, 2.3, 2.4, 2.6_
  
  - [ ] 1.3 Create `HintProvenance` dataclass
    - Implement frozen dataclass with source_category, source_theorem, relevance_score, selection_reasoning
    - Add validation for relevance_score in [0, 1] range
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 1.4 Create `DependencyAnalysis` dataclass
    - Implement frozen dataclass with has_missing_dependencies, missing_symbols, suggested_imports, suggest_global_mode, confidence
    - Add validation for confidence in [0, 1] range and consistency checks
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ] 1.5 Create `ProgressMetrics` dataclass
    - Implement frozen dataclass with complexity_before, complexity_after, reduction_percentage, blockers, iteration_recommendation
    - Add validation for reduction_percentage calculation accuracy
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 1.6 Enhance `Hint` dataclass with optional provenance field
    - Add optional `provenance: HintProvenance | None = None` field
    - Maintain backward compatibility (existing code works without provenance)
    - _Requirements: 3.5, 6.3_
  
  - [ ] 1.7 Create `EnhancementsConfig` dataclass
    - Implement configuration with boolean flags for each enhancement
    - Add optional `target_case` field for case-specific search
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_
  
  - [ ] 1.8 Enhance `SearchAnnotationsCommand` with enhancements field
    - Add optional `enhancements: EnhancementsConfig = EnhancementsConfig()` field
    - Maintain backward compatibility (defaults to all disabled)
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_
  
  - [ ] 1.9 Enhance `SearchAnnotationsResult` with optional enhancement fields
    - Add optional fields: subgoal_state, case_analysis, dependency_analysis, progress_metrics
    - Ensure fields are None by default for backward compatibility
    - _Requirements: 6.1, 6.2, 6.4, 6.5, 7.1, 7.2_
  
  - [ ] 1.10 Write property test for serialization round-trip
    - **Property 10: Serialization Round-Trip**
    - **Validates: Requirements 9.6**
    - Generate random instances of all new data structures
    - Serialize to JSON, deserialize, verify equivalence
  
  - [ ] 1.11 Write unit tests for data model validation
    - Test invalid inputs raise ValueError
    - Test edge cases (empty lists, boundary values)
    - _Requirements: 1.1, 1.2, 2.2, 3.1, 4.1, 5.1_

- [ ] 2. Checkpoint - Verify data models and serialization
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement SubgoalAnalyzer service
  - [ ] 3.1 Create `SubgoalAnalyzer` class with dependency injection
    - Accept `LeanInteractRunner` in constructor
    - Follow hexagonal architecture (no infrastructure in core logic)
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 3.2 Implement `analyze()` method
    - Parse Lean execution output to extract remaining goals
    - Calculate complexity metrics before and after hints
    - Return `SubgoalState` with all required fields
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  
  - [ ] 3.3 Implement `calculate_complexity()` helper function
    - Count symbols, nesting depth, quantifiers
    - Return integer complexity score
    - _Requirements: 1.2, 5.1, 5.2_
  
  - [ ] 3.4 Write unit tests for SubgoalAnalyzer
    - Test with mock Lean output
    - Test complexity calculation accuracy
    - Test edge cases (no remaining goals, empty output)
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 3.5 Write property test for complexity monotonicity
    - **Property 2: Complexity Monotonicity**
    - **Validates: Requirements 1.2, 5.1, 5.2**
    - Generate random SubgoalState instances
    - Verify complexity_after <= complexity_before

- [ ] 4. Integrate SubgoalAnalyzer into SearchAnnotationsCommandHandler
  - [ ] 4.1 Add SubgoalAnalyzer to handler dependencies
    - Update `__init__` to accept SubgoalAnalyzer
    - Update composition root in `search_annotations.py`
    - _Requirements: 1.1_
  
  - [ ] 4.2 Call SubgoalAnalyzer when outcome is "partial"
    - Check if `enhancements.enable_subgoal_reporting` is True
    - Call `analyzer.analyze()` with execution output
    - Set `result.subgoal_state` with returned SubgoalState
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 4.3 Handle SubgoalAnalyzer errors gracefully
    - Catch exceptions and log warnings
    - Continue without subgoal_state if analysis fails
    - Add error to metadata
    - _Requirements: 12.1, 12.2_
  
  - [ ] 4.4 Write integration test for subgoal reporting
    - Test end-to-end with real Lean execution
    - Verify subgoal_state in result
    - Verify artifact logging includes subgoal_state
    - _Requirements: 1.1, 1.2, 1.3, 10.2_

- [ ] 5. Checkpoint - Verify subgoal reporting works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement ProvenanceTracker service
  - [ ] 6.1 Create `ProvenanceTracker` class with Index dependency
    - Accept `Index` in constructor
    - Follow hexagonal architecture
    - _Requirements: 3.1, 3.2_
  
  - [ ] 6.2 Implement `track()` method
    - Determine source_category from hint.source
    - Look up source_theorem from index if applicable
    - Calculate relevance_score based on goal/context
    - Generate selection_reasoning string
    - Return `HintProvenance` instance
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 6.3 Implement relevance scoring heuristic
    - Score based on symbol overlap with goal
    - Score based on namespace proximity
    - Score based on usage frequency
    - Return score in [0, 1] range
    - _Requirements: 3.3_
  
  - [ ] 6.4 Write unit tests for ProvenanceTracker
    - Test with mock Index
    - Test relevance scoring accuracy
    - Test edge cases (no source theorem, empty goal)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 6.5 Write property test for provenance completeness
    - **Property 5: Hint Provenance Completeness**
    - **Validates: Requirements 3.1, 3.3, 3.4**
    - Generate random hints with provenance
    - Verify all required fields present and valid

- [ ] 7. Integrate ProvenanceTracker into candidate generation
  - [ ] 7.1 Add ProvenanceTracker to CandidateGenerator dependencies
    - Update `__init__` to accept ProvenanceTracker
    - Update composition root
    - _Requirements: 3.1_
  
  - [ ] 7.2 Track provenance when generating candidates
    - Check if `enhancements.enable_provenance_tracking` is True
    - Call `tracker.track()` for each generated hint
    - Set hint.provenance field
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 7.3 Handle ProvenanceTracker errors gracefully
    - Catch exceptions and log warnings
    - Continue without provenance if tracking fails
    - _Requirements: 12.1, 12.2_
  
  - [ ] 7.4 Write integration test for provenance tracking
    - Test end-to-end with candidate generation
    - Verify hints have provenance in result
    - Verify artifact logging includes provenance
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 10.6_

- [ ] 8. Checkpoint - Verify provenance tracking works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement DependencyAnalyzer service
  - [ ] 9.1 Create `DependencyAnalyzer` class with Index dependency
    - Accept `Index` in constructor
    - Follow hexagonal architecture
    - _Requirements: 4.1_
  
  - [ ] 9.2 Implement `analyze()` method
    - Extract symbols from theorem declaration
    - Check each symbol against index
    - Identify undefined symbols
    - Suggest imports for missing symbols
    - Calculate confidence based on validation
    - Return `DependencyAnalysis` instance
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ] 9.3 Implement symbol validation to avoid false positives
    - Check if symbol is defined in current file
    - Check if symbol is in standard library
    - Check if symbol is a built-in
    - _Requirements: 4.4_
  
  - [ ] 9.4 Write unit tests for DependencyAnalyzer
    - Test with mock Index
    - Test false positive avoidance
    - Test edge cases (no dependencies, all missing)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ] 9.5 Write property test for dependency detection accuracy
    - **Property 6: Dependency Detection Accuracy**
    - **Validates: Requirements 4.1, 4.4**
    - Generate theorems with undefined symbols
    - Verify detection identifies them correctly

- [ ] 10. Integrate DependencyAnalyzer into viability check
  - [ ] 10.1 Add DependencyAnalyzer to handler dependencies
    - Update `__init__` to accept DependencyAnalyzer
    - Update composition root
    - _Requirements: 4.1_
  
  - [ ] 10.2 Call DependencyAnalyzer during viability check
    - Check if `enhancements.enable_dependency_detection` is True
    - Call `analyzer.analyze()` with theorem declaration
    - Set `result.dependency_analysis` with returned DependencyAnalysis
    - _Requirements: 4.1, 4.2, 4.3, 4.5_
  
  - [ ] 10.3 Handle DependencyAnalyzer errors gracefully
    - Catch exceptions and log warnings
    - Continue without dependency_analysis if analysis fails
    - _Requirements: 12.1, 12.2_
  
  - [ ] 10.4 Write integration test for dependency detection
    - Test end-to-end with theorems having missing imports
    - Verify dependency_analysis in result
    - Verify artifact logging includes dependency_analysis
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.4_

- [ ] 11. Checkpoint - Verify dependency detection works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement CaseDetector service
  - [ ] 12.1 Create `CaseDetector` class (no external dependencies)
    - Pure domain logic for detecting induction structure
    - Follow hexagonal architecture
    - _Requirements: 2.2, 2.3_
  
  - [ ] 12.2 Implement `detect()` method
    - Scan proof text for `induction` tactic
    - Extract case labels from proof structure
    - Identify induction variable
    - Parse case-specific goals
    - Return `CaseAnalysis` instance
    - _Requirements: 2.2, 2.3_
  
  - [ ] 12.3 Implement `recommend_hints_for_case()` method
    - Filter hints by relevance to specific case
    - Rank hints by case-specific relevance
    - Return list of recommended hints
    - _Requirements: 2.4_
  
  - [ ] 12.4 Write unit tests for CaseDetector
    - Test with various induction patterns
    - Test case label extraction
    - Test edge cases (no induction, nested induction)
    - _Requirements: 2.2, 2.3, 2.4_
  
  - [ ] 12.5 Write property test for induction detection accuracy
    - **Property 4: Induction Detection Accuracy**
    - **Validates: Requirements 2.2, 2.3**
    - Generate theorems with/without induction
    - Verify detection is correct

- [ ] 13. Integrate CaseDetector into SearchAnnotationsCommandHandler
  - [ ] 13.1 Add CaseDetector to handler dependencies
    - Update `__init__` to accept CaseDetector
    - Update composition root
    - _Requirements: 2.2_
  
  - [ ] 13.2 Call CaseDetector during viability check
    - Check if `enhancements.enable_case_analysis` is True
    - Call `detector.detect()` with theorem declaration
    - Set `result.case_analysis` with returned CaseAnalysis
    - _Requirements: 2.2, 2.3_
  
  - [ ] 13.3 Implement case-specific search when target_case is specified
    - Check if `enhancements.target_case` is not None
    - Filter candidates to case-specific hints
    - Search only for that case
    - _Requirements: 2.1, 2.4_
  
  - [ ] 13.4 Handle CaseDetector errors gracefully
    - Catch exceptions and log warnings
    - Continue without case_analysis if detection fails
    - _Requirements: 12.1, 12.2_
  
  - [ ] 13.5 Write integration test for case-aware search
    - Test end-to-end with inductive theorems
    - Test with target_case parameter
    - Verify case_analysis in result
    - Verify artifact logging includes case_analysis
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 10.3_
  
  - [ ] 13.6 Write property test for case-specific search correctness
    - **Property 3: Case-Specific Search Correctness**
    - **Validates: Requirements 2.1, 2.4**
    - Generate theorems with cases
    - Search with target_case
    - Verify returned hints are case-specific

- [ ] 14. Checkpoint - Verify case-aware search works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Implement ProgressCalculator service
  - [ ] 15.1 Create `ProgressCalculator` class (no external dependencies)
    - Pure domain logic for calculating progress metrics
    - Follow hexagonal architecture
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [ ] 15.2 Implement `calculate()` method
    - Accept complexity_before, complexity_after, execution_output
    - Calculate reduction_percentage
    - Identify blockers from execution output
    - Generate iteration recommendation
    - Return `ProgressMetrics` instance
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 15.3 Implement `identify_blockers()` helper method
    - Parse execution output for error patterns
    - Identify missing symbols, type mismatches, etc.
    - Return list of blocker descriptions
    - _Requirements: 5.4_
  
  - [ ] 15.4 Write unit tests for ProgressCalculator
    - Test reduction calculation accuracy
    - Test blocker identification
    - Test recommendation generation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 15.5 Write property test for progress reduction calculation
    - **Property 7: Progress Reduction Calculation**
    - **Validates: Requirements 5.3**
    - Generate random complexity values
    - Calculate ProgressMetrics
    - Verify reduction_percentage formula

- [ ] 16. Integrate ProgressCalculator into SearchAnnotationsCommandHandler
  - [ ] 16.1 Add ProgressCalculator to handler dependencies
    - Update `__init__` to accept ProgressCalculator
    - Update composition root
    - _Requirements: 5.1_
  
  - [ ] 16.2 Call ProgressCalculator after search phase
    - Check if `enhancements.enable_progress_metrics` is True
    - Call `calculator.calculate()` with complexity and output
    - Set `result.progress_metrics` with returned ProgressMetrics
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ] 16.3 Handle ProgressCalculator errors gracefully
    - Catch exceptions and log warnings
    - Continue without progress_metrics if calculation fails
    - _Requirements: 12.1, 12.2_
  
  - [ ] 16.4 Write integration test for progress metrics
    - Test end-to-end with partial outcomes
    - Verify progress_metrics in result
    - Verify artifact logging includes progress_metrics
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 10.5_

- [ ] 17. Checkpoint - Verify progress metrics work end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. Implement backward compatibility and artifact logging tests
  - [ ] 18.1 Write property test for backward compatibility - optional fields
    - **Property 8: Backward Compatibility - Optional Fields**
    - **Validates: Requirements 7.1, 7.2, 7.5**
    - Generate SearchAnnotationsResult with enhancements disabled
    - Verify new fields are None and omitted from JSON
  
  - [ ] 18.2 Write property test for backward compatibility - existing fields
    - **Property 9: Backward Compatibility - Existing Fields**
    - **Validates: Requirements 7.3**
    - Generate SearchAnnotationsResult
    - Verify all existing fields maintain original types and names
  
  - [ ] 18.3 Write property test for artifact logging completeness
    - **Property 11: Artifact Logging Completeness**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**
    - Generate SearchAnnotationsResult with all enhancements
    - Store via ArtifactStore
    - Load result.json and verify all enhancement fields present
  
  - [ ] 18.4 Write integration test for full backward compatibility
    - Test with enhancements disabled (default)
    - Verify response identical to current behavior
    - Verify artifacts identical to current structure
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 10.7_

- [ ] 19. Update MCP tool argument parsing
  - [ ] 19.1 Add `enhancements` parameter to search_annotations tool
    - Accept optional dict with enhancement flags
    - Parse into `EnhancementsConfig` dataclass
    - Default to all disabled for backward compatibility
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_
  
  - [ ] 19.2 Update argument validation in `_build_command()`
    - Validate enhancement flags are booleans
    - Validate target_case is string or None
    - Raise ValueError for invalid inputs
    - _Requirements: 1.1, 2.1_
  
  - [ ] 19.3 Write unit tests for argument parsing
    - Test with various enhancement configurations
    - Test validation errors
    - Test backward compatibility (no enhancements param)
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1_

- [ ] 20. Update JSON serialization to omit None fields
  - [ ] 20.1 Enhance `to_json_serializable()` function
    - Check if field value is None
    - Omit field from output dict if None
    - Maintain existing behavior for non-None values
    - _Requirements: 7.2_
  
  - [ ] 20.2 Test serialization with optional fields
    - Test with all fields None (omitted)
    - Test with some fields populated (included)
    - Test with all fields populated (all included)
    - _Requirements: 7.2, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 21. Final checkpoint - End-to-end validation
  - [ ] 21.1 Run full integration test suite
    - Test all enhancements together
    - Test with real Lean execution
    - Verify artifacts contain all enhancement data
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_
  
  - [ ] 21.2 Run backward compatibility test suite
    - Test with enhancements disabled
    - Verify no changes to existing behavior
    - Verify API version unchanged
    - _Requirements: 6.6, 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ] 21.3 Run performance validation
    - Measure overhead for each enhancement
    - Verify total overhead < 500ms
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 22. Documentation and cleanup
  - [ ] 22.1 Update API documentation with new fields
    - Document all new data structures
    - Document enhancement configuration options
    - Provide examples of enhanced responses
    - _Requirements: 6.7_
  
  - [ ] 22.2 Update CHANGELOG.md
    - Document new features
    - Note backward compatibility
    - Provide migration examples
  
  - [ ] 22.3 Update README.md with enhancement examples
    - Show how to enable enhancements
    - Show example enhanced responses
    - Explain use cases for each enhancement

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows with real Lean execution
- All enhancements maintain backward compatibility (disabled by default)
- Artifact logging works automatically via existing `ArtifactStore` interface
