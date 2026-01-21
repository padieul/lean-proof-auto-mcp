# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-21

### Added
- `scan_file` MCP tool: static analysis of Lean files (theorem indexing, proof detection, basic automation signals).
- `scan_theorem` MCP tool: theorem-level scan including proof segmentation and automation scoring.
- Contract and property-based tests for both tools.
- Working-directory configuration support.

### Notes
- Pre-1.0 release: tool output schemas may change in minor versions.
