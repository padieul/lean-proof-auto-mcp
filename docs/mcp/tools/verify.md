# verify Tool

## Overview

The `verify` tool is the foundational Lean execution primitive for the `lean-proof-auto-mcp` repository. It provides deterministic, sandboxed, budget-bounded verification of Lean files and theorems using LeanInteract as the execution backend.

## Purpose

The `verify` tool answers one fundamental question: "Does Lean accept this scope (file or theorem), and if not, what are the diagnostics?"

This tool establishes the core Lean execution runtime that other tools (`probe`, `probe_file`, `search_automated_proof`, `try_automated_proof`, `get_proof_context`) reuse. It is pure infrastructure with no LLM calls, designed for reproducible verification in isolated workspaces.

## Use Cases

### File-Level Verification
Verify that a complete `.lean` file compiles successfully within a time budget. Useful for:
- Validating changes before applying patches
- Testing automation workflows
- Continuous integration checks
- Pre-commit validation

### Theorem-Level Verification
Verify a specific theorem without recompiling the entire file. Useful for:
- Faster feedback on localized changes
- Targeted testing of theorem modifications
- Incremental development workflows
- Proof exploration and refinement

### Deterministic Testing
Receive identical JSON outputs for identical inputs, enabling:
- Reproducible test results
- Reliable automation pipelines
- Consistent error reporting
- Regression detection

## Input Schema

```json
{
  "file": "string (required)",
  "theorem_id": "string | null (optional)",
  "budget_s": "number (optional, default: 30.0)",
  "max_log_excerpt_chars": "number (optional, default: 2000)",
  "store_full_logs": "boolean (optional, default: true)",
  "workspace_mode": "string | null (optional, values: 'worktree' | 'temp' | null)"
}
```

### Parameters

#### `file` (required)
- **Type**: `string`
- **Description**: Path to the `.lean` file to verify, relative to the project root
- **Example**: `"Mathlib/Data/List/Basic.lean"`
- **Validation**: Must be non-empty string pointing to existing file

#### `theorem_id` (optional)
- **Type**: `string | null`
- **Default**: `null`
- **Description**: Identifier of specific theorem to verify. If provided, only verifies content up to the theorem's end line
- **Example**: `"List.append_assoc"`
- **Format**: Must match theorem name format from `scan_file` output
- **Behavior**:
  - If valid: Creates abridged file and verifies theorem scope
  - If invalid: Returns error with code `theorem_not_found`

#### `budget_s` (optional)
- **Type**: `number`
- **Default**: `30.0`
- **Description**: Maximum wall-clock time (in seconds) allowed for verification
- **Range**: Must be positive (> 0)
- **Enforcement**: Hard timeout with process tree kill
- **Accuracy**: Timeout enforced within 100ms of specified budget

#### `max_log_excerpt_chars` (optional)
- **Type**: `number`
- **Default**: `2000`
- **Description**: Maximum characters to include in stdout/stderr excerpts in response
- **Purpose**: Keeps response JSON small while providing debugging context
- **Behavior**: Truncates at last newline before limit, appends "... (truncated)"
- **Full Logs**: Complete logs stored in artifacts if `store_full_logs=true`

#### `store_full_logs` (optional)
- **Type**: `boolean`
- **Default**: `true`
- **Description**: Whether to store full logs and metadata in artifact directory
- **Artifacts Created**:
  - `request.json`: Complete input parameters
  - `result.json`: Complete output response
  - `lean_output.log`: Full stdout/stderr from Lean process
- **Location**: `{LPAM_ARTIFACTS_DIR}/{run_id}/`

#### `workspace_mode` (optional)
- **Type**: `string | null`
- **Default**: `null` (auto-detect)
- **Values**:
  - `"worktree"`: Use git worktree for isolation (fast, requires git repo)
  - `"temp"`: Copy project to temp directory (slower, works without git)
  - `null`: Auto-detect based on git repository presence
- **Purpose**: Controls workspace isolation strategy

## Output Schema

```json
{
  "api_version": "0.2.0",
  "status": "success | fail | timeout | error",
  "run_id": "string",
  "file": "string",
  "theorem_id": "string | null",
  "verification_scope_used": "file | theorem | file_fallback",
  "diagnostics": [
    {
      "severity": "error | warning | info",
      "message": "string",
      "location": {
        "file": "string",
        "line": "number",
        "col": "number",
        "end_line": "number | null",
        "end_col": "number | null"
      }
    }
  ],
  "diagnostic_summary": {
    "error_count": "number",
    "warning_count": "number",
    "info_count": "number"
  },
  "evidence": {
    "stdout_excerpt": "string",
    "stderr_excerpt": "string",
    "notes": ["string"]
  },
  "metadata": {
    "workspace_mode": "worktree | temp",
    "workspace_id": "string",
    "repo_commit": "string | null",
    "lean_version": "string | null",
    "lake_version": "string | null"
  },
  "timing": {
    "total_s": "number",
    "lean_execution_s": "number",
    "overhead_s": "number"
  }
}
```

### Response Fields

#### `api_version`
- **Type**: `string`
- **Value**: `"0.2.0"`
- **Description**: API version for schema compatibility tracking

#### `status`
- **Type**: `string`
- **Values**:
  - `"success"`: File/theorem verified successfully with no errors
  - `"fail"`: Verification completed but found errors or type issues
  - `"timeout"`: Verification exceeded budget_s time limit
  - `"error"`: Tool encountered internal error (invalid input, workspace failure, etc.)

#### `run_id`
- **Type**: `string`
- **Format**: `"verify-{timestamp}-{file_hash}"`
- **Example**: `"verify-20250126-143022-a1b2c3d4"`
- **Purpose**: Unique identifier for artifact lookup and correlation
- **Uniqueness**: Guaranteed unique across all invocations

#### `file`
- **Type**: `string`
- **Description**: Echo of input file path

#### `theorem_id`
- **Type**: `string | null`
- **Description**: Echo of input theorem_id (if provided)

#### `verification_scope_used`
- **Type**: `string`
- **Values**:
  - `"file"`: Verified entire file
  - `"theorem"`: Verified specific theorem scope
  - `"file_fallback"`: Attempted theorem verification but fell back to file
  - `"none"`: No verification performed (error case)

#### `diagnostics`
- **Type**: `array`
- **Description**: Structured compilation diagnostics from Lean
- **Sorting**: Deterministically sorted by (file, line, col, severity, message)
- **Fields**:
  - `severity`: Error level (`"error"`, `"warning"`, `"info"`)
  - `message`: Human-readable diagnostic message
  - `location`: Source location with file, line, col, optional end_line/end_col

#### `diagnostic_summary`
- **Type**: `object`
- **Description**: Aggregate counts of diagnostics by severity
- **Fields**:
  - `error_count`: Number of error-level diagnostics
  - `warning_count`: Number of warning-level diagnostics
  - `info_count`: Number of info-level diagnostics
- **Consistency**: Counts always match diagnostics array

#### `evidence`
- **Type**: `object`
- **Description**: Supporting evidence for verification result
- **Fields**:
  - `stdout_excerpt`: Truncated stdout from Lean process
  - `stderr_excerpt`: Truncated stderr from Lean process
  - `notes`: Array of structured notes (error codes, context)

#### `metadata`
- **Type**: `object`
- **Description**: Execution context and environment information
- **Fields**:
  - `workspace_mode`: Isolation strategy used (`"worktree"` or `"temp"`)
  - `workspace_id`: Unique workspace identifier
  - `repo_commit`: Git commit hash (if available)
  - `lean_version`: Lean toolchain version (if detected)
  - `lake_version`: Lake build system version (if detected)

#### `timing`
- **Type**: `object`
- **Description**: Execution time breakdown
- **Fields**:
  - `total_s`: Total wall-clock time for verification
  - `lean_execution_s`: Time spent in Lean process
  - `overhead_s`: Tool overhead (workspace setup, cleanup, parsing)
- **Performance**: Overhead typically < 500ms

## Usage Examples

### Example 1: File-Level Verification (Success)

**Request:**
```json
{
  "file": "Mathlib/Data/List/Basic.lean",
  "budget_s": 30.0
}
```

**Response:**
```json
{
  "api_version": "0.2.0",
  "status": "success",
  "run_id": "verify-20250126-143022-a1b2c3d4",
  "file": "Mathlib/Data/List/Basic.lean",
  "theorem_id": null,
  "verification_scope_used": "file",
  "diagnostics": [],
  "diagnostic_summary": {
    "error_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "evidence": {
    "stdout_excerpt": "Lean compilation successful\n",
    "stderr_excerpt": "",
    "notes": []
  },
  "metadata": {
    "workspace_mode": "worktree",
    "workspace_id": "20250126-143022-abc123",
    "repo_commit": "a1b2c3d4e5f6",
    "lean_version": "4.3.0",
    "lake_version": "4.3.0"
  },
  "timing": {
    "total_s": 2.45,
    "lean_execution_s": 2.12,
    "overhead_s": 0.33
  }
}
```

### Example 2: File-Level Verification (Type Error)

**Request:**
```json
{
  "file": "MyProject/BadTheorem.lean",
  "budget_s": 30.0
}
```

**Response:**
```json
{
  "api_version": "0.2.0",
  "status": "fail",
  "run_id": "verify-20250126-143100-b2c3d4e5",
  "file": "MyProject/BadTheorem.lean",
  "theorem_id": null,
  "verification_scope_used": "file",
  "diagnostics": [
    {
      "severity": "error",
      "message": "type mismatch\n  Nat\nhas type\n  Type : Type 1\nbut is expected to have type\n  Prop : Type",
      "location": {
        "file": "MyProject/BadTheorem.lean",
        "line": 15,
        "col": 8,
        "end_line": 15,
        "end_col": 11
      }
    }
  ],
  "diagnostic_summary": {
    "error_count": 1,
    "warning_count": 0,
    "info_count": 0
  },
  "evidence": {
    "stdout_excerpt": "",
    "stderr_excerpt": "error: type mismatch at line 15\n",
    "notes": ["error_code: type_mismatch"]
  },
  "metadata": {
    "workspace_mode": "worktree",
    "workspace_id": "20250126-143100-def456",
    "repo_commit": "a1b2c3d4e5f6",
    "lean_version": "4.3.0",
    "lake_version": "4.3.0"
  },
  "timing": {
    "total_s": 1.82,
    "lean_execution_s": 1.55,
    "overhead_s": 0.27
  }
}
```

### Example 3: Theorem-Level Verification

**Request:**
```json
{
  "file": "Mathlib/Data/List/Basic.lean",
  "theorem_id": "List.append_assoc",
  "budget_s": 15.0
}
```

**Response:**
```json
{
  "api_version": "0.2.0",
  "status": "success",
  "run_id": "verify-20250126-143200-c3d4e5f6",
  "file": "Mathlib/Data/List/Basic.lean",
  "theorem_id": "List.append_assoc",
  "verification_scope_used": "theorem",
  "diagnostics": [],
  "diagnostic_summary": {
    "error_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "evidence": {
    "stdout_excerpt": "Theorem verification successful\n",
    "stderr_excerpt": "",
    "notes": ["scope: theorem", "abridged_file_created"]
  },
  "metadata": {
    "workspace_mode": "worktree",
    "workspace_id": "20250126-143200-ghi789",
    "repo_commit": "a1b2c3d4e5f6",
    "lean_version": "4.3.0",
    "lake_version": "4.3.0"
  },
  "timing": {
    "total_s": 0.95,
    "lean_execution_s": 0.72,
    "overhead_s": 0.23
  }
}
```

### Example 4: Timeout

**Request:**
```json
{
  "file": "MyProject/SlowProof.lean",
  "budget_s": 5.0
}
```

**Response:**
```json
{
  "api_version": "0.2.0",
  "status": "timeout",
  "run_id": "verify-20250126-143300-d4e5f6g7",
  "file": "MyProject/SlowProof.lean",
  "theorem_id": null,
  "verification_scope_used": "file",
  "diagnostics": [],
  "diagnostic_summary": {
    "error_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "evidence": {
    "stdout_excerpt": "Verification in progress...\n... (truncated)",
    "stderr_excerpt": "",
    "notes": ["timeout_exceeded", "budget_s: 5.0", "actual_s: 5.08"]
  },
  "metadata": {
    "workspace_mode": "worktree",
    "workspace_id": "20250126-143300-jkl012",
    "repo_commit": "a1b2c3d4e5f6",
    "lean_version": "4.3.0",
    "lake_version": "4.3.0"
  },
  "timing": {
    "total_s": 5.08,
    "lean_execution_s": 5.08,
    "overhead_s": 0.0
  }
}
```

### Example 5: Invalid Input (Error)

**Request:**
```json
{
  "file": "NonExistent.lean",
  "budget_s": 30.0
}
```

**Response:**
```json
{
  "api_version": "0.2.0",
  "status": "error",
  "run_id": "verify-20250126-143400-e5f6g7h8",
  "file": "NonExistent.lean",
  "theorem_id": null,
  "verification_scope_used": "none",
  "diagnostics": [
    {
      "severity": "error",
      "message": "File not found: NonExistent.lean",
      "location": null
    }
  ],
  "diagnostic_summary": {
    "error_count": 1,
    "warning_count": 0,
    "info_count": 0
  },
  "evidence": {
    "stdout_excerpt": "",
    "stderr_excerpt": "",
    "notes": ["error_code: input_validation_error"]
  },
  "metadata": {},
  "timing": {}
}
```

## Error Codes

Error codes are included in the `evidence.notes` array for programmatic handling:

### Input Validation Errors
- **`input_validation_error`**: Invalid input parameters (missing file, negative budget, etc.)
- **`theorem_not_found`**: Specified theorem_id does not exist in file

### Execution Errors
- **`workspace_creation_failed`**: Cannot create isolated workspace (git worktree or temp copy)
- **`lean_execution_failed`**: Lean process crashed or returned unexpected error
- **`timeout_exceeded`**: Verification exceeded budget_s time limit

### Internal Errors
- **`internal_error`**: Unexpected exception in tool logic
- **`artifact_storage_failed`**: Failed to write artifacts to disk

## Error Handling

### Error Response Structure

All errors return valid JSON with consistent structure:
- `status`: Set to `"error"`
- `diagnostics`: Contains error diagnostic with severity `"error"`
- `evidence.notes`: Contains error code for programmatic handling
- `verification_scope_used`: Set to `"none"` for errors before verification

### Process Cleanup Guarantees

The tool guarantees cleanup in all cases:
- **Success**: Workspace and processes cleaned up normally
- **Failure**: Workspace and processes cleaned up after diagnostics captured
- **Timeout**: Lean process killed, workspace cleaned up within 100ms
- **Error**: All resources cleaned up even on internal exceptions

### Workspace Isolation

All verifications run in isolated workspaces:
- **Git Worktree Mode**: Creates temporary git worktree, never modifies original working tree
- **Temp Copy Mode**: Copies project to temp directory, original files untouched
- **Concurrent Safety**: Multiple verifications can run simultaneously without interference

## Performance Characteristics

### Execution Time

- **Overhead**: < 500ms beyond Lean compilation time
- **Timeout Accuracy**: Within 100ms of specified budget_s
- **Cleanup Time**: < 100ms after completion or timeout

### Resource Usage

- **Memory**: Depends on Lean compilation (typically 500MB - 2GB)
- **Disk**: Workspace size equals project size (git worktree shares .git objects)
- **Processes**: One Lean process per verification (cleaned up on completion)

### Scalability

- **Concurrent Executions**: Supports multiple simultaneous verifications
- **Workspace Isolation**: Each verification gets isolated workspace
- **No Shared State**: Verifications do not interfere with each other

### Optimization Tips

1. **Use theorem-level verification** for faster feedback on localized changes
2. **Set appropriate budget_s** to avoid unnecessary waiting
3. **Use git worktree mode** for faster workspace creation (requires git repo)
4. **Disable store_full_logs** if artifacts not needed (saves disk I/O)
5. **Reduce max_log_excerpt_chars** for smaller response payloads

## Determinism Guarantees

The tool provides deterministic outputs for reproducible testing:

### Identical Inputs → Identical Outputs

For the same repository state and input parameters:
- **Diagnostics**: Always sorted in same order
- **Log Excerpts**: Always truncated at same points
- **JSON Keys**: Always in same order
- **Exception**: `run_id` and timestamps vary by design

### Sorting Rules

- **Diagnostics**: Sorted by (file, line, col, severity, message)
- **Notes**: Sorted lexicographically
- **JSON Keys**: Alphabetically ordered

### Truncation Rules

- **Log Excerpts**: Truncate at last newline before `max_log_excerpt_chars`
- **Notes**: Trim to 200 chars each, cap at 10 notes total

## Integration with Other Tools

### scan_file Integration

The `verify` tool accepts file paths and theorem_id formats from `scan_file`:
```python
# Get theorems from scan_file
scan_result = scan_file({"file": "MyFile.lean"})
theorem_id = scan_result["theorems"][0]["theorem_id"]

# Verify specific theorem
verify_result = verify({
    "file": "MyFile.lean",
    "theorem_id": theorem_id,
    "budget_s": 15.0
})
```

### rank_targets Integration

Verify ranked theorems from `rank_targets`:
```python
# Get ranked theorems
rank_result = rank_targets({"file": "MyFile.lean"})
top_theorem = rank_result["ranked_theorems"][0]

# Verify top-ranked theorem
verify_result = verify({
    "file": top_theorem["file"],
    "theorem_id": top_theorem["theorem_id"],
    "budget_s": 20.0
})
```

### Future Tool Integration

The `verify` tool serves as the foundation for:
- **probe**: Interactive proof state exploration
- **probe_file**: File-level proof search
- **search_automated_proof**: Annotation-guided proof search
- **try_automated_proof**: Validate concrete proof attempts
- **get_proof_context**: Extract theorem context for iterative loops

## Artifact Storage

When `store_full_logs=true` (default), artifacts are stored under:

```
{LPAM_ARTIFACTS_DIR}/{run_id}/
  ├── request.json          # Complete input parameters
  ├── result.json           # Complete output response
  └── lean_output.log       # Full stdout/stderr from Lean
```

### Artifact Retention

- **Default**: Artifacts persist indefinitely
- **Configuration**: Set retention policy via environment variable
- **Cleanup**: Manual cleanup or automated retention policy

### Artifact Lookup

Use `run_id` from response to locate artifacts:
```python
import json
from pathlib import Path

run_id = verify_result["run_id"]
artifact_dir = Path(os.environ["LPAM_ARTIFACTS_DIR"]) / run_id

# Read full logs
full_logs = (artifact_dir / "lean_output.log").read_text()

# Read original request
request = json.loads((artifact_dir / "request.json").read_text())
```

## API Version

**Current Version**: `0.2.0`

### Version History

- **0.2.0**: Initial release with file and theorem-level verification
  - LeanInteract integration
  - Workspace isolation (git worktree + temp copy)
  - Deterministic outputs
  - Artifact storage
  - Timeout enforcement

### Compatibility

- **Breaking Changes**: Require major version bump
- **Backward Compatibility**: Maintained within major version
- **Schema Evolution**: New optional fields allowed in minor versions

## See Also

- [Input Schema](../schemas/verify_input.json)
- [Output Schema](../schemas/verify_output.json)
- [MCP Tool Contract](../tool_contract.md)
- [scan_file Tool](./scan_file.md)
- [rank_targets Tool](./rank_targets.md)
