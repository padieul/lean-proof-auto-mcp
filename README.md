# lean-proof-auto-mcp

A Model Context Protocol (MCP) server for **Lean 4 proof automation analysis and annotation discovery**.

This project provides deterministic tooling to analyze Lean proofs, probe automation potential (e.g. `aesop`, `grind`), and search for automation annotations in a reproducible, LLM-agnostic way.

**Status:**
- MCP Server Version: 0.2.0
- API Version: 1.0 - Production Ready

**Audience:** Lean 4 community

## Features

- **Proof Analysis**: Scan Lean files to extract automation profiles for all theorems
- **Intelligent Ranking**: Rank theorems by automation potential using configurable objectives
- **Already-Automated Detection**: Filter out theorems that already use automation tactics
- **Tier System**: S/A/B/C/D tier classification for quick quality assessment
- **Configurable Heuristics**: Customize all scoring parameters via YAML configuration
- **Objective Discovery**: Explore available ranking strategies without trial-and-error
- **Deterministic**: Same inputs always produce identical outputs
- **LLM-Agnostic**: Server executes experiments, clients decide policy

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/lean-proof-auto-mcp.git
cd lean-proof-auto-mcp

# Install dependencies
uv sync --dev
uv run pre-commit install

# Run tests
uv run pytest

# Type checking
uv run mypy .

# Linting and formatting
uv run ruff check . --fix
uv run ruff format .
```

### Basic Usage

#### Scan a Lean File

Analyze all theorems in a file:

```json
{
  "tool": "scan_file",
  "arguments": {
    "file": "Mathlib/Data/List/Basic.lean"
  }
}
```

Response includes automation profiles with confidence values:

```json
{
  "api_version": "1.0",
  "status": "success",
  "theorems": [
    {
      "theorem_id": "List.append_nil",
      "automation_profile": {
        "whole_goal_potential": {"aesop": 0.90, "grind": 0.75},
        "subgoal_potential": {"aesop": 0.85, "grind": 0.70},
        "annotation_value": 0.80
      },
      "notes": [
        "confidence: 0.95",
        "very high confidence proof",
        "excellent aesop candidate"
      ]
    }
  ]
}
```

#### Rank Theorems by Automation Potential

Get top automation candidates:

```json
{
  "tool": "rank_targets",
  "arguments": {
    "file": "Mathlib/Data/List/Basic.lean",
    "objective": "maximize_success",
    "skip_already_automated": false,
    "limit": 10
  }
}
```

Response includes ranked theorems with tiers:

```json
{
  "api_version": "1.0",
  "status": "success",
  "ranking": [
    {
      "theorem_id": "List.append_nil",
      "score": 0.92,
      "tier": "S",
      "components": {
        "success_likelihood": 0.95,
        "impact": 0.45,
        "annotation_value": 0.80,
        "subgoal_potential": 0.60,
        "risk": 0.10,
        "already_automated_penalty": 0.0
      },
      "reasons": [
        "confidence: 0.95",
        "very high confidence proof",
        "excellent aesop candidate (0.90)"
      ]
    }
  ],
  "summary": {
    "total": 150,
    "returned": 10,
    "skipped_low_confidence": 0,
    "skipped_already_automated": 0,
    "tier_distribution": {
      "S": 15,
      "A": 22,
      "B": 38,
      "C": 37,
      "D": 38
    }
  },
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate"
    }
  ]
}
```

#### Skip Already-Automated Theorems

Focus on unannotated work:

```json
{
  "tool": "rank_targets",
  "arguments": {
    "file": "Mathlib/Algebra/Ring/Basic.lean",
    "objective": "maximize_impact",
    "skip_already_automated": true,
    "limit": 10
  }
}
```

This filters out theorems that already use `aesop`, `grind`, `simp`, or have automation attributes like `@[aesop]`, `@[simp]`.

### Ranking Objectives

Choose the objective that matches your use case:

- **maximize_success**: Quick wins, high success rate (first-time automation, demos)
- **maximize_impact**: Maximum time saved (mature projects, refactoring)
- **maximize_subgoal_automation**: Partial automation (incremental automation, complex proofs)
- **balanced**: General-purpose ranking (exploratory analysis)

### Tier System

Each ranked theorem includes a tier classification:

- **S-tier** (top 10%): Exceptional candidates, highest priority
- **A-tier** (10-25%): Strong candidates, high priority
- **B-tier** (25-50%): Good candidates, medium priority
- **C-tier** (50-75%): Acceptable candidates, lower priority
- **D-tier** (75-100%): Weak candidates, consider skipping

Tiers are relative to the file, not absolute scores.

### Workspace Modes

The verify tool supports two workspace isolation modes:

- **temp** (default): Copies files to a temporary directory. Safest option, works everywhere.
- **worktree**: Uses git worktree for faster isolation. Requires git repository.

**Default behavior**: The system always uses temp mode unless you explicitly request worktree mode.

To use worktree mode explicitly:

```json
{
  "tool": "verify",
  "arguments": {
    "file": "MyTheorem.lean",
    "budget_s": 30.0,
    "workspace_mode": "worktree"
  }
}
```

**For tests**: Always use temp mode to avoid polluting your development repository with git worktrees.

See [Workspace Modes Documentation](docs/workspace_modes.md) for complete details on workspace isolation, trade-offs, and best practices.

### Configuration

Customize all heuristic parameters via YAML configuration:

```yaml
# custom_heuristics.yaml
version: "1.0"

confidence:
  base_score: 0.4  # Increase base confidence
  bonuses:
    proof_structure: 0.25  # Reward good structure more

aesop_scoring:
  base_score: 0.3  # Higher base for structural proofs

tiers:
  s_tier_percentile: 5  # Top 5% are S-tier (stricter)
```

Use custom configuration:

```json
{
  "tool": "rank_targets",
  "arguments": {
    "file": "MyFile.lean",
    "objective": "maximize_success",
    "skip_already_automated": false,
    "config_path": "/path/to/custom_heuristics.yaml"
  }
}
```

Or via environment variable:

```bash
export LEAN_PROOF_AUTO_MCP_CONFIG=/path/to/custom_heuristics.yaml
```

See [Configuration Guide](docs/configuration.md) for complete documentation.

## Migration Guide: API 0.1 → 1.0

### Breaking Changes

1. **New Required Parameter**: `skip_already_automated` is now required for `rank_targets`
2. **Response Structure**: All tools include new fields (tier, available_objectives, etc.)
3. **Confidence Values**: Now properly exposed in notes (was always 0.0 in API 0.1)
4. **API Version**: Bumped from "0.1" to "1.0"

### Migration Steps

#### Update rank_targets Calls

**Before (API 0.1):**
```json
{
  "file": "MyFile.lean",
  "objective": "maximize_success"
}
```

**After (API 1.0):**
```json
{
  "file": "MyFile.lean",
  "objective": "maximize_success",
  "skip_already_automated": false
}
```

#### Update Response Parsing

**New fields in rank_targets response:**
- `tier` (string): S/A/B/C/D tier classification
- `available_objectives` (array): List of available objectives with metadata
- `already_automated_penalty` (number): Penalty component in components
- `tier_distribution` (object): Count of theorems in each tier
- `skipped_already_automated` (number): Count of filtered theorems
- `config_source` (string): Configuration source in metadata

**New fields in scan_file/scan_theorem response:**
- Numeric confidence in notes: `"confidence: 0.85"`
- `config_source` (string): Configuration source in metadata

#### Update API Version Checks

Change version checks from `"0.1"` to `"1.0"`:

```python
# Before
if response["api_version"] == "0.1":
    # ...

# After
if response["api_version"] == "1.0":
    # ...
```

### No Backward Compatibility

API 1.0 is **not backward compatible** with 0.1. All clients must be updated to use the new API.

## Documentation

- [Tool Contract](docs/mcp/tool_contract.md) - Complete API reference
- [Configuration Guide](docs/configuration.md) - Heuristic parameter documentation
- [JSON Schemas](docs/mcp/schemas/) - Request/response schemas
- [Architecture](docs/architecture/) - System design and decisions

## Development

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Property-based tests
uv run pytest tests/property/

# Integration tests
uv run pytest tests/integration/

# Contract tests
uv run pytest tests/mcp_contract/
```

### Code Quality

```bash
# Type checking
uv run mypy .

# Linting
uv run ruff check .

# Formatting
uv run ruff format .

# Pre-commit hooks
uv run pre-commit run --all-files
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

More detailed design docs live in `docs/`. Specs and steering
files for **Kiro** can be found in `.kiro/steering` and `.kiro/specs`.

## Citation

If you use this project in academic work, please cite it using the
`CITATION.cff` file provided in the repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
