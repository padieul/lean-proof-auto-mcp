"""Automation potential scoring for Lean theorems.

This module provides data structures and functions for computing
automation scores that estimate how well different automation tools
(like aesop and grind) might perform on theorem proofs.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

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
    whole_goal_potential: Dict[str, float]  # {"aesop": 0.8, "grind": 0.3}
    subgoal_potential: Dict[str, float]
    annotation_value: float
    notes: List[str]
    
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
    structure: Optional[ProofStructure] = None
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
    notes = _generate_notes(features, structure, {
        'aesop_whole': aesop_whole,
        'grind_whole': grind_whole,
        'aesop_subgoal': aesop_subgoal,
        'grind_subgoal': grind_subgoal,
        'annotation_value': annotation_value
    })
    
    return AutomationProfile(
        whole_goal_potential={
            "aesop": round(aesop_whole, 2),
            "grind": round(grind_whole, 2)
        },
        subgoal_potential={
            "aesop": round(aesop_subgoal, 2),
            "grind": round(grind_subgoal, 2)
        },
        annotation_value=round(annotation_value, 2),
        notes=notes
    )


def score_aesop_potential(features: TheoremFeatures) -> float:
    """Heuristic: aesop works well on structural proofs.
    
    Aesop is a proof search tactic that works well on goals that can be
    solved by applying constructors, destructors, and simple reasoning.
    It tends to work better on shorter, more structural proofs.
    
    Args:
        features: Theorem features to analyze
        
    Returns:
        Score between 0.0 and 1.0 indicating aesop potential
    """
    if features.proof_lines == 0:
        return 0.0
    
    score = 0.3  # Base score
    
    # Aesop likes structural tactics
    structural_tactics = {
        'intro', 'intros', 'constructor', 'left', 'right', 'split',
        'ext', 'funext', 'use', 'exists', 'apply'
    }
    structural_count = len(features.tactic_kinds & structural_tactics)
    if structural_count > 0:
        score += min(0.4, structural_count * 0.1)
    
    # Aesop prefers shorter proofs
    if features.proof_lines <= 5:
        score += 0.3
    elif features.proof_lines <= 10:
        score += 0.2
    elif features.proof_lines <= 20:
        score += 0.1
    # No bonus for longer proofs
    
    # Aesop doesn't like heavy rewriting
    if features.rewrite_count > 5:
        score -= 0.2
    elif features.rewrite_count > 2:
        score -= 0.1
    
    # Aesop doesn't like heavy simp usage
    if features.simp_count > 3:
        score -= 0.15
    
    # Boost for high confidence (well-structured proof)
    if features.confidence > 0.8:
        score += 0.1
    
    return max(0.0, min(1.0, score))


def score_grind_potential(features: TheoremFeatures) -> float:
    """Heuristic: grind works well on rewrite-heavy proofs.
    
    Grind is an automation tactic that excels at equational reasoning
    and simplification. It works well on proofs with lots of rewrites
    and algebraic manipulation.
    
    Args:
        features: Theorem features to analyze
        
    Returns:
        Score between 0.0 and 1.0 indicating grind potential
    """
    if features.proof_lines == 0:
        return 0.0
    
    score = 0.2  # Base score
    
    # Grind likes rewrite-heavy proofs
    if features.rewrite_count > 0:
        score += min(0.4, features.rewrite_count * 0.08)
    
    # Grind likes simp usage
    if features.simp_count > 0:
        score += min(0.3, features.simp_count * 0.1)
    
    # Grind works well with medium-length proofs
    if 5 <= features.proof_lines <= 30:
        score += 0.2
    elif features.proof_lines <= 5:
        score += 0.1  # Still good, but less opportunity
    
    # Grind doesn't like induction/cases (structural reasoning)
    if features.has_induction:
        score -= 0.2
    if features.has_cases:
        score -= 0.15
    
    # Grind likes algebraic tactics
    algebraic_tactics = {
        'ring_nf', 'field_simp', 'norm_num', 'linarith', 'omega'
    }
    algebraic_count = len(features.tactic_kinds & algebraic_tactics)
    if algebraic_count > 0:
        score += min(0.2, algebraic_count * 0.1)
    
    # Boost for high confidence
    if features.confidence > 0.8:
        score += 0.1
    
    return max(0.0, min(1.0, score))


def score_annotation_value(features: TheoremFeatures) -> float:
    """ROI estimate: long proof + patterns + local lemmas.
    
    Estimates the return on investment for adding automation annotations
    to this theorem. Higher scores indicate theorems where automation
    annotations would provide more value.
    
    Args:
        features: Theorem features to analyze
        
    Returns:
        Score between 0.0 and 1.0 indicating annotation value
    """
    if features.proof_lines == 0:
        return 0.0
    
    score = 0.1  # Base score
    
    # Longer proofs have more potential for automation
    if features.proof_lines > 20:
        score += 0.4
    elif features.proof_lines > 10:
        score += 0.3
    elif features.proof_lines > 5:
        score += 0.2
    
    # Local lemmas indicate complex proofs that could benefit from automation
    if features.local_lemmas_count > 0:
        score += min(0.3, features.local_lemmas_count * 0.1)
    
    # Repeated patterns (high tactic diversity) suggest automation opportunities
    tactic_diversity = len(features.tactic_kinds)
    if tactic_diversity > 5:
        score += 0.2
    elif tactic_diversity > 3:
        score += 0.1
    
    # Rewrite-heavy proofs often benefit from automation
    if features.rewrite_count > 3:
        score += 0.15
    
    # Simp-heavy proofs might benefit from better simp sets
    if features.simp_count > 2:
        score += 0.1
    
    # High confidence proofs are better candidates for automation
    if features.confidence > 0.8:
        score += 0.1
    elif features.confidence < 0.5:
        score -= 0.1  # Low confidence might indicate parsing issues
    
    return max(0.0, min(1.0, score))


def _score_aesop_subgoal_potential(
    features: TheoremFeatures,
    structure: Optional[ProofStructure]
) -> float:
    """Score aesop potential for individual subgoals.
    
    Aesop can be useful for automating individual subgoals even when
    it can't solve the whole goal, especially in case analysis.
    """
    base_score = score_aesop_potential(features) * 0.7  # Start lower than whole goal
    
    # Boost if we have induction/cases (can automate branches)
    if features.has_induction or features.has_cases:
        base_score += 0.3
    
    # Boost if we have structure info showing cases
    if structure and structure.cases:
        base_score += min(0.2, len(structure.cases) * 0.05)
    
    return max(0.0, min(1.0, base_score))


def _score_grind_subgoal_potential(
    features: TheoremFeatures,
    structure: Optional[ProofStructure]
) -> float:
    """Score grind potential for individual subgoals.
    
    Grind can be useful for automating rewrite-heavy subgoals even
    when the overall proof structure doesn't suit it.
    """
    base_score = score_grind_potential(features) * 0.8  # Start close to whole goal
    
    # Boost if we have rewrite/simp blocks
    if structure and structure.blocks:
        rewrite_blocks = [b for b in structure.blocks if b.kind == "rewrite_simp"]
        if rewrite_blocks:
            base_score += min(0.2, len(rewrite_blocks) * 0.1)
    
    return max(0.0, min(1.0, base_score))


def _generate_notes(
    features: TheoremFeatures,
    structure: Optional[ProofStructure],
    scores: Dict[str, float]
) -> List[str]:
    """Generate explanatory notes for the scoring.
    
    Creates human-readable explanations of why certain scores were assigned,
    helping users understand the automation recommendations.
    """
    notes = []
    
    # Note about proof length
    if features.proof_lines == 0:
        notes.append("no proof found")
    elif features.proof_lines > 20:
        notes.append("long proof")
    elif features.proof_lines <= 3:
        notes.append("short proof")
    
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
    
    # Note about confidence
    if features.confidence < 0.5:
        notes.append("uncertain proof boundaries")
    
    # Note about high-scoring automation
    if scores['aesop_whole'] > 0.7:
        notes.append("good aesop candidate")
    if scores['grind_whole'] > 0.7:
        notes.append("good grind candidate")
    
    # Limit to 10 notes and 200 chars each
    notes = notes[:10]
    notes = [note[:200] for note in notes]
    
    return notes