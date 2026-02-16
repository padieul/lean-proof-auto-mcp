# scan_file Tool

`scan_file` performs deterministic static analysis of a Lean file and returns
theorem-level automation signals.

## Entrypoint and runtime path

- FastMCP entry: `server.py::scan_file_tool(file)`
- Tool function: `tools/scan_file.py::scan_file`
- Core pipeline: `core/indexer.py` -> `core/features.py` -> `core/scoring.py`

`scan_file` does not execute Lean REPL commands.

## Request fields

```json
{
  "file": "path/to/File.lean"
}
```

## Response highlights

- `api_version`: `1.1.0`
- `status`: `success | fail`
- `tool`: `scan_file`
- `summary.theorem_count`
- `theorems[]` with `location`, `automation`, and `notes`

## Status semantics

| Status | Meaning | Trigger |
|---|---|---|
| `success` | analysis completed | indexing + feature/scoring pipeline returned normally |
| `fail` | request/analysis failed | input validation failure or analysis exception |

## Workflow

```mermaid
flowchart LR
    A["MCP entry"] --> B["args validation"]
    B --> C["read file text"]
    C --> D["build_index"]
    D --> E["extract_features per theorem"]
    E --> F["compute_profile per theorem"]
    F --> G["deterministic formatting"]
    G --> H["response"]
```
