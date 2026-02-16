# lean-proof-auto-mcp

Deterministic Model Context Protocol (MCP) server for Lean 4 proof analysis, automation probing, proof validation, and theorem context extraction.

## Current status

- Package/server version: `0.4.0`
- Tool API version in response envelopes: `1.1.0`

## Implemented tools

| Tool | Purpose | Status values |
|---|---|---|
| `scan_file` | Static theorem-level analysis for one Lean file | `success`, `fail` |
| `scan_theorem` | Deep analysis for one theorem target | `success`, `fail` |
| `rank_targets` | Objective-based ranking and tiering | `success`, `fail` |
| `verify` | Lean validation for file/theorem scope | `success`, `fail`, `timeout`, `error` |
| `probe` | Single-theorem automation probe (`aesop`, `aesop?`, `grind`) | `success`, `fail`, `timeout`, `error` |
| `probe_file` | Batch probe across theorem set | `success`, `partial`, `error` |
| `search_automated_proof` | Hint-set search for automated proofs | `success`, `partial`, `fail`, `error` |
| `try_automated_proof` | Validate a concrete proof attempt | `success`, `rejected`, `incomplete`, `timeout`, `error` |
| `get_proof_context` | Extract statement/proof/scope/similar-proof context | `success`, `fail`, `error` |

## Quick start

### Prerequisites

- Python `>=3.10`
- `uv`
- Lean 4 project/toolchain for runtime tools (`verify`, `probe`, `search_automated_proof`, `try_automated_proof`)

### Install and validate

```bash
uv sync --dev
uv run pre-commit install
uv run pytest
uv run mypy .
uv run ruff check .
uv run ruff format .
```

### Run the MCP server

```bash
uv run lean-proof-auto-mcp
```

Optional environment variables:

- `LPAMCP_SERVER_NAME`
- `LPAMCP_API_VERSION`
- `LPAMCP_WORKING_DIR`

## Typical workflow

1. Discover and triage with `scan_file` and `rank_targets`.
2. Inspect one target with `scan_theorem`.
3. Measure baseline automation with `probe` or `probe_file`.
4. Pull theorem context with `get_proof_context`.
5. Search candidate automation with `search_automated_proof`.
6. Validate candidate scripts with `try_automated_proof`.
7. Run final check with `verify`.

## Minimal examples

`scan_file`:

```json
{
  "tool": "scan_file",
  "arguments": {
    "file": "Mathlib/Data/List/Basic.lean"
  }
}
```

`rank_targets`:

```json
{
  "tool": "rank_targets",
  "arguments": {
    "file": "Mathlib/Data/List/Basic.lean",
    "objective": "balanced",
    "limit": 30
  }
}
```

`try_automated_proof`:

```json
{
  "tool": "try_automated_proof",
  "arguments": {
    "file": "Mathlib/Data/List/Basic.lean",
    "theorem_id": "List.append_nil",
    "proof_attempt": "by aesop",
    "timeout_s": 10.0
  }
}
```

## Runtime notes

- Tool responses are normalized and deterministic, with `status` and `api_version`.
- Lean server instances are reused by project root.
- Harness-based tools use range-based source splicing (`RangeBasedHarnessConstructor`).

### Workspace behavior (current)

- Provider modes supported by adapters: `none`, `worktree`, `temp`.
- Current auto-detection resolves to `none` in runtime adapters.
- In current composition roots, workflows run against project root unless wiring is changed to explicitly pass `temp`/`worktree`.
- `verify` accepts a `workspace_mode` argument at the tool boundary, but current composition-root wiring still uses auto-detected mode.

## Configuration

Heuristics configuration source priority:

1. `config_path` request parameter
2. `LEAN_PROOF_AUTO_MCP_CONFIG` environment variable
3. Built-in defaults

See `docs/docs/configuration.md` for full schema and parameter ranges.

## Documentation map

- Overview: `docs/docs/overview.md`
- Tool runtime hub: `docs/docs/mcp/README.md`
- Tool contract: `docs/docs/mcp/tool_contract.md`
- Tool pages: `docs/docs/mcp/tools/`
- Architecture: `docs/docs/architecture/system_overview.md`
- Workspace modes: `docs/docs/workspace_modes.md`
- Workflow: `docs/docs/workflows/interactive_user_flow.md`
- Requirements: `docs/docs/requirements/functional.md`

## Citation

If you use this project in academic work, cite `CITATION.cff`.

## License

MIT. See `LICENSE`.
