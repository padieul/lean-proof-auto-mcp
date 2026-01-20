# Tasks: Static Analysis Tools Implementation

## ⚠️ IMPLEMENTATION PHASES - READ CAREFULLY

This spec uses a **phased approach** to prevent premature implementation:

1. **Phase 0 (Schemas)**: Create JSON schema files only
2. **Phase 1 (Stubs)**: Create MINIMAL placeholder implementations that return valid JSON with fake/empty data
   - **DO NOT implement actual parsing, file reading, or analysis**
   - Stubs should return empty arrays, zero scores, placeholder data
   - Purpose: Enable contract testing before real implementation
3. **Phase 2 (Tests)**: Write tests that validate stub responses
4. **Phase 3 (Core)**: Implement ACTUAL parsing and analysis logic
5. **Phase 4 (Integration)**: Wire tools to core modules, replacing stubs with real functionality

**CRITICAL**: Do not skip ahead. Each phase must be completed before moving to the next.

---

## Phase 0: JSON Schemas

**NOTE: This phase creates JSON schema files only - no code implementation.**

- [x] Create scan_theorem.json schema with complete structure (api_version, status, run_id, tool, file, target, theorem, diagnostics)
- [x] Update scan_file.json schema to include theorems array with automation signals

## Phase 1: Stubs

**⚠️ CRITICAL: This phase creates STUBS ONLY - minimal placeholder implementations that return valid JSON with fake/empty data. DO NOT implement actual parsing, analysis, or core logic. That comes in Phase 3 and Phase 4.**

- [x] Update scan_file stub to include empty theorems array (STUB ONLY - no actual theorem detection)
- [x] Create scan_theorem stub with minimal valid response (STUB ONLY - placeholder data with empty skeleton, empty blocks, zero scores)

**END OF PHASE 1**: At this point, both tools should return valid JSON with placeholder/empty data. No actual Lean parsing or analysis should be implemented yet.

## Phase 2: Contract Tests

**NOTE: This phase creates tests that validate stub responses. Tests should pass with stubs returning placeholder data.**
- [x] Set up test infrastructure (add jsonschema and hypothesis to dependencies, create test directories)
- [x] Write scan_file contract tests (schema compliance, required fields, determinism, error handling)
- [x] Write scan_theorem contract tests (schema compliance, both input modes, structure validation, score ranges)
- [x] Verify all contract tests pass with stub implementations


## Phase 3: Core Modules

**NOTE: This phase implements the ACTUAL parsing and analysis logic. This is where real implementation happens, NOT in Phase 1 stubs.**

- [x] Implement core/source.py (SourceText, Span dataclasses with get_lines, get_span_text methods)
- [x] Implement core/lean_syntax.py (strip_comments, detect_string_literals, normalize_whitespace functions)
- [x] Implement core/indexer.py (TheoremDecl, FileIndex dataclasses with build_index, find_by_id, find_by_range functions)
- [x] Implement core/features.py (TheoremFeatures dataclass with extract_features, detect_tactics, count functions)
- [x] Implement core/segmenter.py (ProofStructure dataclass with segment_proof, extract_skeleton, identify_blocks functions)
- [x] Implement core/scoring.py (AutomationProfile dataclass with compute_profile, score_aesop_potential, score_grind_potential functions)
- [x] Implement core/format.py (stable_sort_theorems, normalize_notes, ensure_deterministic functions)
- [ ] Write unit tests for all core modules with inline Lean snippets


## Phase 4: Tool Integration

**NOTE: This phase wires the tools to the core modules implemented in Phase 3. This replaces the stub implementations with real functionality.**

- [ ] Integrate scan_file with core modules (add file reading, call build_index, extract features, compute profiles, format response)
- [ ] Implement scan_theorem with core modules (add file reading, find target theorem, extract features, segment proof, format response)
- [ ] Run all contract tests and verify they pass with real implementations
- [ ] Write property-based tests (determinism, schema compliance, score bounds, stable ordering, consistency checks)
- [ ] Final validation (run full test suite, check coverage >90%, test with real Lean files, verify performance targets)

