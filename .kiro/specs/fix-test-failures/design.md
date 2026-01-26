---
title: Design - Fix Test Failures and Prevent Git Worktree Pollution
status: draft
created: 2026-01-26
---

# Design Document: Fix Test Failures and Prevent Git Worktree Pollution

## Overview

This design implements **Option 3: Default tests to temp mode, not git worktree** to fix test failures and prevent git worktree pollution in the development repository.

## Architecture Decisions

### AD-1: Use Temp Mode for All Tests
**Decision**: All tests will explicitly use `workspace_mode: "temp"` instead of relying on auto-detection.

**Rationale**:
- Prevents git worktrees from polluting the development repository
- Avoids IDE confusion with nested git repositories
- Works consistently across all environments (no git dependency)
- Simpler cleanup (OS handles temp directory removal)

**Trade-offs**:
- Slightly slower than worktree mode (full copy vs. git worktree)
- Acceptable for tests since correctness > performance

### AD-2: Change Default Auto-Detection to Temp Mode
**Decision**: `detect_workspace_mode()` will always return "temp" instead of detecting git repositories.

**Rationale**:
- Safest default for library users
- Prevents unexpected worktree creation
- Users can still explicitly request worktree mode
- Aligns with principle of least surprise

**Trade-offs**:
- Users who want worktree performance must explicitly opt-in
- Breaking change for users relying on auto-detection (acceptable since it was causing issues)

### AD-3: Maintain Hexagonal Architecture
**Decision**: All changes remain in adapter layer, no core logic changes.

**Rationale**:
- Preserves separation of concerns
- Core domain remains independent of infrastructure
- Adapters handle external library API changes

## Component Design

### 1. LeanInteractRunner Adapter (TR-1)

**Current Implementation** (Broken):
```python
server = LeanServer(
    project_path=str(workspace_path),  # ❌ Doesn't exist
    timeout=budget_s,                   # ❌ Wrong location
)
response = server.run_file(target_file)  # ❌ Method doesn't exist
```

**New Implementation**:
```python
from lean_interact import LeanServer
from lean_interact.config import LeanREPLConfig
from lean_interact.interface import FileCommand, LeanError

# Create config without project (test fixtures aren't full Lean projects)
config = LeanREPLConfig(lean_version="v4.15.0")
server = LeanServer(config)

# Run verification with timeout
command = FileCommand(path=target_file)
response = server.run(command, timeout=budget_s)

# Handle timeout via LeanError response
if isinstance(response, LeanError):
    if "timeout" in str(response).lower():
        return timeout_result
    else:
        return error_result
```

**Key Changes**:
- Use `LeanREPLConfig` with explicit `lean_version` (no project needed)
- Use `FileCommand` + `server.run()` instead of `run_file()`
- Pass `timeout` to `run()` method, not constructor
- Check response type for `LeanError` to detect timeouts
- Use `server.kill()` for cleanup instead of `server.close()`

### 2. Property Test Deadline (TR-2)

**Current Implementation** (Flaky):
```python
@given(args=scan_theorem_args())
def test_determinism(self, args: dict[str, Any]) -> None:
    # Test runs in 264ms or 171ms randomly
```

**New Implementation**:
```python
from hypothesis import given, settings

@given(args=scan_theorem_args())
@settings(deadline=None)  # ✅ Disable deadline checking
def test_determinism(self, args: dict[str, Any]) -> None:
    # Test can take variable time without failing
```

### 3. Pytest Markers (TR-3)

**Current Configuration** (Incomplete):
```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

**New Configuration**:
```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
]
```

### 4. Test Workspace Mode Enforcement (TR-4)

**Strategy**: Add explicit `workspace_mode: "temp"` to all test verify() calls.

**Integration Tests** (5 tests):
```python
result = verify({
    "file": VALID_THEOREM,
    "budget_s": 30.0,
    "workspace_mode": "temp",  # ✅ Explicit temp mode
})
```

**MCP Contract Tests** (~20 tests):
```python
# Tests that don't need real verification
resp = verify({"file": "test.lean", "workspace_mode": "temp"})

# Tests that validate error handling
resp = verify({"file": "", "workspace_mode": "temp"})
```

**Property Tests**:
- Tests that test worktree functionality: Use isolated test git repos (already correct)
- Other property tests: Don't call verify() directly (already correct)

**Unit Tests**:
- Should mock/stub workspace creation (already correct)

### 5. Workspace Mode Auto-Detection (TR-5)

**Current Implementation** (Problematic):
```python
def detect_workspace_mode(project_root: Path | None = None) -> str:
    project_root = Path.cwd() if project_root is None else Path(project_root)
    git_dir = project_root / ".git"
    if git_dir.exists() and git_dir.is_dir():
        return "worktree"  # ❌ Creates worktrees in dev repo
    else:
        return "temp"
```

**New Implementation**:
```python
def detect_workspace_mode(project_root: Path | None = None) -> str:
    """
    Auto-detect appropriate workspace mode.
    
    Always returns "temp" for safety and IDE compatibility.
    Users can explicitly request "worktree" mode if needed.
    
    Rationale:
    - Temp mode works in all environments
    - Prevents git worktree pollution in development repos
    - Avoids IDE confusion with nested git repositories
    - Users who want worktree performance can opt-in explicitly
    
    Args:
        project_root: Ignored (kept for API compatibility)
    
    Returns:
        Always "temp"
    """
    return "temp"
```

### 6. Repository Cleanup (TR-6)

**Actions**:
1. Remove `.worktrees/` directory: `Remove-Item -Recurse -Force .worktrees`
2. Prune git worktree metadata: `git worktree prune`
3. Update `.gitignore`:
   - Add `.worktrees/` (for any worktree mode usage)
   - Verify `tmp/` is present (for any local temp directories)
   - Verify `.artifacts/` is present (already done)

**Note on Temp Directories**:
- `TempCopyProvider` uses Python's `tempfile.mkdtemp()` which creates directories in the system temp location (e.g., `/tmp` on Unix, `%TEMP%` on Windows)
- These are **outside the git repository** and don't need `.gitignore` entries
- The `tmp/` entry in `.gitignore` is for any manually created local temp directories, not for system temp

## Data Flow

### Before (Broken):
```
Test calls verify()
  ↓
Auto-detect workspace mode
  ↓ (sees .git directory)
Use worktree mode
  ↓
GitWorktreeProvider(Path.cwd())  ← Uses dev repo!
  ↓
git worktree add .worktrees/worktree-xxx HEAD
  ↓
Worktree of dev repo created ❌
```

### After (Fixed):
```
Test calls verify(workspace_mode="temp")
  ↓
Explicit temp mode
  ↓
TempCopyProvider
  ↓
Copy files to /tmp/temp-xxx/
  ↓
Isolated test environment ✅
```

## Error Handling

### LeanError Response Handling
```python
response = server.run(command, timeout=budget_s)

if isinstance(response, LeanError):
    error_msg = str(response)
    
    # Detect timeout
    if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
        return LeanRunResult(
            status="timeout",
            diagnostics=[],
            scope_used=scope_used,
            full_logs=error_msg,
            timing={"lean_execution_s": elapsed},
            exit_code=-1,
        )
    
    # Other errors
    return LeanRunResult(
        status="error",
        diagnostics=[],
        scope_used=scope_used,
        full_logs=error_msg,
        timing={"lean_execution_s": elapsed},
        exit_code=1,
    )
```

## Testing Strategy

### Verification Steps
1. **Run integration tests**: `uv run pytest tests/integration/test_verify_integration.py -v`
   - Expected: All 5 tests pass
   - Expected: No worktrees created

2. **Run property test**: `uv run pytest tests/property/test_scan_theorem_properties.py::TestScanTheoremProperties::test_determinism -v`
   - Expected: Test passes without deadline errors

3. **Run MCP contract tests**: `uv run pytest tests/mcp_contract/test_verify_contract.py -v`
   - Expected: All tests pass
   - Expected: No worktrees created

4. **Check git worktrees**: `git worktree list`
   - Expected: Only main worktree shown

5. **Check directory**: `Test-Path .worktrees`
   - Expected: False (directory doesn't exist)

6. **Run pre-commit**: `uv run pre-commit run --all-files`
   - Expected: All hooks pass

## Implementation Order

1. **Phase 1: Fix LeanServer API** (TR-1)
   - Update imports in `lean_interact_runner.py`
   - Modify `verify_file()` method
   - Test with one integration test

2. **Phase 2: Fix Property Test** (TR-2)
   - Add `@settings(deadline=None)`
   - Verify test passes

3. **Phase 3: Register Markers** (TR-3)
   - Update `pyproject.toml`
   - Verify no warnings

4. **Phase 4: Enforce Temp Mode** (TR-4)
   - Update integration tests (already done)
   - Update MCP contract tests
   - Verify no worktrees created

5. **Phase 5: Change Default** (TR-5)
   - Update `detect_workspace_mode()`
   - Update docstring
   - Test auto-detection

6. **Phase 6: Cleanup** (TR-6)
   - Remove `.worktrees/`
   - Update `.gitignore`
   - Run `git worktree prune`

## Files to Modify

| File | Changes | Requirement |
|------|---------|-------------|
| `src/lean_proof_auto_mcp/adapters/lean_interact_runner.py` | Fix LeanServer API usage | TR-1 |
| `tests/property/test_scan_theorem_properties.py` | Add deadline setting | TR-2 |
| `pyproject.toml` | Register pytest markers | TR-3 |
| `tests/mcp_contract/test_verify_contract.py` | Add workspace_mode to verify() calls | TR-4 |
| `src/lean_proof_auto_mcp/adapters/workspace_provider.py` | Change default to temp | TR-5 |
| `.gitignore` | Add .worktrees/ | TR-6 |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking change for users relying on auto-detection | Medium | Document change, provide migration guide |
| Temp mode slower than worktree | Low | Acceptable for tests, users can opt-in to worktree |
| Hardcoded Lean version | Low | Document limitation, make configurable in future |
| Timeout overhead (~2s) | Low | Adjust test expectations, document limitation |

## Success Criteria

- ✅ All 5 integration tests pass
- ✅ Property test passes without flaky failures
- ✅ No pytest marker warnings
- ✅ No git worktrees created during test runs
- ✅ `git worktree list` shows only main worktree
- ✅ `.worktrees/` directory doesn't exist
- ✅ Pre-commit hooks pass
- ✅ Code follows hexagonal architecture
- ✅ Documentation updated

## Documentation Updates

### README.md
Add section explaining workspace modes:
```markdown
## Workspace Modes

The verify tool supports two workspace isolation modes:

- **temp** (default): Copies files to a temporary directory. Safest option, works everywhere.
- **worktree**: Uses git worktree for faster isolation. Requires git repository.

To use worktree mode explicitly:
```python
verify({"file": "theorem.lean", "workspace_mode": "worktree"})
```

For tests, always use temp mode to avoid polluting your development repository.
```

### CHANGELOG.md
```markdown
## [0.2.1] - 2026-01-26

### Fixed
- Fixed LeanServer API usage to work with lean_interact library
- Fixed flaky property test deadline failures
- Fixed git worktree pollution in development repository during tests

### Changed
- Default workspace mode changed from auto-detect to "temp" for safety
- All tests now explicitly use temp mode
- Users must explicitly request worktree mode if desired
```
