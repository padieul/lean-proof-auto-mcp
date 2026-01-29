# Requirements Document

## Introduction

This document specifies requirements for enhancing the lean-proof-auto-mcp system to support LLM-guided proof refactoring through iterative orchestration. The system will enable refactoring of 20-30% of mathlib proofs from tactical proofs to automation-based proofs with explicit hints.

The key innovation is replacing regex-based hint extraction with LeanInteract for 95%+ accuracy, enabling rich feedback mechanisms for LLM-guided iterative refinement. The system combines deterministic search, LLM reasoning, and fast validation feedback loops to bridge the gap between tactical proofs and hint-based automation.

## Glossary

- **System**: The lean-proof-auto-mcp enhanced system for LLM-guided proof refactoring
- **LeanInteract**: Python library providing REPL-based interaction with Lean 4
- **Declaration**: A Lean theorem, lemma, or definition with name, type, value, and metadata
- **Hint**: A lemma or definition suggestion for automation (e.g., add_safe, add_simp)
- **Proof_State**: The current goal, hypotheses, and type context during proof construction
- **Candidate_Source**: A mechanism for extracting potential hints (goal_symbols, local_context, same_namespace, original_proof_refs)
- **Tactical_Proof**: A proof using explicit tactics (rw, simp, exact, etc.)
- **Automation_Proof**: A proof using automation with hints (aesop, simp, omega, grind)
- **Validation_Result**: The outcome of validating a proof attempt (success, error, incomplete, timeout)
- **Feedback**: Structured information about proof attempts including proof states, partial progress, and suggestions
- **LLM**: Large Language Model used for proof reasoning and generation
- **MCP_Tool**: Model Context Protocol tool exposed to the LLM
- **Refactoring**: Converting a tactical proof to an automation proof with hints

## Requirements

### Requirement 1: LeanInteract-Based Declaration Extraction

**User Story:** As a proof refactoring system, I want to extract accurate declaration information from Lean files, so that I can identify theorems and their proof structures reliably.

#### Acceptance Criteria

1. WHEN a file path is provided, THE System SHALL extract all declarations using LeanInteract FileCommand with declarations=True
2. FOR ALL extracted declarations, THE System SHALL provide the fully qualified name, type signature, proof value, attributes, and position range
3. WHEN a declaration has a proof value, THE System SHALL extract both the pretty-printed text and the constants list
4. THE System SHALL achieve 95% or greater accuracy for declaration extraction compared to manual inspection

### Requirement 2: Accurate Proof Reference Extraction

**User Story:** As a proof refactoring system, I want to extract lemma references from proofs accurately, so that I can identify which hints are needed for automation.

#### Acceptance Criteria

1. WHEN extracting proof references, THE System SHALL use declaration.value.constants as the primary source
2. WHEN declaration.value.constants is incomplete, THE System SHALL parse declaration.value.pp text as a fallback
3. FOR ALL extracted references, THE System SHALL validate them against the file's declaration list
4. THE System SHALL achieve 95% or greater accuracy for lemma extraction from proofs
5. WHEN a proof contains no lemma references, THE System SHALL return an empty list without errors

### Requirement 3: Theorem Context Extraction

**User Story:** As an LLM reasoning about proofs, I want rich context about theorems, so that I can understand what's available and make informed refactoring decisions.

#### Acceptance Criteria

1. WHEN a theorem identifier is provided, THE System SHALL extract the complete theorem statement from declaration.type
2. WHEN a theorem has hypotheses, THE System SHALL extract them from the initial proof state
3. THE System SHALL extract all declarations visible in the theorem's scope
4. THE System SHALL extract the current namespace from declaration.scope.curr_namespace
5. WHEN context extraction fails, THE System SHALL return an error with diagnostic information

### Requirement 4: Enhanced Search Tool with LLM Control

**User Story:** As an LLM refactoring proofs, I want to control search parameters dynamically, so that I can adjust search depth based on theorem complexity.

#### Acceptance Criteria

1. THE System SHALL provide a search_automated_proof MCP tool replacing the existing search_annotations tool
2. THE System SHALL support search_depth parameter with values: quick, normal, deep, exhaustive
3. WHEN search_depth is quick, THE System SHALL use search_budget_s=10.0 and max_candidates=20
4. WHEN search_depth is normal, THE System SHALL use search_budget_s=30.0 and max_candidates=50
5. WHEN search_depth is deep, THE System SHALL use search_budget_s=60.0 and max_candidates=100
6. WHEN search_depth is exhaustive, THE System SHALL use search_budget_s=120.0 and max_candidates=200
8. THE System SHALL allow LLM to override individual parameters regardless of search_depth preset
9. WHEN search_annotations is called, THE System SHALL return an error directing users to use search_automated_proof instead

### Requirement 5: Candidate Source Configuration

**User Story:** As an LLM refactoring proofs, I want to select which candidate sources to use, so that I can focus on the most relevant hints for each theorem.

#### Acceptance Criteria

1. THE System SHALL support four candidate sources: goal_symbols, local_context, same_namespace, original_proof_refs
2. WHEN goal_symbols is selected, THE System SHALL extract candidates from the theorem's type signature using LeanInteract
3. WHEN local_context is selected, THE System SHALL extract candidates from proof state hypotheses using LeanInteract
4. WHEN same_namespace is selected, THE System SHALL extract candidates from declarations in the same namespace using LeanInteract
5. WHEN original_proof_refs is selected, THE System SHALL extract candidates from the original proof using declaration.value.constants
6. THE System SHALL enable original_proof_refs by default in candidate source lists
7. FOR ALL candidate sources, THE System SHALL support per-source candidate limits via max_candidates_per_source parameter

### Requirement 6: Rich Feedback Mechanisms

**User Story:** As an LLM iterating on proof attempts, I want detailed feedback about what worked and what didn't, so that I can refine my approach effectively.

#### Acceptance Criteria

1. WHEN return_proof_states is true, THE System SHALL return initial and post-hint proof states
2. WHEN return_partial_progress is true, THE System SHALL return hints that helped, goal complexity reduction, and progress scores
3. WHEN return_context is true, THE System SHALL return theorem statement, original proof, namespace, and in-scope declarations
4. WHEN return_similar_proofs is true, THE System SHALL return similar theorems with similarity scores and their proofs
5. WHEN return_search_trace is true, THE System SHALL return detailed step-by-step search execution trace
6. THE System SHALL always return tactical suggestions with confidence scores and reasoning

### Requirement 7: Proof Validation Tool

**User Story:** As an LLM generating proof attempts, I want fast validation with detailed feedback, so that I can iterate quickly toward a correct proof.

#### Acceptance Criteria

1. THE System SHALL provide a try_automated_proof MCP tool for validating proof attempts
2. WHEN a proof attempt is provided, THE System SHALL validate it using LeanInteract Command within the specified timeout
3. WHEN validation succeeds, THE System SHALL return status=success with verification confirmation
4. WHEN validation fails with an error, THE System SHALL return status=error with error message and location information
5. WHEN validation times out, THE System SHALL return status=timeout with partial results if available
6. WHEN validation produces an incomplete proof, THE System SHALL return status=incomplete with remaining proof state and goals
7. FOR ALL validation results, THE System SHALL return tactical suggestions for next steps
8. THE System SHALL complete validation within 10 seconds by default

### Requirement 8: Proof Context Tool

**User Story:** As an LLM learning refactoring patterns, I want to see similar proofs and their context, so that I can pattern-match and apply successful strategies.

#### Acceptance Criteria

1. THE System SHALL provide a get_proof_context MCP tool for extracting theorem context
2. WHEN a theorem identifier is provided, THE System SHALL return the complete theorem statement and original proof
3. THE System SHALL return all hypotheses available in the initial proof state
4. THE System SHALL return all declarations visible in the theorem's scope
5. WHEN include_similar_proofs is true, THE System SHALL return similar theorems with similarity scores above 0.7
6. FOR ALL similar proofs, THE System SHALL return their proof bodies and hints used if available

### Requirement 9: Hexagonal Architecture Compliance

**User Story:** As a system maintainer, I want clear separation between MCP tools, business logic, and Lean interaction, so that the system is maintainable and testable.

#### Acceptance Criteria

1. THE System SHALL implement three distinct layers: MCP Tool Layer, Core Domain Layer, LeanInteract Adapter Layer
2. THE Core Domain Layer SHALL NOT depend on MCP tool interfaces or LeanInteract implementation details
3. THE LeanInteract Adapter Layer SHALL encapsulate all LeanInteract interaction behind abstract interfaces
4. WHEN LeanInteract is unavailable, THE System SHALL provide graceful degradation with clear error messages
5. THE System SHALL use dependency injection for all cross-layer dependencies

### Requirement 10: Performance Requirements

**User Story:** As a user refactoring proofs, I want fast iteration cycles, so that I can refactor multiple theorems efficiently.

#### Acceptance Criteria

1. WHEN search_depth is quick, THE System SHALL complete search within 15 seconds
2. WHEN search_depth is normal, THE System SHALL complete search within 40 seconds
3. WHEN search_depth is deep, THE System SHALL complete search within 90 seconds
4. WHEN validating a proof attempt, THE System SHALL complete within 10 seconds by default
5. THE System SHALL complete a full iteration cycle (search + validate) within 50 seconds for normal depth
6. THE System SHALL reuse LeanInteract server instances across multiple operations to avoid startup overhead

### Requirement 11: Error Handling and Reliability

**User Story:** As a system user, I want robust error handling, so that the system continues operating even when individual operations fail.

#### Acceptance Criteria

1. WHEN LeanInteract crashes, THE System SHALL detect the failure and restart the server automatically
2. WHEN a timeout occurs, THE System SHALL return partial results with timeout status
3. WHEN invalid input is provided, THE System SHALL return a descriptive error message without crashing
4. THE System SHALL log all LeanInteract interactions for debugging purposes
5. WHEN validation produces false positives, THE System SHALL detect them through secondary verification
6. THE System SHALL achieve less than 5% false positive rate for refactored proofs

### Requirement 12: Candidate Generator Refactoring

**User Story:** As a system component, I want to use LeanInteract instead of regex for hint extraction, so that I can achieve 95%+ accuracy.

#### Acceptance Criteria

1. THE Candidate_Generator SHALL use LeanInteract for all proof reference extraction
2. THE Candidate_Generator SHALL NOT use regex-based parsing for lemma identification
3. WHEN inferring hint types, THE Candidate_Generator SHALL use declaration attributes from LeanInteract
4. THE Candidate_Generator SHALL support all four candidate sources using LeanInteract-based extraction
5. WHEN a candidate source fails, THE Candidate_Generator SHALL log the error and continue with remaining sources

### Requirement 13: Feedback Builder Component

**User Story:** As a system component, I want to build structured feedback from search results, so that LLMs receive actionable information for iteration.

#### Acceptance Criteria

1. THE System SHALL implement a Feedback_Builder component for generating structured feedback
2. WHEN search produces partial results, THE Feedback_Builder SHALL identify which hints helped and by how much
3. THE Feedback_Builder SHALL calculate goal complexity reduction as a percentage
4. THE Feedback_Builder SHALL generate tactical suggestions with confidence scores between 0.0 and 1.0
5. FOR ALL suggestions, THE Feedback_Builder SHALL provide reasoning explaining why the suggestion is relevant

### Requirement 14: Success Rate Targets

**User Story:** As a project stakeholder, I want to achieve 20-30% refactoring success rate, so that the system provides meaningful value for mathlib maintenance.

#### Acceptance Criteria

1. THE System SHALL successfully refactor 20% or more of trivial theorems (reflexivity, symmetry, transitivity)
2. THE System SHALL successfully refactor 10% or more of simple theorems (forward reasoning, simple rewrites)
3. THE System SHALL successfully refactor 5% or more of medium theorems (rewrite chains, tactics + automation)
4. THE System SHALL achieve an overall success rate between 20% and 35% across all theorem complexity tiers
5. WHEN a theorem cannot be refactored, THE System SHALL preserve the original proof unchanged

### Requirement 15: Iteration Efficiency

**User Story:** As an LLM refactoring proofs, I want to converge on solutions quickly, so that I can refactor theorems within reasonable time budgets.

#### Acceptance Criteria

1. THE System SHALL enable successful refactoring within 2-3 LLM iterations on average
2. WHEN an iteration fails, THE System SHALL provide feedback that reduces the search space for the next iteration
3. THE System SHALL detect repeated failed attempts and suggest alternative strategies
4. WHEN 5 iterations fail to produce a valid proof, THE System SHALL recommend keeping the original proof
5. THE System SHALL complete 3-5 iteration cycles within 2-3 minutes for normal search depth

### Requirement 16: Proof State Inspection

**User Story:** As an LLM reasoning about proofs, I want to see proof states at each step, so that I can understand what remains to be proven.

#### Acceptance Criteria

1. THE System SHALL extract initial proof states using LeanInteract Command with sorry
2. WHEN a tactic is applied, THE System SHALL return the resulting proof state using LeanInteract ProofStep
3. FOR ALL proof states, THE System SHALL return the current goal, hypotheses, and type context
4. WHEN multiple goals exist, THE System SHALL return all goals with their indices
5. WHEN a proof state cannot be extracted, THE System SHALL return an error with diagnostic information

### Requirement 17: Validation Result Structure

**User Story:** As an LLM receiving validation results, I want structured information about failures, so that I can fix errors systematically.

#### Acceptance Criteria

1. WHEN validation fails with an error, THE Validation_Result SHALL include the error message and location (line and column)
2. WHEN validation produces an incomplete proof, THE Validation_Result SHALL include remaining goals and current hypotheses
3. WHEN validation times out, THE Validation_Result SHALL include the last known proof state
4. FOR ALL validation results, THE Validation_Result SHALL include suggestions for next steps
5. WHEN validation succeeds, THE Validation_Result SHALL include confirmation that the proof was verified by Lean

### Requirement 18: Similar Proof Discovery

**User Story:** As an LLM learning refactoring patterns, I want to find similar proofs, so that I can apply successful strategies from analogous theorems.

#### Acceptance Criteria

1. WHEN similar proofs are requested, THE System SHALL compute similarity scores based on theorem structure and type signatures
2. THE System SHALL return similar proofs with similarity scores of 0.7 or higher
3. FOR ALL similar proofs, THE System SHALL return the theorem statement, proof body, and hints used
4. THE System SHALL rank similar proofs by similarity score in descending order
5. WHEN no similar proofs exist above the threshold, THE System SHALL return an empty list

### Requirement 19: Search Strategy Configuration

**User Story:** As an LLM controlling search, I want to select search strategies, so that I can optimize for different theorem types.

#### Acceptance Criteria

1. THE System SHALL support three search strategies: greedy, beam, exhaustive
2. WHEN strategy is greedy, THE System SHALL explore candidates in rank order and stop at first success
3. WHEN strategy is beam, THE System SHALL maintain beam_width parallel search paths
4. WHEN strategy is exhaustive, THE System SHALL try all candidate combinations up to max_search_steps
5. THE System SHALL allow LLM to configure beam_width, max_search_steps, and max_hints_in_set parameters

### Requirement 20: Automation Mode Selection

**User Story:** As an LLM refactoring proofs, I want to select automation modes, so that I can use the most appropriate automation for each theorem.

#### Acceptance Criteria

1. THE System SHALL support four automation modes: aesop, simp, omega, grind
2. WHEN automation_mode is aesop, THE System SHALL use aesop with configured hints
3. WHEN automation_mode is simp, THE System SHALL use simp with configured simp lemmas
4. WHEN automation_mode is omega, THE System SHALL use omega for arithmetic goals
5. WHEN automation_mode is grind, THE System SHALL use grind for equational reasoning
6. THE System SHALL support automation_secondary parameter for fallback automation when primary fails

### Requirement 21: Hint Type Configuration

**User Story:** As an LLM configuring search, I want to control which hint types are allowed, so that I can focus on relevant automation strategies.

#### Acceptance Criteria

1. THE System SHALL support allow_simp_hints parameter for including simp lemmas
2. THE System SHALL support allow_unfold_hints parameter for including definitions to unfold
3. THE System SHALL support allow_unsafe_hints parameter for including unsafe aesop rules
4. WHEN a hint type is disabled, THE System SHALL exclude candidates of that type from search
5. THE System SHALL infer hint types from declaration attributes using LeanInteract

### Requirement 22: Hint Set Minimization

**User Story:** As a proof maintainer, I want minimal hint sets, so that refactored proofs are concise and maintainable.

#### Acceptance Criteria

1. WHEN minimize_hints is true, THE System SHALL attempt to reduce the hint set after finding a solution
2. THE System SHALL remove hints one at a time and verify the proof still closes
3. THE System SHALL complete minimization within the minimize_budget_s time limit
4. WHEN minimization times out, THE System SHALL return the best minimized set found so far
5. THE System SHALL preserve proof correctness during minimization by validating each reduction

### Requirement 23: Metadata and Traceability

**User Story:** As a system user, I want detailed metadata about search execution, so that I can understand what was tried and debug failures.

#### Acceptance Criteria

1. FOR ALL search results, THE System SHALL return metadata including Lean version, Lake version, and workspace mode
2. THE System SHALL return the search_depth, candidate_sources, and automation_mode used
3. THE System SHALL return timing information for each phase: viability check, baseline probe, candidate generation, search execution, minimization
4. WHEN search_trace is requested, THE System SHALL return step-by-step execution details with hint sets tried and outcomes
5. THE System SHALL return the total number of candidate combinations attempted

### Requirement 24: Existing Tool Migration to LeanInteract

**User Story:** As a system maintainer, I want all existing tools to use LeanInteract consistently, so that the system has a unified foundation for Lean interaction.

#### Acceptance Criteria

1. THE probe MCP tool SHALL use LeanInteract for all Lean interaction instead of direct Lean CLI calls
2. THE probe_file MCP tool SHALL use LeanInteract for file-level operations instead of direct Lean CLI calls
3. THE verify MCP tool SHALL use LeanInteract for proof verification instead of direct Lean CLI calls
4. WHEN any existing tool interacts with Lean, THE System SHALL route the interaction through the LeanInteract Adapter Layer
5. THE System SHALL ensure all existing tools maintain their current functionality after migration to LeanInteract
6. WHEN LeanInteract is unavailable, THE System SHALL provide clear error messages for all tools indicating the missing dependency

### Requirement 25: Test Suite Migration

**User Story:** As a system developer, I want the test suite updated to reflect LeanInteract-based implementation, so that tests validate the new architecture correctly.

#### Acceptance Criteria

1. THE System SHALL update all tests for search_annotations to work with the new search_automated_proof tool
2. THE System SHALL remove or update tests that rely on regex-based hint extraction
3. THE System SHALL add tests validating LeanInteract-based candidate source extraction
4. THE System SHALL add tests validating the accuracy of original_proof_refs extraction using declaration.value.constants
5. WHEN tests mock Lean interaction, THE System SHALL mock the LeanInteract Adapter Layer interfaces instead of Lean CLI
6. THE System SHALL ensure test coverage remains at 80% or greater after migration

### Requirement 26: Backward Compatibility

**User Story:** As a system integrator, I want backward compatibility with existing workflows, so that current usage patterns continue functioning.

#### Acceptance Criteria

1. THE System SHALL maintain the existing MCP tool interface for probe, probe_file, and verify tools
2. WHEN new parameters are added to search_automated_proof, THE System SHALL provide sensible defaults that preserve search_annotations behavior
3. THE System SHALL support Lean 4.26.0-rc1 or later versions
4. THE System SHALL maintain compatibility with the current workspace configuration format
5. WHEN existing code calls search_annotations, THE System SHALL return an error message directing users to use search_automated_proof

### Requirement 27: Comprehensive Testing and Validation

**User Story:** As a system developer, I want comprehensive testing, so that I can verify correctness and prevent regressions.

#### Acceptance Criteria

1. THE System SHALL have unit tests for all Core Domain Layer components
2. THE System SHALL have integration tests for LeanInteract Adapter Layer components
3. THE System SHALL have end-to-end tests validating the complete refactoring workflow on real mathlib theorems
4. THE System SHALL achieve 80% or greater code coverage after migration
5. THE System SHALL validate all refactored proofs against Lean to ensure correctness
6. THE System SHALL have tests validating that probe, probe_file, and verify work correctly with LeanInteract

### Requirement 28: LeanInteract Foundation

**User Story:** As a system architect, I want LeanInteract as the sole foundation for Lean interaction, so that the system has consistent, reliable communication with Lean.

#### Acceptance Criteria

1. THE System SHALL use LeanInteract for all Lean interaction across all components
2. THE System SHALL NOT use direct Lean CLI calls, regex parsing of Lean output, or file-based communication
3. THE System SHALL use lean-interact-runner as the execution wrapper for LeanInteract
4. WHEN LeanInteract server crashes, THE System SHALL detect the failure and restart automatically
5. THE System SHALL maintain a single LeanInteract server instance per file to avoid startup overhead
6. THE System SHALL log all LeanInteract requests and responses for debugging purposes
