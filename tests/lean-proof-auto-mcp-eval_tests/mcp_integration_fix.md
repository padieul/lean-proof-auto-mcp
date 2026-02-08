# MCP Integration Test Fixes

## Issues Fixed to Enable Real Server Communication

### 1. MCP Protocol Format
**Problem**: Initial implementation used incorrect JSON-RPC format
```python
# ❌ Wrong
{"method": "verify", "params": {"file": "..."}}

# ✅ Correct
{"method": "tools/call", "params": {"name": "verify", "arguments": {"file": "..."}}}
```

### 2. Module Execution
**Problem**: Server couldn't be run directly due to relative imports
```python
# ❌ Wrong - ImportError: attempted relative import with no known parent package
["python", str(server_path)]

# ✅ Correct - Run as module
["python", "-m", "lean_proof_auto_mcp.server"]
```

### 3. PYTHONPATH Configuration
**Problem**: Module execution requires src directory in PYTHONPATH
```python
# ✅ Solution
env = os.environ.copy()
src_dir = server_path.parent.parent  # Get src directory
env['PYTHONPATH'] = str(src_dir)
```

### 4. Working Directory
**Problem**: Server needs to operate in eval repository context
```python
# ✅ Solution
subprocess.Popen(
    ["python", "-m", "lean_proof_auto_mcp.server"],
    cwd=str(working_dir),  # Set to eval repo path
    env=env,               # Include PYTHONPATH
    ...
)
```

## Result
Both integration tests now pass:
- `test_full_lifecycle_with_real_server` ✓
- `test_tool_calls_return_valid_responses` ✓

Server successfully starts, responds to tool calls, and terminates cleanly.
