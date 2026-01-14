# MCP tool contract

## Versioning
- All tools include `api_version`.
- All responses include `status` and `run_id`.

## Common response fields
- `status`: `success` | `fail` | `timeout` | `error` | other terminal states
- `run_id`: unique identifier for artifact lookup
- `diagnostics`: structured list when applicable

## Tool list (v0)
- scan_file
- scan_theorem
- rank_targets
- probe
- probe_file
- search_annotations
- check_patch
- verify
- apply_patch (optional)
- get_artifacts
