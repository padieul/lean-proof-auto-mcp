# Configuration Guide

## Overview

The Lean Proof Automation MCP uses a comprehensive configuration system to control all heuristic parameters for scoring and ranking automation potential. This guide explains the configuration architecture, all available parameters, and how to customize the system for your needs.

## Architecture

The configuration system follows hexagonal architecture principles:

- **Core logic** depends on the `HeuristicsConfig` protocol (port), not concrete implementations
- **Configuration is immutable** once loaded - changes require reloading
- **Validation happens at load time** with clear error messages
- **Configuration is versioned** for compatibility tracking

### Configuration Sources (Priority Order)

1. **Explicit parameter**: `config_path` in tool request
2. **Environment variable**: `LEAN_PROOF_AUTO_MCP_CONFIG`
3. **Package default**: Built-in `heuristics.yaml`

## Quick Start

### Using Default Configuration

The package ships with a default configuration that works well for typical Lean codebases. No configuration is required:

```json
{
  "file": "MyFile.lean",
  "skip_already_automated": false
}
```

### Using Custom Configuration

Create a custom YAML file and reference it:

```json
{
  "file": "MyFile.lean",
  "skip_already_automated": false,
  "config_path": "/path/to/custom_heuristics.yaml"
}
```

Or set the environment variable:

```bash
export LEAN_PROOF_AUTO_MCP_CONFIG=/path/to/custom_heuristics.yaml
```

## Configuration File Format

All configuration files must:
- Be valid YAML
- Include `version: "1.0"` at the top
- Follow the schema defined below
- Use values in valid ranges (validated at load time)

### Minimal Example

```yaml
version: "1.0"

confidence:
  base_score: 0.3
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

# ... (all other sections required)
```

## Configuration Parameters

### Version

**Required**: Must be `"1.0"` for API 1.0 compatibility.

```yaml
version: "1.0"
```

### Confidence Calculation

Controls how confident the system is in proof detection and analysis.

```yaml
confidence:
  base_score: 0.3  # Starting confidence level [0.0, 1.0]
  bonuses:
    proof_structure: 0.2  # Bonus for well-structured proofs [0.0, 1.0]
    tactic_detection: 0.2  # Bonus for detecting tactics [0.0, 1.0]
    structural_tactics: 0.15  # Bonus for structural tactics [0.0, 1.0]
    term_mode_patterns: 0.15  # Bonus for term-mode patterns [0.0, 1.0]
    automation_tactics: 0.1  # Bonus for automation tactics [0.0, 1.0]
    indentation_consistency: 0.05  # Bonus for consistent indentation [0.0, 1.0]
  penalties:
    sorry: -0.3  # Penalty for incomplete proofs [-1.0, 0.0]
    error_patterns: -0.1  # Penalty for error indicators [-1.0, 0.0]
  thresholds:
    proof_length_min: 1  # Minimum proof lines for confidence (positive integer)
    proof_length_max: 50  # Maximum proof lines for full confidence (positive integer)
    proof_length_max_bonus: 0.05  # Bonus for appropriate length [0.0, 1.0]
```

**Use Cases:**
- Increase `base_score` if your proofs are generally well-structured
- Adjust `proof_length_max` based on typical proof complexity in your codebase
- Increase `sorry` penalty if you want to strongly discourage incomplete proofs

### Aesop Scoring

Aesop works well on structural proofs with constructors and destructors.

```yaml
aesop_scoring:
  base_score: 0.2  # Starting score for aesop potential [0.0, 1.0]
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.3 }  # High confidence boost
    good: { threshold: 0.6, bonus: 0.2 }  # Good confidence boost
    moderate: { threshold: 0.4, bonus: 0.1 }  # Moderate confidence boost
    low: { threshold: 0.0, bonus: 0.05 }  # Any confidence is better than none
  structural_tactics:
    bonus_per_tactic: 0.08  # Bonus per structural tactic [0.0, 1.0]
    max_bonus: 0.3  # Maximum bonus from structural tactics [0.0, 1.0]
  term_mode:
    bonus_per_pattern: 0.1  # Bonus per term-mode pattern [0.0, 1.0]
    max_bonus: 0.25  # Maximum bonus from term-mode patterns [0.0, 1.0]
  proof_length_bonuses:
    - { max_lines: 5, bonus: 0.2 }  # Very short proofs
    - { max_lines: 10, bonus: 0.15 }  # Short proofs
    - { max_lines: 20, bonus: 0.1 }  # Medium proofs
  penalties:
    rewrite_heavy: { threshold: 5, penalty: -0.15 }  # Heavy rewriting
    rewrite_moderate: { threshold: 2, penalty: -0.08 }  # Moderate rewriting
    simp_heavy: { threshold: 3, penalty: -0.1 }  # Heavy simp usage
  bonuses:
    tactic_mode: 0.05  # Bonus for tactic-mode proofs [0.0, 1.0]
```

**Use Cases:**
- Increase `base_score` if your codebase has many structural proofs
- Adjust `proof_length_bonuses` based on typical proof lengths
- Increase `rewrite_heavy.penalty` if you want to discourage rewrite-heavy proofs

### Grind Scoring

Grind excels at equational reasoning and simplification.

```yaml
grind_scoring:
  base_score: 0.15  # Starting score for grind potential [0.0, 1.0]
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.25 }  # High confidence boost
    good: { threshold: 0.6, bonus: 0.18 }  # Good confidence boost
    moderate: { threshold: 0.4, bonus: 0.1 }  # Moderate confidence boost
    low: { threshold: 0.0, bonus: 0.05 }  # Any confidence is better than none
  rewrite:
    bonus_per_count: 0.06  # Bonus per rewrite occurrence [0.0, 1.0]
    max_bonus: 0.35  # Maximum bonus from rewrites [0.0, 1.0]
  simp:
    bonus_per_count: 0.08  # Bonus per simp occurrence [0.0, 1.0]
    max_bonus: 0.25  # Maximum bonus from simp [0.0, 1.0]
  algebraic_terms:
    bonus_per_pattern: 0.08  # Bonus per algebraic term pattern [0.0, 1.0]
    max_bonus: 0.2  # Maximum bonus from algebraic terms [0.0, 1.0]
  proof_length_bonuses:
    - { min_lines: 5, max_lines: 30, bonus: 0.15 }  # Medium-length proofs
    - { max_lines: 5, bonus: 0.08 }  # Short proofs
  penalties:
    induction: -0.15  # Penalty for induction [-1.0, 0.0]
    cases: -0.1  # Penalty for case analysis [-1.0, 0.0]
  algebraic_tactics:
    bonus_per_tactic: 0.08  # Bonus per algebraic tactic [0.0, 1.0]
    max_bonus: 0.2  # Maximum bonus from algebraic tactics [0.0, 1.0]
  bonuses:
    pure_term_proof: 0.1  # Bonus for pure term-mode proofs [0.0, 1.0]
```

**Use Cases:**
- Increase `base_score` if your codebase has many equational proofs
- Adjust `rewrite.bonus_per_count` based on typical rewrite usage
- Decrease `induction` penalty if you want to encourage grind on inductive proofs

### Annotation Value Scoring

Estimates ROI for adding automation annotations.

```yaml
annotation_value_scoring:
  base_score: 0.05  # Starting annotation value [0.0, 1.0]
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.25 }  # High confidence proofs
    good: { threshold: 0.6, bonus: 0.18 }  # Good confidence proofs
    moderate: { threshold: 0.4, bonus: 0.1 }  # Some confidence
    low: { threshold: 0.0, bonus: 0.05 }  # Any confidence
  penalties:
    low_confidence: -0.1  # Penalty for low confidence [-1.0, 0.0]
  proof_length_bonuses:
    - { min_lines: 20, bonus: 0.3 }  # Long proofs
    - { min_lines: 10, bonus: 0.2 }  # Medium proofs
    - { min_lines: 5, bonus: 0.15 }  # Short proofs
    - { min_lines: 2, bonus: 0.1 }  # Very short proofs
  local_lemmas:
    bonus_per_count: 0.08  # Bonus per local lemma [0.0, 1.0]
    max_bonus: 0.25  # Maximum bonus from local lemmas [0.0, 1.0]
  tactic_diversity_bonuses:
    - { min_diversity: 5, bonus: 0.15 }  # High diversity
    - { min_diversity: 3, bonus: 0.1 }  # Medium diversity
    - { min_diversity: 0, bonus: 0.05 }  # Any detected patterns
  rewrite_bonuses:
    - { min_count: 3, bonus: 0.12 }  # Many rewrites
    - { min_count: 0, bonus: 0.08 }  # Some rewrites
  simp_bonuses:
    - { min_count: 2, bonus: 0.08 }  # Multiple simps
    - { min_count: 0, bonus: 0.05 }  # Some simp usage
  bonuses:
    term_application: 0.1  # Complex term applications [0.0, 1.0]
    structural_proof: 0.1  # Structural proofs with cases [0.0, 1.0]
```

**Use Cases:**
- Increase `proof_length_bonuses` if you want to prioritize longer proofs
- Adjust `local_lemmas.bonus_per_count` based on typical local lemma usage
- Increase `tactic_diversity_bonuses` if you value diverse proof strategies

### Subgoal Potential Scoring

Estimates potential for automating individual subgoals.

```yaml
subgoal_potential_scoring:
  confidence_multipliers:
    high: { threshold: 0.8, multiplier: 0.8 }  # High confidence
    good: { threshold: 0.6, multiplier: 0.7 }  # Good confidence
    moderate: { threshold: 0.4, multiplier: 0.6 }  # Some confidence
    low: { threshold: 0.0, multiplier: 0.5 }  # Low confidence
    none: { threshold: 0.0, multiplier: 0.0 }  # No confidence
  bonuses:
    induction_or_cases: 0.25  # Can automate branches [0.0, 1.0]
    term_application: 0.1  # Term applications [0.0, 1.0]
    algebraic_term: 0.12  # Algebraic terms [0.0, 1.0]
  structure_cases:
    bonus_per_case: 0.04  # Bonus per case branch [0.0, 1.0]
    max_bonus: 0.2  # Maximum bonus from cases [0.0, 1.0]
  rewrite_blocks:
    bonus_per_block: 0.08  # Bonus per rewrite block [0.0, 1.0]
    max_bonus: 0.2  # Maximum bonus from rewrite blocks [0.0, 1.0]
```

**Use Cases:**
- Increase `induction_or_cases` bonus if you want to prioritize case analysis
- Adjust `confidence_multipliers` based on your confidence in proof detection
- Increase `structure_cases.bonus_per_case` if you have many case-heavy proofs

### Risk Scoring

Estimates risk of automation breaking or causing issues.

```yaml
risk_scoring:
  global_change_risk:
    rewrite_heavy: { threshold: 5, risk: 0.6 }  # Heavy rewriting
    simp_heavy: { threshold: 3, risk: 0.4 }  # Heavy simp
    simp_question_mark: 0.8  # simp? is very risky [0.0, 1.0]
  simp_risk:
    heavy: { threshold: 3, risk: 0.6 }  # Heavy simp usage
    moderate: { threshold: 1, risk: 0.3 }  # Moderate simp usage
  local_lemma_risk:
    heavy: { threshold: 3, risk: 0.5 }  # Many local lemmas
    moderate: { threshold: 1, risk: 0.2 }  # Some local lemmas
  low_confidence_risk:
    very_low: { threshold: 0.4, risk: 0.7 }  # Very low confidence
    low: { threshold: 0.6, risk: 0.4 }  # Low confidence
  component_weights:
    global_change: 0.3  # Weight for global change risk [0.0, 1.0]
    simp: 0.3  # Weight for simp risk [0.0, 1.0]
    local_lemma: 0.2  # Weight for local lemma risk [0.0, 1.0]
    confidence: 0.2  # Weight for confidence risk [0.0, 1.0]
```

**Use Cases:**
- Increase `simp_question_mark` risk if you want to strongly discourage simp?
- Adjust `component_weights` to emphasize different risk factors
- Increase `local_lemma_risk` if you're concerned about local lemma usage

### Impact Scoring

Estimates time saved by automation.

```yaml
impact_scoring:
  proof_length_scores:
    - { max_lines: 0, score: 0.0 }  # No proof
    - { max_lines: 5, score: 0.2 }  # Very short
    - { max_lines: 10, score: 0.4 }  # Short
    - { max_lines: 20, score: 0.6 }  # Medium
    - { max_lines: 40, score: 0.8 }  # Long
    - { min_lines: 40, score: 1.0 }  # Very long
  reusability:
    score_per_local_lemma: 0.2  # Score per local lemma [0.0, 1.0]
    max_score: 1.0  # Maximum reusability score [0.0, 1.0]
  component_weights:
    proof_length: 0.5  # Weight for proof length [0.0, 1.0]
    annotation_value: 0.3  # Weight for annotation value [0.0, 1.0]
    reusability: 0.2  # Weight for reusability [0.0, 1.0]
```

**Use Cases:**
- Adjust `proof_length_scores` based on typical proof lengths in your codebase
- Increase `reusability.score_per_local_lemma` if you value reusable proofs
- Adjust `component_weights` to emphasize different impact factors

### Success Likelihood Scoring

Estimates likelihood of successful automation.

```yaml
success_likelihood_scoring:
  complexity_penalties:
    induction_or_cases: 0.2  # Penalty for structural complexity [0.0, 1.0]
    long_proof: { threshold: 30, penalty: 0.1 }  # Penalty for long proofs
    many_local_lemmas: { threshold: 3, penalty: 0.1 }  # Penalty for many local lemmas
    max_penalty: 0.5  # Maximum complexity penalty [0.0, 1.0]
  component_weights:
    max_potential: 0.6  # Weight for maximum automation potential [0.0, 1.0]
    confidence: 0.3  # Weight for confidence [0.0, 1.0]
    complexity_penalty: -0.1  # Weight for complexity penalty (negative)
```

**Use Cases:**
- Adjust `complexity_penalties` based on your tolerance for complex proofs
- Increase `max_penalty` if you want to strongly discourage complex proofs
- Adjust `component_weights` to emphasize different success factors

### Objectives

Different ranking strategies for different use cases.

```yaml
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
```

**Use Cases:**
- Create custom objectives by adding new entries
- Adjust weights to emphasize different factors
- Use negative weights for risk to penalize risky theorems

### Already-Automated Detection

Detects theorems that already use automation tactics or attributes.

```yaml
already_automated:
  penalties:
    tactic_usage: 0.3  # Penalty for using automation tactics [0.0, 1.0]
    attribute: 0.5  # Penalty for automation attributes [0.0, 1.0]
    trivial_proof: 0.8  # Penalty for trivial proofs [0.0, 1.0]
  tactic_patterns:
    - "by aesop"
    - "by grind"
    - "by simp"
    - "by omega"
    - "by decide"
    - "by tauto"
    - "aesop"
    - "grind"
    - "simp"
  attribute_patterns:
    - "@[aesop"
    - "@[simp"
  trivial_patterns:
    - ":= rfl"
    - "by rfl"
    - ":= trivial"
    - "by trivial"
```

**Use Cases:**
- Add custom tactic patterns to detect additional automation tactics
- Adjust penalties based on how much you want to discourage already-automated theorems
- Add custom attribute patterns for your own automation attributes

### Tiers

Percentile thresholds for S/A/B/C/D tier assignment.

```yaml
tiers:
  s_tier_percentile: 10  # Top 10% are S-tier (positive number < 100)
  a_tier_percentile: 25  # Top 10-25% are A-tier (positive number < 100)
  b_tier_percentile: 50  # Top 25-50% are B-tier (positive number < 100)
  c_tier_percentile: 75  # Top 50-75% are C-tier (positive number < 100)
  # Bottom 25% are D-tier (implicit)
```

**Use Cases:**
- Adjust percentiles to make tiers more or less selective
- Use smaller `s_tier_percentile` for stricter S-tier classification
- Use larger percentiles for more lenient tier classification

## Validation

Configuration files are validated at load time. Invalid configurations fail fast with clear error messages:

### Version Validation

```yaml
version: "2.0"  # ❌ Invalid version
```

Error: `Configuration version must be "1.0", got "2.0"`

### Range Validation

```yaml
confidence:
  base_score: 1.5  # ❌ Out of range
```

Error: `confidence.base_score must be in [0.0, 1.0], got 1.5`

### Threshold Validation

```yaml
tiers:
  s_tier_percentile: 30
  a_tier_percentile: 20  # ❌ Not monotonic
```

Error: `Tier thresholds must be strictly increasing`

## Example Custom Configurations

### Conservative Configuration

Prioritize safety and low risk:

```yaml
version: "1.0"

# ... (standard sections)

objectives:
  conservative:
    description: "Prioritize safe, low-risk automation"
    use_case: "When you want to minimize breaking changes"
    weights:
      success_likelihood: 0.40
      impact: 0.15
      annotation_value: 0.15
      subgoal_potential: 0.10
      risk: -0.40  # Strong risk penalty

risk_scoring:
  component_weights:
    global_change: 0.4  # Emphasize global change risk
    simp: 0.3
    local_lemma: 0.2
    confidence: 0.1
```

### Aggressive Configuration

Prioritize impact and automation potential:

```yaml
version: "1.0"

# ... (standard sections)

objectives:
  aggressive:
    description: "Prioritize maximum automation potential"
    use_case: "When you want to automate as much as possible"
    weights:
      success_likelihood: 0.30
      impact: 0.50
      annotation_value: 0.20
      subgoal_potential: 0.15
      risk: -0.05  # Weak risk penalty

aesop_scoring:
  base_score: 0.3  # Higher base score
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.4 }  # Larger bonuses
```

### Research Configuration

Prioritize experimentation and exploration:

```yaml
version: "1.0"

# ... (standard sections)

tiers:
  s_tier_percentile: 5  # Top 5% are S-tier (stricter)
  a_tier_percentile: 15  # Top 5-15% are A-tier
  b_tier_percentile: 40  # Top 15-40% are B-tier
  c_tier_percentile: 70  # Top 40-70% are C-tier

confidence:
  base_score: 0.2  # Lower base (more conservative)
  bonuses:
    proof_structure: 0.3  # Higher bonuses for good structure
```

## Troubleshooting

### Configuration Not Loading

**Problem**: Custom configuration not being used.

**Solution**: Check configuration source in response metadata:

```json
{
  "metadata": {
    "config_source": "default"  // Should be "path" or "environment"
  }
}
```

Verify:
1. File path is correct and accessible
2. Environment variable is set correctly
3. YAML syntax is valid

### Validation Errors

**Problem**: Configuration fails to load with validation error.

**Solution**: Check error message for specific field and valid range:

```
Error: confidence.base_score must be in [0.0, 1.0], got 1.5
```

Fix the invalid value and reload.

### Unexpected Scores

**Problem**: Scores don't match expectations.

**Solution**: 
1. Check objective weights in configuration
2. Verify component scores in response (use `include_components: true`)
3. Adjust relevant parameters incrementally
4. Test with small changes to understand impact

## Best Practices

1. **Start with defaults**: Use the package default configuration initially
2. **Make incremental changes**: Adjust one parameter at a time
3. **Test thoroughly**: Verify changes produce expected results
4. **Document changes**: Add comments explaining why parameters were changed
5. **Version control**: Track configuration files in version control
6. **Share configurations**: Share successful configurations with your team
7. **Validate early**: Test configuration loading before running full analysis

## See Also

- [Tool Contract Documentation](mcp/tool_contract.md) - API reference
- [README](../README.md) - Quick start guide
- Default configuration: `src/lean_proof_auto_mcp/heuristics.yaml`
