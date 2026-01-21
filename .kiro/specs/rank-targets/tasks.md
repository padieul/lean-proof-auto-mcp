# Tasks: rank_targets MCP Tool

**Feature:** rank_targets  
**Status:** in_progress  
**Created:** 2026-01-21

## 1. Core Ranking Module

- [x] 1 Implement complete core ranking module
  - Complete all subtasks: data structures, scoring functions, ranking logic, and reason generation
  - **Validates: Requirements US-2, US-4, NFR-1, NFR-3**

- [x] 1.1 Create ranking.py module with data structures
  - Create `src/lean_proof_auto_mcp/core/ranking.py` with frozen dataclasses following hexagonal architecture
  - Implement `ComponentScores` dataclass with validation (success_likelihood, impact, annotation_value, subgoal_potential, risk all in [0.0, 1.0])
  - Implement `TheoremData` dataclass for internal representation (theorem_id, range, signals, structure)
  - Follow existing patterns from core.scoring and core.features modules
  - **Validates: Requirements US-4 (AC 4.1, 4.3), NFR-1**

- [x] 1.2 Implement component scoring functions
  - Implement `compute_success_likelihood()` using whole_goal_potential, confidence, and complexity penalty
  - Implement `compute_impact()` using proof_length_score, annotation_value, and reusability_score
  - Implement `compute_subgoal_potential()` using subgoal_potential signals and structure bonus
  - Implement `compute_risk()` using global_change_risk, simp_risk, local_lemma_risk, and low_confidence_risk
  - All functions must return values in [0.0, 1.0] range with deterministic rounding to 2 decimal places
  - Use same rounding approach as core.scoring module
  - **Validates: Requirements US-4 (AC 4.1, 4.3), NFR-1, NFR-3**

- [x] 1.3 Implement objective ranking logic
  - Define objective weight configurations as immutable dicts (maximize_success, maximize_impact, maximize_subgoal_automation, balanced)
  - Implement `compute_final_score()` function applying objective weights to component scores
  - Implement `rank_theorems()` function with stable sorting (score desc, then theorem_id, then start_line)
  - **Validates: Requirements US-2 (AC 2.1, 2.2, 2.5), NFR-1**

- [x] 1.4 Implement reason generation
  - Implement `generate_reasons()` function producing human-readable explanations
  - Reasons must reference specific features from scan_file analysis
  - Limit to 10 reasons max, 200 chars each
  - Follow note generation patterns from core.scoring module
  - **Validates: Requirements US-4 (AC 4.2, 4.4), NFR-3**

## 2. Tool Entry Point

- [x] 2 Implement complete rank_targets tool
  - Complete all subtasks: argument parsing, data loading, filtering/ranking, and error handling
  - **Validates: Requirements US-1, US-3, US-5, US-6, NFR-1, NFR-4, NFR-5**

- [x] 2.1 Create rank_targets.py tool with argument parsing
  - Create `src/lean_proof_auto_mcp/tools/rank_targets.py` following scan_file/scan_theorem pattern
  - Implement `RankTargetsArgs` frozen dataclass with all parameters
  - Implement `_coerce_args()` function with validation (required: file; optional: objective, limit, include_components, include_reasons, use_deep_structure, min_confidence)
  - Return structured error responses for invalid inputs
  - **Validates: Requirements US-1 (AC 1.1), US-3 (AC 3.1), NFR-5**

- [x] 2.2 Implement data loading and integration
  - Implement `_load_theorem_data()` function calling scan_file
  - Optionally call scan_theorem when use_deep_structure=true
  - Handle missing optional fields with defaults and diagnostics
  - Merge scan_file and scan_theorem data into TheoremData objects
  - **Validates: Requirements US-5 (AC 5.1, 5.2), US-6 (AC 6.1, 6.2, 6.3)**

- [x] 2.3 Implement filtering, ranking, and response formatting
  - Implement confidence filtering using min_confidence parameter
  - Apply objective-based ranking using core.ranking module
  - Implement `_format_response()` function building JSON response with summary statistics
  - Implement `_generate_run_id()` function using deterministic hash (follow scan_file pattern)
  - Use `ensure_deterministic()` from core.format for output normalization
  - **Validates: Requirements US-1 (AC 1.2, 1.3), US-3 (AC 3.2, 3.3), US-4 (AC 4.5), NFR-1, NFR-4**

- [x] 2.4 Implement main tool function with error handling
  - Implement `rank_targets()` function orchestrating all steps
  - Handle all errors with structured JSON responses (status="fail")
  - Include diagnostics with severity levels (error, warning, info)
  - Return partial results when possible
  - **Validates: Requirements US-1 (AC 1.5), NFR-5**

## 3. Unit Tests

- [x] 3 Create all unit tests
  - Complete all subtasks: component scoring tests, ranking logic tests, and tool entry point tests
  - **Validates: Requirements US-2, US-3, US-4, NFR-1, NFR-5**

- [x] 3.1 Create unit tests for component scoring
  - Create `tests/unit/core/test_ranking.py`
  - Test `compute_success_likelihood()` with various inputs (high/low confidence, complexity penalties)
  - Test `compute_impact()` with various proof lengths and annotation values
  - Test `compute_subgoal_potential()` with and without structure data
  - Test `compute_risk()` with various risk factors
  - Verify all scores are in [0.0, 1.0] range
  - **Validates: Requirements US-4 (AC 4.3)**

- [x] 3.2 Create unit tests for ranking logic
  - Test objective weight configurations are correct
  - Test `compute_final_score()` applies weights correctly
  - Test `rank_theorems()` stable sorting (score desc, theorem_id, start_line)
  - Test tie-breaking rules
  - **Validates: Requirements US-2 (AC 2.2, 2.5), NFR-1**

- [x] 3.3 Create unit tests for tool entry point
  - Create `tests/unit/tools/test_rank_targets.py`
  - Test `_coerce_args()` with valid and invalid inputs
  - Test error response formatting
  - Test confidence filtering logic
  - Test response structure and required fields
  - **Validates: Requirements US-3 (AC 3.1, 3.2), NFR-5**

## 4. Property-Based Tests

- [x] 4 Create all property-based tests
  - Complete all subtasks: determinism/stability tests, objective consistency tests, and filtering/bounds tests
  - **Validates: Requirements US-1, US-2, US-3, US-4, NFR-1, Design P1-P6**

- [x] 4.1 Create property tests for determinism and stability
  - Create `tests/property/test_rank_targets_properties.py` following test_scan_file_properties.py pattern
  - Write property test for deterministic output (same inputs produce identical JSON)
  - Write property test for stable sorting (scores monotonic, tie-breaking consistent)
  - **Validates: Requirements US-1 (AC 1.3), NFR-1, Design P1, P2, P3**

- [x] 4.2 Create property tests for objective consistency
  - Write property test verifying different objectives produce different rankings (when sufficient theorems)
  - **Validates: Requirements US-2 (AC 2.3), Design P6**

- [x] 4.3 Create property tests for filtering and bounds
  - Write property test for confidence filtering (all returned theorems >= min_confidence)
  - Write property test for score bounds (all scores in [0.0, 1.0])
  - **Validates: Requirements US-3 (AC 3.1, 3.2), US-4 (AC 4.3), Design P4, P5**

## 5. Contract Tests

- [x] 5 Create JSON schemas and contract tests
  - Complete all subtasks: JSON schema creation and contract test implementation
  - **Validates: Requirements NFR-4**

- [x] 5.1 Create JSON schemas
  - Create `docs/mcp/schemas/rank_targets.json` following scan_file.json pattern
  - Define input schema with required/optional fields
  - Define output schema with ranking structure
  - Reference common.json for shared types
  - **Validates: Requirements NFR-4**

- [x] 5.2 Create contract tests
  - Create `tests/mcp_contract/test_rank_targets_contract.py` following test_scan_file_contract.py pattern
  - Test input schema validation
  - Test output schema validation
  - Test required field presence
  - Test enum value validation
  - **Validates: Requirements NFR-4**

## 6. Integration Tests

- [x] 6 Create integration tests and performance benchmarks
  - Complete all subtasks: end-to-end integration tests and performance benchmarks
  - **Validates: Requirements US-1, US-2, US-5, NFR-2**

- [x] 6.1 Create end-to-end integration tests
  - Create `tests/integration/test_rank_targets_integration.py`
  - Test with real Lean files from fixtures (Coeff.lean, Defs.lean, Degree.lean)
  - Test all four objectives produce valid rankings
  - Test deep structure mode integration with scan_theorem
  - Test error scenarios (missing file, invalid objective)
  - **Validates: Requirements US-1 (AC 1.1, 1.2, 1.4), US-2 (AC 2.1), US-5 (AC 5.2)**

- [x] 6.2 Create performance benchmarks
  - Test performance with 200 theorems without deep structure (target < 50ms)
  - Test performance with 200 theorems with deep structure (target < 200ms)
  - Include computation_time_ms in metadata
  - **Validates: Requirements US-1 (AC 1.4), US-5 (AC 5.3), NFR-2**

## 7. MCP Server Integration

- [x] 7 Register tool with MCP server
  - Add rank_targets import to `src/lean_proof_auto_mcp/tools/__init__.py`
  - Register rank_targets in router in `src/lean_proof_auto_mcp/server.py`
  - Add @app.tool decorator for rank_targets following scan_file/scan_theorem pattern
  - **Validates: Requirements US-5 (AC 5.5)**

## 8. Documentation

- [x] 8 Update tool documentation
  - Update `docs/mcp/tool_contract.md` with rank_targets API contract
  - Document all parameters, objectives, and response structure
  - Include examples for each objective
  - **Validates: Requirements NFR-3, NFR-4**

## 9. Final Validation

- [x] 9 Complete final validation
  - Complete all subtasks: run complete test suite and perform manual testing
  - **Validates: All requirements**

- [x] 9.1 Run complete test suite
  - Run all unit tests and verify pass
  - Run all property-based tests and verify pass
  - Run all contract tests and verify pass
  - Run all integration tests and verify pass
  - **Validates: All requirements**

- [x] 9.2 Manual testing and validation
  - Test with various Lean files from fixtures
  - Test all four objectives produce sensible rankings
  - Test edge cases (empty file, single theorem, low confidence theorems)
  - Verify performance targets met
  - **Validates: Requirements US-1, US-2, US-3, US-4, NFR-2**
