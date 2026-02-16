# MCP Tool Contract

This contract reflects the current implementation in `server.py` and
`tools/*.py`.

## Registered tools

- `scan_file`
- `scan_theorem`
- `rank_targets`
- `verify`
- `probe`
- `probe_file`
- `search_automated_proof`
- `try_automated_proof`
- `get_proof_context`

## Common response envelope

All tools return JSON objects and include:

- `status`: terminal tool status (tool-specific set)
- `api_version`: tool API version string (`1.1.0`)
- Tool-specific correlation fields such as `run_id`, `file`, `theorem_id`
- Structured diagnostics/metadata fields when available

## Status normalization model

Status semantics are normalized at the tool boundary:

- `success`: operation completed with positive terminal outcome
- `fail`: operation completed but requested goal was not achieved
- `partial`: mixed or incomplete-but-usable outcome
- `timeout`: budget exhausted (tools that expose timeout explicitly)
- `rejected`: Lean rejected proof attempt (try_automated_proof only)
- `error`: input/infrastructure/runtime failure

The exact status set is per tool. See `docs/mcp/README.md` for per-tool tables.

## API versioning

All registered tools currently emit `api_version: "1.1.0"`.

## MCP server version

Current MCP server/package version: `0.4.0`.

## Error metadata conventions

Common metadata keys in error/fail paths include:

- `error_code` (for tool/infrastructure errors)
- `fail_code` or `fail_type` (for expected non-success outcomes)
- `error_message` / `fail_message`

Names vary slightly by tool implementation; clients should branch on `status`
first, then inspect metadata payload keys.

## Schemas

Reference schemas remain under `docs/mcp/schemas/`:

- `scan_file.json`
- `scan_theorem.json`
- `rank_targets.json`
- `verify_input.json`
- `verify_output.json`
- `probe.json`
- `probe_file.json`
- `common.json`
