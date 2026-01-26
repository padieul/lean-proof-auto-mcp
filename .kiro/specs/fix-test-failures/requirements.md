---
title: Fix Test Failures and Prevent Git Worktree Pollution
status: in-progress
created: 2026-01-26
updated: 2026-01-26
---

# Fix Test Failures and Prevent Git Worktree Pollution

## Problem Statement

The test suite has multiple critical issues:

1. **6 Test Failures**:
   - 5 integration tests: TypeError on LeanServer initialization (incorrect API usage)
   - 1 property test: Hypothesis deadline exceeded (flaky timing)

2. **Critical Bug: Git Worktree Pollution**:
   - Tests create git worktrees in the development repository
   - 29+ worktrees accumulated in `.worktrees/` directory
   - Worktrees appear in IDE git interfaces during test runs
   - Causes confusion and repository pollution

3. **Incomplete Test Isolation**:
   - Integration tests now use temp mode (partially fixed)
   - MCP contract tests still auto-detect and may use worktree mode
   - No consistent policy across all test suites

## Root Causes

### Issue 1: LeanServer API Mismatch
The `lean_interact` library API changed. Code uses non-existent `LeanServer(project_path=..., timeout=...)` parameters.

### Issue 2: Property Test Timing
Hypothesis detects timing variability (264ms vs 171ms) as flaky behavior.

### Issue 3: Git Worktree Auto-Detection
`GitWorktreeProvider` defaults to `Path.cwd()` and auto-detects git repos, causing tests to create worktrees of the development repository instead of isolated test environments.

## User Stories

### Story 1: All Tests Pass Reliably
**As a** developer running the test suite  
**I want** all tests to pass without failures  
**So that** I can verify code correctness and merge changes confidently

**Acceptance Criteria**:
- [ ] All 5 integration tests pass
- [ ] Property test passes without flaky failures
- [ ] No pytest marker warnings
- [ ] Tests complete in reasonable time (<5 minutes total)

### Story 2: Tests Never Pollute Development Repository
**As a** developer working on the codebase  
**I want** tests to never create git worktrees in my development repository  
**So that** my IDE doesn't show confusing nested repos and my workspace stays clean

**Acceptance Criteria**:
- [ ] No git worktrees created in development repo during any test run
- [ ] All tests use temp mode (copy to temporary directory)
- [ ] `.worktrees/` directory never created by tests
- [ ] `git worktree list` shows only main worktree after test runs

### Story 3: Consistent Test Isolation Policy
**As a** developer or CI system running tests  
**I want** all test suites to use the same isolation strategy  
**So that** behavior is predictable and consistent across environments

**Acceptance Criteria**:
- [ ] Integration tests explicitly use `workspace_mode: "temp"`
- [ ] MCP contract tests explicitly use `workspace_mode: "temp"`
- [ ] Property tests that test worktree functionality use isolated test git repos (not dev repo)
- [ ] Unit tests don't create any workspaces (mock/stub only)
- [ ] Documentation explains why temp mode is used for tests

### Story 4: Production Users Can Choose Workspace Mode
**As a** user of the MCP server in production  
**I want** to choose between temp and worktree modes based on my needs  
**So that** I can optimize for performance (worktree) or safety (temp)

**Acceptance Criteria**:
- [ ] Default workspace mode is "temp" (safest, works everywhere)
- [ ] Users can explicitly request "worktree" mode via API parameter
- [ ] Documentation explains trade-offs between modes
- [ ] Worktree mode works correctly when explicitly requested
- [ ] Auto-detection defaults to "temp" instead of detecting git repos

### Story 5: Clean Repository State
**As a** developer  
**I want** leftover test artifacts cleaned up  
**So that** my repository is in a clean state

**Acceptance Criteria**:
- [ ] Existing `.worktrees/` directory removed
- [ ] `.worktrees/` added to `.gitignore`
- [ ] `.artifacts/` properly ignored (already done)
- [ ] No test artifacts committed to git

## Technical Requirements

### TR-1: Fix LeanServer API Usage
**Requirement**: Update `LeanInteractRunner` to use correct lean_interact API

**Details**:
- Import: `LeanREPLConfig`, `FileCommand`, `LeanError` from lean_interact
- Initialize: `config = LeanREPLConfig(lean_version="v4.15.0")` (no project)
- Create server: `server = LeanServer(config)`
- Run verification: `command = FileCommand(path=file); response = server.run(command, timeout=budget_s)`
- Handle timeout: Check if `isinstance(response, LeanError)` and detect timeout in error message
- Cleanup: Use `server.kill()` instead of `server.close()`

### TR-2: Fix Property Test Deadline
**Requirement**: Eliminate flaky timing failures in property tests

**Details**:
- Add `@settings(deadline=None)` to `test_determinism` method
- Import `settings` from hypothesis

### TR-3: Register Pytest Markers
**Requirement**: Eliminate pytest marker warnings

**Details**:
- Add `integration` marker to `pyproject.toml` markers list
- Add `slow` marker if not already present

### TR-4: Enforce Temp Mode in All Tests
**Requirement**: All test suites must explicitly use temp mode to prevent worktree pollution

**Details**:
- Integration tests: Add `"workspace_mode": "temp"` to all `verify()` calls
- MCP contract tests: Add `"workspace_mode": "temp"` to all `verify()` calls that don't already have it
- Property tests: Tests that test worktree functionality should use isolated test git repos
- Unit tests: Should mock/stub workspace creation, not create real workspaces

### TR-5: Change Default Workspace Mode to Temp
**Requirement**: Auto-detection should default to temp mode instead of detecting git repos

**Details**:
- Update `detect_workspace_mode()` in `workspace_provider.py` to always return "temp"
- Add comment explaining why (safety, IDE compatibility, predictability)
- Users can still explicitly request "worktree" mode via API parameter
- Update docstring to reflect new behavior

### TR-6: Clean Up Repository
**Requirement**: Remove leftover test artifacts and prevent future pollution

**Details**:
- Remove `.worktrees/` directory if it exists
- Add `.worktrees/` to `.gitignore`
- Run `git worktree prune` to clean up git metadata
- Verify `.artifacts/` is in `.gitignore` (already done)

## Implementation Constraints

1. **Hexagonal Architecture**: Maintain adapter pattern - changes should be in adapters, not core
2. **Backward Compatibility**: Don't break existing API - users can still request worktree mode
3. **Test Independence**: Each test should be isolated and not depend on others
4. **No External Dependencies**: Don't require users to create directories outside the repo
5. **Cross-Platform**: Solution must work on Windows, macOS, and Linux

## Success Metrics

- [ ] All integration tests pass (5/5)
- [ ] Property test passes without flaky failures
- [ ] No pytest marker warnings
- [ ] No git worktrees created during test runs
- [ ] `git worktree list` shows only main worktree after tests
- [ ] `.worktrees/` directory does not exist after tests
- [ ] Pre-commit hooks pass
- [ ] Code follows hexagonal architecture patterns
- [ ] Documentation updated to explain workspace modes

## Out of Scope

- Optimizing worktree performance for production use
- Creating worktrees outside the repository (Option 1)
- Adding VS Code settings to hide worktrees (Option 2)
- Changing the workspace isolation architecture

## Related Requirements

- Requirements 1.1: File-level verification
- Requirements 1.2: Workspace isolation
- Requirements 1.3: Timeout enforcement
- Requirements 2.1: Theorem-level verification
- Requirements 6.1: Workspace creation
- Requirements 6.3: Workspace cleanup
- Requirements 6.5: Workspace mode detection
