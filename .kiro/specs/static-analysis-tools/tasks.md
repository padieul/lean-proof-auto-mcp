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

- [ ] 0.1 Create scan_theorem.json schema
  - [ ] 0.1.1 Define top-level structure (api_version, status, run_id, tool, file, target, theorem, diagnostics)
  - [ ] 0.1.2 Define target object with oneOf (theorem_id | range)
  - [ ] 0.1.3 Define theorem object (name, kind, location, structure, automation)
  - [ ] 0.1.4 Define structure object (skeleton, blocks, cases)
  - [ ] 0.1.5 Define automation object (whole_goal_potential, subgoal_potential, annotation_value)
  - [ ] 0.1.6 Validate schema with online JSON schema validator

- [ ] 0.2 Update scan_file.json schema
  - [ ] 0.2.1 Add theorems array (optional)
  - [ ] 0.2.2 Define theorem item schema (theorem_id, name, kind, location, automation, notes)
  - [ ] 0.2.3 Ensure automation structure matches scan_theorem
  - [ ] 0.2.4 Validate updated schema

## Phase 1: Stubs

**⚠️ CRITICAL: This phase creates STUBS ONLY - minimal placeholder implementations that return valid JSON with fake/empty data. DO NOT implement actual parsing, analysis, or core logic. That comes in Phase 3 and Phase 4.**

- [ ] 1.1 Update scan_file stub
  - **STUB ONLY**: Add empty theorems array to response, no actual theorem detection
  - [ ] 1.1.1 Add empty theorems array to response (just `"theorems": []`)
  - [ ] 1.1.2 Ensure response conforms to updated schema (validate structure only)
  - [ ] 1.1.3 Test manually with sample input (should return empty theorems)
  - **DO NOT**: Read actual files, parse Lean code, or detect theorems

- [ ] 1.2 Create scan_theorem stub
  - **STUB ONLY**: Return minimal valid response with placeholder data, no actual analysis
  - [ ] 1.2.1 Create tools/scan_theorem.py file
  - [ ] 1.2.2 Implement _coerce_args for both input modes (theorem_id and range) - validation only
  - [ ] 1.2.3 Implement scan_theorem function returning minimal valid response with:
    - Empty skeleton: `[]`
    - Empty blocks: `[]`
    - Zero automation scores: `{"aesop": 0.0, "grind": 0.0}`
    - Placeholder location: echo input range or use line 1
  - [ ] 1.2.4 Handle invalid input with fail status
  - [ ] 1.2.5 Return deterministic run_id for testing (e.g., "scan-theorem-stub-001")
  - [ ] 1.2.6 Test manually with both input modes (should return placeholder data)
  - **DO NOT**: Read actual files, parse Lean code, detect theorems, or analyze proofs

**END OF PHASE 1**: At this point, both tools should return valid JSON with placeholder/empty data. No actual Lean parsing or analysis should be implemented yet.

## Phase 2: Contract Tests

**NOTE: This phase creates tests that validate stub responses. Tests should pass with stubs returning placeholder data.**

- [ ] 2.1 Set up test infrastructure
  - [ ] 2.1.1 Add jsonschema to dependencies
  - [ ] 2.1.2 Add hypothesis to dependencies
  - [ ] 2.1.3 Create tests/mcp_contract/ directory
  - [ ] 2.1.4 Create tests/fixtures/lean_snippets.py with inline Lean code

- [ ] 2.2 Write scan_file contract tests
  - [ ] 2.2.1 Test schema compliance (validate against scan_file.json)
  - [ ] 2.2.2 Test required fields present
  - [ ] 2.2.3 Test field types correct
  - [ ] 2.2.4 Test determinism (same input → same output)
  - [ ] 2.2.5 Test error handling (invalid file path)
  - [ ] 2.2.6 Test theorems array structure when present

- [ ] 2.3 Write scan_theorem contract tests
  - [ ] 2.3.1 Test schema compliance (validate against scan_theorem.json)
  - [ ] 2.3.2 Test required fields present
  - [ ] 2.3.3 Test theorem_id input mode
  - [ ] 2.3.4 Test range input mode
  - [ ] 2.3.5 Test structure validation (skeleton, blocks, cases)
  - [ ] 2.3.6 Test automation score ranges (0.0-1.0)
  - [ ] 2.3.7 Test determinism
  - [ ] 2.3.8 Test error handling (missing theorem)

- [ ] 2.4 Verify stubs pass contract tests
  - [ ] 2.4.1 Run all contract tests against stubs
  - [ ] 2.4.2 Fix any failures
  - [ ] 2.4.3 Ensure all tests pass


## Phase 3: Core Modules

**NOTE: This phase implements the ACTUAL parsing and analysis logic. This is where real implementation happens, NOT in Phase 1 stubs.**

- [ ] 3.1 Implement core/source.py
  - [ ] 3.1.1 Create core/ directory and __init__.py
  - [ ] 3.1.2 Define Span dataclass
  - [ ] 3.1.3 Define SourceText dataclass
  - [ ] 3.1.4 Implement get_lines method with bounds checking
  - [ ] 3.1.5 Implement get_span_text method
  - [ ] 3.1.6 Implement line_count helper
  - [ ] 3.1.7 Write unit tests (tests/unit/core/test_source.py)
  - [ ] 3.1.8 Test boundary conditions (empty file, single line, out of bounds)

- [ ] 3.2 Implement core/lean_syntax.py
  - [ ] 3.2.1 Implement strip_comments function (handle -- and /- -/)
  - [ ] 3.2.2 Implement detect_string_literals function
  - [ ] 3.2.3 Implement normalize_whitespace function
  - [ ] 3.2.4 Implement get_indentation_level function
  - [ ] 3.2.5 Write unit tests (tests/unit/core/test_lean_syntax.py)
  - [ ] 3.2.6 Test with inline Lean snippets (comments, strings, mixed indentation)

- [ ] 3.3 Implement core/indexer.py
  - [ ] 3.3.1 Define TheoremDecl dataclass
  - [ ] 3.3.2 Define FileIndex dataclass
  - [ ] 3.3.3 Implement build_index function (regex for theorem|lemma|example|instance)
  - [ ] 3.3.4 Implement theorem name extraction
  - [ ] 3.3.5 Implement proof span detection (find 'by' keyword)
  - [ ] 3.3.6 Implement stable theorem_id generation
  - [ ] 3.3.7 Implement find_by_id function
  - [ ] 3.3.8 Implement find_by_range function
  - [ ] 3.3.9 Write unit tests (tests/unit/core/test_indexer.py)
  - [ ] 3.3.10 Test with various theorem styles (with/without proofs, different keywords)

- [ ] 3.4 Implement core/features.py
  - [ ] 3.4.1 Define TheoremFeatures dataclass
  - [ ] 3.4.2 Implement extract_features function
  - [ ] 3.4.3 Implement detect_tactics function (regex for common tactics)
  - [ ] 3.4.4 Implement count_rewrites function
  - [ ] 3.4.5 Implement count_local_lemmas function (have, suffices, let)
  - [ ] 3.4.6 Implement proof_lines calculation
  - [ ] 3.4.7 Implement confidence scoring
  - [ ] 3.4.8 Write unit tests (tests/unit/core/test_features.py)
  - [ ] 3.4.9 Test with inline proofs with various tactic patterns

- [ ] 3.5 Implement core/segmenter.py
  - [ ] 3.5.1 Define ProofBlock dataclass
  - [ ] 3.5.2 Define CaseBlock dataclass
  - [ ] 3.5.3 Define ProofStructure dataclass
  - [ ] 3.5.4 Implement segment_proof function
  - [ ] 3.5.5 Implement extract_skeleton function (find top-level tactics)
  - [ ] 3.5.6 Implement identify_blocks function (classify by dominant pattern)
  - [ ] 3.5.7 Implement extract_cases function (find case/induction branches)
  - [ ] 3.5.8 Write unit tests (tests/unit/core/test_segmenter.py)
  - [ ] 3.5.9 Test with inline proofs with clear structure

- [ ] 3.6 Implement core/scoring.py
  - [ ] 3.6.1 Define AutomationProfile dataclass
  - [ ] 3.6.2 Implement compute_profile function
  - [ ] 3.6.3 Implement score_aesop_potential function (heuristic for structural proofs)
  - [ ] 3.6.4 Implement score_grind_potential function (heuristic for rewrite-heavy)
  - [ ] 3.6.5 Implement score_annotation_value function (ROI estimate)
  - [ ] 3.6.6 Write unit tests (tests/unit/core/test_scoring.py)
  - [ ] 3.6.7 Test with feature objects with known patterns
  - [ ] 3.6.8 Verify score ranges (0.0-1.0)

- [ ] 3.7 Implement core/format.py
  - [ ] 3.7.1 Implement stable_sort_theorems function
  - [ ] 3.7.2 Implement normalize_notes function (trim, cap)
  - [ ] 3.7.3 Implement ensure_deterministic function (sort lists, round floats)
  - [ ] 3.7.4 Write unit tests (tests/unit/core/test_format.py)
  - [ ] 3.7.5 Test sorting, rounding, capping


## Phase 4: Tool Integration

**NOTE: This phase wires the tools to the core modules implemented in Phase 3. This replaces the stub implementations with real functionality.**

- [ ] 4.1 Integrate scan_file with core modules
  - [ ] 4.1.1 Import core modules
  - [ ] 4.1.2 Add file reading logic (handle FileNotFoundError)
  - [ ] 4.1.3 Create SourceText from file content
  - [ ] 4.1.4 Call build_index to get theorems
  - [ ] 4.1.5 Loop through theorems, extract features
  - [ ] 4.1.6 Compute automation profiles
  - [ ] 4.1.7 Build theorems array with all required fields
  - [ ] 4.1.8 Apply stable sorting
  - [ ] 4.1.9 Generate unique run_id (UUID)
  - [ ] 4.1.10 Return complete response
  - [ ] 4.1.11 Add error handling with diagnostics

- [ ] 4.2 Implement scan_theorem with core modules
  - [ ] 4.2.1 Import core modules
  - [ ] 4.2.2 Add file reading logic
  - [ ] 4.2.3 Create SourceText and build index
  - [ ] 4.2.4 Find target theorem (by ID or range)
  - [ ] 4.2.5 Handle theorem not found case
  - [ ] 4.2.6 Extract features for target theorem
  - [ ] 4.2.7 Segment proof structure
  - [ ] 4.2.8 Compute automation profile
  - [ ] 4.2.9 Build complete theorem object
  - [ ] 4.2.10 Generate unique run_id
  - [ ] 4.2.11 Return complete response
  - [ ] 4.2.12 Add error handling with diagnostics

- [ ] 4.3 Run all contract tests
  - [ ] 4.3.1 Run scan_file contract tests
  - [ ] 4.3.2 Run scan_theorem contract tests
  - [ ] 4.3.3 Fix any failures
  - [ ] 4.3.4 Ensure all tests pass

- [ ] 4.4 Write property-based tests
  - [ ] 4.4.1 Create tests/property/ directory
  - [ ] 4.4.2 Write test_determinism (Property 1)
  - [ ] 4.4.3 Write test_schema_compliance (Property 2)
  - [ ] 4.4.4 Write test_score_bounds (Property 3)
  - [ ] 4.4.5 Write test_stable_ordering (Property 4)
  - [ ] 4.4.6 Write test_theorem_count_consistency (Property 5)
  - [ ] 4.4.7 Write test_location_validity (Property 6)
  - [ ] 4.4.8 Write test_target_echo (Property 7)
  - [ ] 4.4.9 Run all property tests
  - [ ] 4.4.10 Fix any failures

- [ ] 4.5 Final validation
  - [ ] 4.5.1 Run full test suite (unit + contract + property)
  - [ ] 4.5.2 Check test coverage (aim for >90%)
  - [ ] 4.5.3 Test with real Lean files from Mathlib (manual)
  - [ ] 4.5.4 Verify performance targets (<100ms for scan_file, <50ms for scan_theorem)
  - [ ] 4.5.5 Document any known limitations
  - [ ] 4.5.6 Update README with usage examples

