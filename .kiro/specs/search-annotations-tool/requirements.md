# Requirements Document: Search Annotations Tool

## Introduction

The Search Annotations Tool is a Lean proof automation enhancement system that discovers minimal sets of local proof hints to make theorems provable by automation. Unlike the existing probe tool which only checks if automation currently closes a goal, this tool actively searches for the right combination of local hints (lemmas, definitions, rules) that enable automation to succeed, then minimizes that set to a stable, minimal configuration.

## Glossary

- **System**: The Search Annotations Tool
- **Probe_Engine**: The underlying automation testing service that attempts to close goals
- **Theorem_Locator**: Service that finds and validates theorem locations in Lean files
- **Scan_Service**: Service that extracts candidate hints from Lean code
- **Lean_Attempt_Runner**: Service that executes Lean automation attempts
- **Verify_Engine**: Service that validates proof correctness
- **Local_Hint**: A proof annotation (lemma, definition, or rule) used within a specific proof
- **Global_Annotation**: A file-level or project-level attribute like @[aesop] or @[simp]
- **Candidate_Hint**: A potential local hint identified during search
- **Hint_Set**: A collection of local hints being tested together
- **Viability_Check**: Initial validation that a theorem exists and can be processed
- **Baseline_Attempt**: Initial automation attempt without additional hints
- **Search_Strategy**: Algorithm for exploring hint combinations (beam or greedy)
- **Delta_Debugging**: Minimization technique that removes hints while preserving success
- **Automation_Tool**: Proof automation system (aesop or grind)
- **Proof_Patch**: Ready-to-paste Lean code containing the discovered proof
- **Worktree**: Isolated Git workspace for safe experimentation

## Requirements

### Requirement 1: Theorem Viability Validation

**User Story:** As a Lean developer, I want the system to validate that my target theorem exists and is processable, so that I don't waste time on invalid inputs.

#### Acceptance Criteria

1. WHEN a file path and theorem_id are provided, THE System SHALL verify the file exists and is readable
2. WHEN locating a theorem, THE System SHALL use the Theorem_Locator service to find the theorem's position
3. WHEN a theorem cannot be located, THE System SHALL return a descriptive error indicating the failure reason
4. WHEN the Lean environment cannot be entered, THE System SHALL return an error with diagnostic information
5. WHEN the viability check exceeds the viability_check_s budget, THE System SHALL terminate and return a timeout error
6. THE System SHALL complete viability checks without modifying any files

### Requirement 2: Baseline Automation Assessment

**User Story:** As a Lean developer, I want to know if automation already closes my goal, so that I don't search for hints unnecessarily.

#### Acceptance Criteria

1. WHEN viability checks pass, THE System SHALL attempt to close the goal using the Probe_Engine with the primary automation tool
2. WHEN the primary automation tool is aesop, THE System SHALL configure it according to provided parameters
3. WHEN a secondary automation tool is specified, THE System SHALL attempt it if the primary fails
4. WHEN baseline automation succeeds, THE System SHALL return success without performing hint search
5. WHEN baseline attempts exceed baseline_probe_s budget, THE System SHALL record timeout and proceed to search
6. THE System SHALL record all baseline attempt outcomes for the final report

### Requirement 3: Candidate Hint Generation

**User Story:** As a Lean developer, I want the system to identify relevant proof hints from multiple sources, so that the search explores high-quality candidates.

#### Acceptance Criteria

1. WHEN generating candidates, THE System SHALL extract hints from all enabled candidate sources
2. WHEN goal_symbols is enabled, THE System SHALL extract symbols appearing in the goal statement
3. WHEN local_context is enabled, THE System SHALL extract available hypotheses and local definitions
4. WHEN same_namespace is enabled, THE System SHALL extract declarations from the theorem's namespace
5. WHEN nearby_decls is enabled, THE System SHALL extract declarations within a configurable distance
6. WHEN original_proof_refs is enabled, THE System SHALL extract lemmas referenced in the original proof
7. WHEN allow_simp_hints is true, THE System SHALL include simp lemma candidates
8. WHEN allow_unfold_hints is true, THE System SHALL include definition unfolding candidates
9. THE System SHALL limit candidates per source to max_candidates_per_source
10. THE System SHALL rank candidates prioritizing .def lemmas, [simp] lemmas, and original proof references

### Requirement 4: Hint Set Search Execution

**User Story:** As a Lean developer, I want the system to efficiently search for hint combinations that enable automation, so that I can find working proofs quickly.

#### Acceptance Criteria

1. WHEN search strategy is greedy, THE System SHALL start with an empty hint set and add the best candidate each step
2. WHEN search strategy is beam, THE System SHALL maintain beam_width hint sets and expand by adding candidates
3. WHEN testing a hint set, THE System SHALL use the Lean_Attempt_Runner with the configured automation tool
4. WHEN a hint set closes the goal, THE System SHALL record it as a successful configuration
5. WHEN stop_on_first_close is true and a closing hint set is found, THE System SHALL terminate search immediately
6. WHEN stop_on_first_close is false, THE System SHALL continue searching until max_steps or budget exhaustion
7. WHEN a hint set exceeds max_hints, THE System SHALL exclude it from further exploration
8. WHEN search exceeds search_total_s budget, THE System SHALL return the best partial result found
9. THE System SHALL score hint sets by automation outcome quality

### Requirement 5: Hint Set Minimization

**User Story:** As a Lean developer, I want the system to minimize the hint set to the smallest stable configuration, so that my proof is clean and maintainable.

#### Acceptance Criteria

1. WHEN a closing hint set is found, THE System SHALL apply delta-debugging minimization
2. WHEN minimizing, THE System SHALL iteratively remove hints while preserving the closing property
3. WHEN a hint removal causes failure, THE System SHALL restore that hint to the set
4. WHEN minimization exceeds minimize_total_s budget, THE System SHALL return the current minimized state
5. THE System SHALL verify the final minimized set closes the goal
6. THE System SHALL ensure the minimized set is stable across multiple verification attempts

### Requirement 6: Proof Patch Generation

**User Story:** As a Lean developer, I want a ready-to-paste proof script with the discovered hints, so that I can immediately apply the solution.

#### Acceptance Criteria

1. WHEN generating a proof patch, THE System SHALL format it as valid Lean syntax
2. WHEN the closing automation is simp and prefer_simp_over_aesop is true, THE System SHALL emit a simp-based proof
3. WHEN the closing automation is aesop, THE System SHALL emit an aesop-based proof with local hints
4. WHEN emit_compact is true, THE System SHALL format hints on a single line
5. WHEN emit_compact is false, THE System SHALL format hints with one per line
6. WHEN simp_only_list is true, THE System SHALL emit "simp only [...]" instead of "simp_all [...]"
7. THE System SHALL NOT replace definitional proofs (rfl, Iff.rfl, trivial)
8. THE System SHALL include the automation configuration used in the proof patch

### Requirement 7: Global Annotation Suggestions

**User Story:** As a Lean developer, I want optional suggestions for global annotations, so that I can improve automation across my entire project.

#### Acceptance Criteria

1. WHEN mode is local_only, THE System SHALL NOT generate global annotation suggestions
2. WHEN mode is suggest_global, THE System SHALL analyze the minimized hint set for globalization candidates
3. WHEN a hint appears frequently effective, THE System SHALL suggest adding @[aesop] or @[simp] attributes
4. WHEN suggesting global annotations, THE System SHALL provide rationale for each suggestion
5. THE System SHALL NOT apply global annotations unless allow_global_edits is true
6. WHEN allow_global_edits is false, THE System SHALL only provide advisory suggestions

### Requirement 8: Workspace Isolation

**User Story:** As a Lean developer, I want the system to perform experiments in isolated workspaces, so that my working directory remains unchanged.

#### Acceptance Criteria

1. WHEN workspace mode is git_worktree, THE System SHALL create an isolated Git worktree for experiments
2. WHEN experiments complete, THE System SHALL clean up the worktree unless keep_artifacts is true
3. WHEN keep_artifacts is true, THE System SHALL preserve the worktree and log its location
4. WHEN the system crashes or times out, THE System SHALL ensure worktree cleanup occurs
5. THE System SHALL NOT leave orphan processes after completion or failure
6. THE System SHALL NOT modify files in the original working directory during search

### Requirement 9: Budget Enforcement

**User Story:** As a Lean developer, I want configurable time budgets for each phase, so that the system doesn't run indefinitely.

#### Acceptance Criteria

1. WHEN any phase exceeds its time budget, THE System SHALL terminate that phase gracefully
2. WHEN viability_check_s is exceeded, THE System SHALL return a viability timeout error
3. WHEN baseline_probe_s is exceeded, THE System SHALL record baseline timeout and proceed to search
4. WHEN search_total_s is exceeded, THE System SHALL return the best hint set found so far
5. WHEN candidate_trial_s is exceeded for a single trial, THE System SHALL mark that trial as timeout
6. WHEN minimize_total_s is exceeded, THE System SHALL return the current minimization state
7. WHEN final_verify_s is exceeded, THE System SHALL return a verification timeout error
8. THE System SHALL track and report time spent in each phase

### Requirement 10: Result Reporting

**User Story:** As a Lean developer, I want comprehensive results including timing, evidence, and artifacts, so that I can understand what the system did.

#### Acceptance Criteria

1. WHEN returning results, THE System SHALL include status (success/fail)
2. WHEN returning results, THE System SHALL include viability check details
3. WHEN returning results, THE System SHALL include baseline attempt outcomes
4. WHEN returning results, THE System SHALL include the final hint set and proof patch
5. WHEN returning results, THE System SHALL include evidence of the closing configuration
6. WHEN mode is suggest_global, THE System SHALL include global annotation suggestions
7. WHEN returning results, THE System SHALL include timing breakdown for all phases
8. WHEN returning results, THE System SHALL include paths to artifacts (request, result, logs)
9. THE System SHALL format output as deterministic JSON with stable ordering
10. THE System SHALL ensure hint ordering is stable and reproducible

### Requirement 11: Service Integration Architecture

**User Story:** As a system architect, I want the tool to reuse core services directly, so that we maintain architectural consistency and avoid tool-to-tool coupling.

#### Acceptance Criteria

1. THE System SHALL call Theorem_Locator service directly for theorem location
2. THE System SHALL call Scan_Service directly for candidate extraction
3. THE System SHALL call Lean_Attempt_Runner directly for automation attempts
4. THE System SHALL call Probe_Engine directly for baseline probing
5. THE System SHALL call Verify_Engine directly for final verification
6. THE System SHALL NOT invoke other MCP tools
7. THE System SHALL receive all service dependencies via dependency injection
8. THE System SHALL directly use existing core services without additional port abstractions

### Requirement 12: Error Handling and Diagnostics

**User Story:** As a Lean developer, I want clear error messages and diagnostic information, so that I can understand and fix problems.

#### Acceptance Criteria

1. WHEN a file cannot be read, THE System SHALL return an error with the file path and reason
2. WHEN a theorem cannot be located, THE System SHALL return an error with the theorem_id and search details
3. WHEN the Lean environment fails to load, THE System SHALL return diagnostic information from Lean
4. WHEN search finds no closing hint set, THE System SHALL return the best partial results and explain why
5. WHEN minimization fails, THE System SHALL return the pre-minimization hint set with explanation
6. WHEN verification fails, THE System SHALL return the verification error details
7. THE System SHALL include structured error types for programmatic handling
8. THE System SHALL log detailed diagnostic information to artifact files

### Requirement 13: Deterministic Output

**User Story:** As a Lean developer, I want reproducible results with stable formatting, so that I can rely on consistent behavior.

#### Acceptance Criteria

1. WHEN generating JSON output, THE System SHALL order keys deterministically
2. WHEN listing hints, THE System SHALL order them deterministically by name
3. WHEN listing candidates, THE System SHALL order them deterministically by ranking criteria
4. WHEN formatting proof patches, THE System SHALL use consistent whitespace and indentation
5. FOR ALL identical inputs and configurations, THE System SHALL produce identical output
6. THE System SHALL document any sources of non-determinism in the output

### Requirement 14: Skeleton Search Support

**User Story:** As a Lean developer, I want optional skeleton-based search for complex proofs, so that I can find structured proof outlines.

#### Acceptance Criteria

1. WHEN skeleton.enabled is false, THE System SHALL perform standard hint search
2. WHEN skeleton.enabled is true, THE System SHALL explore proof skeletons with tactic moves
3. WHEN exploring skeletons, THE System SHALL limit depth to skeleton.max_depth
4. WHEN exploring skeletons, THE System SHALL use moves from skeleton.moves list
5. THE System SHALL combine skeleton exploration with hint search
6. THE System SHALL report skeleton structure in successful results

### Requirement 15: Proof Style Preservation

**User Story:** As a Lean developer, I want the system to respect existing proof styles, so that my codebase remains consistent.

#### Acceptance Criteria

1. WHEN the original proof is "rfl", THE System SHALL NOT replace it with automation
2. WHEN the original proof is "Iff.rfl", THE System SHALL NOT replace it with automation
3. WHEN the original proof is "trivial", THE System SHALL NOT replace it with automation
4. WHEN prefer_simp_over_aesop is true and simp closes, THE System SHALL emit a simp proof
5. WHEN prefer_simp_over_aesop is false and aesop closes, THE System SHALL emit an aesop proof
6. THE System SHALL preserve the indentation style of the original file
