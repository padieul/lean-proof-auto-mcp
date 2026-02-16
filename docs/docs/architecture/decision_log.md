# Architecture Decision Log

## ADR-001: Shared Lean server managers per project root

- **Status:** Adopted
- **Where:** `lean/server_manager.py`
- **Decision:** Reuse `LeanInteractServerManager` instances across tool calls,
  keyed by project root.
- **Why:** Avoid repeated Lean REPL cold starts and reduce end-to-end latency
  for multi-call workflows.

## ADR-002: Range-based harness construction

- **Status:** Adopted
- **Where:** `core/harness_construction.py`
- **Decision:** Build harnesses by splicing Lean-provided declaration value ranges.
- **Why:** Remove brittle hand-parsing of Lean source and make replacement
  behavior deterministic and testable.

## ADR-003: Command/handler orchestration for stateful tools

- **Status:** Adopted
- **Where:** `tools/*.py`, `core/*_domain.py`, `core/search_orchestrator.py`
- **Decision:** Keep validation + composition roots in tool entrypoints; keep
  orchestration logic in core handlers/orchestrators.
- **Why:** Maintain clear separation between transport concerns and domain logic.

## ADR-004: Status normalization at tool boundaries

- **Status:** Adopted
- **Where:** tool entry modules and core handlers
- **Decision:** Normalize rich internal results into stable external MCP status
  codes per tool contract.
- **Why:** Make client behavior predictable while preserving internal detail in
  diagnostics/metadata.

## ADR-005: Current workspace default behavior

- **Status:** Adopted (current implementation)
- **Where:** `adapters/workspace_provider.py`
- **Decision:** Auto-detection returns `none`, so tools run directly in project
  root unless composition roots explicitly request another mode.
- **Why:** Fastest runtime path and avoids temp/worktree overhead in current code.
