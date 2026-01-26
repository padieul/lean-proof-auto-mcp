# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/claude-code) when working with code in this repository.

## Project Overview

**lean-proof-auto-mcp** is a Model Context Protocol (MCP) server for Lean 4 proof automation analysis and annotation discovery. It provides deterministic tooling to analyze Lean proofs, assess automation potential (e.g., `aesop`, `grind`), and discover automation annotations.

- **API Version**: 1.0 (Production Ready)
- **Python Version**: 3.10+
- **Package Manager**: uv

## Common Commands

```bash
# Install dependencies
uv sync --dev

# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/unit/           # Unit tests
uv run pytest tests/property/       # Property-based tests (Hypothesis)
uv run pytest tests/integration/    # Integration tests
uv run pytest tests/mcp_contract/   # Contract tests

# Type checking
uv run mypy .

# Linting and formatting
uv run ruff check . --fix
uv run ruff format .

# Run pre-commit hooks
uv run pre-commit run --all-files

# Run the MCP server
uv run lean-proof-auto-mcp
```

## Architecture

The codebase follows **hexagonal architecture** with strict separation of concerns:

```
src/lean_proof_auto_mcp/
├── core/           # Pure domain logic (no external dependencies)
│   ├── automation_detection.py  # Detect existing automation in proofs
│   ├── config.py                # Configuration management
│   ├── features.py              # Feature extraction from Lean code
│   ├── format.py                # Output formatting
│   ├── indexer.py               # Theorem indexing
│   ├── lean_syntax.py           # Lean syntax parsing
│   ├── ranking.py               # Theorem ranking algorithms
│   ├── scoring.py               # Automation scoring heuristics
│   ├── segmenter.py             # Code segmentation
│   ├── source.py                # Source code handling
│   └── verify_domain.py         # Verification domain types
├── adapters/       # External interface adapters
│   ├── errors.py                # Error handling
│   └── router.py                # Request routing
├── tools/          # MCP tool implementations
│   ├── scan_file.py             # scan_file tool
│   ├── scan_theorem.py          # scan_theorem tool
│   └── rank_targets.py          # rank_targets tool
├── lean/           # Lean-specific utilities
├── workspace/      # Workspace management
├── observability/  # Logging and metrics
├── server.py       # MCP server entry point
├── config.py       # Top-level configuration
└── heuristics.yaml # Default heuristic parameters
```

## Design Patterns (Mandatory)

These patterns are enforced throughout the codebase (see `.kiro/steering/code-conventions.md`):

1. **Hexagonal Architecture**: Core logic has no external dependencies; all I/O through ports/adapters
2. **Dependency Injection**: Objects receive dependencies via constructor, wiring in composition root
3. **Command Pattern**: Operations encapsulated as immutable data structures with handlers
4. **Strategy Pattern**: Behavioral variation via interchangeable algorithms, not if/else chains
5. **Builder Pattern**: Complex objects constructed step-by-step with invariant validation
6. **Result/Either Pattern**: Explicit success/failure in return values; exceptions for programmer errors only

## MCP Tools

The server exposes three main tools:

- **scan_file**: Analyze all theorems in a Lean file for automation potential
- **scan_theorem**: Deep structural analysis of a single theorem
- **rank_targets**: Rank theorems by automation potential using configurable objectives

### Ranking Objectives

- `maximize_success`: Quick wins, high success rate
- `maximize_impact`: Maximum time saved
- `maximize_subgoal_automation`: Partial automation opportunities
- `balanced`: General-purpose ranking

## Key Concepts

### Automation Profile

Each theorem gets an automation profile with:
- `whole_goal_potential`: Likelihood aesop/grind can solve entire goal
- `subgoal_potential`: Likelihood automation can help with subgoals
- `annotation_value`: ROI of adding automation annotations

### Tier System

Theorems are classified into tiers (relative to file):
- **S-tier** (top 10%): Exceptional candidates
- **A-tier** (10-25%): Strong candidates
- **B-tier** (25-50%): Good candidates
- **C-tier** (50-75%): Acceptable candidates
- **D-tier** (75-100%): Weak candidates

### Already-Automated Detection

The system detects existing automation:
- Tactic usage: `by aesop`, `by grind`, `by simp`
- Attributes: `@[aesop]`, `@[simp]`
- Trivial proofs: `:= rfl`, `:= trivial`

## Configuration

All heuristics are configurable via YAML. Priority order:
1. `config_path` parameter in request
2. `LEAN_PROOF_AUTO_MCP_CONFIG` environment variable
3. Package default (`heuristics.yaml`)

## Testing Strategy

- **Unit tests**: Test core logic in isolation
- **Property tests**: Hypothesis-based testing for invariants
- **Integration tests**: Test component interactions
- **Contract tests**: Verify MCP API contract compliance

## Specs and Steering

Design specifications live in `.kiro/specs/`. Key specs:
- `lean-verify-tool/`: Verification tool design
- `rank-targets/`: Ranking system design
- `scan-rank-shared-semantics/`: Shared concepts between scan/rank
- `static-analysis-tools/`: Static analysis design

Steering files in `.kiro/steering/` define architectural constraints.
