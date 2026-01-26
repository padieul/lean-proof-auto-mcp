# Overview

`lean-proof-auto-mcp` is an MCP server that provides deterministic tools for:
- probing Lean 4 automation (`aesop`, `grind`)
- searching for annotation/config changes under a strict budget
- validating patches and collecting reproducible artifacts

## Key properties
- Reproducible: every run has a `run_id` with stored evidence
- Safe: execution happens in isolated workspaces with enforced timeouts
- Bounded: all search/probe operations are time-capped

## Workspace Isolation

The system uses workspace isolation to ensure safe, reproducible verification:

- **temp mode** (default): Copies files to a temporary directory
- **worktree mode**: Uses git worktree for faster isolation

Temp mode is the default for safety and IDE compatibility. Users must explicitly request worktree mode if needed.

See [Workspace Modes Documentation](workspace_modes.md) for complete details.
