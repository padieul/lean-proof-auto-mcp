# Tasks: Fix Test Failures and Prevent Git Worktree Pollution

## Phase 1: Fix LeanServer API Usage (TR-1)

- [x] 1. Fix LeanServer API Usage
  - [x] 1.1 Update imports in lean_interact_runner.py
    - Add import for `LeanREPLConfig` from `lean_interact.config`
    - Add import for `FileCommand` from `lean_interact.interface`
    - Add import for `LeanError` from `lean_interact.interface`
    - Update exception handling imports to include `contextlib.suppress`
    - **Validates**: TR-1 (Fix LeanServer API Usage)

  - [x] 1.2 Update verify_file() method to use correct LeanServer API
    - Replace `LeanServer(project_path=..., timeout=...)` with `LeanREPLConfig(lean_version="v4.15.0")`
    - Create `LeanServer(config)` instance
    - Replace `server.run_file()` with `FileCommand(path=...)` and `server.run(command, timeout=...)`
    - Add `LeanError` response type checking
    - Implement timeout detection by checking error message for "timeout" or "timed out"
    - Replace `server.close()` with `server.kill()` using `contextlib.suppress(Exception)`
    - **Validates**: TR-1 (Fix LeanServer API Usage)

  - [x] 1.3 Test LeanServer API fix with one integration test
    - Run `uv run pytest tests/integration/test_verify_integration.py::TestVerifyIntegration::test_valid_theorem_verification -v`
    - Verify test passes
    - Verify no errors in output
    - **Validates**: TR-1 (Fix LeanServer API Usage)

## Phase 2: Fix Property Test Deadline (TR-2)

- [x] 2. Fix Property Test Deadline
  - [x] 2.1 Add deadline setting to test_determinism
    - Import `settings` from `hypothesis` in `tests/property/test_scan_theorem_properties.py`
    - Add `@settings(deadline=None)` decorator to `test_determinism` method
    - Verify imports are at top of file
    - **Validates**: TR-2 (Fix Property Test Deadline)

  - [x] 2.2 Verify property test passes
    - Run `uv run pytest tests/property/test_scan_theorem_properties.py::TestScanTheoremProperties::test_determinism -v`
    - Verify test passes without deadline errors
    - Verify test still validates determinism correctly
    - **Validates**: TR-2 (Fix Property Test Deadline)

## Phase 3: Register Pytest Markers (TR-3)

- [x] 3. Register Pytest Markers
  - [x] 3.1 Update pyproject.toml with pytest markers
    - Open `pyproject.toml`
    - Locate `[tool.pytest.ini_options]` section
    - Verify `slow` marker exists in markers list
    - Add `integration` marker to markers list if not present
    - Format: `"integration: marks tests as integration tests (deselect with '-m \"not integration\"')"`
    - **Validates**: TR-3 (Register Pytest Markers)

  - [x] 3.2 Verify no pytest marker warnings
    - Run `uv run pytest tests/integration/test_verify_integration.py -v`
    - Verify no "Unknown pytest.mark.integration" warnings in output
    - Verify no "Unknown pytest.mark.slow" warnings in output
    - **Validates**: TR-3 (Register Pytest Markers)

## Phase 4: Enforce Temp Mode in All Tests (TR-4)

- [x] 4. Enforce Temp Mode in All Tests
  - [x] 4.1 Update MCP contract tests to use temp mode
    - Open `tests/mcp_contract/test_verify_contract.py`
    - Find all `verify({...})` calls
    - Add `"workspace_mode": "temp"` to each verify() call that doesn't have it
    - Ensure consistent formatting
    - **Validates**: TR-4 (Enforce Temp Mode in All Tests)

  - [x] 4.2 Verify MCP contract tests don't create worktrees
    - Run `git worktree list` and note current worktrees
    - Run `uv run pytest tests/mcp_contract/test_verify_contract.py -v`
    - Run `git worktree list` again
    - Verify no new worktrees were created
    - Verify all tests pass
    - **Validates**: TR-4 (Enforce Temp Mode in All Tests)

  - [x] 4.3 Verify integration tests still work with temp mode
    - Run `uv run pytest tests/integration/test_verify_integration.py -v`
    - Verify all 5 tests pass
    - Run `git worktree list`
    - Verify no new worktrees were created
    - **Validates**: TR-4 (Enforce Temp Mode in All Tests)

## Phase 5: Change Default Workspace Mode (TR-5)

- [x] 5. Change Default Workspace Mode to Temp
  - [x] 5.1 Update detect_workspace_mode() to default to temp
    - Open `src/lean_proof_auto_mcp/adapters/workspace_provider.py`
    - Locate `detect_workspace_mode()` function
    - Replace implementation to always return "temp"
    - Update docstring to explain rationale (safety, IDE compatibility, predictability)
    - Add note that users can explicitly request worktree mode
    - Keep `project_root` parameter for API compatibility
    - **Validates**: TR-5 (Change Default Workspace Mode to Temp)

  - [x] 5.2 Verify auto-detection defaults to temp
    - Create a simple test script that calls `detect_workspace_mode()`
    - Verify it returns "temp" regardless of git repo presence
    - Test in directory with .git
    - Test in directory without .git
    - Verify both return "temp"
    - **Validates**: TR-5 (Change Default Workspace Mode to Temp)

## Phase 6: Repository Cleanup (TR-6)

- [x] 6. Clean Up Repository
  - [x] 6.1 Remove .worktrees directory
    - Check if `.worktrees/` directory exists
    - If exists, run `Remove-Item -Recurse -Force .worktrees` (Windows) or `rm -rf .worktrees` (Unix)
    - Verify directory is removed
    - **Validates**: TR-6 (Clean Up Repository)

  - [x] 6.2 Prune git worktree metadata
    - Run `git worktree prune`
    - Verify command completes successfully
    - Run `git worktree list`
    - Verify only main worktree is shown
    - **Validates**: TR-6 (Clean Up Repository)

  - [x] 6.3 Update .gitignore
    - Open `.gitignore`
    - Verify `.worktrees/` entry exists (should already be added)
    - Verify `tmp/` entry exists
    - Verify `.artifacts/` entry exists (should already be present)
    - Add comment explaining each entry if not present
    - **Validates**: TR-6 (Clean Up Repository)

## Phase 7: Final Verification

- [x] 7. Run Final Verification Suite
  - [x] 7.1 Run full integration test suite
    - Run `uv run pytest tests/integration/test_verify_integration.py -v`
    - Verify all 5 tests pass
    - Verify no worktrees created
    - **Validates**: Story 1 (All Tests Pass Reliably)

  - [x] 7.2 Run property test suite
    - Run `uv run pytest tests/property/test_scan_theorem_properties.py -v`
    - Verify all tests pass
    - Verify no deadline errors
    - **Validates**: Story 1 (All Tests Pass Reliably)

  - [x] 7.3 Run MCP contract test suite
    - Run `uv run pytest tests/mcp_contract/test_verify_contract.py -v`
    - Verify all tests pass
    - Verify no worktrees created
    - **Validates**: Story 1 (All Tests Pass Reliably)

  - [x] 7.4 Verify no git worktree pollution
    - Run `git worktree list`
    - Verify only main worktree is shown
    - Check if `.worktrees/` directory exists
    - Verify it does not exist
    - **Validates**: Story 2 (Tests Never Pollute Development Repository)

  - [x] 7.5 Run pre-commit hooks
    - Run `uv run pre-commit run --all-files`
    - Verify all hooks pass (fix end of files, trim whitespace, check yaml, ruff, ruff-format)
    - Fix any issues if they arise
    - **Validates**: Success Metrics

  - [x] 7.6 Run full test suite
    - Run `uv run pytest -q`
    - Verify all tests pass (or note any expected failures)
    - Verify test execution completes in reasonable time (<5 minutes)
    - **Validates**: Story 1 (All Tests Pass Reliably)

## Phase 8: Documentation (Optional)

- [x] 8. Update Documentation
  - [x] 8.1* Update /docs (NOT README!!) with workspace mode documentation
    - Add section explaining workspace modes (temp vs worktree)
    - Explain default behavior (temp mode)
    - Show how to explicitly request worktree mode
    - Explain why temp mode is used for tests
    - **Validates**: Story 4 (Production Users Can Choose Workspace Mode)

  - [x] 8.2* Update readmde.md AND /docs
    - Note that users must explicitly request worktree mode
    - **Validates**: Story 4 (Production Users Can Choose Workspace Mode)

## Notes

- Tasks marked with `*` are optional
- Run `git worktree list` frequently to verify no worktrees are being created
- If any test fails, stop and investigate before proceeding
- Keep `.worktrees/` directory removed throughout implementation
- System temp directories (from `tempfile.mkdtemp()`) are outside the repo and don't need `.gitignore` entries
