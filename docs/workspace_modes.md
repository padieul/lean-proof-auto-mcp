# Workspace Modes

## Overview

The Lean Proof Automation MCP uses workspace isolation to ensure safe, reproducible verification. When verifying Lean files, the system creates an isolated workspace to prevent interference with your development environment.

Two workspace modes are available:

- **temp** (default): Copies files to a temporary directory
- **worktree**: Uses git worktree for faster isolation

## Workspace Mode Comparison

| Feature | Temp Mode | Worktree Mode |
|---------|-----------|---------------|
| **Speed** | Slower (full copy) | Faster (git worktree) |
| **Safety** | Safest | Safe |
| **Requirements** | None | Git repository |
| **IDE Impact** | None | May show nested repos |
| **Cleanup** | Automatic (OS) | Manual (git worktree prune) |
| **Default** | ✅ Yes | No |

## Temp Mode (Default)

Temp mode copies the necessary files to a system temporary directory (e.g., `/tmp` on Unix, `%TEMP%` on Windows).

### Advantages

- **Works everywhere**: No git repository required
- **Clean isolation**: No impact on development repository
- **IDE-friendly**: No nested git repositories to confuse IDEs
- **Automatic cleanup**: OS handles temporary directory removal
- **Predictable**: Same behavior across all environments

### Disadvantages

- **Slower**: Full file copy takes more time than git worktree
- **Disk usage**: Creates complete copies of files

### When to Use

- **Default choice**: Use temp mode unless you have specific performance needs
- **CI/CD pipelines**: Ensures consistent, isolated test environments
- **IDE integration**: Prevents git worktree pollution in development repository
- **Non-git projects**: Works without git repository

### Example

```json
{
  "tool": "verify",
  "arguments": {
    "file": "MyTheorem.lean",
    "budget_s": 30.0,
    "workspace_mode": "temp"
  }
}
```

## Worktree Mode

Worktree mode uses `git worktree` to create a lightweight checkout of your repository.

### Advantages

- **Faster**: Git worktree is faster than full copy
- **Efficient**: Shares git objects with main repository
- **Git-aware**: Preserves git history and metadata

### Disadvantages

- **Requires git**: Only works in git repositories
- **IDE confusion**: May show nested repositories in IDE
- **Manual cleanup**: Requires `git worktree prune` to clean up metadata
- **Repository pollution**: Creates worktrees in development repository (if not configured carefully)

### When to Use

- **Performance-critical**: When verification speed is important
- **Batch processing**: When running many verifications in sequence
- **Git-based workflows**: When you need git metadata during verification

### Example

```json
{
  "tool": "verify",
  "arguments": {
    "file": "MyTheorem.lean",
    "budget_s": 30.0,
    "workspace_mode": "worktree"
  }
}
```

### Important Notes

- Worktree mode must be **explicitly requested** via the `workspace_mode` parameter
- Auto-detection defaults to temp mode for safety
- Worktrees are created in a `.worktrees/` directory (add to `.gitignore`)

## Default Behavior

The system **always defaults to temp mode** for safety and IDE compatibility.

### Why Temp Mode is Default

1. **Safety**: Prevents git worktree pollution in development repository
2. **IDE compatibility**: Avoids nested git repositories that confuse IDEs
3. **Predictability**: Works consistently across all environments
4. **Simplicity**: No git repository required

### Auto-Detection (Deprecated)

Previous versions auto-detected git repositories and used worktree mode automatically. This caused issues:

- Git worktrees polluted development repositories
- IDEs showed confusing nested repositories during test runs
- Inconsistent behavior across environments

**Current behavior**: Auto-detection always returns "temp" mode. Users must explicitly request worktree mode.

## Configuration

### Explicit Mode Selection

Always specify `workspace_mode` explicitly in production code:

```json
{
  "tool": "verify",
  "arguments": {
    "file": "MyTheorem.lean",
    "budget_s": 30.0,
    "workspace_mode": "temp"  // Explicit is better than implicit
  }
}
```

### Environment Variables

No environment variables control workspace mode selection. Mode must be specified per-request.

## Testing Guidelines

### Test Isolation

**All tests must use temp mode** to prevent git worktree pollution:

```python
# ✅ Correct: Explicit temp mode
result = verify({
    "file": "test.lean",
    "budget_s": 30.0,
    "workspace_mode": "temp",
})

# ❌ Wrong: Relying on auto-detection
result = verify({
    "file": "test.lean",
    "budget_s": 30.0,
    # Missing workspace_mode - defaults to temp, but implicit
})
```

### Why Tests Use Temp Mode

1. **Prevents repository pollution**: No git worktrees created in development repository
2. **IDE-friendly**: No nested repositories during test runs
3. **Consistent**: Same behavior across all test environments
4. **Clean**: OS handles cleanup automatically

### Testing Worktree Functionality

If you need to test worktree functionality:

1. Create an isolated test git repository
2. Use that repository for worktree tests
3. Never use the development repository for worktree tests

```python
# ✅ Correct: Isolated test repository
with tempfile.TemporaryDirectory() as tmpdir:
    test_repo = Path(tmpdir) / "test_repo"
    # Initialize git repo, add files, etc.
    result = verify({
        "file": str(test_repo / "test.lean"),
        "workspace_mode": "worktree",
    })
```

## Troubleshooting

### Git Worktree Pollution

**Problem**: `.worktrees/` directory created in development repository.

**Solution**:
1. Remove worktrees: `Remove-Item -Recurse -Force .worktrees` (Windows) or `rm -rf .worktrees` (Unix)
2. Prune git metadata: `git worktree prune`
3. Add to `.gitignore`: `.worktrees/`
4. Use temp mode instead: `"workspace_mode": "temp"`

### IDE Shows Nested Repositories

**Problem**: IDE shows nested git repositories during verification.

**Solution**: Use temp mode instead of worktree mode:

```json
{
  "workspace_mode": "temp"
}
```

### Slow Verification

**Problem**: Verification is slow with temp mode.

**Solution**: Consider using worktree mode for performance:

```json
{
  "workspace_mode": "worktree"
}
```

**Trade-off**: Faster verification vs. potential IDE confusion.

### Worktree Mode Not Working

**Problem**: Worktree mode fails with error.

**Possible causes**:
1. Not in a git repository
2. Git not installed
3. Insufficient permissions

**Solution**: Use temp mode instead, which works everywhere.

## Best Practices

1. **Default to temp mode**: Use temp mode unless you have specific performance needs
2. **Explicit is better**: Always specify `workspace_mode` explicitly
3. **Test with temp mode**: All tests should use temp mode
4. **Add to .gitignore**: Add `.worktrees/` to `.gitignore` if using worktree mode
5. **Clean up regularly**: Run `git worktree prune` periodically if using worktree mode
6. **Document choice**: Document why you chose worktree mode if you use it

## Migration Guide

### From Auto-Detection to Explicit Mode

**Before (auto-detection)**:
```json
{
  "file": "MyTheorem.lean",
  "budget_s": 30.0
  // Auto-detected based on git repository presence
}
```

**After (explicit mode)**:
```json
{
  "file": "MyTheorem.lean",
  "budget_s": 30.0,
  "workspace_mode": "temp"  // Explicit mode selection
}
```

### From Worktree to Temp Mode

If you were relying on auto-detection and want to switch to temp mode:

1. Add `"workspace_mode": "temp"` to all verify calls
2. Remove existing worktrees: `rm -rf .worktrees`
3. Prune git metadata: `git worktree prune`
4. Add `.worktrees/` to `.gitignore`

## See Also

- [Configuration Guide](configuration.md) - Heuristic parameter documentation
- [Tool Contract](mcp/tool_contract.md) - Complete API reference
- [README](../README.md) - Quick start guide
