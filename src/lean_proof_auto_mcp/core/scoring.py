"""Automation potential scoring for Lean theorems.

This module provides data structures and functions for computing
automation scores that estimate how well different automation tools
(like aesop and grind) might perform on theorem proofs.
"""

from dataclasses import dataclass

from .features import TheoremFeatures
from .segmenter import ProofStructure


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
    features: TheoremFeatures, structure: ProofStructure | None = None
) -> AutomationProfile:
    """Compute automation scores from features.

    Uses heuristics to estimate how well different automation tools
    would perform on the given theorem based on its features and structure.

    Args:
        features: Extracted theorem features
        structure: Optional proof structure analysis

    Returns:
        AutomationProfile with computed scores and explanatory notes
    """
    # Compute individual scores
    aesop_whole = score_aesop_potential(features)
    grind_whole = score_grind_potential(features)

    # Compute subgoal scores (enhanced if we have structure info)
    aesop_subgoal = _score_aesop_subgoal_potential(features, structure)
    grind_subgoal = _score_grind_subgoal_potential(features, structure)

    # Compute annotation value
    annotation_value = score_annotation_value(features)

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


def score_aesop_potential(features: TheoremFeatures) -> float:
    """Heuristic: aesop works well on structural proofs.

    Aesop is a proof search tactic that works well on goals that can be
    solved by applying constructors, destructors, and simple reasoning.
    It tends to work better on shorter, more structural proofs.
    Enhanced to better handle term-mode proofs and confidence signals.

    Args:
        features: Theorem features to analyze

    Returns:
        Score between 0.0 and 1.0 indicating aesop potential
    """
    if features.proof_lines == 0:
        return 0.0

    score = 0.2  # Lower base score, build up from evidence

    # Enhanced confidence-based scoring
    if features.confidence >= 0.8:
        score += 0.3  # High confidence gets significant boost
    elif features.confidence >= 0.6:
        score += 0.2  # Good confidence gets moderate boost
    elif features.confidence >= 0.4:
        score += 0.1  # Some confidence gets small boost
    elif features.confidence > 0.0:
        score += 0.05  # Any confidence is better than none
    else:
        return 0.0  # No confidence means no meaningful score

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
        score += min(0.3, structural_count * 0.08)

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
        score += min(0.25, term_mode_count * 0.1)  # Term-mode proofs can be good for aesop

    # Aesop prefers shorter proofs
    if features.proof_lines <= 5:
        score += 0.2
    elif features.proof_lines <= 10:
        score += 0.15
    elif features.proof_lines <= 20:
        score += 0.1
    # No bonus for longer proofs

    # Aesop doesn't like heavy rewriting
    if features.rewrite_count > 5:
        score -= 0.15
    elif features.rewrite_count > 2:
        score -= 0.08

    # Aesop doesn't like heavy simp usage
    if features.simp_count > 3:
        score -= 0.1

    # Enhanced pattern recognition
    if "tactic_mode" in features.tactic_kinds:
        score += 0.05  # Tactic mode is generally good for aesop

    return max(0.0, min(1.0, score))


def score_grind_potential(features: TheoremFeatures) -> float:
    """Heuristic: grind works well on rewrite-heavy proofs.

    Grind is an automation tactic that excels at equational reasoning
    and simplification. It works well on proofs with lots of rewrites
    and algebraic manipulation.
    Enhanced to better handle term-mode proofs and confidence signals.

    Args:
        features: Theorem features to analyze

    Returns:
        Score between 0.0 and 1.0 indicating grind potential
    """
    if features.proof_lines == 0:
        return 0.0

    score = 0.15  # Lower base score, build up from evidence

    # Enhanced confidence-based scoring
    if features.confidence >= 0.8:
        score += 0.25  # High confidence gets significant boost
    elif features.confidence >= 0.6:
        score += 0.18  # Good confidence gets moderate boost
    elif features.confidence >= 0.4:
        score += 0.1  # Some confidence gets small boost
    elif features.confidence > 0.0:
        score += 0.05  # Any confidence is better than none
    else:
        return 0.0  # No confidence means no meaningful score

    # Grind likes rewrite-heavy proofs
    if features.rewrite_count > 0:
        score += min(0.35, features.rewrite_count * 0.06)

    # Grind likes simp usage
    if features.simp_count > 0:
        score += min(0.25, features.simp_count * 0.08)

    # Enhanced term-mode proof support for algebraic reasoning
    algebraic_term_patterns = {"map_application", "ring_hom_application", "term_application"}
    algebraic_term_count = len(features.tactic_kinds & algebraic_term_patterns)
    if algebraic_term_count > 0:
        score += min(0.2, algebraic_term_count * 0.08)  # Algebraic term-mode is good for grind

    # Grind works well with medium-length proofs
    if 5 <= features.proof_lines <= 30:
        score += 0.15
    elif features.proof_lines <= 5:
        score += 0.08  # Still good, but less opportunity

    # Grind doesn't like induction/cases (structural reasoning)
    if features.has_induction:
        score -= 0.15
    if features.has_cases:
        score -= 0.1

    # Grind likes algebraic tactics
    algebraic_tactics = {"ring_nf", "field_simp", "norm_num", "linarith", "omega"}
    algebraic_count = len(features.tactic_kinds & algebraic_tactics)
    if algebraic_count > 0:
        score += min(0.2, algebraic_count * 0.08)

    # Enhanced pattern recognition
    if "term_proof" in features.tactic_kinds and features.rewrite_count == 0:
        score += 0.1  # Pure term proofs can be good for grind

    return max(0.0, min(1.0, score))


def score_annotation_value(features: TheoremFeatures) -> float:
    """ROI estimate: long proof + patterns + local lemmas.

    Estimates the return on investment for adding automation annotations
    to this theorem. Higher scores indicate theorems where automation
    annotations would provide more value.
    Enhanced to better consider confidence and proof quality.

    Args:
        features: Theorem features to analyze

    Returns:
        Score between 0.0 and 1.0 indicating annotation value
    """
    if features.proof_lines == 0:
        return 0.0

    score = 0.05  # Lower base score, build up from evidence

    # Enhanced confidence-based scoring - confidence is crucial for annotation value
    if features.confidence >= 0.8:
        score += 0.25  # High confidence proofs are great annotation candidates
    elif features.confidence >= 0.6:
        score += 0.18  # Good confidence proofs are good candidates
    elif features.confidence >= 0.4:
        score += 0.1  # Some confidence is still valuable
    elif features.confidence > 0.0:
        score += 0.05  # Any confidence is better than none
    else:
        score -= 0.1  # Low confidence reduces annotation value significantly

    # Longer proofs have more potential for automation
    if features.proof_lines > 20:
        score += 0.3
    elif features.proof_lines > 10:
        score += 0.2
    elif features.proof_lines > 5:
        score += 0.15
    elif features.proof_lines > 2:
        score += 0.1  # Even short proofs can have value if well-structured

    # Local lemmas indicate complex proofs that could benefit from automation
    if features.local_lemmas_count > 0:
        score += min(0.25, features.local_lemmas_count * 0.08)

    # Repeated patterns (high tactic diversity) suggest automation opportunities
    tactic_diversity = len(features.tactic_kinds)
    if tactic_diversity > 5:
        score += 0.15
    elif tactic_diversity > 3:
        score += 0.1
    elif tactic_diversity > 0:
        score += 0.05  # Any detected patterns are valuable

    # Rewrite-heavy proofs often benefit from automation
    if features.rewrite_count > 3:
        score += 0.12
    elif features.rewrite_count > 0:
        score += 0.08

    # Simp-heavy proofs might benefit from better simp sets
    if features.simp_count > 2:
        score += 0.08
    elif features.simp_count > 0:
        score += 0.05

    # Enhanced pattern-based scoring
    if "term_application" in features.tactic_kinds:
        score += 0.1  # Complex term applications often benefit from automation

    if features.has_induction or features.has_cases:
        score += 0.1  # Structural proofs with cases often benefit from automation

    return max(0.0, min(1.0, score))


def _score_aesop_subgoal_potential(
    features: TheoremFeatures, structure: ProofStructure | None
) -> float:
    """Score aesop potential for individual subgoals.

    Aesop can be useful for automating individual subgoals even when
    it can't solve the whole goal, especially in case analysis.
    Enhanced to better use confidence information.
    """
    # Start with a confidence-adjusted base score
    if features.confidence >= 0.8:
        base_score = score_aesop_potential(features) * 0.8  # High confidence gets better base
    elif features.confidence >= 0.6:
        base_score = score_aesop_potential(features) * 0.7  # Good confidence
    elif features.confidence >= 0.4:
        base_score = score_aesop_potential(features) * 0.6  # Some confidence
    elif features.confidence > 0.0:
        base_score = score_aesop_potential(features) * 0.5  # Low confidence
    else:
        base_score = 0.0  # No confidence means no subgoal potential

    # Boost if we have induction/cases (can automate branches)
    if features.has_induction or features.has_cases:
        base_score += 0.25

    # Boost if we have structure info showing cases
    if structure and structure.cases:
        base_score += min(0.2, len(structure.cases) * 0.04)

    # Enhanced term-mode support for subgoals
    if "term_application" in features.tactic_kinds:
        base_score += 0.1  # Term applications often create good subgoals for aesop

    return max(0.0, min(1.0, base_score))


def _score_grind_subgoal_potential(
    features: TheoremFeatures, structure: ProofStructure | None
) -> float:
    """Score grind potential for individual subgoals.

    Grind can be useful for automating rewrite-heavy subgoals even
    when the overall proof structure doesn't suit it.
    Enhanced to better use confidence information.
    """
    # Start with a confidence-adjusted base score
    if features.confidence >= 0.8:
        base_score = score_grind_potential(features) * 0.85  # High confidence gets better base
    elif features.confidence >= 0.6:
        base_score = score_grind_potential(features) * 0.8  # Good confidence
    elif features.confidence >= 0.4:
        base_score = score_grind_potential(features) * 0.7  # Some confidence
    elif features.confidence > 0.0:
        base_score = score_grind_potential(features) * 0.6  # Low confidence
    else:
        base_score = 0.0  # No confidence means no subgoal potential

    # Boost if we have rewrite/simp blocks
    if structure and structure.blocks:
        rewrite_blocks = [b for b in structure.blocks if b.kind == "rewrite_simp"]
        if rewrite_blocks:
            base_score += min(0.2, len(rewrite_blocks) * 0.08)

    # Enhanced algebraic term-mode support for subgoals
    if (
        "map_application" in features.tactic_kinds
        or "ring_hom_application" in features.tactic_kinds
    ):
        base_score += 0.12  # Algebraic term applications often create good subgoals for grind

    return max(0.0, min(1.0, base_score))


def _generate_notes(
    features: TheoremFeatures, structure: ProofStructure | None, scores: dict[str, float]
) -> list[str]:
    """Generate explanatory notes for the scoring.

    Creates human-readable explanations of why certain scores were assigned,
    helping users understand the automation recommendations.
    """
    notes = []

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
