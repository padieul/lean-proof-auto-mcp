# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-01-26

### Added
- **Verify tool**: Foundational Lean execution primitive for deterministic, sandboxed proof validation
  - File-level and theorem-level verification with budget-bounded execution (default: 30s timeout)
  - Isolated workspace execution via git worktree (preferred) or temp copy (fallback)
  - Structured diagnostics with severity levels (error/warning/info) and precise source locations
  - Deterministic output formatting with sorted diagnostics and stable JSON key ordering
  - Artifact storage system: stores request.json, result.json, and full logs under unique run_id
  - Process cleanup guarantees: no orphaned Lean processes or leaked workspace resources
  - Concurrent execution safety: multiple verifications run in isolated workspaces without interference
  - Hexagonal architecture: core domain logic separated from adapters (LeanInteract, git, filesystem)
  - Integration with existing tools: accepts file paths and theorem_id format from scan_file/rank_targets
  - Comprehensive metadata: workspace mode, repo commit, Lean/Lake versions, execution timing
- `lean-interact` as mandatory dependency for Lean 4 REPL interaction
- LeanInteractRunner adapter for executing Lean verification with timeout enforcement
- GitWorktreeProvider and TempCopyProvider adapters for workspace isolation
- FilesystemArtifactStore adapter for persistent verification artifacts
- Property-based test suite with 19 correctness properties (minimum 100 iterations per property)
- Integration tests with mathlib fixtures for real-world Lean file validation

### Changed
- Moved `lean-interact` from optional to required dependencies
- Coverage artifacts now ignored in version control
- API version remains 1.0 for existing tools (scan_file, scan_theorem, rank_targets)
- Verify tool uses API version 0.2.0 for independent evolution

## [0.1.0] - 2026-01-22

### 🚨 BREAKING CHANGES - API Version 1.0

**No backward compatibility with API 0.1.**

- `rank_targets`: New required parameter `skip_already_automated` (boolean)
- All tools: API version bumped from "0.1" to "1.0"
- Response fields added: `tier` (S/A/B/C/D), `available_objectives`, `tier_distribution`, `already_automated_penalty`

**Migration:** Add `"skip_already_automated": false` to all `rank_targets` calls.

### Added

- Already-automated detection (filters theorems using `aesop`, `grind`, `simp`, automation attributes, trivial proofs)
- Tier system (S/A/B/C/D percentile-based classification)
- Objective discovery (`available_objectives` array with metadata)
- Configuration system (external YAML for all heuristic parameters via `config_path` or `LEAN_PROOF_AUTO_MCP_CONFIG`)

### Fixed

- Confidence values now properly exposed in notes (was always 0.0 in API 0.1)
- `min_confidence` filtering now works correctly

## [0.1.0] - 2026-01-21

### Added
- `scan_file`, `scan_theorem`, `rank_targets` MCP tools
- Contract and property-based tests
- Working-directory configuration support

### Known Issues (Fixed in API 1.0)
- Confidence values always return 0.0
- No already-automated filtering
- No objective discovery
- Hardcoded heuristics
