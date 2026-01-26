# Requirements: verify MCP Tool

## Problem Statement

The `verify` tool is the foundational Lean execution primitive for the `lean-proof-auto-mcp` repository. It provides a deterministic, sandboxed, budget-bounded way to answer one question: "Does Lean accept this scope (file or theorem), and if not, what are the diagnostics?"

This tool establishes the core Lean execution runtime that later tools (`probe`, `probe_file`, `check_patch`, `search_annotations`) will reuse. It is pure infrastructure with no LLM calls, designed for reproducible verification in isolated workspaces.

## User Stories

### US-1: File-Level Verification
**As a** Lean developer or automated agent
**I want to** verify that a `.lean` file compiles successfully within a time budget
**So that** I can validate changes before applying patches or testing automation

**Acceptance Criteria:**
- 1.1: Tool accepts a file path and returns success/fail/timeout/error status
- 1.2: Tool runs verification in isolated workspace (git worktree or temp copy)
- 1.3: Tool enforces hard wall-clock timeout with process tree kill
- 1.4: Tool returns structured diagnostics with severity, message, and location
- 1.5: Tool stores full logs and metadata under unique run_id
- 1.6: Response contains only log excerpts to stay small (configurable max chars)

### US-2: Theorem-Level Verification (Optional)
**As a** user testing targeted theorem changes
**I want to** verify a specific theorem without recompiling the entire file
**So that** I can get faster feedback on localized changes

**Acceptance Criteria:**
- 2.1: Tool accepts theorem_id in addition to file path
- 2.2: If theorem-level verification is reliable, tool verifies only that theorem
- 2.3: If theorem-level verification is unreliable, tool either:
  - Rejects with clear error code `theorem_scope_not_supported`, OR
  - Falls back to file-level verification and reports `verification_scope_used = "file_fallback"`
- 2.4: Tool returns diagnostics filtered to the theorem scope when possible
- 2.5: Tool integrates with scan_file theorem_id format

### US-3: Deterministic Outputs
**As a** user or automated system
**I want to** receive identical JSON for identical inputs (same repo state)
**So that** I can rely on reproducible results for testing and automation

**Acceptance Criteria:**
- 3.1: Diagnostics sorted by (file, line, col, severity, message)
- 3.2: Tie-breakers use stable lexical order for same location
- 3.3: Log excerpts use deterministic truncation (first N chars)
- 3.4: run_id may include timestamp but response content is stable
- 3.5: JSON keys have stable ordering

### US-4: Budget Enforcement
**As a** user with time constraints
**I want to** specify a time budget and have it strictly enforced
**So that** verification never hangs or blocks indefinitely

**Acceptance Criteria:**
- 4.1: Tool accepts budget_s parameter (default: 30 seconds)
- 4.2: Tool enforces hard timeout with process tree kill
- 4.3: Tool returns status="timeout" when budget exceeded
- 4.4: Tool cleans up all processes and workspace resources on timeout
- 4.5: Tool overhead is < 500ms beyond Lean execution time

### US-5: Structured Diagnostics
**As a** user debugging compilation failures
**I want to** receive normalized, structured diagnostics
**So that** I can programmatically process errors and warnings

**Acceptance Criteria:**
- 5.1: Each diagnostic has severity (error/warning/info), message, and location
- 5.2: Location includes file, line, col (end_line, end_col optional)
- 5.3: Diagnostics are normalized from Lean compiler output
- 5.4: Response includes diagnostic_summary with error/warning counts
- 5.5: Evidence section includes stdout/stderr excerpts and notes

### US-6: Workspace Isolation
**As a** user running multiple verifications
**I want to** ensure each verification runs in isolated workspace
**So that** verifications don't interfere with each other or modify my working tree

**Acceptance Criteria:**
- 6.1: Tool creates isolated workspace (git worktree or temp copy)
- 6.2: Tool never modifies source files in original working tree
- 6.3: Tool cleans up workspace after completion (configurable retention on failure)
- 6.4: Tool supports concurrent invocations safely
- 6.5: Tool reports workspace_mode and workspace_id in metadata

### US-7: Artifact Storage
**As a** user investigating verification results
**I want to** access full logs and metadata via run_id
**So that** I can debug issues without cluttering the response JSON

**Acceptance Criteria:**
- 7.1: Tool stores request.json, result.json, and full logs under run_id directory
- 7.2: Tool provides configurable max_log_excerpt_chars for response
- 7.3: Tool includes run_id in response for artifact lookup
- 7.4: Artifacts persist after tool completion (configurable retention policy)
- 7.5: Tool provides store_full_logs flag to control artifact creation

### US-8: Integration with Existing Tools
**As a** user of scan_file and rank_targets
**I want to** verify files and theorems identified by those tools
**So that** I can validate automation recommendations

**Acceptance Criteria:**
- 8.1: Tool accepts file paths from scan_file/rank_targets output
- 8.2: Tool accepts theorem_id format from scan_file output
- 8.3: Tool returns JSON conforming to MCP contract (api_version, status, run_id)
- 8.4: Tool provides metadata for correlation (repo_commit, toolchain versions)
- 8.5: Tool follows same deterministic formatting as scan_file/rank_targets

## Non-Functional Requirements

### NFR-1: Determinism
- Same repo state + same inputs => identical JSON (modulo run_id/timestamps)
- Diagnostics sorted deterministically
- Excerpts truncated deterministically
- No nondeterministic reordering of content

### NFR-2: Performance
- Overhead: < 500ms beyond Lean compilation time
- Timeout enforcement: Within 100ms of specified budget
- Process cleanup: < 100ms after completion/timeout
- No memory leaks from repeated invocations
- Reuse build cache in isolated workspace when safe

### NFR-3: Reliability
- Tool never hangs or blocks indefinitely
- Tool always cleans up Lean processes and workspaces
- Tool handles Lean crashes gracefully
- Tool returns valid JSON even on internal errors
- Tool provides clear error messages for all failure modes

### NFR-4: Safety
- Tool never modifies source files in original working tree
- Tool runs verification in isolated workspace
- Tool enforces hard timeout with process tree kill
- Tool validates all input parameters before execution
- Tool applies read-only policy to workspace when possible

### NFR-5: API Stability
- Tool contract versioned with api_version field (0.2.0)
- Schema changes require version bump
- Backward compatibility maintained within major version
- Consistent response structure with other MCP tools

### NFR-6: Observability
- All invocations logged with unique run_id
- Execution time tracked and reported in timing section
- Lean process exit codes captured
- Timeout events clearly indicated in status
- Diagnostics include severity levels for filtering

## Dependencies

### External Dependencies
- **LeanInteract**: Python package for Lean 4 interaction via Lean REPL
  - Source: LeanInteract provides programmatic execution of Lean code/files through the Lean REPL (read-eval-print loop that exposes Lean as interactive subprocess)
  - Used for: Running Lean verification in project context with structured output
- **Lean 4 Toolchain**: Lean compiler, Lake build system, elan version manager
  - Source: `lake lean <file>` ensures imports are built before checking file
  - Used for: Compiling Lean files in correct Lake environment
- **Git**: For creating isolated worktrees
  - Used for: Workspace isolation via git worktree

### Internal Dependencies (Read-Only)
- **core.format**: Deterministic output formatting (ensure_deterministic, normalize_notes)
- **core.source**: SourceText representation (for theorem extraction if needed)
- **core.indexer**: Theorem indexing (for theorem-level verification if implemented)

### Integration Points
- **scan_file**: Provides file paths and theorem_id format
- **rank_targets**: Provides ranked theorems for verification
- **probe/probe_file** (future): Will use verify as building block
- **check_patch** (future): Will use verify to validate patches
- **search_annotations** (future): Will use verify in search loop

## Technical Constraints

### Lean Execution
- Must use LeanInteract with Lean REPL for structured interaction
- Must ensure imports are built before checking file (lake lean behavior)
- Must run in correct Lake environment with project dependencies
- Must handle Lean 4 diagnostic output format
- Must work with Mathlib and other Lean projects

### Process Management
- Must terminate Lean process on timeout (hard kill)
- Must capture stdout and stderr
- Must handle process crashes and non-zero exit codes
- Must work on Windows, Linux, and macOS
- Must kill entire process tree on timeout

### Workspace Isolation
- Must create isolated workspace (git worktree preferred, temp copy fallback)
- Must not modify original working tree
- Must clean up workspace after completion
- Must handle concurrent invocations safely
- Must detect and report workspace_mode

### Artifact Storage
- Must store artifacts under LPAM_ARTIFACTS_DIR or configurable location
- Must use run_id as directory key
- Must persist request.json, result.json, full logs
- Must handle disk space limits gracefully
- Must support configurable retention policy

## Out of Scope

- Interactive proof state exploration (compile-check only)
- Modifying source files or applying patches (use check_patch tool)
- Running Lean in interactive mode or language server
- Caching compilation results across invocations (stateless tool)
- Building entire Lean projects (single file/theorem scope only)
- Memory limit enforcement (OS-dependent, not portable)
- LLM calls or policy decisions (pure infrastructure)
- Proof search or automation (use probe tools)

## Success Criteria

- Verification accuracy: 100% match with Lean compiler behavior
- Timeout accuracy: Within 100ms of specified budget
- Process cleanup: 100% (no orphaned processes or leaked workspaces)
- Determinism: Identical outputs for identical inputs (modulo run_id/timestamps)
- API stability: No breaking changes within major version
- Performance overhead: < 500ms beyond Lean compilation time
- Integration: Seamless use with scan_file/rank_targets outputs
