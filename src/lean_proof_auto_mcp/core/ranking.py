"""Ranking logic for theorem automation targets.

This module provides data structures and functions for ranking theorem
declarations based on automation potential, following hexagonal architecture
principles with immutable data structures and explicit validation.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ComponentScores:
    """Component scores for ranking computation.

    All scores must be in the range [0.0, 1.0].

    Attributes:
        success_likelihood: Probability that automation will succeed
        impact: Value of automating this theorem (time saved, reusability)
        annotation_value: ROI estimate for adding automation annotations
        subgoal_potential: Value of automating individual subgoals
        risk: Heuristic penalty for likely global changes or side effects
    """

    success_likelihood: float
    impact: float
    annotation_value: float
    subgoal_potential: float
    risk: float

    def __post_init__(self) -> None:
        """Validate component score invariants."""
        scores = {
            "success_likelihood": self.success_likelihood,
            "impact": self.impact,
            "annotation_value": self.annotation_value,
            "subgoal_potential": self.subgoal_potential,
            "risk": self.risk,
        }

        for name, score in scores.items():
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {score}")


@dataclass(frozen=True)
class TheoremData:
    """Internal representation of theorem data for ranking.

    Attributes:
        theorem_id: Unique identifier for the theorem
        range: Source location (start_line, end_line)
        signals: Automation signals from scan_file
        structure: Optional deep structure data from scan_theorem
    """

    theorem_id: str
    range: dict[str, int]
    signals: dict[str, Any]
    structure: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate theorem data invariants."""
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")

        if "start_line" not in self.range or "end_line" not in self.range:
            raise ValueError("range must contain start_line and end_line")

        if self.range["start_line"] < 0 or self.range["end_line"] < 0:
            raise ValueError("line numbers must be non-negative")

        if self.range["start_line"] > self.range["end_line"]:
            raise ValueError("start_line must be <= end_line")


def compute_success_likelihood(signals: dict[str, Any], config: "SuccessLikelihoodScoringConfig") -> float:
    """Compute success likelihood score from automation signals.

    Estimates probability that automation will successfully solve the theorem
    based on whole_goal_potential, confidence, and complexity penalties.

    Args:
        signals: Automation signals from scan_file
        config: Success likelihood scoring configuration

    Returns:
        Score in [0.0, 1.0] indicating success likelihood
    """
    # Extract signals with defaults
    whole_goal = signals.get("whole_goal_potential", {})
    confidence = signals.get("confidence", 0.0)
    proof_lines = signals.get("proof_lines", 0)
    has_induction = signals.get("has_induction", False)
    has_cases = signals.get("has_cases", False)
    local_lemmas_count = signals.get("local_lemmas_count", 0)

    # Base score from automation potential
    aesop_score = whole_goal.get("aesop", 0.0)
    grind_score = whole_goal.get("grind", 0.0)
    max_potential = max(aesop_score, grind_score)

    # Compute complexity penalty
    complexity_penalty = 0.0
    if has_induction or has_cases:
        complexity_penalty += config.complexity_induction_or_cases_penalty
    if proof_lines > config.complexity_long_proof_threshold:
        complexity_penalty += config.complexity_long_proof_penalty
    if local_lemmas_count > config.complexity_many_local_lemmas_threshold:
        complexity_penalty += config.complexity_many_local_lemmas_penalty
    complexity_penalty = min(config.complexity_max_penalty, complexity_penalty)

    # Compute final score
    score = (
        config.component_weight_max_potential * max_potential
        + config.component_weight_confidence * confidence
        + config.component_weight_complexity_penalty * complexity_penalty
    )

    # Clamp and round
    score = max(0.0, min(1.0, score))
    return float(round(score, 2))


def compute_impact(signals: dict[str, Any], config: "ImpactScoringConfig") -> float:
    """Compute impact score from automation signals.

    Estimates value of automating this theorem based on proof length,
    annotation value, and reusability.

    Args:
        signals: Automation signals from scan_file
        config: Impact scoring configuration

    Returns:
        Score in [0.0, 1.0] indicating automation impact
    """
    # Extract signals with defaults
    proof_lines = signals.get("proof_lines", 0)
    annotation_value = signals.get("annotation_value", 0.0)
    local_lemmas_count = signals.get("local_lemmas_count", 0)

    # Compute proof length score (saturating)
    proof_length_score = 0.0
    for length_config in config.proof_length_scores:
        min_lines = length_config.min_lines if length_config.min_lines is not None else 0
        max_lines = length_config.max_lines if length_config.max_lines is not None else float('inf')
        
        if min_lines <= proof_lines <= max_lines:
            proof_length_score = length_config.score
            break

    # Compute reusability score
    # Based on local lemmas (indicates complexity worth reusing)
    reusability_score = min(
        config.reusability_max_score,
        local_lemmas_count * config.reusability_score_per_local_lemma
    )

    # Compute final score
    score = (
        config.component_weight_proof_length * proof_length_score
        + config.component_weight_annotation_value * annotation_value
        + config.component_weight_reusability * reusability_score
    )

    # Clamp and round
    score = max(0.0, min(1.0, score))
    return float(round(score, 2))


def compute_subgoal_potential(
    signals: dict[str, Any], structure: dict[str, Any] | None = None, config: "SubgoalPotentialScoringConfig | None" = None
) -> float:
    """Compute subgoal potential score from automation signals.

    Estimates value of automating individual subgoals vs. whole goal
    based on subgoal_potential signals and structure analysis.

    Args:
        signals: Automation signals from scan_file
        structure: Optional deep structure data from scan_theorem
        config: Optional subgoal potential scoring configuration. If None, loads default config.

    Returns:
        Score in [0.0, 1.0] indicating subgoal automation potential
    """
    # Load default config if not provided
    if config is None:
        from .config import load_default_config
        full_config = load_default_config()
        config = full_config.subgoal_potential_scoring
    
    # Extract signals with defaults
    subgoal_potential = signals.get("subgoal_potential", {})
    confidence = signals.get("confidence", 0.0)

    # Base score from subgoal potential
    aesop_subgoal = subgoal_potential.get("aesop", 0.0)
    grind_subgoal = subgoal_potential.get("grind", 0.0)
    max_subgoal = max(aesop_subgoal, grind_subgoal)

    # Compute structure bonus (requires deep structure)
    structure_bonus = 0.0
    if structure:
        cases = structure.get("cases", [])
        blocks = structure.get("blocks", [])

        if cases:
            structure_bonus += min(
                config.structure_cases_max_bonus,
                len(cases) * config.structure_cases_bonus_per_case
            )

        # Check for rewrite_simp blocks
        rewrite_simp_blocks = [b for b in blocks if b.get("kind") == "rewrite_simp"]
        if rewrite_simp_blocks:
            structure_bonus += min(
                config.rewrite_blocks_max_bonus,
                len(rewrite_simp_blocks) * config.rewrite_blocks_bonus_per_block
            )

        # Multiple blocks bonus (already included in rewrite_blocks calculation)

    structure_bonus = min(1.0, structure_bonus)

    # Compute final score
    score = 0.5 * max_subgoal + 0.3 * structure_bonus + 0.2 * confidence

    # Clamp and round
    score = max(0.0, min(1.0, score))
    return float(round(score, 2))


def compute_risk(signals: dict[str, Any], config: "RiskScoringConfig") -> float:
    """Compute risk score from automation signals.

    Heuristic penalty for likely global changes or non-local side effects
    based on rewrite patterns, simp usage, local lemmas, and confidence.

    Args:
        signals: Automation signals from scan_file
        config: Risk scoring configuration

    Returns:
        Score in [0.0, 1.0] indicating automation risk
    """
    # Extract signals with defaults
    rewrite_count = signals.get("rewrite_count", 0)
    simp_count = signals.get("simp_count", 0)
    local_lemmas_count = signals.get("local_lemmas_count", 0)
    confidence = signals.get("confidence", 1.0)
    notes = signals.get("notes", [])

    # Compute global change risk
    global_change_risk = 0.0
    if rewrite_count > config.global_change_rewrite_heavy_threshold:
        global_change_risk = config.global_change_rewrite_heavy_risk
    elif simp_count > config.global_change_simp_heavy_threshold:
        global_change_risk = config.global_change_simp_heavy_risk

    # Check for "simp?" in notes (indicates need for simp set refinement)
    if any("simp?" in note.lower() for note in notes):
        global_change_risk = max(global_change_risk, config.global_change_simp_question_mark_risk)

    # Compute simp risk
    simp_risk = 0.0
    if simp_count > config.simp_heavy_threshold:
        simp_risk = config.simp_heavy_risk
    elif simp_count > config.simp_moderate_threshold:
        simp_risk = config.simp_moderate_risk

    # Compute local lemma risk
    local_lemma_risk = 0.0
    if local_lemmas_count > config.local_lemma_heavy_threshold:
        local_lemma_risk = config.local_lemma_heavy_risk
    elif local_lemmas_count > config.local_lemma_moderate_threshold:
        local_lemma_risk = config.local_lemma_moderate_risk

    # Compute low confidence risk
    low_confidence_risk = 0.0
    if confidence < config.low_confidence_very_low_threshold:
        low_confidence_risk = config.low_confidence_very_low_risk
    elif confidence < config.low_confidence_low_threshold:
        low_confidence_risk = config.low_confidence_low_risk

    # Compute final risk score
    risk = (
        config.component_weight_global_change * global_change_risk
        + config.component_weight_simp * simp_risk
        + config.component_weight_local_lemma * local_lemma_risk
        + config.component_weight_confidence * low_confidence_risk
    )

    # Clamp and round
    risk = max(0.0, min(1.0, risk))
    return round(risk, 2)


# Objective weight configurations (immutable)
OBJECTIVE_WEIGHTS = {
    "maximize_success": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "annotation_value": 0.10,
        "subgoal_potential": 0.10,
        "risk": -0.20,
    },
    "maximize_impact": {
        "success_likelihood": 0.20,
        "impact": 0.40,
        "annotation_value": 0.30,
        "subgoal_potential": 0.05,
        "risk": -0.05,
    },
    "maximize_subgoal_automation": {
        "success_likelihood": 0.15,
        "impact": 0.15,
        "annotation_value": 0.20,
        "subgoal_potential": 0.40,
        "risk": -0.10,
    },
    "balanced": {
        "success_likelihood": 0.25,
        "impact": 0.25,
        "annotation_value": 0.20,
        "subgoal_potential": 0.20,
        "risk": -0.10,
    },
}


def compute_final_score(components: ComponentScores, objective: str) -> float:
    """Compute final score by applying objective weights to component scores.

    Args:
        components: Component scores for a theorem
        objective: Ranking objective name

    Returns:
        Final score in [0.0, 1.0]

    Raises:
        ValueError: If objective is not recognized
    """
    if objective not in OBJECTIVE_WEIGHTS:
        raise ValueError(
            f"Unknown objective: {objective}. "
            f"Valid objectives: {', '.join(OBJECTIVE_WEIGHTS.keys())}"
        )

    weights = OBJECTIVE_WEIGHTS[objective]

    # Apply weights to components
    score = (
        weights["success_likelihood"] * components.success_likelihood
        + weights["impact"] * components.impact
        + weights["annotation_value"] * components.annotation_value
        + weights["subgoal_potential"] * components.subgoal_potential
        + weights["risk"] * components.risk
    )

    # Clamp and round
    score = max(0.0, min(1.0, score))
    return round(score, 2)


@dataclass(frozen=True)
class RankedTheorem:
    """A theorem with its ranking score and components.

    Attributes:
        theorem_data: The underlying theorem data
        score: Final ranking score
        components: Component scores breakdown
    """

    theorem_data: TheoremData
    score: float
    components: ComponentScores

    def __post_init__(self) -> None:
        """Validate ranked theorem invariants."""
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"score must be in [0.0, 1.0], got {self.score}")


def rank_theorems(
    theorems: list[TheoremData], objective: str, min_confidence: float = 0.0
) -> list[RankedTheorem]:
    """Rank theorems according to objective with stable sorting.

    Applies confidence filtering, computes component scores, applies
    objective weights, and sorts with stable tie-breaking rules.

    Args:
        theorems: List of theorem data to rank
        objective: Ranking objective name
        min_confidence: Minimum confidence threshold (default 0.0)

    Returns:
        List of ranked theorems sorted by score (desc), then theorem_id, then start_line

    Raises:
        ValueError: If objective is not recognized or min_confidence is invalid
    """
    if not (0.0 <= min_confidence <= 1.0):
        raise ValueError(f"min_confidence must be in [0.0, 1.0], got {min_confidence}")

    # Filter by confidence
    filtered_theorems = [t for t in theorems if t.signals.get("confidence", 0.0) >= min_confidence]

    # Compute scores for each theorem
    ranked = []
    for theorem in filtered_theorems:
        # Compute component scores
        components = ComponentScores(
            success_likelihood=compute_success_likelihood(theorem.signals),
            impact=compute_impact(theorem.signals),
            annotation_value=theorem.signals.get("annotation_value", 0.0),
            subgoal_potential=compute_subgoal_potential(theorem.signals, theorem.structure),
            risk=compute_risk(theorem.signals),
        )

        # Compute final score
        final_score = compute_final_score(components, objective)

        # Create ranked theorem
        ranked.append(RankedTheorem(theorem_data=theorem, score=final_score, components=components))

    # Sort with stable tie-breaking:
    # 1. Score descending
    # 2. Theorem ID lexicographic
    # 3. Start line ascending
    ranked.sort(
        key=lambda r: (
            -r.score,  # Negative for descending
            r.theorem_data.theorem_id,
            r.theorem_data.range["start_line"],
        )
    )

    return ranked


def generate_reasons(
    signals: dict[str, Any], components: ComponentScores, structure: dict[str, Any] | None = None
) -> list[str]:
    """Generate human-readable explanations for ranking.

    Produces explanations that reference specific features from scan_file
    analysis, following note generation patterns from core.scoring module.

    Args:
        signals: Automation signals from scan_file
        components: Computed component scores
        structure: Optional deep structure data from scan_theorem

    Returns:
        List of reasons (max 10, each max 200 chars)
    """
    reasons = []

    # Extract signals
    confidence = signals.get("confidence", 0.0)
    proof_lines = signals.get("proof_lines", 0)
    whole_goal = signals.get("whole_goal_potential", {})
    subgoal_potential = signals.get("subgoal_potential", {})
    annotation_value = signals.get("annotation_value", 0.0)
    rewrite_count = signals.get("rewrite_count", 0)
    simp_count = signals.get("simp_count", 0)
    local_lemmas_count = signals.get("local_lemmas_count", 0)
    has_induction = signals.get("has_induction", False)
    has_cases = signals.get("has_cases", False)
    notes = signals.get("notes", [])

    # Reason about confidence
    if confidence >= 0.8:
        reasons.append("high confidence proof")
    elif confidence >= 0.6:
        reasons.append("good proof structure")
    elif confidence >= 0.4:
        reasons.append("moderate confidence")
    elif confidence > 0.0:
        reasons.append("uncertain proof boundaries")

    # Reason about proof length
    if proof_lines == 0:
        reasons.append("no proof found")
    elif proof_lines > 20:
        reasons.append("long proof")
    elif proof_lines <= 3:
        reasons.append("short proof")
    else:
        reasons.append("moderate proof length")

    # Reason about automation potential
    aesop_whole = whole_goal.get("aesop", 0.0)
    grind_whole = whole_goal.get("grind", 0.0)

    if aesop_whole > 0.7:
        reasons.append("good aesop candidate")
    elif aesop_whole > 0.5:
        reasons.append("moderate aesop potential")

    if grind_whole > 0.7:
        reasons.append("good grind candidate")
    elif grind_whole > 0.5:
        reasons.append("moderate grind potential")

    # Reason about subgoal potential
    aesop_subgoal = subgoal_potential.get("aesop", 0.0)
    grind_subgoal = subgoal_potential.get("grind", 0.0)

    if max(aesop_subgoal, grind_subgoal) > 0.6:
        reasons.append("good subgoal automation potential")

    # Reason about annotation value
    if annotation_value > 0.8:
        reasons.append("high annotation value")
    elif annotation_value > 0.6:
        reasons.append("good annotation candidate")

    # Reason about proof patterns
    if has_induction:
        reasons.append("uses induction")
    if has_cases:
        reasons.append("uses cases")

    if rewrite_count > 5:
        reasons.append("rewrite-heavy")
    elif rewrite_count > 0:
        reasons.append("uses rewrites")

    if simp_count > 3:
        reasons.append("simp-heavy")
    elif simp_count > 0:
        reasons.append("uses simp")

    if local_lemmas_count > 2:
        reasons.append("many local lemmas")
    elif local_lemmas_count > 0:
        reasons.append("has local lemmas")

    # Reason about structure (if available)
    if structure:
        cases = structure.get("cases", [])
        blocks = structure.get("blocks", [])

        if cases:
            reasons.append(f"{len(cases)} case branches")

        if blocks:
            block_kinds = {b.get("kind") for b in blocks}
            if "rewrite_simp" in block_kinds:
                reasons.append("rewrite-heavy sections")
            if "closing" in block_kinds:
                reasons.append("has closing tactics")

    # Reason about risk factors
    if components.risk > 0.6:
        reasons.append("high automation risk")
    elif components.risk > 0.4:
        reasons.append("moderate automation risk")

    # Include relevant notes from scan_file
    for note in notes[:3]:  # Include up to 3 notes
        if note not in reasons:  # Avoid duplicates
            reasons.append(note)

    # Limit to 10 reasons and 200 chars each
    reasons = reasons[:10]
    reasons = [reason[:200] for reason in reasons]

    return reasons
