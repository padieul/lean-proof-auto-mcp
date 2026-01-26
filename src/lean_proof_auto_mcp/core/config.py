"""Configuration system for heuristic parameters.

Follows hexagonal architecture:
- Core logic depends on HeuristicsConfig protocol (port)
- YamlHeuristicsConfig is an adapter (infrastructure detail)
- Configuration is immutable once loaded
- Validation happens at construction time

Environment Variables:
    LEAN_PROOF_AUTO_MCP_CONFIG: Path to custom configuration file
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml


class HeuristicsConfig(Protocol):
    """Port: Configuration interface for heuristic parameters.

    Core scoring logic depends on this abstraction, not concrete implementations.
    """

    @property
    def confidence(self) -> "ConfidenceConfig": ...

    @property
    def aesop_scoring(self) -> "AesopScoringConfig": ...

    @property
    def grind_scoring(self) -> "GrindScoringConfig": ...

    @property
    def annotation_value_scoring(self) -> "AnnotationValueScoringConfig": ...

    @property
    def subgoal_potential_scoring(self) -> "SubgoalPotentialScoringConfig": ...

    @property
    def risk_scoring(self) -> "RiskScoringConfig": ...

    @property
    def impact_scoring(self) -> "ImpactScoringConfig": ...

    @property
    def success_likelihood_scoring(self) -> "SuccessLikelihoodScoringConfig": ...

    @property
    def objectives(self) -> dict[str, "ObjectiveConfig"]: ...

    @property
    def automation_detection(self) -> "AutomationDetectionConfig": ...

    @property
    def tiers(self) -> "TierConfig": ...


@dataclass(frozen=True)
class ConfidenceConfig:
    """Configuration for confidence calculation."""

    base_score: float
    proof_structure_bonus: float
    tactic_detection_bonus: float
    structural_tactics_bonus: float
    term_mode_patterns_bonus: float
    automation_tactics_bonus: float
    indentation_consistency_bonus: float
    sorry_penalty: float
    error_patterns_penalty: float
    proof_length_min: int
    proof_length_max: int
    proof_length_max_bonus: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        scores = {
            "base_score": self.base_score,
            "proof_structure_bonus": self.proof_structure_bonus,
            "tactic_detection_bonus": self.tactic_detection_bonus,
            "structural_tactics_bonus": self.structural_tactics_bonus,
            "term_mode_patterns_bonus": self.term_mode_patterns_bonus,
            "automation_tactics_bonus": self.automation_tactics_bonus,
            "indentation_consistency_bonus": self.indentation_consistency_bonus,
            "proof_length_max_bonus": self.proof_length_max_bonus,
        }

        for name, score in scores.items():
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {score}")

        penalties = {
            "sorry_penalty": self.sorry_penalty,
            "error_patterns_penalty": self.error_patterns_penalty,
        }

        for name, penalty in penalties.items():
            if not (-1.0 <= penalty <= 0.0):
                raise ValueError(f"{name} must be in [-1.0, 0.0], got {penalty}")

        if self.proof_length_min < 0:
            raise ValueError(f"proof_length_min must be >= 0, got {self.proof_length_min}")

        if self.proof_length_max < self.proof_length_min:
            raise ValueError(
                f"proof_length_max ({self.proof_length_max}) must be >= "
                f"proof_length_min ({self.proof_length_min})"
            )


@dataclass(frozen=True)
class ConfidenceBonusTier:
    """Confidence tier with threshold and bonus."""

    threshold: float
    bonus: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.threshold <= 1.0):
            raise ValueError(f"threshold must be in [0.0, 1.0], got {self.threshold}")
        if not (0.0 <= self.bonus <= 1.0):
            raise ValueError(f"bonus must be in [0.0, 1.0], got {self.bonus}")


@dataclass(frozen=True)
class ProofLengthBonus:
    """Proof length bonus configuration."""

    max_lines: int
    bonus: float

    def __post_init__(self) -> None:
        if self.max_lines < 0:
            raise ValueError(f"max_lines must be >= 0, got {self.max_lines}")
        if not (0.0 <= self.bonus <= 1.0):
            raise ValueError(f"bonus must be in [0.0, 1.0], got {self.bonus}")


@dataclass(frozen=True)
class PenaltyThreshold:
    """Penalty threshold configuration."""

    threshold: int
    penalty: float

    def __post_init__(self) -> None:
        if self.threshold < 0:
            raise ValueError(f"threshold must be >= 0, got {self.threshold}")
        if not (-1.0 <= self.penalty <= 0.0):
            raise ValueError(f"penalty must be in [-1.0, 0.0], got {self.penalty}")


@dataclass(frozen=True)
class AesopScoringConfig:
    """Configuration for aesop potential scoring."""

    base_score: float
    confidence_bonuses: list[ConfidenceBonusTier]
    structural_tactics_bonus_per_tactic: float
    structural_tactics_max_bonus: float
    term_mode_bonus_per_pattern: float
    term_mode_max_bonus: float
    proof_length_bonuses: list[ProofLengthBonus]
    rewrite_heavy_threshold: int
    rewrite_heavy_penalty: float
    rewrite_moderate_threshold: int
    rewrite_moderate_penalty: float
    simp_heavy_threshold: int
    simp_heavy_penalty: float
    tactic_mode_bonus: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if not (0.0 <= self.base_score <= 1.0):
            raise ValueError(f"base_score must be in [0.0, 1.0], got {self.base_score}")

        bonuses = {
            "structural_tactics_bonus_per_tactic": self.structural_tactics_bonus_per_tactic,
            "structural_tactics_max_bonus": self.structural_tactics_max_bonus,
            "term_mode_bonus_per_pattern": self.term_mode_bonus_per_pattern,
            "term_mode_max_bonus": self.term_mode_max_bonus,
            "tactic_mode_bonus": self.tactic_mode_bonus,
        }

        for name, bonus in bonuses.items():
            if not (0.0 <= bonus <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {bonus}")

        penalties = {
            "rewrite_heavy_penalty": self.rewrite_heavy_penalty,
            "rewrite_moderate_penalty": self.rewrite_moderate_penalty,
            "simp_heavy_penalty": self.simp_heavy_penalty,
        }

        for name, penalty in penalties.items():
            if not (-1.0 <= penalty <= 0.0):
                raise ValueError(f"{name} must be in [-1.0, 0.0], got {penalty}")

        thresholds = {
            "rewrite_heavy_threshold": self.rewrite_heavy_threshold,
            "rewrite_moderate_threshold": self.rewrite_moderate_threshold,
            "simp_heavy_threshold": self.simp_heavy_threshold,
        }

        for name, threshold in thresholds.items():
            if threshold < 0:
                raise ValueError(f"{name} must be >= 0, got {threshold}")


@dataclass(frozen=True)
class GrindScoringConfig:
    """Configuration for grind potential scoring."""

    base_score: float
    confidence_bonuses: list[ConfidenceBonusTier]
    rewrite_bonus_per_count: float
    rewrite_max_bonus: float
    simp_bonus_per_count: float
    simp_max_bonus: float
    algebraic_terms_bonus_per_pattern: float
    algebraic_terms_max_bonus: float
    proof_length_min_for_bonus: int
    proof_length_max_for_bonus: int
    proof_length_bonus: float
    short_proof_bonus: float
    induction_penalty: float
    cases_penalty: float
    algebraic_tactics_bonus_per_tactic: float
    algebraic_tactics_max_bonus: float
    pure_term_proof_bonus: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if not (0.0 <= self.base_score <= 1.0):
            raise ValueError(f"base_score must be in [0.0, 1.0], got {self.base_score}")

        bonuses = {
            "rewrite_bonus_per_count": self.rewrite_bonus_per_count,
            "rewrite_max_bonus": self.rewrite_max_bonus,
            "simp_bonus_per_count": self.simp_bonus_per_count,
            "simp_max_bonus": self.simp_max_bonus,
            "algebraic_terms_bonus_per_pattern": self.algebraic_terms_bonus_per_pattern,
            "algebraic_terms_max_bonus": self.algebraic_terms_max_bonus,
            "proof_length_bonus": self.proof_length_bonus,
            "short_proof_bonus": self.short_proof_bonus,
            "algebraic_tactics_bonus_per_tactic": self.algebraic_tactics_bonus_per_tactic,
            "algebraic_tactics_max_bonus": self.algebraic_tactics_max_bonus,
            "pure_term_proof_bonus": self.pure_term_proof_bonus,
        }

        for name, bonus in bonuses.items():
            if not (0.0 <= bonus <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {bonus}")

        penalties = {
            "induction_penalty": self.induction_penalty,
            "cases_penalty": self.cases_penalty,
        }

        for name, penalty in penalties.items():
            if not (-1.0 <= penalty <= 0.0):
                raise ValueError(f"{name} must be in [-1.0, 0.0], got {penalty}")

        if self.proof_length_min_for_bonus < 0:
            raise ValueError(
                f"proof_length_min_for_bonus must be >= 0, got {self.proof_length_min_for_bonus}"
            )

        if self.proof_length_max_for_bonus < self.proof_length_min_for_bonus:
            raise ValueError(
                f"proof_length_max_for_bonus ({self.proof_length_max_for_bonus}) must be >= "
                f"proof_length_min_for_bonus ({self.proof_length_min_for_bonus})"
            )


@dataclass(frozen=True)
class AnnotationValueScoringConfig:
    """Configuration for annotation value scoring."""

    base_score: float
    confidence_bonuses: list[ConfidenceBonusTier]
    low_confidence_penalty: float
    proof_length_thresholds: list[tuple[int, float]]  # [(min_lines, bonus), ...]
    local_lemmas_bonus_per_count: float
    local_lemmas_max_bonus: float
    tactic_diversity_thresholds: list[tuple[int, float]]  # [(min_diversity, bonus), ...]
    rewrite_count_thresholds: list[tuple[int, float]]  # [(min_count, bonus), ...]
    simp_count_thresholds: list[tuple[int, float]]  # [(min_count, bonus), ...]
    term_application_bonus: float
    structural_proof_bonus: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if not (0.0 <= self.base_score <= 1.0):
            raise ValueError(f"base_score must be in [0.0, 1.0], got {self.base_score}")

        if not (-1.0 <= self.low_confidence_penalty <= 0.0):
            raise ValueError(
                f"low_confidence_penalty must be in [-1.0, 0.0], got {self.low_confidence_penalty}"
            )

        bonuses = {
            "local_lemmas_bonus_per_count": self.local_lemmas_bonus_per_count,
            "local_lemmas_max_bonus": self.local_lemmas_max_bonus,
            "term_application_bonus": self.term_application_bonus,
            "structural_proof_bonus": self.structural_proof_bonus,
        }

        for name, bonus in bonuses.items():
            if not (0.0 <= bonus <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {bonus}")


@dataclass(frozen=True)
class ConfidenceMultiplier:
    """Confidence multiplier configuration."""

    threshold: float
    multiplier: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.threshold <= 1.0):
            raise ValueError(f"threshold must be in [0.0, 1.0], got {self.threshold}")
        if not (0.0 <= self.multiplier <= 1.0):
            raise ValueError(f"multiplier must be in [0.0, 1.0], got {self.multiplier}")


@dataclass(frozen=True)
class SubgoalPotentialScoringConfig:
    """Configuration for subgoal potential scoring."""

    confidence_multipliers: list[ConfidenceMultiplier]
    induction_or_cases_bonus: float
    term_application_bonus: float
    algebraic_term_bonus: float
    structure_cases_bonus_per_case: float
    structure_cases_max_bonus: float
    rewrite_blocks_bonus_per_block: float
    rewrite_blocks_max_bonus: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        bonuses = {
            "induction_or_cases_bonus": self.induction_or_cases_bonus,
            "term_application_bonus": self.term_application_bonus,
            "algebraic_term_bonus": self.algebraic_term_bonus,
            "structure_cases_bonus_per_case": self.structure_cases_bonus_per_case,
            "structure_cases_max_bonus": self.structure_cases_max_bonus,
            "rewrite_blocks_bonus_per_block": self.rewrite_blocks_bonus_per_block,
            "rewrite_blocks_max_bonus": self.rewrite_blocks_max_bonus,
        }

        for name, bonus in bonuses.items():
            if not (0.0 <= bonus <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {bonus}")


@dataclass(frozen=True)
class RiskThreshold:
    """Risk threshold configuration."""

    threshold: int
    risk: float

    def __post_init__(self) -> None:
        if self.threshold < 0:
            raise ValueError(f"threshold must be >= 0, got {self.threshold}")
        if not (0.0 <= self.risk <= 1.0):
            raise ValueError(f"risk must be in [0.0, 1.0], got {self.risk}")


@dataclass(frozen=True)
class RiskScoringConfig:
    """Configuration for risk scoring."""

    global_change_rewrite_heavy_threshold: int
    global_change_rewrite_heavy_risk: float
    global_change_simp_heavy_threshold: int
    global_change_simp_heavy_risk: float
    global_change_simp_question_mark_risk: float
    simp_heavy_threshold: int
    simp_heavy_risk: float
    simp_moderate_threshold: int
    simp_moderate_risk: float
    local_lemma_heavy_threshold: int
    local_lemma_heavy_risk: float
    local_lemma_moderate_threshold: int
    local_lemma_moderate_risk: float
    low_confidence_very_low_threshold: float
    low_confidence_very_low_risk: float
    low_confidence_low_threshold: float
    low_confidence_low_risk: float
    component_weight_global_change: float
    component_weight_simp: float
    component_weight_local_lemma: float
    component_weight_confidence: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        thresholds = {
            "global_change_rewrite_heavy_threshold": self.global_change_rewrite_heavy_threshold,
            "global_change_simp_heavy_threshold": self.global_change_simp_heavy_threshold,
            "simp_heavy_threshold": self.simp_heavy_threshold,
            "simp_moderate_threshold": self.simp_moderate_threshold,
            "local_lemma_heavy_threshold": self.local_lemma_heavy_threshold,
            "local_lemma_moderate_threshold": self.local_lemma_moderate_threshold,
        }

        for name, threshold in thresholds.items():
            if threshold < 0:
                raise ValueError(f"{name} must be >= 0, got {threshold}")

        risks = {
            "global_change_rewrite_heavy_risk": self.global_change_rewrite_heavy_risk,
            "global_change_simp_heavy_risk": self.global_change_simp_heavy_risk,
            "global_change_simp_question_mark_risk": self.global_change_simp_question_mark_risk,
            "simp_heavy_risk": self.simp_heavy_risk,
            "simp_moderate_risk": self.simp_moderate_risk,
            "local_lemma_heavy_risk": self.local_lemma_heavy_risk,
            "local_lemma_moderate_risk": self.local_lemma_moderate_risk,
            "low_confidence_very_low_risk": self.low_confidence_very_low_risk,
            "low_confidence_low_risk": self.low_confidence_low_risk,
        }

        for name, risk in risks.items():
            if not (0.0 <= risk <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {risk}")

        confidence_thresholds: dict[str, float] = {
            "low_confidence_very_low_threshold": self.low_confidence_very_low_threshold,
            "low_confidence_low_threshold": self.low_confidence_low_threshold,
        }

        for name, threshold in confidence_thresholds.items():  # type: ignore[assignment]
            if not (0.0 <= threshold <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {threshold}")

        weights = {
            "component_weight_global_change": self.component_weight_global_change,
            "component_weight_simp": self.component_weight_simp,
            "component_weight_local_lemma": self.component_weight_local_lemma,
            "component_weight_confidence": self.component_weight_confidence,
        }

        for name, weight in weights.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {weight}")


@dataclass(frozen=True)
class ProofLengthScore:
    """Proof length score configuration."""

    max_lines: int | None  # None means no upper bound
    min_lines: int | None  # None means no lower bound
    score: float

    def __post_init__(self) -> None:
        if self.max_lines is not None and self.max_lines < 0:
            raise ValueError(f"max_lines must be >= 0, got {self.max_lines}")
        if self.min_lines is not None and self.min_lines < 0:
            raise ValueError(f"min_lines must be >= 0, got {self.min_lines}")
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"score must be in [0.0, 1.0], got {self.score}")


@dataclass(frozen=True)
class ImpactScoringConfig:
    """Configuration for impact scoring."""

    proof_length_scores: list[ProofLengthScore]
    reusability_score_per_local_lemma: float
    reusability_max_score: float
    component_weight_proof_length: float
    component_weight_annotation_value: float
    component_weight_reusability: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if not (0.0 <= self.reusability_score_per_local_lemma <= 1.0):
            raise ValueError(
                "reusability_score_per_local_lemma must be in [0.0, 1.0], "
                f"got {self.reusability_score_per_local_lemma}"
            )

        if not (0.0 <= self.reusability_max_score <= 1.0):
            raise ValueError(
                f"reusability_max_score must be in [0.0, 1.0], got {self.reusability_max_score}"
            )

        weights = {
            "component_weight_proof_length": self.component_weight_proof_length,
            "component_weight_annotation_value": self.component_weight_annotation_value,
            "component_weight_reusability": self.component_weight_reusability,
        }

        for name, weight in weights.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {weight}")


@dataclass(frozen=True)
class ComplexityPenalty:
    """Complexity penalty configuration."""

    threshold: int
    penalty: float

    def __post_init__(self) -> None:
        if self.threshold < 0:
            raise ValueError(f"threshold must be >= 0, got {self.threshold}")
        if not (0.0 <= self.penalty <= 1.0):
            raise ValueError(f"penalty must be in [0.0, 1.0], got {self.penalty}")


@dataclass(frozen=True)
class SuccessLikelihoodScoringConfig:
    """Configuration for success likelihood scoring."""

    complexity_induction_or_cases_penalty: float
    complexity_long_proof_threshold: int
    complexity_long_proof_penalty: float
    complexity_many_local_lemmas_threshold: int
    complexity_many_local_lemmas_penalty: float
    complexity_max_penalty: float
    component_weight_max_potential: float
    component_weight_confidence: float
    component_weight_complexity_penalty: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        penalties = {
            "complexity_induction_or_cases_penalty": self.complexity_induction_or_cases_penalty,
            "complexity_long_proof_penalty": self.complexity_long_proof_penalty,
            "complexity_many_local_lemmas_penalty": self.complexity_many_local_lemmas_penalty,
            "complexity_max_penalty": self.complexity_max_penalty,
        }

        for name, penalty in penalties.items():
            if not (0.0 <= penalty <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {penalty}")

        thresholds = {
            "complexity_long_proof_threshold": self.complexity_long_proof_threshold,
            "complexity_many_local_lemmas_threshold": self.complexity_many_local_lemmas_threshold,
        }

        for name, threshold in thresholds.items():
            if threshold < 0:
                raise ValueError(f"{name} must be >= 0, got {threshold}")

        weights = {
            "component_weight_max_potential": self.component_weight_max_potential,
            "component_weight_confidence": self.component_weight_confidence,
            "component_weight_complexity_penalty": self.component_weight_complexity_penalty,
        }

        for name, weight in weights.items():
            if not (-1.0 <= weight <= 1.0):
                raise ValueError(f"{name} must be in [-1.0, 1.0], got {weight}")


@dataclass(frozen=True)
class ObjectiveConfig:
    """Configuration for a ranking objective."""

    description: str
    use_case: str
    weight_success_likelihood: float
    weight_impact: float
    weight_annotation_value: float
    weight_subgoal_potential: float
    weight_risk: float

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        weights = {
            "weight_success_likelihood": self.weight_success_likelihood,
            "weight_impact": self.weight_impact,
            "weight_annotation_value": self.weight_annotation_value,
            "weight_subgoal_potential": self.weight_subgoal_potential,
            "weight_risk": self.weight_risk,
        }

        for name, weight in weights.items():
            if not (-1.0 <= weight <= 1.0):
                raise ValueError(f"{name} must be in [-1.0, 1.0], got {weight}")


@dataclass(frozen=True)
class AutomationDetectionConfig:
    """Configuration for automation detection.

    Attributes:
        tactic_penalty: Penalty for theorems using automation tactics
        attribute_penalty: Penalty for theorems with automation attributes
        trivial_penalty: Penalty for trivial proofs
        tactic_patterns: Patterns to detect in proof text
        attribute_patterns: Patterns to detect in declaration
        trivial_patterns: Patterns for trivial proofs
    """

    tactic_penalty: float
    attribute_penalty: float
    trivial_penalty: float
    tactic_patterns: list[str]
    attribute_patterns: list[str]
    trivial_patterns: list[str]

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        penalties = {
            "tactic_penalty": self.tactic_penalty,
            "attribute_penalty": self.attribute_penalty,
            "trivial_penalty": self.trivial_penalty,
        }

        for name, penalty in penalties.items():
            if not (0.0 <= penalty <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {penalty}")


@dataclass(frozen=True)
class TierConfig:
    """Configuration for tier thresholds."""

    s_tier_percentile: float
    a_tier_percentile: float
    b_tier_percentile: float
    c_tier_percentile: float

    def __post_init__(self) -> None:
        """Validate tier thresholds are monotonic."""
        thresholds = [
            self.s_tier_percentile,
            self.a_tier_percentile,
            self.b_tier_percentile,
            self.c_tier_percentile,
        ]

        for i in range(len(thresholds) - 1):
            if thresholds[i] >= thresholds[i + 1]:
                raise ValueError("Tier thresholds must be strictly increasing")

        for i, threshold in enumerate(thresholds):
            if not (0 < threshold < 100):
                raise ValueError(f"Tier threshold {i} must be in (0, 100), got {threshold}")


@dataclass(frozen=True)
class YamlHeuristicsConfig:
    """Adapter: Load configuration from YAML file.

    This is an infrastructure detail. Core logic depends on HeuristicsConfig
    protocol, not this concrete implementation.
    """

    confidence: ConfidenceConfig
    aesop_scoring: AesopScoringConfig
    grind_scoring: GrindScoringConfig
    annotation_value_scoring: AnnotationValueScoringConfig
    subgoal_potential_scoring: SubgoalPotentialScoringConfig
    risk_scoring: RiskScoringConfig
    impact_scoring: ImpactScoringConfig
    success_likelihood_scoring: SuccessLikelihoodScoringConfig
    objectives: dict[str, ObjectiveConfig]
    automation_detection: AutomationDetectionConfig
    tiers: TierConfig
    version: str

    @classmethod
    def load(cls, path: Path | None = None) -> "YamlHeuristicsConfig":
        """Load configuration from YAML file with validation.

        Args:
            path: Path to YAML config file. If None, loads default config
                  from package (src/lean_proof_auto_mcp/heuristics.yaml)

        Returns:
            Validated configuration object

        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If config file doesn't exist
        """
        if path is None:
            # Load default config from package
            path = Path(__file__).parent.parent / "heuristics.yaml"

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Validate version
        version = data.get("version")
        if version != "1.0":
            raise ValueError(f"Unsupported configuration version: {version}. Expected version 1.0")

        # Build and validate configuration
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "YamlHeuristicsConfig":
        """Build configuration from dictionary with validation."""
        try:
            # Parse confidence config
            conf_data = data["confidence"]
            confidence = ConfidenceConfig(
                base_score=conf_data["base_score"],
                proof_structure_bonus=conf_data["bonuses"]["proof_structure"],
                tactic_detection_bonus=conf_data["bonuses"]["tactic_detection"],
                structural_tactics_bonus=conf_data["bonuses"]["structural_tactics"],
                term_mode_patterns_bonus=conf_data["bonuses"]["term_mode_patterns"],
                automation_tactics_bonus=conf_data["bonuses"]["automation_tactics"],
                indentation_consistency_bonus=conf_data["bonuses"]["indentation_consistency"],
                sorry_penalty=conf_data["penalties"]["sorry"],
                error_patterns_penalty=conf_data["penalties"]["error_patterns"],
                proof_length_min=conf_data["thresholds"]["proof_length_min"],
                proof_length_max=conf_data["thresholds"]["proof_length_max"],
                proof_length_max_bonus=conf_data["thresholds"]["proof_length_max_bonus"],
            )

            # Parse aesop scoring config
            aesop_data = data["aesop_scoring"]
            aesop_bonuses = [
                ConfidenceBonusTier(threshold=tier_data["threshold"], bonus=tier_data["bonus"])
                for tier_data in aesop_data["confidence_bonuses"].values()
            ]
            aesop_length_bonuses = [
                ProofLengthBonus(max_lines=bonus_data["max_lines"], bonus=bonus_data["bonus"])
                for bonus_data in aesop_data["proof_length_bonuses"]
            ]
            aesop_scoring = AesopScoringConfig(
                base_score=aesop_data["base_score"],
                confidence_bonuses=aesop_bonuses,
                structural_tactics_bonus_per_tactic=aesop_data["structural_tactics"][
                    "bonus_per_tactic"
                ],
                structural_tactics_max_bonus=aesop_data["structural_tactics"]["max_bonus"],
                term_mode_bonus_per_pattern=aesop_data["term_mode"]["bonus_per_pattern"],
                term_mode_max_bonus=aesop_data["term_mode"]["max_bonus"],
                proof_length_bonuses=aesop_length_bonuses,
                rewrite_heavy_threshold=aesop_data["penalties"]["rewrite_heavy"]["threshold"],
                rewrite_heavy_penalty=aesop_data["penalties"]["rewrite_heavy"]["penalty"],
                rewrite_moderate_threshold=aesop_data["penalties"]["rewrite_moderate"]["threshold"],
                rewrite_moderate_penalty=aesop_data["penalties"]["rewrite_moderate"]["penalty"],
                simp_heavy_threshold=aesop_data["penalties"]["simp_heavy"]["threshold"],
                simp_heavy_penalty=aesop_data["penalties"]["simp_heavy"]["penalty"],
                tactic_mode_bonus=aesop_data["bonuses"]["tactic_mode"],
            )

            # Parse grind scoring config
            grind_data = data["grind_scoring"]
            grind_bonuses = [
                ConfidenceBonusTier(threshold=tier_data["threshold"], bonus=tier_data["bonus"])
                for tier_data in grind_data["confidence_bonuses"].values()
            ]
            # Handle proof length bonuses - can have min_lines, max_lines, or both
            grind_length_bonus_data = grind_data["proof_length_bonuses"][0]
            grind_scoring = GrindScoringConfig(
                base_score=grind_data["base_score"],
                confidence_bonuses=grind_bonuses,
                rewrite_bonus_per_count=grind_data["rewrite"]["bonus_per_count"],
                rewrite_max_bonus=grind_data["rewrite"]["max_bonus"],
                simp_bonus_per_count=grind_data["simp"]["bonus_per_count"],
                simp_max_bonus=grind_data["simp"]["max_bonus"],
                algebraic_terms_bonus_per_pattern=grind_data["algebraic_terms"][
                    "bonus_per_pattern"
                ],
                algebraic_terms_max_bonus=grind_data["algebraic_terms"]["max_bonus"],
                proof_length_min_for_bonus=grind_length_bonus_data.get("min_lines", 5),
                proof_length_max_for_bonus=grind_length_bonus_data.get("max_lines", 30),
                proof_length_bonus=grind_length_bonus_data["bonus"],
                short_proof_bonus=grind_data["proof_length_bonuses"][1]["bonus"]
                if len(grind_data["proof_length_bonuses"]) > 1
                else 0.08,
                induction_penalty=grind_data["penalties"]["induction"],
                cases_penalty=grind_data["penalties"]["cases"],
                algebraic_tactics_bonus_per_tactic=grind_data["algebraic_tactics"][
                    "bonus_per_tactic"
                ],
                algebraic_tactics_max_bonus=grind_data["algebraic_tactics"]["max_bonus"],
                pure_term_proof_bonus=grind_data["bonuses"]["pure_term_proof"],
            )

            # Parse annotation value scoring config
            annot_data = data["annotation_value_scoring"]
            annot_bonuses = [
                ConfidenceBonusTier(threshold=tier_data["threshold"], bonus=tier_data["bonus"])
                for tier_data in annot_data["confidence_bonuses"].values()
            ]
            annot_length_thresholds = [
                (bonus_data["min_lines"], bonus_data["bonus"])
                for bonus_data in annot_data["proof_length_bonuses"]
            ]
            annot_diversity_thresholds = [
                (bonus_data["min_diversity"], bonus_data["bonus"])
                for bonus_data in annot_data["tactic_diversity_bonuses"]
            ]
            annot_rewrite_thresholds = [
                (bonus_data["min_count"], bonus_data["bonus"])
                for bonus_data in annot_data["rewrite_bonuses"]
            ]
            annot_simp_thresholds = [
                (bonus_data["min_count"], bonus_data["bonus"])
                for bonus_data in annot_data["simp_bonuses"]
            ]
            annotation_value_scoring = AnnotationValueScoringConfig(
                base_score=annot_data["base_score"],
                confidence_bonuses=annot_bonuses,
                low_confidence_penalty=annot_data["penalties"]["low_confidence"],
                proof_length_thresholds=annot_length_thresholds,
                local_lemmas_bonus_per_count=annot_data["local_lemmas"]["bonus_per_count"],
                local_lemmas_max_bonus=annot_data["local_lemmas"]["max_bonus"],
                tactic_diversity_thresholds=annot_diversity_thresholds,
                rewrite_count_thresholds=annot_rewrite_thresholds,
                simp_count_thresholds=annot_simp_thresholds,
                term_application_bonus=annot_data["bonuses"]["term_application"],
                structural_proof_bonus=annot_data["bonuses"]["structural_proof"],
            )

            # Parse subgoal potential scoring config
            subgoal_data = data["subgoal_potential_scoring"]
            subgoal_multipliers = [
                ConfidenceMultiplier(
                    threshold=mult_data["threshold"], multiplier=mult_data["multiplier"]
                )
                for mult_data in subgoal_data["confidence_multipliers"].values()
            ]
            subgoal_potential_scoring = SubgoalPotentialScoringConfig(
                confidence_multipliers=subgoal_multipliers,
                induction_or_cases_bonus=subgoal_data["bonuses"]["induction_or_cases"],
                term_application_bonus=subgoal_data["bonuses"]["term_application"],
                algebraic_term_bonus=subgoal_data["bonuses"]["algebraic_term"],
                structure_cases_bonus_per_case=subgoal_data["structure_cases"]["bonus_per_case"],
                structure_cases_max_bonus=subgoal_data["structure_cases"]["max_bonus"],
                rewrite_blocks_bonus_per_block=subgoal_data["rewrite_blocks"]["bonus_per_block"],
                rewrite_blocks_max_bonus=subgoal_data["rewrite_blocks"]["max_bonus"],
            )

            # Parse risk scoring config
            risk_data = data["risk_scoring"]
            risk_scoring = RiskScoringConfig(
                global_change_rewrite_heavy_threshold=risk_data["global_change_risk"][
                    "rewrite_heavy"
                ]["threshold"],
                global_change_rewrite_heavy_risk=risk_data["global_change_risk"]["rewrite_heavy"][
                    "risk"
                ],
                global_change_simp_heavy_threshold=risk_data["global_change_risk"]["simp_heavy"][
                    "threshold"
                ],
                global_change_simp_heavy_risk=risk_data["global_change_risk"]["simp_heavy"]["risk"],
                global_change_simp_question_mark_risk=risk_data["global_change_risk"][
                    "simp_question_mark"
                ],
                simp_heavy_threshold=risk_data["simp_risk"]["heavy"]["threshold"],
                simp_heavy_risk=risk_data["simp_risk"]["heavy"]["risk"],
                simp_moderate_threshold=risk_data["simp_risk"]["moderate"]["threshold"],
                simp_moderate_risk=risk_data["simp_risk"]["moderate"]["risk"],
                local_lemma_heavy_threshold=risk_data["local_lemma_risk"]["heavy"]["threshold"],
                local_lemma_heavy_risk=risk_data["local_lemma_risk"]["heavy"]["risk"],
                local_lemma_moderate_threshold=risk_data["local_lemma_risk"]["moderate"][
                    "threshold"
                ],
                local_lemma_moderate_risk=risk_data["local_lemma_risk"]["moderate"]["risk"],
                low_confidence_very_low_threshold=risk_data["low_confidence_risk"]["very_low"][
                    "threshold"
                ],
                low_confidence_very_low_risk=risk_data["low_confidence_risk"]["very_low"]["risk"],
                low_confidence_low_threshold=risk_data["low_confidence_risk"]["low"]["threshold"],
                low_confidence_low_risk=risk_data["low_confidence_risk"]["low"]["risk"],
                component_weight_global_change=risk_data["component_weights"]["global_change"],
                component_weight_simp=risk_data["component_weights"]["simp"],
                component_weight_local_lemma=risk_data["component_weights"]["local_lemma"],
                component_weight_confidence=risk_data["component_weights"]["confidence"],
            )

            # Parse impact scoring config
            impact_data = data["impact_scoring"]
            impact_length_scores = []
            for score_data in impact_data["proof_length_scores"]:
                impact_length_scores.append(
                    ProofLengthScore(
                        max_lines=score_data.get("max_lines"),
                        min_lines=score_data.get("min_lines"),
                        score=score_data["score"],
                    )
                )
            impact_scoring = ImpactScoringConfig(
                proof_length_scores=impact_length_scores,
                reusability_score_per_local_lemma=impact_data["reusability"][
                    "score_per_local_lemma"
                ],
                reusability_max_score=impact_data["reusability"]["max_score"],
                component_weight_proof_length=impact_data["component_weights"]["proof_length"],
                component_weight_annotation_value=impact_data["component_weights"][
                    "annotation_value"
                ],
                component_weight_reusability=impact_data["component_weights"]["reusability"],
            )

            # Parse success likelihood scoring config
            success_data = data["success_likelihood_scoring"]
            success_likelihood_scoring = SuccessLikelihoodScoringConfig(
                complexity_induction_or_cases_penalty=success_data["complexity_penalties"][
                    "induction_or_cases"
                ],
                complexity_long_proof_threshold=success_data["complexity_penalties"]["long_proof"][
                    "threshold"
                ],
                complexity_long_proof_penalty=success_data["complexity_penalties"]["long_proof"][
                    "penalty"
                ],
                complexity_many_local_lemmas_threshold=success_data["complexity_penalties"][
                    "many_local_lemmas"
                ]["threshold"],
                complexity_many_local_lemmas_penalty=success_data["complexity_penalties"][
                    "many_local_lemmas"
                ]["penalty"],
                complexity_max_penalty=success_data["complexity_penalties"]["max_penalty"],
                component_weight_max_potential=success_data["component_weights"]["max_potential"],
                component_weight_confidence=success_data["component_weights"]["confidence"],
                component_weight_complexity_penalty=success_data["component_weights"][
                    "complexity_penalty"
                ],
            )

            # Parse objectives
            objectives_data = data["objectives"]
            objectives = {}
            for obj_name, obj_data in objectives_data.items():
                objectives[obj_name] = ObjectiveConfig(
                    description=obj_data["description"],
                    use_case=obj_data["use_case"],
                    weight_success_likelihood=obj_data["weights"]["success_likelihood"],
                    weight_impact=obj_data["weights"]["impact"],
                    weight_annotation_value=obj_data["weights"]["annotation_value"],
                    weight_subgoal_potential=obj_data["weights"]["subgoal_potential"],
                    weight_risk=obj_data["weights"]["risk"],
                )

            # Parse automation detection config
            auto_data = data["already_automated"]
            automation_detection = AutomationDetectionConfig(
                tactic_penalty=auto_data["penalties"]["tactic_usage"],
                attribute_penalty=auto_data["penalties"]["attribute"],
                trivial_penalty=auto_data["penalties"]["trivial_proof"],
                tactic_patterns=auto_data["tactic_patterns"],
                attribute_patterns=auto_data["attribute_patterns"],
                trivial_patterns=auto_data["trivial_patterns"],
            )

            # Parse tier config
            tier_data = data["tiers"]
            tiers = TierConfig(
                s_tier_percentile=tier_data["s_tier_percentile"],
                a_tier_percentile=tier_data["a_tier_percentile"],
                b_tier_percentile=tier_data["b_tier_percentile"],
                c_tier_percentile=tier_data["c_tier_percentile"],
            )

            return cls(
                confidence=confidence,
                aesop_scoring=aesop_scoring,
                grind_scoring=grind_scoring,
                annotation_value_scoring=annotation_value_scoring,
                subgoal_potential_scoring=subgoal_potential_scoring,
                risk_scoring=risk_scoring,
                impact_scoring=impact_scoring,
                success_likelihood_scoring=success_likelihood_scoring,
                objectives=objectives,
                automation_detection=automation_detection,
                tiers=tiers,
                version=data["version"],
            )

        except KeyError as e:
            raise ValueError(f"Missing required configuration field: {e}") from e
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid configuration value: {e}") from e


def load_default_config() -> HeuristicsConfig:
    """Load default configuration from package.

    Checks environment variable LEAN_PROOF_AUTO_MCP_CONFIG first,
    then falls back to package default.

    This is the composition root for configuration.

    Returns:
        Validated configuration object
    """
    # Check environment variable first
    env_config_path = os.getenv("LEAN_PROOF_AUTO_MCP_CONFIG")
    if env_config_path:
        return YamlHeuristicsConfig.load(Path(env_config_path))

    # Fall back to package default
    return YamlHeuristicsConfig.load()


def load_config(path: Path) -> HeuristicsConfig:
    """Load configuration from custom path.

    Args:
        path: Path to custom YAML configuration file

    Returns:
        Validated configuration object
    """
    return YamlHeuristicsConfig.load(path)
