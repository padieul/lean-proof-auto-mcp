# MCP Tools Runtime

This section is the runtime hub for the MCP tool surface registered in
`src/lean_proof_auto_mcp/server.py`.

## Tool registry

| Tool | API Version | Detailed Page |
|---|---|---|
| `scan_file` | `1.1.0` | `docs/mcp/tools/scan_file.md` |
| `scan_theorem` | `1.1.0` | `docs/mcp/tools/scan_theorem.md` |
| `rank_targets` | `1.1.0` | `docs/mcp/tools/rank_targets.md` |
| `verify` | `1.1.0` | `docs/mcp/tools/verify.md` |
| `probe` | `1.1.0` | `docs/mcp/tools/probe.md` |
| `probe_file` | `1.1.0` | `docs/mcp/tools/probe_file.md` |
| `search_automated_proof` | `1.1.0` | `docs/mcp/tools/search_automated_proof.md` |
| `try_automated_proof` | `1.1.0` | `docs/mcp/tools/try_automated_proof.md` |
| `get_proof_context` | `1.1.0` | `docs/mcp/tools/get_proof_context.md` |

## Generic workflow (tool-agnostic)

```mermaid
flowchart LR
    A["Entry: FastMCP tool function"] --> B["Args validation + command/config build in tools/*.py"]
    B --> C["Core handler/orchestrator invocation"]
    C --> D{"Lean interaction required?"}
    D -- yes --> E["Lean adapters (querier/validator/proof_state)"]
    E --> F["Lean REPL execution"]
    F --> G["Domain result"]
    D -- no --> G
    G --> H["Status mapping + response normalization"]
    H --> I["Output JSON"]
```

## Primary runtime pattern

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant FastMCP as FastMCP
    participant Tool as tools/*.py
    participant Core as Core Handler/Orchestrator
    participant Adapter as Lean/Workspace Adapters
    participant Lean as Lean REPL

    Client->>FastMCP: tools/call(name, args)
    FastMCP->>Tool: router.dispatch(name, args)
    Tool->>Tool: validate args + build command/config
    Tool->>Core: handle(...) / search(...) / extract(...)
    Core->>Adapter: invoke ports
    Adapter->>Lean: command/file execution
    Lean-->>Adapter: diagnostics/result
    Adapter-->>Core: normalized domain result
    Core-->>Tool: result object
    Tool->>Tool: status normalization
    Tool-->>FastMCP: response dict
    FastMCP-->>Client: JSON result
```

## Status set by tool

| Tool | Status values |
|---|---|
| `scan_file` | `success`, `fail` |
| `scan_theorem` | `success`, `fail` |
| `rank_targets` | `success`, `fail` |
| `verify` | `success`, `fail`, `timeout`, `error` |
| `probe` | `success`, `fail`, `timeout`, `error` |
| `probe_file` | `success`, `partial`, `error` |
| `search_automated_proof` | `success`, `partial`, `fail`, `error` |
| `try_automated_proof` | `success`, `rejected`, `incomplete`, `timeout`, `error` |
| `get_proof_context` | `success`, `fail`, `error` |

For semantics and request/response details, use the individual tool pages.
