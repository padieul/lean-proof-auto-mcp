"""Automation potential scoring for Lean theorems.

This module provides data structures and functions for computing
automation scores that estimate how well different automation tools
(like aesop and grind) might perform on theorem proofs.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .features import TheoremFeatures
from .segmenter import ProofStructure

if TYPE_CHECKING:
    from .config import (
        AesopScoringConfig,
        AnnotationValueScoringConfig,
        GrindScoringConfig,
        HeuristicsConfig,
        SubgoalPotentialScoringConfig,
    )


@dataclass(frozen=True)
class AutomationProfile:
    """Automation potential scores for a theorem.

    Attributes:
        whole_goal_potential: Scores for automating the entire goal
        subgoal_potential: Scores for automating individual subgoals
        annotation_value: ROI estimate for adding automation annotations
        notes: Human-readable explanations of the scoring
    """

    whole_goal_potential: dict[str, float]  # {"aesop": 0.8, "grind": 0.3}
    subgoal_potential: dict[str, float]
    annotation_value: float
    notes: list[str]

    def __post_init__(self) -> None:
        """Validate automation profile invariants."""
        # Validate score ranges
        for tool, score in self.whole_goal_potential.items():
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"whole_goal_potential[{tool}] must be in [0.0, 1.0], got {score}")

        for tool, score in self.subgoal_potential.items():
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"subgoal_potential[{tool}] must be in [0.0, 1.0], got {score}")

        if not (0.0 <= self.annotation_value <= 1.0):
            raise ValueError(f"annotation_value must be in [0.0, 1.0], got {self.annotation_value}")

        # Validate notes
        if len(self.notes) > 10:
            raise ValueError(f"Too many notes: {len(self.notes)}. Maximum is 10.")

        for note in self.notes:
            if len(note) > 200:
                raise ValueError(f"Note too long: {len(note)} chars. Maximum is 200.")


def compute_profile(
    features: TheoremFeatures,
    structure: ProofStructure | None = None,
    config: "HeuristicsConfig | None" = None,
) -> AutomationProfile:
    """Compute automation scores from features.

    Uses heuristics to estimate how well different automation tools
    would perform on the given theorem based on its features and structure.

    Args:
        features: Extracted theorem features
        structure: Optional proof structure analysis
        config: Heuristics configuration. If None, loads default config.

    Returns:
        AutomationProfile with computed scores and explanatory notes
    """
    # Load default config if not provided
    if config is None:
        from .config import load_default_config

        config = load_default_config()

    # Compute individual scores
    aesop_whole = score_aesop_potential(features, config.aesop_scoring)
    grind_whole = score_grind_potential(features, config.grind_scoring)

    # Compute subgoal scores (enhanced if we have structure info)
    aesop_subgoal = _score_aesop_subgoal_potential(
        features, structure, config.subgoal_potential_scoring
    )
    grind_subgoal = _score_grind_subgoal_potential(
        features, structure, config.subgoal_potential_scoring
    )

    # Compute annotation value
    annotation_value = score_annotation_value(features, config.annotation_value_scoring)

    # Generate explanatory notes
    notes = _generate_notes(
        features,
        structure,
        {
            "aesop_whole": aesop_whole,
            "grind_whole": grind_whole,
            "aesop_subgoal": aesop_subgoal,
            "grind_subgoal": grind_subgoal,
            "annotation_value": annotation_value,
        },
    )

    return AutomationProfile(
        whole_goal_potential={"aesop": round(aesop_whole, 2), "grind": round(grind_whole, 2)},
        subgoal_potential={"aesop": round(aesop_subgoal, 2), "grind": round(grind_subgoal, 2)},
        annotation_value=round(annotation_value, 2),
        notes=notes,
    )


def score_aesop_potential(features: TheoremFeatures, config: "AesopScoringConfig") -> float:
    """Heuristic: aesop works well on structural proofs.

    Aesop is a proof search tactic that works well on goals that can be
    solved by applying constructors, destructors, and simple reasoning.
    It tends to work better on shorter, more structural proofs.
    Enhanced to better handle term-mode proofs and confidence signals.

    Args:
        features: Theorem features to analyze
        config: Aesop scoring configuration

    Returns:
        Score between 0.0 and 1.0 indicating aesop potential
    """
    if features.proof_lines == 0:
        return 0.0

    score = config.base_score  # Use configured base score

    # Enhanced confidence-based scoring
    for tier in config.confidence_bonuses:
        if features.confidence >= tier.threshold:
            score += tier.bonus
            break  # Use the first matching tier (highest threshold)

    # If no tier matched but confidence > 0, give minimal bonus
    if features.confidence > 0.0 and not any(
        features.confidence >= tier.threshold for tier in config.confidence_bonuses
    ):
        score += 0.05  # Minimal bonus for any confidence

    # Aesop likes structural tactics
    structural_tactics = {
        "intro",
        "intros",
        "constructor",
        "left",
        "right",
        "split",
        "ext",
        "funext",
        "use",
        "exists",
        "apply",
    }
    structural_count = len(features.tactic_kinds & structural_tactics)
    if structural_count > 0:
        score += min(
            config.structural_tactics_max_bonus,
            structural_count * config.structural_tactics_bonus_per_tactic,
        )

    # Enhanced term-mode proof support
    term_mode_patterns = {
        "term_application",
        "rfl",
        "term_proof",
        "constructor_term",
        "map_application",
        "ring_hom_application",
        "inference_placeholder",
    }
    term_mode_count = len(features.tactic_kinds & term_mode_patterns)
    if term_mode_count > 0:
        score += min(
            config.term_mode_max_bonus, term_mode_count * config.term_mode_bonus_per_pattern
        )

    # Aesop prefers shorter proofs
    for length_bonus in config.proof_length_bonuses:
        if features.proof_lines <= length_bonus.max_lines:
            score += length_bonus.bonus
            break  # Use the first matching bonus

    # Aesop doesn't like heavy rewriting
    if features.rewrite_count > config.rewrite_heavy_threshold:
        score += config.rewrite_heavy_penalty  # Penalty is negative
    elif features.rewrite_count > config.rewrite_moderate_threshold:
        score += config.rewrite_moderate_penalty  # Penalty is negative

    # Aesop doesn't like heavy simp usage
    if features.simp_count > config.simp_heavy_threshold:
        score += config.simp_heavy_penalty  # Penalty is negative

    # Enhanced pattern recognition
    if "tactic_mode" in features.tactic_kinds:
        score += config.tactic_mode_bonus

    return float(max(0.0, min(1.0, score)))


def score_grind_potential(features: TheoremFeatures, config: "GrindScoringConfig") -> float:
    """Heuristic: grind works well on rewrite-heavy proofs.

    Grind is an automation tactic that excels at equational reasoning
    and simplification. It works well on proofs with lots of rewrites
    and algebraic manipulation.
    Enhanced to better handle term-mode proofs and confidence signals.

    Args:
        features: Theorem features to analyze
        config: Grind scoring configuration

    Returns:
        Score between 0.0 and 1.0 indicating grind potential
    """
    if features.proof_lines == 0:
        return 0.0

    score = config.base_score  # Use configured base score

    # Enhanced confidence-based scoring
    for tier in config.confidence_bonuses:
        if features.confidence >= tier.threshold:
            score += tier.bonus
            break  # Use the first matching tier (highest threshold)

    # If no tier matched but confidence > 0, give minimal bonus
    if features.confidence > 0.0 and not any(
        features.confidence >= tier.threshold for tier in config.confidence_bonuses
    ):
        score += 0.05  # Minimal bonus for any confidence

    # Grind likes rewrite-heavy proofs
    if features.rewrite_count > 0:
        score += min(
            config.rewrite_max_bonus, features.rewrite_count * config.rewrite_bonus_per_count
        )

    # Grind likes simp usage
    if features.simp_count > 0:
        score += min(config.simp_max_bonus, features.simp_count * config.simp_bonus_per_count)

    # Enhanced term-mode proof support for algebraic reasoning
    algebraic_term_patterns = {"map_application", "ring_hom_application", "term_application"}
    algebraic_term_count = len(features.tactic_kinds & algebraic_term_patterns)
    if algebraic_term_count > 0:
        score += min(
            config.algebraic_terms_max_bonus,
            algebraic_term_count * config.algebraic_terms_bonus_per_pattern,
        )

    # Grind works well with medium-length proofs
    if (
        config.proof_length_min_for_bonus
        <= features.proof_lines
        <= config.proof_length_max_for_bonus
    ):
        score += config.proof_length_bonus
    elif features.proof_lines <= config.proof_length_min_for_bonus:
        score += config.short_proof_bonus  # Still good, but less opportunity

    # Grind doesn't like induction/cases (structural reasoning)
    if features.has_induction:
        score += config.induction_penalty  # Penalty is negative
    if features.has_cases:
        score += config.cases_penalty  # Penalty is negative

    # Grind likes algebraic tactics
    algebraic_tactics = {"ring_nf", "field_simp", "norm_num", "linarith", "omega"}
    algebraic_count = len(features.tactic_kinds & algebraic_tactics)
    if algebraic_count > 0:
        score += min(
            config.algebraic_tactics_max_bonus,
            algebraic_count * config.algebraic_tactics_bonus_per_tactic,
        )

    # Enhanced pattern recognition
    if "term_proof" in features.tactic_kinds and features.rewrite_count == 0:
        score += config.pure_term_proof_bonus

    return float(max(0.0, min(1.0, score)))


def score_annotation_value(
    features: TheoremFeatures, config: "AnnotationValueScoringConfig"
) -> float:
    """ROI estimate: long proof + patterns + local lemmas.

    Estimates the return on investment for adding automation annotations
    to this theorem. Higher scores indicate theorems where automation
    annotations would provide more value.
    Enhanced to better consider confidence and proof quality.

    Args:
        features: Theorem features to analyze
        config: Annotation value scoring configuration

    Returns:
        Score between 0.0 and 1.0 indicating annotation value
    """
    if features.proof_lines == 0:
        return 0.0

    score = config.base_score  # Use configured base score

    # Enhanced confidence-based scoring - confidence is crucial for annotation value
    for tier in config.confidence_bonuses:
        if features.confidence >= tier.threshold:
            score += tier.bonus
            break  # Use the first matching tier (highest threshold)

    # Low confidence reduces annotation value significantly
    if features.confidence == 0.0:
        score += config.low_confidence_penalty  # Penalty is negative

    # Longer proofs have more potential for automation
    for min_lines, bonus in config.proof_length_thresholds:
        if features.proof_lines > min_lines:
            score += bonus
            break  # Use the first matching threshold

    # Local lemmas indicate complex proofs that could benefit from automation
    if features.local_lemmas_count > 0:
        score += min(
            config.local_lemmas_max_bonus,
            features.local_lemmas_count * config.local_lemmas_bonus_per_count,
        )

    # Repeated patterns (high tactic diversity) suggest automation opportunities
    tactic_diversity = len(features.tactic_kinds)
    for min_diversity, bonus in config.tactic_diversity_thresholds:
        if tactic_diversity > min_diversity:
            score += bonus
            break  # Use the first matching threshold

    # Rewrite-heavy proofs often benefit from automation
    for min_count, bonus in config.rewrite_count_thresholds:
        if features.rewrite_count > min_count:
            score += bonus
            break  # Use the first matching threshold

    # Simp-heavy proofs might benefit from better simp sets
    for min_count, bonus in config.simp_count_thresholds:
        if features.simp_count > min_count:
            score += bonus
            break  # Use the first matching threshold

    # Enhanced pattern-based scoring
    if "term_application" in features.tactic_kinds:
        score += config.term_application_bonus

    if features.has_induction or features.has_cases:
        score += config.structural_proof_bonus

    return float(max(0.0, min(1.0, score)))


def _score_aesop_subgoal_potential(
    features: TheoremFeatures,
    structure: ProofStructure | None,
    config: "SubgoalPotentialScoringConfig",
) -> float:
    """Score aesop potential for individual subgoals.

    Aesop can be useful for automating individual subgoals even when
    it can't solve the whole goal, especially in case analysis.
    Enhanced to better use confidence information.

    Args:
        features: Theorem features to analyze
        structure: Optional proof structure analysis
        config: Subgoal potential scoring configuration

    Returns:
        Score between 0.0 and 1.0 indicating aesop subgoal potential
    """
    # Import here to avoid circular dependency
    from .config import load_default_config

    full_config = load_default_config()

    # Start with a confidence-adjusted base score
    base_score = score_aesop_potential(features, full_config.aesop_scoring)

    # Apply confidence multiplier
    for multiplier in config.confidence_multipliers:
        if features.confidence >= multiplier.threshold:
            base_score *= multiplier.multiplier
            break  # Use the first matching multiplier

    # Boost if we have induction/cases (can automate branches)
    if features.has_induction or features.has_cases:
        base_score += config.induction_or_cases_bonus

    # Boost if we have structure info showing cases
    if structure and structure.cases:
        base_score += min(
            config.structure_cases_max_bonus,
            len(structure.cases) * config.structure_cases_bonus_per_case,
        )

    # Enhanced term-mode support for subgoals
    if "term_application" in features.tactic_kinds:
        base_score += config.term_application_bonus

    return max(0.0, min(1.0, base_score))


def _score_grind_subgoal_potential(
    features: TheoremFeatures,
    structure: ProofStructure | None,
    config: "SubgoalPotentialScoringConfig",
) -> float:
    """Score grind potential for individual subgoals.

    Grind can be useful for automating rewrite-heavy subgoals even
    when the overall proof structure doesn't suit it.
    Enhanced to better use confidence information.

    Args:
        features: Theorem features to analyze
        structure: Optional proof structure analysis
        config: Subgoal potential scoring configuration

    Returns:
        Score between 0.0 and 1.0 indicating grind subgoal potential
    """
    # Import here to avoid circular dependency
    from .config import load_default_config

    full_config = load_default_config()

    # Start with a confidence-adjusted base score
    base_score = score_grind_potential(features, full_config.grind_scoring)

    # Apply confidence multiplier (using slightly higher multipliers for grind)
    for multiplier in config.confidence_multipliers:
        if features.confidence >= multiplier.threshold:
            # Grind gets slightly better multipliers
            adjusted_multiplier = min(1.0, multiplier.multiplier + 0.05)
            base_score *= adjusted_multiplier
            break  # Use the first matching multiplier

    # Boost if we have rewrite/simp blocks
    if structure and structure.blocks:
        rewrite_blocks = [b for b in structure.blocks if b.kind == "rewrite_simp"]
        if rewrite_blocks:
            base_score += min(
                config.rewrite_blocks_max_bonus,
                len(rewrite_blocks) * config.rewrite_blocks_bonus_per_block,
            )

    # Enhanced algebraic term-mode support for subgoals
    if (
        "map_application" in features.tactic_kinds
        or "ring_hom_application" in features.tactic_kinds
    ):
        base_score += config.algebraic_term_bonus

    return max(0.0, min(1.0, base_score))


def _generate_notes(
    features: TheoremFeatures, structure: ProofStructure | None, scores: dict[str, float]
) -> list[str]:
    """Generate explanatory notes for the scoring.

    Creates human-readable explanations of why certain scores were assigned,
    helping users understand the automation recommendations.
    """
    notes = []

    # CRITICAL: Add numeric confidence for downstream tools
    # This enables rank_targets to extract and use confidence values
    if features.confidence > 0.0:
        notes.append(f"confidence: {features.confidence:.2f}")

    # Enhanced note about proof detection and confidence
    if features.proof_lines == 0:
        if features.confidence == 0.0:
            notes.append("no proof found")
        else:
            notes.append("proof detection uncertain")
    elif features.proof_lines > 20:
        notes.append("long proof")
    elif features.proof_lines <= 3:
        notes.append("short proof")

    # Note about proof quality based on enhanced confidence signals
    if features.confidence >= 0.8:
        notes.append("high confidence proof")
    elif features.confidence >= 0.6:
        notes.append("good proof structure")
    elif features.confidence >= 0.4:
        notes.append("moderate confidence")
    elif features.confidence > 0.0:
        notes.append("uncertain proof boundaries")

    # Enhanced notes about proof patterns
    if "term_application" in features.tactic_kinds or "term_proof" in features.tactic_kinds:
        notes.append("term-mode proof")
    elif "tactic_mode" in features.tactic_kinds:
        notes.append("tactic-mode proof")

    # Note about structural patterns
    if features.has_induction:
        notes.append("uses induction")
    if features.has_cases:
        notes.append("uses cases")

    # Note about rewrite patterns
    if features.rewrite_count > 5:
        notes.append("rewrite-heavy")
    elif features.rewrite_count > 0:
        notes.append("uses rewrites")

    # Note about simp usage
    if features.simp_count > 3:
        notes.append("simp-heavy")

    # Note about local lemmas
    if features.local_lemmas_count > 2:
        notes.append("many local lemmas")
    elif features.local_lemmas_count > 0:
        notes.append("has local lemmas")

    # Enhanced notes about proof complexity
    tactic_diversity = len(features.tactic_kinds)
    if tactic_diversity > 8:
        notes.append("highly diverse tactics")
    elif tactic_diversity > 5:
        notes.append("diverse tactics")
    elif tactic_diversity == 0 and features.proof_lines > 0:
        notes.append("minimal tactic detection")

    # Note about structure if available
    if structure:
        if len(structure.skeleton) > 3:
            notes.append("complex structure")
        if structure.cases:
            notes.append(f"{len(structure.cases)} case branches")

        # Note about block types
        if structure.blocks:
            block_kinds = {b.kind for b in structure.blocks}
            if "rewrite_simp" in block_kinds:
                notes.append("rewrite-heavy sections")
            if "closing" in block_kinds:
                notes.append("has closing tactics")

    # Enhanced notes about automation potential
    if scores["aesop_whole"] > 0.7:
        notes.append("good aesop candidate")
    elif scores["aesop_whole"] > 0.5:
        notes.append("moderate aesop potential")

    if scores["grind_whole"] > 0.7:
        notes.append("good grind candidate")
    elif scores["grind_whole"] > 0.5:
        notes.append("moderate grind potential")

    # Note about annotation value
    if scores["annotation_value"] > 0.8:
        notes.append("high annotation value")
    elif scores["annotation_value"] > 0.6:
        notes.append("good annotation candidate")

    # Limit to 10 notes and 200 chars each
    notes = notes[:10]
    notes = [note[:200] for note in notes]

    return notes
