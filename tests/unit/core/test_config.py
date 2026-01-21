"""Unit tests for configuration system.

Tests configuration loading, validation, and environment variable support.
"""

import os
import pytest
from pathlib import Path
from src.lean_proof_auto_mcp.core.config import (
    load_default_config,
    load_config,
    YamlHeuristicsConfig,
    ConfidenceConfig,
    AesopScoringConfig,
    TierConfig,
    AutomationDetectionConfig,
)


class TestLoadDefaultConfig:
    """Test loading default configuration."""
    
    def test_load_default_config_succeeds(self):
        """Test that default configuration loads successfully."""
        config = load_default_config()
        
        # Verify config is loaded
        assert config is not None
        assert config.version == "1.0"
        
        # Verify all sections are present
        assert config.confidence is not None
        assert config.aesop_scoring is not None
        assert config.grind_scoring is not None
        assert config.annotation_value_scoring is not None
        assert config.subgoal_potential_scoring is not None
        assert config.risk_scoring is not None
        assert config.impact_scoring is not None
        assert config.success_likelihood_scoring is not None
        assert config.objectives is not None
        assert config.automation_detection is not None
        assert config.tiers is not None
    
    def test_default_config_has_expected_values(self):
        """Test that default configuration has expected values."""
        config = load_default_config()
        
        # Check confidence config
        assert config.confidence.base_score == 0.3
        assert config.confidence.proof_structure_bonus == 0.2
        
        # Check aesop scoring config
        assert config.aesop_scoring.base_score == 0.2
        
        # Check objectives
        assert len(config.objectives) == 4
        assert "maximize_success" in config.objectives
        assert "maximize_impact" in config.objectives
        assert "maximize_subgoal_automation" in config.objectives
        assert "balanced" in config.objectives
    
    def test_default_config_objectives_have_metadata(self):
        """Test that objectives have description and use_case."""
        config = load_default_config()
        
        for obj_name, obj_config in config.objectives.items():
            assert obj_config.description, f"{obj_name} missing description"
            assert obj_config.use_case, f"{obj_name} missing use_case"
            
            # Check weights are present
            assert hasattr(obj_config, "weight_success_likelihood")
            assert hasattr(obj_config, "weight_impact")
            assert hasattr(obj_config, "weight_annotation_value")
            assert hasattr(obj_config, "weight_subgoal_potential")
            assert hasattr(obj_config, "weight_risk")


class TestLoadCustomConfig:
    """Test loading custom configuration from file."""
    
    def test_load_custom_config_succeeds(self, tmp_path):
        """Test loading custom configuration from file."""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("""
version: "1.0"

confidence:
  base_score: 0.5
  bonuses:
    proof_structure: 0.3
    tactic_detection: 0.25
    structural_tactics: 0.2
    term_mode_patterns: 0.2
    automation_tactics: 0.15
    indentation_consistency: 0.1
  penalties:
    sorry: -0.5
    error_patterns: -0.2
  thresholds:
    proof_length_min: 2
    proof_length_max: 100
    proof_length_max_bonus: 0.1

aesop_scoring:
  base_score: 0.3
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.3 }
    good: { threshold: 0.6, bonus: 0.2 }
    moderate: { threshold: 0.4, bonus: 0.1 }
    low: { threshold: 0.0, bonus: 0.05 }
  structural_tactics:
    bonus_per_tactic: 0.08
    max_bonus: 0.3
  term_mode:
    bonus_per_pattern: 0.1
    max_bonus: 0.25
  proof_length_bonuses:
    - { max_lines: 5, bonus: 0.2 }
    - { max_lines: 10, bonus: 0.15 }
    - { max_lines: 20, bonus: 0.1 }
  penalties:
    rewrite_heavy: { threshold: 5, penalty: -0.15 }
    rewrite_moderate: { threshold: 2, penalty: -0.08 }
    simp_heavy: { threshold: 3, penalty: -0.1 }
  bonuses:
    tactic_mode: 0.05

grind_scoring:
  base_score: 0.15
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.25 }
    good: { threshold: 0.6, bonus: 0.18 }
    moderate: { threshold: 0.4, bonus: 0.1 }
    low: { threshold: 0.0, bonus: 0.05 }
  rewrite:
    bonus_per_count: 0.06
    max_bonus: 0.35
  simp:
    bonus_per_count: 0.08
    max_bonus: 0.25
  algebraic_terms:
    bonus_per_pattern: 0.08
    max_bonus: 0.2
  proof_length_bonuses:
    - { min_lines: 5, max_lines: 30, bonus: 0.15 }
    - { max_lines: 5, bonus: 0.08 }
  penalties:
    induction: -0.15
    cases: -0.1
  algebraic_tactics:
    bonus_per_tactic: 0.08
    max_bonus: 0.2
  bonuses:
    pure_term_proof: 0.1

annotation_value_scoring:
  base_score: 0.05
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.25 }
    good: { threshold: 0.6, bonus: 0.18 }
    moderate: { threshold: 0.4, bonus: 0.1 }
    low: { threshold: 0.0, bonus: 0.05 }
  penalties:
    low_confidence: -0.1
  proof_length_bonuses:
    - { min_lines: 20, bonus: 0.3 }
    - { min_lines: 10, bonus: 0.2 }
    - { min_lines: 5, bonus: 0.15 }
    - { min_lines: 2, bonus: 0.1 }
  local_lemmas:
    bonus_per_count: 0.08
    max_bonus: 0.25
  tactic_diversity_bonuses:
    - { min_diversity: 5, bonus: 0.15 }
    - { min_diversity: 3, bonus: 0.1 }
    - { min_diversity: 0, bonus: 0.05 }
  rewrite_bonuses:
    - { min_count: 3, bonus: 0.12 }
    - { min_count: 0, bonus: 0.08 }
  simp_bonuses:
    - { min_count: 2, bonus: 0.08 }
    - { min_count: 0, bonus: 0.05 }
  bonuses:
    term_application: 0.1
    structural_proof: 0.1

subgoal_potential_scoring:
  confidence_multipliers:
    high: { threshold: 0.8, multiplier: 0.8 }
    good: { threshold: 0.6, multiplier: 0.7 }
    moderate: { threshold: 0.4, multiplier: 0.6 }
    low: { threshold: 0.0, multiplier: 0.5 }
    none: { threshold: 0.0, multiplier: 0.0 }
  bonuses:
    induction_or_cases: 0.25
    term_application: 0.1
    algebraic_term: 0.12
  structure_cases:
    bonus_per_case: 0.04
    max_bonus: 0.2
  rewrite_blocks:
    bonus_per_block: 0.08
    max_bonus: 0.2

risk_scoring:
  global_change_risk:
    rewrite_heavy: { threshold: 5, risk: 0.6 }
    simp_heavy: { threshold: 3, risk: 0.4 }
    simp_question_mark: 0.8
  simp_risk:
    heavy: { threshold: 3, risk: 0.6 }
    moderate: { threshold: 1, risk: 0.3 }
  local_lemma_risk:
    heavy: { threshold: 3, risk: 0.5 }
    moderate: { threshold: 1, risk: 0.2 }
  low_confidence_risk:
    very_low: { threshold: 0.4, risk: 0.7 }
    low: { threshold: 0.6, risk: 0.4 }
  component_weights:
    global_change: 0.3
    simp: 0.3
    local_lemma: 0.2
    confidence: 0.2

impact_scoring:
  proof_length_scores:
    - { max_lines: 0, score: 0.0 }
    - { max_lines: 5, score: 0.2 }
    - { max_lines: 10, score: 0.4 }
    - { max_lines: 20, score: 0.6 }
    - { max_lines: 40, score: 0.8 }
    - { min_lines: 40, score: 1.0 }
  reusability:
    score_per_local_lemma: 0.2
    max_score: 1.0
  component_weights:
    proof_length: 0.5
    annotation_value: 0.3
    reusability: 0.2

success_likelihood_scoring:
  complexity_penalties:
    induction_or_cases: 0.2
    long_proof: { threshold: 30, penalty: 0.1 }
    many_local_lemmas: { threshold: 3, penalty: 0.1 }
    max_penalty: 0.5
  component_weights:
    max_potential: 0.6
    confidence: 0.3
    complexity_penalty: -0.1

objectives:
  maximize_success:
    description: "Prioritize theorems most likely to be automated successfully"
    use_case: "When you want quick wins and high success rate"
    weights:
      success_likelihood: 0.50
      impact: 0.10
      annotation_value: 0.10
      subgoal_potential: 0.10
      risk: -0.20
  maximize_impact:
    description: "Prioritize theorems that save the most time when automated"
    use_case: "When you want maximum ROI on automation effort"
    weights:
      success_likelihood: 0.20
      impact: 0.40
      annotation_value: 0.30
      subgoal_potential: 0.05
      risk: -0.05
  maximize_subgoal_automation:
    description: "Prioritize theorems with good partial automation opportunities"
    use_case: "When you want to automate proof steps rather than whole goals"
    weights:
      success_likelihood: 0.15
      impact: 0.15
      annotation_value: 0.20
      subgoal_potential: 0.40
      risk: -0.10
  balanced:
    description: "Balanced weighting across all factors"
    use_case: "When you want a general-purpose ranking"
    weights:
      success_likelihood: 0.25
      impact: 0.25
      annotation_value: 0.20
      subgoal_potential: 0.20
      risk: -0.10

already_automated:
  penalties:
    tactic_usage: 0.3
    attribute: 0.5
    trivial_proof: 0.8
  tactic_patterns:
    - "by aesop"
    - "by grind"
    - "by simp"
  attribute_patterns:
    - "@[aesop"
    - "@[simp"
  trivial_patterns:
    - ":= rfl"
    - "by rfl"

tiers:
  s_tier_percentile: 10
  a_tier_percentile: 25
  b_tier_percentile: 50
  c_tier_percentile: 75
""")
        
        config = load_config(config_file)
        
        # Verify custom values are loaded
        assert config.confidence.base_score == 0.5
        assert config.confidence.proof_structure_bonus == 0.3
        assert config.aesop_scoring.base_score == 0.3
    
    def test_load_nonexistent_config_raises_error(self):
        """Test that loading nonexistent config raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config(Path("/nonexistent/config.yaml"))


class TestConfigVersionValidation:
    """Test configuration version validation."""
    
    def test_invalid_config_version_raises_error(self, tmp_path):
        """Test that invalid version raises error with clear message."""
        config_file = tmp_path / "invalid_version.yaml"
        config_file.write_text('version: "2.0"')
        
        with pytest.raises(ValueError, match="Unsupported configuration version: 2.0"):
            load_config(config_file)
    
    def test_missing_version_raises_error(self, tmp_path):
        """Test that missing version raises error."""
        config_file = tmp_path / "no_version.yaml"
        config_file.write_text('confidence: { base_score: 0.3 }')
        
        with pytest.raises(ValueError, match="Unsupported configuration version: None"):
            load_config(config_file)


class TestConfigValueValidation:
    """Test configuration value validation."""
    
    def test_invalid_base_score_raises_error(self):
        """Test that base_score > 1.0 raises error."""
        with pytest.raises(ValueError, match="base_score must be in \\[0.0, 1.0\\]"):
            ConfidenceConfig(
                base_score=1.5,  # Invalid
                proof_structure_bonus=0.2,
                tactic_detection_bonus=0.2,
                structural_tactics_bonus=0.15,
                term_mode_patterns_bonus=0.15,
                automation_tactics_bonus=0.1,
                indentation_consistency_bonus=0.05,
                sorry_penalty=-0.3,
                error_patterns_penalty=-0.1,
                proof_length_min=1,
                proof_length_max=50,
                proof_length_max_bonus=0.05,
            )
    
    def test_negative_base_score_raises_error(self):
        """Test that negative base_score raises error."""
        with pytest.raises(ValueError, match="base_score must be in \\[0.0, 1.0\\]"):
            ConfidenceConfig(
                base_score=-0.1,  # Invalid
                proof_structure_bonus=0.2,
                tactic_detection_bonus=0.2,
                structural_tactics_bonus=0.15,
                term_mode_patterns_bonus=0.15,
                automation_tactics_bonus=0.1,
                indentation_consistency_bonus=0.05,
                sorry_penalty=-0.3,
                error_patterns_penalty=-0.1,
                proof_length_min=1,
                proof_length_max=50,
                proof_length_max_bonus=0.05,
            )
    
    def test_invalid_penalty_raises_error(self):
        """Test that penalty > 0 raises error."""
        with pytest.raises(ValueError, match="sorry_penalty must be in \\[-1.0, 0.0\\]"):
            ConfidenceConfig(
                base_score=0.3,
                proof_structure_bonus=0.2,
                tactic_detection_bonus=0.2,
                structural_tactics_bonus=0.15,
                term_mode_patterns_bonus=0.15,
                automation_tactics_bonus=0.1,
                indentation_consistency_bonus=0.05,
                sorry_penalty=0.3,  # Invalid (should be negative)
                error_patterns_penalty=-0.1,
                proof_length_min=1,
                proof_length_max=50,
                proof_length_max_bonus=0.05,
            )
    
    def test_invalid_proof_length_range_raises_error(self):
        """Test that proof_length_max < proof_length_min raises error."""
        with pytest.raises(ValueError, match="proof_length_max .* must be >= proof_length_min"):
            ConfidenceConfig(
                base_score=0.3,
                proof_structure_bonus=0.2,
                tactic_detection_bonus=0.2,
                structural_tactics_bonus=0.15,
                term_mode_patterns_bonus=0.15,
                automation_tactics_bonus=0.1,
                indentation_consistency_bonus=0.05,
                sorry_penalty=-0.3,
                error_patterns_penalty=-0.1,
                proof_length_min=50,
                proof_length_max=10,  # Invalid (less than min)
                proof_length_max_bonus=0.05,
            )
    
    def test_invalid_tier_thresholds_raise_error(self):
        """Test that non-monotonic tier thresholds raise error."""
        with pytest.raises(ValueError, match="Tier thresholds must be strictly increasing"):
            TierConfig(
                s_tier_percentile=10,
                a_tier_percentile=25,
                b_tier_percentile=20,  # Invalid (not increasing)
                c_tier_percentile=75,
            )
    
    def test_tier_threshold_out_of_range_raises_error(self):
        """Test that tier threshold outside (0, 100) raises error."""
        with pytest.raises(ValueError, match="Tier threshold .* must be in \\(0, 100\\)"):
            TierConfig(
                s_tier_percentile=10,
                a_tier_percentile=25,
                b_tier_percentile=50,
                c_tier_percentile=100,  # Invalid (must be < 100)
            )
    
    def test_automation_detection_penalty_out_of_range_raises_error(self):
        """Test that automation detection penalty > 1.0 raises error."""
        with pytest.raises(ValueError, match="tactic_penalty must be in \\[0.0, 1.0\\]"):
            AutomationDetectionConfig(
                tactic_penalty=1.5,  # Invalid
                attribute_penalty=0.5,
                trivial_penalty=0.8,
                tactic_patterns=["by aesop"],
                attribute_patterns=["@[aesop"],
                trivial_patterns=[":= rfl"],
            )


class TestEnvironmentVariableSupport:
    """Test environment variable support for configuration."""
    
    def test_env_var_overrides_default(self, tmp_path, monkeypatch):
        """Test that LEAN_PROOF_AUTO_MCP_CONFIG environment variable is used."""
        # Create custom config
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text("""
version: "1.0"

confidence:
  base_score: 0.7
  bonuses:
    proof_structure: 0.2
    tactic_detection: 0.2
    structural_tactics: 0.15
    term_mode_patterns: 0.15
    automation_tactics: 0.1
    indentation_consistency: 0.05
  penalties:
    sorry: -0.3
    error_patterns: -0.1
  thresholds:
    proof_length_min: 1
    proof_length_max: 50
    proof_length_max_bonus: 0.05

aesop_scoring:
  base_score: 0.2
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.3 }
    good: { threshold: 0.6, bonus: 0.2 }
    moderate: { threshold: 0.4, bonus: 0.1 }
    low: { threshold: 0.0, bonus: 0.05 }
  structural_tactics:
    bonus_per_tactic: 0.08
    max_bonus: 0.3
  term_mode:
    bonus_per_pattern: 0.1
    max_bonus: 0.25
  proof_length_bonuses:
    - { max_lines: 5, bonus: 0.2 }
    - { max_lines: 10, bonus: 0.15 }
    - { max_lines: 20, bonus: 0.1 }
  penalties:
    rewrite_heavy: { threshold: 5, penalty: -0.15 }
    rewrite_moderate: { threshold: 2, penalty: -0.08 }
    simp_heavy: { threshold: 3, penalty: -0.1 }
  bonuses:
    tactic_mode: 0.05

grind_scoring:
  base_score: 0.15
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.25 }
    good: { threshold: 0.6, bonus: 0.18 }
    moderate: { threshold: 0.4, bonus: 0.1 }
    low: { threshold: 0.0, bonus: 0.05 }
  rewrite:
    bonus_per_count: 0.06
    max_bonus: 0.35
  simp:
    bonus_per_count: 0.08
    max_bonus: 0.25
  algebraic_terms:
    bonus_per_pattern: 0.08
    max_bonus: 0.2
  proof_length_bonuses:
    - { min_lines: 5, max_lines: 30, bonus: 0.15 }
    - { max_lines: 5, bonus: 0.08 }
  penalties:
    induction: -0.15
    cases: -0.1
  algebraic_tactics:
    bonus_per_tactic: 0.08
    max_bonus: 0.2
  bonuses:
    pure_term_proof: 0.1

annotation_value_scoring:
  base_score: 0.05
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.25 }
    good: { threshold: 0.6, bonus: 0.18 }
    moderate: { threshold: 0.4, bonus: 0.1 }
    low: { threshold: 0.0, bonus: 0.05 }
  penalties:
    low_confidence: -0.1
  proof_length_bonuses:
    - { min_lines: 20, bonus: 0.3 }
    - { min_lines: 10, bonus: 0.2 }
    - { min_lines: 5, bonus: 0.15 }
    - { min_lines: 2, bonus: 0.1 }
  local_lemmas:
    bonus_per_count: 0.08
    max_bonus: 0.25
  tactic_diversity_bonuses:
    - { min_diversity: 5, bonus: 0.15 }
    - { min_diversity: 3, bonus: 0.1 }
    - { min_diversity: 0, bonus: 0.05 }
  rewrite_bonuses:
    - { min_count: 3, bonus: 0.12 }
    - { min_count: 0, bonus: 0.08 }
  simp_bonuses:
    - { min_count: 2, bonus: 0.08 }
    - { min_count: 0, bonus: 0.05 }
  bonuses:
    term_application: 0.1
    structural_proof: 0.1

subgoal_potential_scoring:
  confidence_multipliers:
    high: { threshold: 0.8, multiplier: 0.8 }
    good: { threshold: 0.6, multiplier: 0.7 }
    moderate: { threshold: 0.4, multiplier: 0.6 }
    low: { threshold: 0.0, multiplier: 0.5 }
    none: { threshold: 0.0, multiplier: 0.0 }
  bonuses:
    induction_or_cases: 0.25
    term_application: 0.1
    algebraic_term: 0.12
  structure_cases:
    bonus_per_case: 0.04
    max_bonus: 0.2
  rewrite_blocks:
    bonus_per_block: 0.08
    max_bonus: 0.2

risk_scoring:
  global_change_risk:
    rewrite_heavy: { threshold: 5, risk: 0.6 }
    simp_heavy: { threshold: 3, risk: 0.4 }
    simp_question_mark: 0.8
  simp_risk:
    heavy: { threshold: 3, risk: 0.6 }
    moderate: { threshold: 1, risk: 0.3 }
  local_lemma_risk:
    heavy: { threshold: 3, risk: 0.5 }
    moderate: { threshold: 1, risk: 0.2 }
  low_confidence_risk:
    very_low: { threshold: 0.4, risk: 0.7 }
    low: { threshold: 0.6, risk: 0.4 }
  component_weights:
    global_change: 0.3
    simp: 0.3
    local_lemma: 0.2
    confidence: 0.2

impact_scoring:
  proof_length_scores:
    - { max_lines: 0, score: 0.0 }
    - { max_lines: 5, score: 0.2 }
    - { max_lines: 10, score: 0.4 }
    - { max_lines: 20, score: 0.6 }
    - { max_lines: 40, score: 0.8 }
    - { min_lines: 40, score: 1.0 }
  reusability:
    score_per_local_lemma: 0.2
    max_score: 1.0
  component_weights:
    proof_length: 0.5
    annotation_value: 0.3
    reusability: 0.2

success_likelihood_scoring:
  complexity_penalties:
    induction_or_cases: 0.2
    long_proof: { threshold: 30, penalty: 0.1 }
    many_local_lemmas: { threshold: 3, penalty: 0.1 }
    max_penalty: 0.5
  component_weights:
    max_potential: 0.6
    confidence: 0.3
    complexity_penalty: -0.1

objectives:
  maximize_success:
    description: "Prioritize theorems most likely to be automated successfully"
    use_case: "When you want quick wins and high success rate"
    weights:
      success_likelihood: 0.50
      impact: 0.10
      annotation_value: 0.10
      subgoal_potential: 0.10
      risk: -0.20
  maximize_impact:
    description: "Prioritize theorems that save the most time when automated"
    use_case: "When you want maximum ROI on automation effort"
    weights:
      success_likelihood: 0.20
      impact: 0.40
      annotation_value: 0.30
      subgoal_potential: 0.05
      risk: -0.05
  maximize_subgoal_automation:
    description: "Prioritize theorems with good partial automation opportunities"
    use_case: "When you want to automate proof steps rather than whole goals"
    weights:
      success_likelihood: 0.15
      impact: 0.15
      annotation_value: 0.20
      subgoal_potential: 0.40
      risk: -0.10
  balanced:
    description: "Balanced weighting across all factors"
    use_case: "When you want a general-purpose ranking"
    weights:
      success_likelihood: 0.25
      impact: 0.25
      annotation_value: 0.20
      subgoal_potential: 0.20
      risk: -0.10

already_automated:
  penalties:
    tactic_usage: 0.3
    attribute: 0.5
    trivial_proof: 0.8
  tactic_patterns:
    - "by aesop"
    - "by grind"
  attribute_patterns:
    - "@[aesop"
  trivial_patterns:
    - ":= rfl"

tiers:
  s_tier_percentile: 10
  a_tier_percentile: 25
  b_tier_percentile: 50
  c_tier_percentile: 75
""")
        
        # Set environment variable
        monkeypatch.setenv("LEAN_PROOF_AUTO_MCP_CONFIG", str(config_file))
        
        # Load config (should use env var)
        config = load_default_config()
        
        # Verify custom value from env var config
        assert config.confidence.base_score == 0.7
    
    def test_no_env_var_uses_package_default(self, monkeypatch):
        """Test that without env var, package default is used."""
        # Ensure env var is not set
        monkeypatch.delenv("LEAN_PROOF_AUTO_MCP_CONFIG", raising=False)
        
        # Load config (should use package default)
        config = load_default_config()
        
        # Verify default value
        assert config.confidence.base_score == 0.3


class TestConfigImmutability:
    """Test that configuration is immutable."""
    
    def test_config_is_frozen(self):
        """Test that config dataclasses are frozen."""
        config = load_default_config()
        
        # Attempt to modify should raise error
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            config.confidence.base_score = 0.9  # type: ignore
