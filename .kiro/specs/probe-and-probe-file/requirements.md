# Requirements Document

## Introduction

This document specifies the requirements for the probe and probe_file tools, which extend the verify execution primitive into empirical measurement of automation behavior. These tools answer one question: What actually happens if we try automation here, under controlled conditions?

The probe tool runs a single automation attempt (aesop, aesop?, or grind) on a single theorem and classifies the outcome deterministically. The probe_file tool runs probe across many theorems in a file to produce a heatmap of automation behavior for triage and prioritization.

These tools are measurement primitives that do not change code, do not search, and do not annotate. They fit into the pipeline as: scan_file → scan_theorem → rank_targets → probe/probe_file (empirical measurement) → search_annotations (only for promising cases).

## Glossary

- **Probe**: A single-theorem automation attempt that measures what happens when automation is applied
- **Automation_Mode**: The type of automation to attempt (aesop, aesop?, or grind)
- **Probe_Result**: The structured outcome of a probe attempt including classification
- **Classification**: A deterministic category for probe outcomes (trivial, promising, failed, timed_out)
- **Heatmap**: An aggregated view of automation behavior across multiple theorems in a file
- **LeanInteract**: The library used for programmatic access to Lean 4 through the Lean REPL
- **Workspace**: An isolated execution environment for running Lean verification
- **Theorem_ID**: A unique identifier for a theorem within a Lean file
- **Budget**: A hard wall-clock time limit for automation attempts

## Requirements

### Requirement 1: Single-Theorem Automation Measurement

**User Story:** As a developer evaluating automation potential, I want to run exactly one automation attempt on a single theorem, so that I can measure what actually happens under controlled conditions.

#### Acceptance Criteria

1. WHEN probe is invoked with a theorem and automation mode, THE Probe_Tool SHALL create an isolated workspace using the same mechanism as verify
2. WHEN probe constructs a verification harness, THE Probe_Tool SHALL import the file, focus the target theorem, and run exactly one automation command
3. WHEN probe executes Lean, THE Probe_Tool SHALL use the same LeanInteract-backed runner as verify
4. WHEN probe runs automation, THE Probe_Tool SHALL enforce a hard wall-clock budget
5. WHEN probe completes, THE Probe_Tool SHALL collect success/failure/timeout status, diagnostics, and optional aesop? suggestion text
6. THE Probe_Tool SHALL never modify source code
7. THE Probe_Tool SHALL never apply patches
8. THE Probe_Tool SHALL support exactly one automation mode per call (aesop, aesop?, or grind)

### Requirement 2: Deterministic Outcome Classification

**User Story:** As a system consuming probe results, I want deterministic classification of automation outcomes, so that I can reliably make decisions about whether search is worth it.

#### Acceptance Criteria

1. WHEN automation closes the goal quickly, THE Probe_Tool SHALL classify the outcome as "trivial"
2. WHEN automation fails but produces shallow subgoals or short trace, THE Probe_Tool SHALL classify the outcome as "promising"
3. WHEN automation fails decisively, THE Probe_Tool SHALL classify the outcome as "failed"
4. WHEN the budget is exhausted, THE Probe_Tool SHALL classify the outcome as "timed_out"
5. WHEN a toolchain or execution error occurs, THE Probe_Tool SHALL classify the outcome as "error"
6. FOR ALL identical inputs, THE Probe_Tool SHALL produce identical classification outputs

### Requirement 3: Structured Probe API

**User Story:** As a tool consumer, I want a well-defined API for probe, so that I can integrate it into automated workflows.

#### Acceptance Criteria

1. WHEN probe is invoked, THE Probe_Tool SHALL accept an input schema with api_version, scope (file and theorem_id), mode, budget_s, and runner configuration
2. WHEN probe completes, THE Probe_Tool SHALL return an output schema with api_version, status, probe_result, diagnostics, timing, metadata, and run_id
3. THE Probe_Tool SHALL include the automation mode in the probe_result
4. THE Probe_Tool SHALL include the outcome classification in the probe_result
5. WHEN the mode is "aesop?", THE Probe_Tool SHALL include suggested_script in the probe_result if successful
6. THE Probe_Tool SHALL include structured diagnostics with severity, message, and location
7. THE Probe_Tool SHALL include timing information with elapsed_ms and budget_s
8. THE Probe_Tool SHALL include metadata with workspace_mode, lean_version, lake_version, and repo_commit

### Requirement 4: Batch Automation Heatmap

**User Story:** As a developer triaging automation opportunities, I want to run probe across many theorems in a file, so that I can see where automation works, almost works, or is hopeless.

#### Acceptance Criteria

1. WHEN probe_file is invoked, THE Probe_File_Tool SHALL use scan_file output to enumerate theorems in stable order
2. FOR ALL theorems in the enumeration, THE Probe_File_Tool SHALL call probe with fixed parameters
3. WHEN probe_file runs probe on a theorem, THE Probe_File_Tool SHALL enforce per-theorem budget isolation
4. WHEN probe_file completes, THE Probe_File_Tool SHALL aggregate results into a summary distribution
5. WHEN probe_file returns results, THE Probe_File_Tool SHALL include both per-theorem results and file-level statistics
6. WHEN some theorems fail, THE Probe_File_Tool SHALL allow partial success and not abort the run
7. THE Probe_File_Tool SHALL maintain deterministic ordering of results

### Requirement 5: Structured Probe_File API

**User Story:** As a tool consumer, I want a well-defined API for probe_file, so that I can batch-process files for automation analysis.

#### Acceptance Criteria

1. WHEN probe_file is invoked, THE Probe_File_Tool SHALL accept an input schema with api_version, file, mode, budget_s_per, limit, and ordering
2. WHEN probe_file completes, THE Probe_File_Tool SHALL return an output schema with api_version, status, file, summary, results, and metadata
3. THE Probe_File_Tool SHALL include a summary with total, closed, promising, failed, and timed_out counts
4. THE Probe_File_Tool SHALL include per-theorem results with theorem_id, outcome, classification, and elapsed_ms
5. THE Probe_File_Tool SHALL support "file_order" and "rank_targets" ordering modes
6. WHEN the limit parameter is provided, THE Probe_File_Tool SHALL process at most that many theorems

### Requirement 6: Infrastructure Reuse

**User Story:** As a system maintainer, I want probe to reuse verify's execution infrastructure, so that behavior is consistent and maintenance is simplified.

#### Acceptance Criteria

1. THE Probe_Tool SHALL reuse verify's workspace isolation mechanism
2. THE Probe_Tool SHALL reuse verify's LeanInteract runner
3. THE Probe_Tool SHALL reuse verify's timeout enforcement mechanism
4. THE Probe_Tool SHALL reuse verify's diagnostic parsing logic
5. THE Probe_Tool SHALL follow the same hexagonal architecture patterns as verify

### Requirement 7: No Side Effects

**User Story:** As a developer using probe for measurement, I want guarantees that probe never modifies my code, so that I can safely run it on any theorem.

#### Acceptance Criteria

1. THE Probe_Tool SHALL never mutate the filesystem outside the isolated workspace
2. THE Probe_Tool SHALL never persist state between invocations
3. THE Probe_Tool SHALL never modify source files
4. THE Probe_Tool SHALL clean up all temporary resources after execution
5. WHEN probe_file runs, THE Probe_File_Tool SHALL never modify source files

### Requirement 8: Hard Timeout Enforcement

**User Story:** As a system operator, I want hard timeout enforcement, so that automation attempts never run indefinitely.

#### Acceptance Criteria

1. WHEN a budget is specified, THE Probe_Tool SHALL enforce it as a hard wall-clock limit
2. WHEN the budget is exceeded, THE Probe_Tool SHALL terminate the Lean process immediately
3. WHEN timeout occurs, THE Probe_Tool SHALL return a timeout status
4. WHEN probe_file runs, THE Probe_File_Tool SHALL enforce per-theorem budget isolation to prevent one theorem from consuming another's budget

### Requirement 9: Stable Diagnostic Ordering

**User Story:** As a tool consumer comparing probe results, I want stable diagnostic ordering, so that identical runs produce identical outputs.

#### Acceptance Criteria

1. THE Probe_Tool SHALL sort diagnostics deterministically by file, line, column, severity, and message
2. FOR ALL identical inputs, THE Probe_Tool SHALL produce diagnostics in the same order
3. THE Probe_Tool SHALL normalize severity strings to standard values (error, warning, info)

### Requirement 10: Error Handling

**User Story:** As a tool consumer, I want structured error handling, so that I can distinguish between different failure modes.

#### Acceptance Criteria

1. WHEN a theorem_id is not found, THE Probe_Tool SHALL return an error status with a descriptive message
2. WHEN the Lean toolchain fails, THE Probe_Tool SHALL return an error status with diagnostic information
3. WHEN invalid parameters are provided, THE Probe_Tool SHALL return an error status with validation details
4. WHEN probe_file encounters an error on one theorem, THE Probe_File_Tool SHALL continue processing remaining theorems
5. THE Probe_Tool SHALL never raise unhandled exceptions to the caller
