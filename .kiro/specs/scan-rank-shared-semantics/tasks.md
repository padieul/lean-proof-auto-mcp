# Tasks: scan-rank-shared-semantics

**Feature:** scan-rank-shared-semantics  
**Status:** not_started  
**Created:** 2025-01-21

## 1. Configuration System (Foundation)

- [x] 1 Implement complete configuration system
  - Complete all subtasks: config module, YAML file, and validation
  - **Validates: Requirements US-7, NFR-6**

- [x] 1.1 Create config.py module with protocol and dataclasses
  - Create `src/lean_proof_auto_mcp/core/config.py` with hexagonal architecture
  - Implement `HeuristicsConfig` protocol (port) defining configuration interface
  - Implement all config dataclasses (ConfidenceConfig, AesopScoringConfig, GrindScoringConfig, etc.)
  - All dataclasses must be frozen with `__post_init__` validation
  - Validate all score/penalty values are in [0.0, 1.0] range
  - Validate all thresholds are positive integers
  - **Validates: Requirements US-7 (AC 7.1, 7.5, 7.6), NFR-6, Design D7**

- [x] 1.2 Create YAML configuration adapter
  - Implement `YamlHeuristicsConfig` adapter class
  - Implement `load()` classmethod loading from file path or package default
  - Implement `_from_dict()` classmethod parsing YAML data into config objects
  - Validate version field (must be "1.0")
  - Provide clear error messages for missing fields or invalid values
  - Implement `load_default_config()` and `load_config(path)` functions
  - **Validates: Requirements US-7 (AC 7.2, 7.3, 7.6), NFR-6, Design D7**

- [x] 1.3 Create default heuristics.yaml configuration file
  - Create `src/lean_proof_auto_mcp/heuristics.yaml` with all default values
  - Include all sections: confidence, aesop_scoring, grind_scoring, annotation_value_scoring, subgoal_potential_scoring, risk_scoring, impact_scoring, success_likelihood_scoring, objectives, already_automated, tiers
  - Document each parameter with inline comments
  - Set version to "1.0"
  - **Validates: Requirements US-7 (AC 7.3), Design D7**

- [x] 1.4 Add environment variable support
  - Support `LEAN_PROOF_AUTO_MCP_CONFIG` environment variable for default config path
  - Update `load_default_config()` to check environment variable before using package default
  - Document environment variable in config module docstring
  - **Validates: Requirements US-7 (AC 7.4), Design D7**

## 2. Refactor Scoring Functions for Configuration

- [x] 2 Refactor all scoring functions to use configuration
  - Complete all subtasks: update all scoring functions in scoring.py and ranking.py
  - **BREAKING CHANGE**: All functions now require config parameter
  - **Validates: Requirements US-7, Design D7**

- [x] 2.1 Refactor confidence calculation (features.py)
  - Update `_calculate_confidence()` to accept `ConfidenceConfig` parameter
  - Replace all hardcoded values with config values
  - Update `extract_features()` to accept optional config parameter (defaults to package config)
  - **BREAKING CHANGE**: Function signature changed
  - **Validates: Requirements US-7 (AC 7.1), Design D7**

- [x] 2.2 Refactor aesop and grind scoring (scoring.py)
  - Update `score_aesop_potential()` to accept `HeuristicsConfig` parameter
  - Update `score_grind_potential()` to accept `HeuristicsConfig` parameter
  - Replace all hardcoded values with config.aesop_scoring and config.grind_scoring values
  - **BREAKING CHANGE**: Function signatures changed
  - **Validates: Requirements US-7 (AC 7.1), Design D7**

- [x] 2.3 Refactor annotation value and subgoal scoring (scoring.py)
  - Update `score_annotation_value()` to accept `HeuristicsConfig` parameter
  - Update `_score_aesop_subgoal_potential()` to accept `HeuristicsConfig` parameter
  - Update `_score_grind_subgoal_potential()` to accept `HeuristicsConfig` parameter
  - Replace all hardcoded values with config values
  - **BREAKING CHANGE**: Function signatures changed
  - **Validates: Requirements US-7 (AC 7.1), Design D7**

- [x] 2.4 Refactor compute_profile to use configuration
  - Update `compute_profile()` to accept `HeuristicsConfig` parameter (required, no default)
  - Pass config to all scoring functions
  - **BREAKING CHANGE**: Function signature changed, config now required
  - **Validates: Requirements US-7 (AC 7.1), Design D7**

- [x] 2.5 Refactor ranking functions for configuration
  - Update `compute_success_likelihood()` to accept `HeuristicsConfig` parameter
  - Update `compute_impact()` to accept `HeuristicsConfig` parameter
  - Update `compute_risk()` to accept `HeuristicsConfig` parameter
  - Update `compute_subgoal_potential()` to accept `HeuristicsConfig` parameter
  - Replace all hardcoded values with config values
  - **BREAKING CHANGE**: Function signatures changed
  - **Validates: Requirements US-7 (AC 7.1), Design D7**

## 3. Confidence Fix

- [x] 3 Fix confidence to expose numeric values
  - Complete subtask: update _generate_notes to include numeric confidence
  - **BREAKING CHANGE**: Note format changed
  - **Validates: Requirements US-1, Design D1**

- [x] 3.1 Add numeric confidence to notes
  - Update `_generate_notes()` in `core/scoring.py`
  - Add `notes.append(f"confidence: {features.confidence:.2f}")` as FIRST note when confidence > 0.0
  - Keep existing qualitative notes after numeric note
  - **BREAKING CHANGE**: All tools now return numeric confidence in notes
  - **Validates: Requirements US-1 (AC 1.1, 1.2, 1.3, 1.4), Design D1**

## 4. Already-Automated Detection

- [x] 4 Implement already-automated detection system
  - Complete all subtasks: detection module, integration with rank_targets
  - **Validates: Requirements US-2, US-5, Design D2**

- [x] 4.1 Create automation_detection.py module
  - Create `src/lean_proof_auto_mcp/core/automation_detection.py`
  - Implement `AutomationStatus` frozen dataclass (is_automated, automation_type, penalty, detected_patterns)
  - Implement `AutomationDetector` protocol (port)
  - Implement `PatternBasedDetector` class with conservative pattern matching
  - Implement `_check_trivial()`, `_check_attributes()`, `_check_tactics()` methods
  - Implement `AutomationDetectionConfig` frozen dataclass
  - **Validates: Requirements US-2 (AC 2.2, 2.5, 2.6), Design D2**

- [x] 4.2 Add automation detection to configuration
  - Add `automation_detection` section to `heuristics.yaml`
  - Include tactic_penalty, attribute_penalty, trivial_penalty
  - Include tactic_patterns, attribute_patterns, trivial_patterns lists
  - Add `AutomationDetectionConfig` to `HeuristicsConfig` protocol
  - **Validates: Requirements US-2 (AC 2.2), US-7, Design D2, D7**

- [x] 4.3 Integrate detection with rank_targets
  - Update `_load_theorem_data()` to detect automation for each theorem
  - Add automation status to theorem signals (already_automated, automation_penalty, automation_type)
  - Implement filtering when `skip_already_automated=true`
  - Track `skipped_already_automated` count in summary
  - **Validates: Requirements US-2 (AC 2.1, 2.3, 2.4), Design D2, D5**

## 5. Already-Automated Penalty Component

- [x] 5 Add already-automated penalty to ranking
  - Complete subtasks: update ComponentScores and ranking logic
  - **BREAKING CHANGE**: ComponentScores now includes already_automated_penalty
  - **Validates: Requirements US-5, Design D6**

- [x] 5.1 Update ComponentScores dataclass
  - Add `already_automated_penalty: float` field to `ComponentScores` in `core/ranking.py`
  - Update `__post_init__` validation to include new field
  - **BREAKING CHANGE**: ComponentScores structure changed
  - **Validates: Requirements US-5 (AC 5.1, 5.2, 5.3, 5.4, 5.5), Design D6**

- [x] 5.2 Update compute_final_score to apply penalty
  - Update `compute_final_score()` to subtract `0.15 * components.already_automated_penalty`
  - Apply penalty consistently across all objectives
  - **BREAKING CHANGE**: Scoring formula changed
  - **Validates: Requirements US-5 (AC 5.6, 5.7), Design D6**

- [x] 5.3 Update rank_theorems to include penalty
  - Extract `automation_penalty` from theorem signals
  - Pass to `ComponentScores` constructor
  - **BREAKING CHANGE**: Ranking logic changed
  - **Validates: Requirements US-5, Design D6**

## 6. Tier System

- [x] 6 Implement S/A/B/C/D tier system
  - Complete all subtasks: tier assignment function and integration
  - **BREAKING CHANGE**: All responses now include tier field
  - **Validates: Requirements US-4, Design D3**

- [x] 6.1 Implement assign_tiers function
  - Create `assign_tiers()` function in `core/ranking.py`
  - Calculate percentile rank for each theorem
  - Assign tiers based on percentile: S (<10%), A (10-25%), B (25-50%), C (50-75%), D (75-100%)
  - Return list of (theorem, tier) tuples
  - **Validates: Requirements US-4 (AC 4.1, 4.2, 4.3), Design D3**

- [x] 6.2 Add tier configuration
  - Add `tiers` section to `heuristics.yaml`
  - Include s_tier_percentile, a_tier_percentile, b_tier_percentile, c_tier_percentile
  - Add `TierConfig` dataclass with validation (thresholds must be monotonic)
  - Add to `HeuristicsConfig` protocol
  - **Validates: Requirements US-4 (AC 4.3), US-7, Design D3, D7**

- [x] 6.3 Integrate tiers into rank_targets response
  - Call `assign_tiers()` after ranking theorems
  - Add `tier` field to each theorem in ranking array
  - Add `tier_distribution` to summary (counts for each tier)
  - **BREAKING CHANGE**: Response structure changed
  - **Validates: Requirements US-4 (AC 4.1, 4.5), Design D3**

## 7. Objective Discovery

- [x] 7 Implement objective discovery system
  - Complete all subtasks: metadata structure and integration
  - **BREAKING CHANGE**: All responses now include available_objectives
  - **Validates: Requirements US-3, Design D4**

- [x] 7.1 Create OBJECTIVE_METADATA structure
  - Create `OBJECTIVE_METADATA` dict in `core/ranking.py`
  - Include name, description, use_case, weights for each objective
  - Keep `OBJECTIVE_WEIGHTS` for backward compatibility (extract from metadata)
  - **Validates: Requirements US-3 (AC 3.1, 3.2, 3.4), Design D4**

- [x] 7.2 Implement get_available_objectives function
  - Create `get_available_objectives()` function returning list of objective metadata
  - Format as list of dicts with name, description, use_case, weights
  - **Validates: Requirements US-3 (AC 3.1, 3.2), Design D4**

- [x] 7.3 Add available_objectives to response
  - Call `get_available_objectives()` in `_format_response()`
  - Add `available_objectives` field to response
  - **BREAKING CHANGE**: Response structure changed
  - **Validates: Requirements US-3 (AC 3.1), Design D4**

- [x] 7.4 Improve error messages for invalid objectives
  - Update `_coerce_args()` to include available objectives in error message
  - Format as bulleted list with descriptions
  - **Validates: Requirements US-3 (AC 3.3), Design D4**

## 8. Update rank_targets Tool

- [x] 8 Update rank_targets tool for breaking changes
  - Complete all subtasks: update parameters, response format, and API version
  - **BREAKING CHANGE**: Multiple parameter and response changes
  - **Validates: All requirements**

- [x] 8.1 Add skip_already_automated parameter
  - Add `skip_already_automated: bool` to `RankTargetsArgs` dataclass
  - Update `_coerce_args()` to parse parameter (REQUIRED, no default)
  - Raise error if parameter is missing
  - **BREAKING CHANGE**: New required parameter
  - **Validates: Requirements US-2 (AC 2.1), Design D5**

- [x] 8.2 Add config_path parameter
  - Add `config_path: str | None` to `RankTargetsArgs` dataclass
  - Update `_coerce_args()` to parse optional parameter
  - **Validates: Requirements US-7 (AC 7.4), Design D7**

- [x] 8.3 Update rank_targets to load configuration
  - Load config from `config_path` if provided, else from environment variable, else package default
  - Pass config to all scoring functions
  - Add `config_source` to metadata (path, environment, or default)
  - **BREAKING CHANGE**: Configuration now required for all scoring
  - **Validates: Requirements US-7 (AC 7.2, 7.4), Design D7**

- [x] 8.4 Update API version to 1.0
  - Change `API_VERSION` constant from "0.1" to "1.0"
  - Update all response formatting to use new version
  - **BREAKING CHANGE**: API version bump indicates breaking changes
  - **Validates: Design (Breaking Changes)**

## 9. Update scan_file and scan_theorem Tools

- [x] 9 Update scan_file and scan_theorem for breaking changes
  - Complete all subtasks: update both tools to use configuration and new API version
  - **BREAKING CHANGE**: API version and note format changed
  - **Validates: Requirements US-1**

- [x] 9.1 Update scan_file to use configuration
  - Update `scan_file()` to load configuration (optional parameter or environment variable)
  - Pass config to `compute_profile()`
  - Update API version to "1.0"
  - **BREAKING CHANGE**: API version changed, note format changed
  - **Validates: Requirements US-1, Design D1**

- [x] 9.2 Update scan_theorem to use configuration
  - Update `scan_theorem()` to load configuration (optional parameter or environment variable)
  - Pass config to `compute_profile()`
  - Update API version to "1.0"
  - **BREAKING CHANGE**: API version changed, note format changed
  - **Validates: Requirements US-1, Design D1**

## 10. Update All Tests

- [ ] 10 Rewrite all tests for breaking changes
  - Complete all subtasks: update unit tests, property tests, contract tests, integration tests
  - **BREAKING CHANGE**: All test expectations changed
  - **Validates: All requirements**

- [ ] 10.1 Update unit tests for configuration system
  - Create `tests/unit/core/test_config.py`
  - Test `load_default_config()` loads successfully
  - Test `load_config(path)` with custom config
  - Test invalid config version raises error
  - Test invalid config values raise errors with clear messages
  - Test environment variable support
  - **Validates: Requirements US-7 (AC 7.5, 7.6), NFR-6**

- [ ] 10.2 Update unit tests for scoring functions
  - Update `tests/unit/core/test_scoring.py`
  - Update all test calls to pass config parameter
  - Test that config values are actually used (not hardcoded)
  - Test `_generate_notes()` includes numeric confidence
  - **BREAKING CHANGE**: All test signatures changed
  - **Validates: Requirements US-1, US-7**

- [ ] 10.3 Update unit tests for ranking functions
  - Update `tests/unit/core/test_ranking.py`
  - Update all test calls to pass config parameter
  - Test `already_automated_penalty` component
  - Test `assign_tiers()` function
  - Test `get_available_objectives()` function
  - **BREAKING CHANGE**: All test signatures changed
  - **Validates: Requirements US-3, US-4, US-5, US-7**

- [ ] 10.4 Create unit tests for automation detection
  - Create `tests/unit/core/test_automation_detection.py`
  - Test `PatternBasedDetector` with various proof patterns
  - Test tactic detection (aesop, grind, simp)
  - Test attribute detection (@[aesop], @[simp])
  - Test trivial proof detection (rfl, trivial)
  - Test no false positives (manual proofs not detected)
  - **Validates: Requirements US-2 (AC 2.5, 2.6)**

- [ ] 10.5 Update unit tests for rank_targets tool
  - Update `tests/unit/tools/test_rank_targets.py`
  - Test `skip_already_automated` parameter (required, no default)
  - Test `config_path` parameter
  - Test error when `skip_already_automated` missing
  - Update all response assertions for new fields (tier, available_objectives, tier_distribution, skipped_already_automated)
  - **BREAKING CHANGE**: All test expectations changed
  - **Validates: Requirements US-2, US-3, US-4, US-7**

- [ ] 10.6 Update property-based tests
  - Update `tests/property/test_rank_targets_properties.py`
  - Update all test calls to include `skip_already_automated` parameter
  - Add property test for tier assignment (percentile-based)
  - Add property test for configuration validation
  - Update all assertions for new response structure
  - **BREAKING CHANGE**: All test expectations changed
  - **Validates: All requirements**

- [ ] 10.7 Update contract tests
  - Update `tests/mcp_contract/test_rank_targets_contract.py`
  - Update `tests/mcp_contract/test_scan_file_contract.py`
  - Update `tests/mcp_contract/test_scan_theorem_contract.py`
  - Update all schema validations for API version 1.0
  - Update all response structure validations
  - **BREAKING CHANGE**: All schemas changed
  - **Validates: All requirements**

- [ ] 10.8 Update integration tests
  - Update `tests/integration/test_rank_targets_integration.py`
  - Update all test calls to include `skip_already_automated` parameter
  - Test with custom configuration file
  - Test environment variable configuration
  - Update all response assertions for new fields
  - **BREAKING CHANGE**: All test expectations changed
  - **Validates: All requirements**

## 11. Update Documentation

- [ ] 11 Rewrite all documentation for breaking changes
  - Complete all subtasks: schemas, user guide, API changelog, README
  - **BREAKING CHANGE**: Complete documentation rewrite
  - **Validates: All requirements**

- [ ] 11.1 Rewrite JSON schemas
  - Update `docs/mcp/schemas/rank_targets.json` for API 1.0
  - Update `docs/mcp/schemas/scan_file.json` for API 1.0
  - Update `docs/mcp/schemas/scan_theorem.json` for API 1.0
  - Add new required/optional fields
  - Update all examples
  - **BREAKING CHANGE**: Schemas completely rewritten
  - **Validates: Requirements NFR-4**

- [ ] 11.2 Rewrite tool contract documentation
  - Update `docs/mcp/tool_contract.md`
  - Document all breaking changes
  - Document new parameters (skip_already_automated, config_path)
  - Document new response fields (tier, available_objectives, etc.)
  - Document configuration system
  - Provide migration guide from API 0.1 to 1.0
  - **BREAKING CHANGE**: Documentation completely rewritten
  - **Validates: Requirements NFR-3, NFR-4**

- [ ] 11.3 Create configuration guide
  - Create `docs/configuration.md`
  - Explain configuration system architecture
  - Document all configuration parameters
  - Provide example custom configurations
  - Document environment variable usage
  - Explain how to validate configuration files
  - **Validates: Requirements US-7, NFR-6**

- [ ] 11.4 Update README
  - Update all examples to API 1.0
  - Add configuration section
  - Add tier system explanation
  - Update quick start guide
  - Add migration guide from 0.1 to 1.0
  - **BREAKING CHANGE**: All examples rewritten
  - **Validates: All requirements**

- [ ] 11.5 Create API changelog
  - Create `docs/CHANGELOG.md` or update existing
  - Document API version 1.0 breaking changes
  - List all removed/changed/added features
  - Provide migration examples
  - Note: No backward compatibility
  - **BREAKING CHANGE**: Complete changelog for 1.0 release
  - **Validates: All requirements**

## 12. Final Validation

- [ ] 12 Complete final validation
  - Complete all subtasks: run complete test suite and perform manual testing
  - **Validates: All requirements**

- [ ] 12.1 Run complete test suite
  - Run all unit tests and verify pass
  - Run all property-based tests and verify pass
  - Run all contract tests and verify pass
  - Run all integration tests and verify pass
  - Verify no tests skipped or disabled
  - **Validates: All requirements**

- [ ] 12.2 Manual testing with real files
  - Test rank_targets with various Lean files
  - Test all four objectives produce sensible rankings
  - Test skip_already_automated filtering
  - Test tier system produces reasonable distribution
  - Test custom configuration file
  - Test environment variable configuration
  - Verify confidence values are non-zero
  - Verify available_objectives is helpful
  - **Validates: All requirements**

- [ ] 12.3 Performance validation
  - Verify performance overhead < 10ms for 200 theorems
  - Verify configuration loading is fast (~5ms)
  - Verify no performance regressions
  - **Validates: Requirements NFR-2**

- [ ] 12.4 Documentation review
  - Verify all documentation is accurate
  - Verify all examples work
  - Verify migration guide is complete
  - Verify configuration guide is clear
  - **Validates: Requirements NFR-3, NFR-4**
