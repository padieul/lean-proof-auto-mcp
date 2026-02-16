# MCP Tools Documentation

This directory contains documentation for all Model Context Protocol (MCP) tools provided by the `lean-proof-auto-mcp` server.

## Available Tools

### Core Analysis Tools

#### [scan_file](./tools/scan_file.md)
Analyzes a Lean file to extract automation profiles for all theorem declarations. Provides whole-goal and subgoal automation potential scores for each theorem.

**Use Cases:**
- Discover all theorems in a file
- Get automation potential scores
- Identify candidates for proof automation

#### [scan_theorem](./tools/scan_theorem.md)
Performs deep structural analysis of a single theorem for enhanced automation scoring. Provides more detailed analysis than `scan_file` by examining proof structure.

**Use Cases:**
- Deep analysis of specific theorems
- Enhanced scoring for ranking decisions
- Detailed proof structure insights

#### [rank_targets](./tools/rank_targets.md)
Provides deterministic, objective-driven ranking of theorem declarations within a Lean file to support proof automation decision-making.

**Use Cases:**
- Prioritize theorems for automation
- Optimize automation effort
- Filter by confidence thresholds
- Skip already-automated theorems

### Verification Tools

#### [verify](./tools/verify.md)
Provides deterministic, sandboxed, budget-bounded verification of Lean files and theorems. The foundational Lean execution primitive for the repository.

**Use Cases:**
- Validate Lean file compilation
- Verify specific theorems
- Check patches before application
- Continuous integration testing
- Deterministic testing workflows

### Proof Automation Tools

The following tools are implemented for proof automation workflows:

- **probe**: Single-theorem automation probe and classification
- **probe_file**: Batch probe across many theorems in a file
- **search_automated_proof**: Bounded hint-search for automation
- **try_automated_proof**: Validate a proposed proof attempt
- **get_proof_context**: Extract rich theorem context for iterative reasoning

## Tool Categories

### Analysis & Discovery
- `scan_file` - File-level theorem discovery
- `scan_theorem` - Deep theorem analysis

### Ranking & Prioritization
- `rank_targets` - Objective-driven theorem ranking

### Verification & Testing
- `verify` - Lean compilation verification

### Proof Automation
- `probe` - Interactive proof exploration
- `probe_file` - Automated proof search
- `search_automated_proof` - Annotation-guided search
- `try_automated_proof` - Proof attempt validation
- `get_proof_context` - Context extraction

## Common Patterns

### API Versioning

All tools include an `api_version` field in both requests and responses:

```json
{
  "api_version": "1.0",
  "tool": "tool_name",
  ...
}
```

### Response Structure

All tools follow a consistent response structure:

```json
{
  "api_version": "string",
  "status": "success | fail | timeout | error",
  "run_id": "string",
  "tool": "string",
  ...
}
```

### Status Values

- **success**: Operation completed successfully
- **fail**: Operation completed but found errors or issues
- **timeout**: Operation exceeded time budget
- **error**: Tool encountered internal error

### Diagnostics

All tools provide structured diagnostics when issues occur:

```json
{
  "diagnostics": [
    {
      "severity": "error | warning | info",
      "message": "string",
      "location": {
        "file": "string",
        "line": "number",
        "col": "number"
      }
    }
  ]
}
```

### Run IDs

Every tool invocation generates a unique `run_id` for:
- Artifact lookup
- Correlation across tools
- Debugging and auditing

Format: `{tool}-{timestamp}-{hash}`

Example: `verify-20250126-143022-a1b2c3d4`

## Configuration

### Custom Heuristics

Most tools support custom heuristic configuration via:

1. **Explicit parameter**: `config_path` in request
2. **Environment variable**: `LEAN_PROOF_AUTO_MCP_CONFIG`
3. **Package default**: Built-in `heuristics.yaml`

See [Configuration Documentation](../configuration.md) for details.

### Artifact Storage

Tools that generate artifacts store them under:

```
{LPAM_ARTIFACTS_DIR}/{run_id}/
  ├── request.json
  ├── result.json
  └── tool_specific_files...
```

Set `LPAM_ARTIFACTS_DIR` environment variable to control location.

## Integration Examples

### Workflow 1: Discover and Verify

```python
# 1. Scan file for theorems
scan_result = scan_file({"file": "MyFile.lean"})

# 2. Verify specific theorem
theorem_id = scan_result["theorems"][0]["theorem_id"]
verify_result = verify({
    "file": "MyFile.lean",
    "theorem_id": theorem_id,
    "budget_s": 15.0
})
```

### Workflow 2: Rank and Verify Top Candidates

```python
# 1. Rank theorems by success likelihood
rank_result = rank_targets({
    "file": "MyFile.lean",
    "objective": "maximize_success",
    "skip_already_automated": True,
    "limit": 10
})

# 2. Verify top-ranked theorem
top_theorem = rank_result["ranking"][0]
verify_result = verify({
    "file": top_theorem["file"],
    "theorem_id": top_theorem["theorem_id"],
    "budget_s": 20.0
})
```

### Workflow 3: Deep Analysis and Verification

```python
# 1. Deep analysis of specific theorem
scan_result = scan_theorem({
    "file": "MyFile.lean",
    "theorem_id": "MyFile.my_theorem"
})

# 2. Verify if high potential
if scan_result["automation_profile"]["whole_goal_potential"]["aesop"] > 0.7:
    verify_result = verify({
        "file": "MyFile.lean",
        "theorem_id": "MyFile.my_theorem",
        "budget_s": 30.0
    })
```

## JSON Schemas

Formal JSON schemas for all tools are available in the [schemas](./schemas/) directory:

- [verify_input.json](./schemas/verify_input.json)
- [verify_output.json](./schemas/verify_output.json)
- More schemas coming soon...

## Tool Contract

See [Tool Contract](./tool_contract.md) for detailed information about:
- API versioning
- Common response fields
- Migration guides
- Complete tool specifications

## Performance Characteristics

### Analysis Tools
- **scan_file**: < 50ms for 200 theorems
- **scan_theorem**: < 50ms per theorem
- **rank_targets**: < 50ms (without deep structure), < 200ms (with deep structure)

### Verification Tools
- **verify**: Overhead < 500ms beyond Lean compilation time
- **verify timeout**: Enforced within 100ms of budget

### Resource Usage
- **Memory**: Depends on Lean compilation (typically 500MB - 2GB)
- **Disk**: Workspace size equals project size
- **Concurrency**: All tools support concurrent invocations

## Error Handling

All tools follow consistent error handling:

1. **Input Validation**: Errors returned immediately with clear messages
2. **Execution Errors**: Structured diagnostics with severity levels
3. **Cleanup Guarantees**: Resources cleaned up even on errors
4. **Partial Results**: Returned when possible

## Support and Feedback

For issues, questions, or feature requests:
- Check tool-specific documentation
- Review [Tool Contract](./tool_contract.md)
- Consult [Configuration Documentation](../configuration.md)
- File issues on the project repository

## Version History

### API 1.0 (Current)
- Added `verify` tool for Lean verification
- Enhanced `rank_targets` with tier system and already-automated detection
- Added configuration system for all tools
- Fixed confidence value reporting in notes

### API 0.1 (Legacy)
- Initial release with `scan_file`, `scan_theorem`, `rank_targets`
