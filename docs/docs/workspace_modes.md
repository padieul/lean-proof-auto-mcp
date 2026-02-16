# Workspace Modes

This document describes current workspace behavior as implemented in
`adapters/workspace_provider.py` and current tool composition roots.

## Supported provider modes

`create_workspace_provider(...)` supports:

- `none`: no isolation, run directly in project root
- `worktree`: git worktree-based isolation
- `temp`: temp-copy isolation

## Current runtime default

`detect_workspace_mode(...)` currently returns `none`.

In current composition roots (`tools/verify.py`, `tools/probe.py`,
`tools/probe_file.py`), providers are created with `workspace_mode=None`, which
means runtime auto-detection is used. In practice this resolves to `none`.

## Practical effect

- Verification/probe workflows run against the project root path directly.
- No temp copy or git worktree is created unless composition roots are changed
  to request `temp` or `worktree`.

## Tool parameter note

The FastMCP `verify` endpoint accepts a `workspace_mode` argument, but current
composition-root wiring does not pass that value through to the provider
factory. The runtime still uses auto-detected mode.

## Mode characteristics

| Mode | Isolation | Speed | Requirements |
|---|---|---|---|
| `none` | none | fastest | none |
| `worktree` | high | medium/high | git repository |
| `temp` | high | lowest | filesystem copy |

## When to revisit mode choice

If strict isolation is required for your deployment model, update tool
composition roots to pass explicit provider mode (`worktree` or `temp`) into
`create_workspace_provider(...)`.
