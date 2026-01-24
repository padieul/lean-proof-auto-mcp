# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
