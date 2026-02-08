# Evaluation Testing Framework

Systematic evaluation of all MCP tools against 23 mathlib fixture files across 7 mathematical domains.

## Quick Start

```bash
# Linux/macOS — using execution script
./tests/lean-proof-auto-mcp-eval_tests/run_eval.sh smoke

# Windows — using execution script
tests\lean-proof-auto-mcp-eval_tests\run_eval.bat smoke

# Or directly via pytest (any platform)
uv run pytest tests/lean-proof-auto-mcp-eval_tests/ -m eval_smoke -v --tb=short
```

## Path Configuration

The framework locates the eval repository automatically:

| Platform | Default Path |
|----------|-------------|
| Linux/macOS | `/home/paul_d/Sources/lean-proof-auto-mcp-eval/` |
| Windows | `C:\Dev\lean-proof-auto-mcp-eval` |

Override with: `LEAN_EVAL_REPO=/custom/path uv run pytest ...`

## Execution Tiers

| Tier | Marker | Scope | Time |
|------|--------|-------|------|
| smoke | `-m eval_smoke` | Totient fixtures only | ~2 min |
| quick | `-m "eval_smoke or eval_quick"` | Data + Group domains | ~10 min |
| normal | `-m "eval_smoke or eval_quick or eval_normal"` | All 23 files | ~30 min |
| full | `-m "eval_smoke or eval_quick or eval_normal or eval_full"` | All + cross-tool | ~2 hours |
| deep | (no marker filter) | Everything | ~8 hours |

## Domain Filtering

Run tests for a specific mathematical domain:

```bash
uv run pytest tests/lean-proof-auto-mcp-eval_tests/ -m eval_algebra -v
```

Available: `eval_algebra`, `eval_analysis`, `eval_data`, `eval_group_theory`, `eval_linear_algebra`, `eval_ring_theory`, `eval_topology`

## Architecture

```
conftest.py          ← Pytest fixtures (session/module/function scoped)
fixtures.py          ← Path resolution + fixture discovery
mcp_client.py        ← MCP client (stdio JSON-RPC with initialize handshake)
result_collector.py  ← Result recording, persistence, baseline comparison
test_verify_eval.py  ← Verify tool evaluation (smoke/quick/normal tiers)
run_eval.sh          ← Tiered execution script (Linux/macOS)
run_eval.bat         ← Tiered execution script (Windows)
reports/             ← Persistent results (gitignored)
```

## Result Files

After running with `ResultCollector.save()`:

- `results.json` — All individual tool results
- `summary.json` — Aggregated stats by tool, domain, status
- `metadata.json` — Execution metadata (count, timestamp)

## Running Unit Tests (no MCP server needed)

```bash
uv run pytest tests/lean-proof-auto-mcp-eval_tests/test_fixtures.py tests/lean-proof-auto-mcp-eval_tests/test_result_collector.py tests/lean-proof-auto-mcp-eval_tests/test_mcp_client.py -v
```

## Bugs Found and Fixed (2026-02-08)

### Bug 1: `LocalProject(path=...)` — wrong parameter name (server_manager.py)

`LeanInteractServerManager._create_server()` called `LocalProject(path=str(workspace))` but the
actual API is `LocalProject(directory=str(workspace))`. This caused a silent `TypeError`, falling
through to standalone `LeanREPLConfig()` with no project context. The standalone config picked up
whatever default toolchain was available (v4.27.0-rc1), whose REPL build was broken (Pickle.c null
character warnings), causing an infinite hang on every verify call.

Fix: `LocalProject(path=...)` → `LocalProject(directory=...)` in `src/lean_proof_auto_mcp/lean/server_manager.py`.

### Bug 2: Windows `charmap` codec error (mcp_client.py)

`MCPClient._start_process()` used `subprocess.Popen(..., text=True)` without specifying
`encoding="utf-8"`. On Windows, `text=True` defaults to the system encoding (cp1252). Lean
diagnostic messages contain Unicode math symbols (φ, ℕ, ∈, ⊢) which cp1252 cannot decode,
causing `'charmap' codec can't decode byte 0x9d` errors and dropped MCP responses.

Fix: Added `encoding="utf-8"` to Popen and `PYTHONIOENCODING=utf-8` to the subprocess env
in `tests/lean-proof-auto-mcp-eval_tests/mcp_client.py`.

### Config 1: Verify budget too low (test_verify_eval.py)

Default `budget_s=30.0` is too short for Mathlib projects. Lean cold start with Mathlib imports
takes ~35-45s. Every first verify call timed out.

Fix: Tests now pass `budget_s=120.0` explicitly.

### Config 2: MCP client timeout too low (conftest.py)

`MCPClient` timeout was 60s. With cold start + verification, responses can take 90s+.

Fix: Increased to `timeout=180.0`.

### Verification

Debug script (`_debug_test_verify_eval.py`) confirmed all fixes:
- Smoke tier: 1/1 PASS (33.8s)
- Quick tier: 6/6 PASS (165s total, ~27s per fixture)
- Pytest smoke: 1/1 PASS (29.37s)
