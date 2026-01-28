# Requirements Document

## Introduction

This specification defines enhancements to the MCP tools (specifically `search_annotations`) to enable more effective iterative orchestration by LLM agents. Based on research, these enhancements address five critical issues that prevent effective iteration in proof automation: subgoal blindness, induction case splitting, hint provenance tracking, cross-file dependency detection, and progress metrics.

The research demonstrated that iterative orchestration (LLM + MCP tools) achieved 100% success on complex polynomial proofs where single-pass automation achieved 0%. These enhancements will provide LLM orchestrators with the contextual information needed to generate better hypotheses and make informed iteration decisions.

## Glossary

- **System**: The `search_annotations` MCP tool and its supporting domain models
- **LLM_Orchestrator**: An AI agent that iteratively calls MCP tools to solve proof automation tasks
- **Subgoal**: A simplified goal state that remains after applying partial hints
- **Hint**: A lemma, definition, or rule provided to automation to help close a goal
- **Partial_Outcome**: A search result where hints make progress but don't fully close the goal
- **Case**: A branch in an inductive proof (base case or inductive case)
- **Provenance**: The source and relevance information for a hint
- **Dependency**: A cross-file symbol or import required for a theorem
- **Progress_Metric**: A quantitative measure of goal complexity reduction

## Requirements

### Requirement 1: Subgoal Reporting

**User Story:** As an LLM orchestrator, I want to see the simplified goal state after applying partial hints, so that I can generate better hypotheses for the next iteration.

#### Acceptance Criteria

1. WHEN `search_annotations` returns `outcome="partial"`, THE System SHALL include the remaining subgoal in the response
2. WHEN a partial outcome occurs, THE System SHALL include goal complexity metrics before and after hint application
3. WHEN reporting subgoals, THE System SHALL include the specific hints that were applied to reach the partial state
4. THE System SHALL maintain backward compatibility by making subgoal fields optional in the response schema
5. WHEN multiple subgoals remain, THE System SHALL report all remaining subgoals with their complexity metrics

### Requirement 2: Case-Aware Search

**User Story:** As an LLM orchestrator working with inductive proofs, I want to search for hints per-case (base/inductive), so that I can target hints to specific proof branches.

#### Acceptance Criteria

1. WHEN `search_annotations` is called with a `target_case` parameter, THE System SHALL search for hints specific to that case
2. WHEN analyzing a theorem, THE System SHALL detect induction structure automatically
3. WHEN induction structure is detected, THE System SHALL identify case labels (base, inductive, etc.)
4. WHEN returning results for case-aware search, THE System SHALL include case-specific hint recommendations
5. WHEN no `target_case` is specified, THE System SHALL search across all cases (current behavior)
6. THE System SHALL return case-specific progress metrics for each identified case

### Requirement 3: Hint Provenance Tracking

**User Story:** As an LLM orchestrator, I want to know where each hint came from and why it was selected, so that I can prioritize hints intelligently.

#### Acceptance Criteria

1. WHEN returning hints, THE System SHALL include the source category for each hint (goal_symbols, local_context, same_namespace, imports)
2. WHEN a hint originates from a theorem, THE System SHALL include the source theorem name
3. WHEN ranking hints, THE System SHALL include relevance scores for each hint
4. WHEN returning hint provenance, THE System SHALL include the reasoning for why the hint was selected
5. THE System SHALL maintain backward compatibility by making provenance fields optional

### Requirement 4: Cross-File Dependency Detection

**User Story:** As an LLM orchestrator, I need to know when theorems require cross-file hints, so that I can automatically switch from `local_only` to `suggest_global` mode.

#### Acceptance Criteria

1. WHEN analyzing a theorem, THE System SHALL detect missing imports or undefined symbols
2. WHEN cross-file dependencies are detected, THE System SHALL suggest switching to `suggest_global` mode
3. WHEN suggesting mode switch, THE System SHALL provide confidence level in the suggestion
4. THE System SHALL avoid false positives by validating that symbols are truly undefined
5. WHEN returning dependency information, THE System SHALL include the specific missing symbols and suggested imports

### Requirement 5: Progress Metrics

**User Story:** As an LLM orchestrator, I need quantitative progress metrics, so that I can decide whether to iterate or move to the next theorem.

#### Acceptance Criteria

1. WHEN reporting search results, THE System SHALL include goal complexity before hint application
2. WHEN reporting search results, THE System SHALL include goal complexity after hint application
3. WHEN reporting progress, THE System SHALL calculate reduction percentage
4. WHEN progress is blocked, THE System SHALL identify what is blocking progress (missing symbols, type mismatches, etc.)
5. THE System SHALL provide iteration recommendations based on progress metrics

### Requirement 6: Response Schema Extensions

**User Story:** As a developer, I want to extend the response schema to include new fields, so that LLM orchestrators can access enhanced information.

#### Acceptance Criteria

1. THE System SHALL extend `SearchAnnotationsResult` to include optional `subgoal_state` field
2. THE System SHALL extend `SearchAnnotationsResult` to include optional `case_analysis` field
3. THE System SHALL extend `Hint` to include optional `provenance` field
4. THE System SHALL extend `SearchAnnotationsResult` to include optional `dependency_analysis` field
5. THE System SHALL extend `SearchAnnotationsResult` to include optional `progress_metrics` field
6. THE System SHALL maintain API version "0.1.0" for backward compatibility
7. WHEN new fields are present, THE System SHALL document them in the API schema

### Requirement 7: Backward Compatibility

**User Story:** As a user of the MCP tools, I want existing integrations to continue working, so that I don't need to update my code immediately.

#### Acceptance Criteria

1. THE System SHALL make all new fields optional in response schemas
2. WHEN new fields are not populated, THE System SHALL omit them from responses (not return null)
3. THE System SHALL maintain existing field names and types
4. THE System SHALL maintain existing API version "0.1.0"
5. WHEN clients don't request new features, THE System SHALL return responses identical to current behavior

### Requirement 8: Performance Requirements

**User Story:** As an LLM orchestrator, I want enhanced features to have minimal performance impact, so that iteration remains fast.

#### Acceptance Criteria

1. WHEN computing subgoal state, THE System SHALL complete within 100ms overhead
2. WHEN detecting induction structure, THE System SHALL complete within 200ms overhead
3. WHEN computing hint provenance, THE System SHALL complete within 50ms per hint
4. WHEN detecting dependencies, THE System SHALL complete within 150ms overhead
5. WHEN computing progress metrics, THE System SHALL complete within 100ms overhead
6. THE System SHALL maintain total tool execution time under 5 seconds for typical cases

### Requirement 9: Serialization and Parsing

**User Story:** As a developer, I want to serialize and deserialize enhanced data structures, so that they can be stored and transmitted correctly.

#### Acceptance Criteria

1. WHEN serializing `SubgoalState`, THE System SHALL encode it as valid JSON
2. WHEN serializing `CaseAnalysis`, THE System SHALL encode it as valid JSON
3. WHEN serializing `HintProvenance`, THE System SHALL encode it as valid JSON
4. WHEN serializing `DependencyAnalysis`, THE System SHALL encode it as valid JSON
5. WHEN serializing `ProgressMetrics`, THE System SHALL encode it as valid JSON
6. FOR ALL enhanced data structures, parsing then serializing SHALL produce equivalent JSON (round-trip property)

### Requirement 10: Artifact Logging Integration

**User Story:** As a developer debugging proof automation, I want all enhancement data to be logged in artifacts, so that I can inspect what information was provided to the LLM orchestrator.

#### Acceptance Criteria

1. WHEN `search_annotations` completes with enhancements enabled, THE System SHALL include all enhancement data in the stored artifacts
2. WHEN storing artifacts, THE System SHALL include `subgoal_state` in the result.json file if present
3. WHEN storing artifacts, THE System SHALL include `case_analysis` in the result.json file if present
4. WHEN storing artifacts, THE System SHALL include `dependency_analysis` in the result.json file if present
5. WHEN storing artifacts, THE System SHALL include `progress_metrics` in the result.json file if present
6. WHEN storing artifacts, THE System SHALL include hint provenance information in the result.json file if present
7. WHEN storing artifacts, THE System SHALL maintain the existing artifact structure (request.json, result.json, lean_output.log)
8. WHEN enhancement data is logged, THE System SHALL use the existing `ArtifactStore` interface without modifications
