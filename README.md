# lean-proof-auto-mcp

A Model Context Protocol (MCP) server for **Lean 4 proof automation analysis and annotation discovery**.

This project provides deterministic tooling to analyze Lean proofs, probe automation potential (e.g. `aesop`, `grind`), and search for automation annotations in a reproducible, LLM-agnostic way.

**Status:** early development phase
**Audience:** Lean 4 community

## Installation (dev)

```bash
uv sync --dev
uv run pre-commit install

uv run ruff check . --fix
uv run ruff format .
uv run pytest
uv run mypy .
```



## Goals

- Expose Lean proof analysis and automation probes via MCP tools
- Treat annotation discovery as a bounded, deterministic search problem
- Support interactive use (IDE + LLMs) and large-scale batch automation (e.g. via AI agents)
- Remain LLM-agnostic: the server executes experiments, clients decide policy

## Background

This project builds on a prototype explored at ItaLean 2025 and focuses on
scaling annotation-based proof automation in existing Lean codebases
(e.g. Mathlib).

More detailed design docs will live in `docs/`. Specs and steering
files for **Kiro** can be found in `.kiro/steering` and `.kiro/specs`

## Citation

If you use this project in academic work, please cite it using the
`CITATION.cff` file provided in the repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
