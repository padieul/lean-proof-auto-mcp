# Overview

`lean-proof-auto-mcp` is an MCP server for deterministic Lean 4 analysis, proof
automation probing, proof validation, and context extraction.

## Implemented MCP tools

- `scan_file`
- `scan_theorem`
- `rank_targets`
- `verify`
- `probe`
- `probe_file`
- `search_automated_proof`
- `try_automated_proof`
- `get_proof_context`

## Current architecture shape

The runtime follows a composition-root pattern in `tools/*.py`:

1. Validate/coerce MCP args.
2. Build command/config objects.
3. Wire concrete adapters (querier, validator, metadata, workspace provider).
4. Call core handler/orchestrator.
5. Normalize to stable JSON response.

See `docs/architecture/system_overview.md` for detailed diagrams and runtime flows.

## Runtime guarantees

- Deterministic response envelopes with `status` and `run_id`.
- Explicit status semantics (tool-level success/fail/timeout/error style).
- Lean server reuse across tool calls per project root.
- Range-based harness construction for proof-attempt tools.

## Workspace behavior (current)

- Auto-detection currently resolves to `none` mode in runtime adapters.
- `none` mode runs against the project root directly (no temp/worktree isolation).
- `worktree` and `temp` providers still exist in adapter code but are not the
  default path used by the current composition roots.

See `docs/workspace_modes.md` for details.
