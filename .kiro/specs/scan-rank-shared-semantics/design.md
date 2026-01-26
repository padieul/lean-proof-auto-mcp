# Design: scan-rank-shared-semantics

## Overview

This design implements shared semantic improvements across `scan_file`, `scan_theorem`, and `rank_targets` tools, addressing critical production-readiness gaps identified in user feedback.

## Architecture Principles

Following the codebase's mandatory design patterns:

1. **Hexagonal Architecture**: Configuration system uses port/adapter pattern
2. **Dependency Injection**: Scoring functions receive config as dependency
3. **Immutable Data**: All configurations and data structures are frozen
4. **Explicit Validation**: All inputs validated with clear error messages
5. **Strategy Pattern**: Scoring strategies remain pluggable
6. **Builder Pattern**: Complex configuration objects built with validation

## Design Decisions

### D1: Confidence Fix - Add Numeric Note

**Problem**: Confidence calculated but always returns 0.0 in tool outputs.

**Root Cause**: `_generate_notes()` adds qualitative notes ("high confidence proof") but not numeric values.

**Solution**: Add numeric confidence note before qualitative notes.

**Implementation** (`core/scoring.py`):
```python
def _generate_notes(
    features: TheoremFeatures,
    structure: ProofStructure | None,
    scores: dict[str, float]
) -> list[str]:
    """Generate explanatory notes for the scoring."""
    notes = []

    # CRITICAL: Add numeric confidence for downstream tools
    # This enables rank_targets to extract and use confidence values
    if features.confidence > 0.0:
        notes.append(f"confidence: {features.confidence:.2f}")

    # Then add qualitative notes as before
    if features.confidence >= 0.8:
        notes.append("high confidence proof")
    elif features.confidence >= 0.6:
        notes.append("good proof structure")
    # ... rest of existing notes
```

**Extraction** (`tools/rank_targets.py` - already exists, will now work):
```python
# This code already exists and will start working
for note in notes:
    if "confidence" in note_lower:
        try:
            parts = note.split(":")
            if len(parts) >= 2:
                conf_str = parts[1].strip()
                signals["confidence"] = float(conf_str)
        except (ValueError, IndexError):
            pass
```

**Impact**:
- Minimal change (1 line added)
- Fixes confidence for all tools (scan_file, scan_theorem, rank_targets)
- Backward compatible (adds note, doesn't remove anything)


### D2: Already-Automated Detection Module

**Problem**: Tools recommend theorems that already use automation tactics or attributes.

**Solution**: Create detection module with conservative pattern matching.

**Module Structure** (`core/automation_detection.py`):
```python
"""Detection of already-automated theorems.

Conservative detection: prefer false negatives over false positives.
Better to recommend an automated theorem than skip a manual one.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AutomationStatus:
    """Result of automation detection.

    Attributes:
        is_automated: Whether theorem uses automation
        automation_type: Type of automation detected
        penalty: Penalty score (0.0-1.0) for ranking
        detected_patterns: List of patterns that matched
    """
    is_automated: bool
    automation_type: str  # "tactic" | "attribute" | "trivial" | "none"
    penalty: float
    detected_patterns: list[str]

    def __post_init__(self) -> None:
        """Validate automation status invariants."""
        if not (0.0 <= self.penalty <= 1.0):
            raise ValueError(f"penalty must be in [0.0, 1.0], got {self.penalty}")

        valid_types = {"tactic", "attribute", "trivial", "none"}
        if self.automation_type not in valid_types:
            raise ValueError(
                f"automation_type must be one of {valid_types}, "
                f"got '{self.automation_type}'"
            )


class AutomationDetector(Protocol):
    """Port for automation detection strategies."""

    def detect(
        self,
        proof_text: str,
        decl_text: str,
        tactic_kinds: set[str]
    ) -> AutomationStatus:
        """Detect if theorem already uses automation."""
        ...


class PatternBasedDetector:
    """Conservative pattern-based automation detection.

    Uses explicit pattern matching to detect automation tactics,
    attributes, and trivial proofs. Prefers false negatives over
    false positives.
    """

    def __init__(self, config: "AutomationDetectionConfig"):
        """Initialize detector with configuration."""
        self.config = config

    def detect(
        self,
        proof_text: str,
        decl_text: str,
        tactic_kinds: set[str]
    ) -> AutomationStatus:
        """Detect automation with conservative pattern matching."""
        detected_patterns = []

        # Check for trivial proofs first (highest penalty)
        trivial_status = self._check_trivial(proof_text)
        if trivial_status.is_automated:
            return trivial_status

        # Check for automation attributes (high penalty)
        attribute_status = self._check_attributes(decl_text)
        if attribute_status.is_automated:
            return attribute_status

        # Check for automation tactics (moderate penalty)
        tactic_status = self._check_tactics(proof_text, tactic_kinds)
        if tactic_status.is_automated:
            return tactic_status

        # No automation detected
        return AutomationStatus(
            is_automated=False,
            automation_type="none",
            penalty=0.0,
            detected_patterns=[]
        )

    def _check_trivial(self, proof_text: str) -> AutomationStatus:
        """Check for trivial proofs (rfl, trivial)."""
        proof_lower = proof_text.lower().strip()

        for pattern in self.config.trivial_patterns:
            if pattern in proof_lower:
                return AutomationStatus(
                    is_automated=True,
                    automation_type="trivial",
                    penalty=self.config.trivial_penalty,
                    detected_patterns=[pattern]
                )

        return AutomationStatus(False, "none", 0.0, [])

    def _check_attributes(self, decl_text: str) -> AutomationStatus:
        """Check for automation attributes (@[aesop], @[simp])."""
        decl_lower = decl_text.lower()
        detected = []

        for pattern in self.config.attribute_patterns:
            if pattern in decl_lower:
                detected.append(pattern)

        if detected:
            return AutomationStatus(
                is_automated=True,
                automation_type="attribute",
                penalty=self.config.attribute_penalty,
                detected_patterns=detected
            )

        return AutomationStatus(False, "none", 0.0, [])

    def _check_tactics(
        self,
        proof_text: str,
        tactic_kinds: set[str]
    ) -> AutomationStatus:
        """Check for automation tactics (aesop, grind, simp)."""
        proof_lower = proof_text.lower()
        detected = []

        # Check tactic patterns in proof text
        for pattern in self.config.tactic_patterns:
            if pattern in proof_lower:
                detected.append(pattern)

        # Check detected tactic kinds
        automation_tactics = {
            "aesop", "grind", "simp", "simp_all",
            "omega", "decide", "tauto"
        }
        detected_tactics = tactic_kinds & automation_tactics
        detected.extend(detected_tactics)

        if detected:
            return AutomationStatus(
                is_automated=True,
                automation_type="tactic",
                penalty=self.config.tactic_penalty,
                detected_patterns=detected
            )

        return AutomationStatus(False, "none", 0.0, [])


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
```

**Usage in rank_targets**:
```python
# In _load_theorem_data or rank_theorems
detector = PatternBasedDetector(config.automation_detection)

for theorem in theorems:
    # Get proof text and declaration text
    proof_text = source.get_span_text(theorem.proof_span)
    decl_text = source.get_span_text(theorem.decl_span)

    # Detect automation
    status = detector.detect(proof_text, decl_text, theorem.tactic_kinds)

    # Add to signals
    theorem.signals["already_automated"] = status.is_automated
    theorem.signals["automation_penalty"] = status.penalty
    theorem.signals["automation_type"] = status.automation_type
```


### D3: Tier System - Percentile-Based Ranking

**Problem**: Raw scores (~0.34-0.38) feel pessimistic and lack intuitive meaning.

**Solution**: Add S/A/B/C/D tier system based on percentile rank within file.

**Implementation** (`core/ranking.py`):
```python
def assign_tiers(ranked_theorems: list[RankedTheorem]) -> list[tuple[RankedTheorem, str]]:
    """Assign S/A/B/C/D tiers based on percentile rank.

    Tiers are relative to the file, not absolute scores:
    - S-tier: Top 10% (exceptional candidates)
    - A-tier: 10-25% (strong candidates)
    - B-tier: 25-50% (good candidates)
    - C-tier: 50-75% (acceptable candidates)
    - D-tier: 75-100% (weak candidates)

    Args:
        ranked_theorems: List of theorems already sorted by score (desc)

    Returns:
        List of (theorem, tier) tuples
    """
    n = len(ranked_theorems)
    if n == 0:
        return []

    result = []
    for i, theorem in enumerate(ranked_theorems):
        # Calculate percentile (0-100)
        percentile = (i / n) * 100

        # Assign tier based on percentile
        if percentile < 10:
            tier = "S"
        elif percentile < 25:
            tier = "A"
        elif percentile < 50:
            tier = "B"
        elif percentile < 75:
            tier = "C"
        else:
            tier = "D"

        result.append((theorem, tier))

    return result
```

**Integration in rank_targets**:
```python
def _format_response(...) -> dict[str, Any]:
    # Rank theorems
    ranked_theorems = rank_theorems(...)

    # Assign tiers
    theorems_with_tiers = assign_tiers(ranked_theorems)

    # Build ranking array
    ranking = []
    for (ranked, tier) in theorems_with_tiers[:args.limit]:
        theorem_obj = {
            "theorem_id": ranked.theorem_data.theorem_id,
            "range": {...},
            "score": ranked.score,
            "tier": tier,  # NEW FIELD
            # ... rest of fields
        }
        ranking.append(theorem_obj)

    # Add tier distribution to summary
    tier_counts = {
        "S": sum(1 for _, t in theorems_with_tiers if t == "S"),
        "A": sum(1 for _, t in theorems_with_tiers if t == "A"),
        "B": sum(1 for _, t in theorems_with_tiers if t == "B"),
        "C": sum(1 for _, t in theorems_with_tiers if t == "C"),
        "D": sum(1 for _, t in theorems_with_tiers if t == "D"),
    }

    summary = {
        "total": total_theorems,
        "returned": len(ranking),
        "skipped_low_confidence": skipped_low_confidence,
        "tier_distribution": tier_counts,  # NEW FIELD
    }
```

**Configurable Thresholds**:
```python
@dataclass(frozen=True)
class TierConfig:
    """Configuration for tier thresholds."""
    s_tier_percentile: float  # default: 10.0
    a_tier_percentile: float  # default: 25.0
    b_tier_percentile: float  # default: 50.0
    c_tier_percentile: float  # default: 75.0

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

        if not (0 < self.s_tier_percentile < 100):
            raise ValueError("s_tier_percentile must be in (0, 100)")
```


### D4: Objective Discovery - Available Objectives Metadata

**Problem**: Clients must guess valid objective names through trial-and-error.

**Solution**: Include objective metadata in response and error messages.

**Implementation** (`core/ranking.py`):
```python
# Extend existing OBJECTIVE_WEIGHTS with metadata
OBJECTIVE_METADATA = {
    "maximize_success": {
        "description": "Prioritize theorems most likely to be automated successfully",
        "use_case": "When you want quick wins and high success rate",
        "weights": {
            "success_likelihood": 0.50,
            "impact": 0.10,
            "annotation_value": 0.10,
            "subgoal_potential": 0.10,
            "risk": -0.20,
        }
    },
    "maximize_impact": {
        "description": "Prioritize theorems that save the most time when automated",
        "use_case": "When you want maximum ROI on automation effort",
        "weights": {
            "success_likelihood": 0.20,
            "impact": 0.40,
            "annotation_value": 0.30,
            "subgoal_potential": 0.05,
            "risk": -0.05,
        }
    },
    "maximize_subgoal_automation": {
        "description": "Prioritize theorems with good partial automation opportunities",
        "use_case": "When you want to automate proof steps rather than whole goals",
        "weights": {
            "success_likelihood": 0.15,
            "impact": 0.15,
            "annotation_value": 0.20,
            "subgoal_potential": 0.40,
            "risk": -0.10,
        }
    },
    "balanced": {
        "description": "Balanced weighting across all factors",
        "use_case": "When you want a general-purpose ranking",
        "weights": {
            "success_likelihood": 0.25,
            "impact": 0.25,
            "annotation_value": 0.20,
            "subgoal_potential": 0.20,
            "risk": -0.10,
        }
    },
}

# Keep OBJECTIVE_WEIGHTS for backward compatibility
OBJECTIVE_WEIGHTS = {
    name: meta["weights"]
    for name, meta in OBJECTIVE_METADATA.items()
}


def get_available_objectives() -> list[dict[str, Any]]:
    """Return objective metadata for client discovery.

    Returns:
        List of objective metadata dictionaries with:
        - name: Objective identifier
        - description: What this objective optimizes for
        - use_case: When to use this objective
        - weights: Component weight configuration
    """
    return [
        {
            "name": name,
            "description": meta["description"],
            "use_case": meta["use_case"],
            "weights": meta["weights"],
        }
        for name, meta in OBJECTIVE_METADATA.items()
    ]
```

**Integration in rank_targets**:
```python
def _format_response(...) -> dict[str, Any]:
    # ... existing response building

    response = {
        "api_version": "0.2",  # Bump version
        "status": "success",
        "run_id": run_id,
        "tool": "rank_targets",
        "file": args.file,
        "objective": args.objective,
        "ranking": ranking,
        "summary": summary,
        "diagnostics": diagnostics,
        "metadata": metadata,
        "available_objectives": get_available_objectives(),  # NEW FIELD
    }

    return ensure_deterministic(response)
```

**Better Error Messages**:
```python
def _coerce_args(args: dict[str, Any]) -> RankTargetsArgs:
    # ... existing validation

    objective = args.get("objective", "balanced")
    if objective not in OBJECTIVE_METADATA:
        available = get_available_objectives()
        objective_names = [obj["name"] for obj in available]
        objective_list = "\n".join([
            f"  - {obj['name']}: {obj['description']}"
            for obj in available
        ])

        raise ValueError(
            f"rank_targets: invalid objective '{objective}'\n"
            f"Available objectives:\n{objective_list}"
        )
```


### D5: Skip Already-Automated Parameter

**Problem**: No way to filter out already-automated theorems.

**Solution**: Add `skip_already_automated` boolean parameter to rank_targets.

**Implementation** (`tools/rank_targets.py`):
```python
@dataclass(frozen=True)
class RankTargetsArgs:
    """Arguments for rank_targets tool."""
    file: str
    objective: str
    limit: int
    include_components: bool
    include_reasons: bool
    use_deep_structure: bool
    min_confidence: float
    skip_already_automated: bool  # NEW PARAMETER

    def __post_init__(self) -> None:
        """Validate argument invariants."""
        # ... existing validation

        if not isinstance(self.skip_already_automated, bool):
            raise ValueError("skip_already_automated must be a boolean")


def _coerce_args(args: dict[str, Any]) -> RankTargetsArgs:
    """Parse and validate rank_targets arguments."""
    # ... existing parsing

    skip_already_automated = args.get("skip_already_automated", False)
    if not isinstance(skip_already_automated, bool):
        raise ValueError("rank_targets: 'skip_already_automated' must be a boolean")

    return RankTargetsArgs(
        # ... existing fields
        skip_already_automated=skip_already_automated,
    )


def rank_targets(args: dict[str, Any]) -> dict[str, Any]:
    """Rank theorem automation targets in a Lean file."""
    # ... existing code

    try:
        # Load theorem data
        theorem_data_list, diagnostics, scan_file_run_id = _load_theorem_data(
            parsed.file, parsed.use_deep_structure
        )

        # Detect already-automated theorems
        detector = PatternBasedDetector(config.automation_detection)
        for theorem_data in theorem_data_list:
            # Get source text
            proof_text = source.get_span_text(theorem_data.proof_span)
            decl_text = source.get_span_text(theorem_data.decl_span)
            tactic_kinds = theorem_data.signals.get("tactic_kinds", set())

            # Detect automation
            status = detector.detect(proof_text, decl_text, tactic_kinds)

            # Add to signals
            theorem_data.signals["already_automated"] = status.is_automated
            theorem_data.signals["automation_penalty"] = status.penalty
            theorem_data.signals["automation_type"] = status.automation_type

        # Filter if requested
        if parsed.skip_already_automated:
            filtered = [
                t for t in theorem_data_list
                if not t.signals.get("already_automated", False)
            ]
            skipped_automated = len(theorem_data_list) - len(filtered)
            theorem_data_list = filtered
        else:
            skipped_automated = 0

        total_theorems = len(theorem_data_list)

        # Rank theorems with confidence filtering
        ranked_theorems = rank_theorems(
            theorem_data_list,
            parsed.objective,
            parsed.min_confidence
        )

        # Calculate skipped counts
        skipped_low_confidence = total_theorems - len(ranked_theorems)

        # Format response with new summary fields
        summary = {
            "total": total_theorems,
            "returned": len(ranking),
            "skipped_low_confidence": skipped_low_confidence,
            "skipped_already_automated": skipped_automated,  # NEW FIELD
        }
```


### D6: Already-Automated Penalty Component

**Problem**: Binary skip is too coarse - users may want to see but de-prioritize automated theorems.

**Solution**: Add `already_automated_penalty` component score that reduces ranking.

**Implementation** (`core/ranking.py`):
```python
@dataclass(frozen=True)
class ComponentScores:
    """Component scores for ranking computation."""
    success_likelihood: float
    impact: float
    annotation_value: float
    subgoal_potential: float
    risk: float
    already_automated_penalty: float  # NEW COMPONENT

    def __post_init__(self) -> None:
        """Validate component score invariants."""
        scores = {
            "success_likelihood": self.success_likelihood,
            "impact": self.impact,
            "annotation_value": self.annotation_value,
            "subgoal_potential": self.subgoal_potential,
            "risk": self.risk,
            "already_automated_penalty": self.already_automated_penalty,  # NEW
        }

        for name, score in scores.items():
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"{name} must be in [0.0, 1.0], got {score}")


def rank_theorems(
    theorems: list[TheoremData],
    objective: str,
    min_confidence: float = 0.0
) -> list[RankedTheorem]:
    """Rank theorems according to objective with stable sorting."""
    # ... existing filtering

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
            already_automated_penalty=theorem.signals.get("automation_penalty", 0.0),  # NEW
        )

        # Compute final score (penalty reduces score)
        final_score = compute_final_score(components, objective)

        # Create ranked theorem
        ranked.append(RankedTheorem(
            theorem_data=theorem,
            score=final_score,
            components=components
        ))

    # ... existing sorting
    return ranked


def compute_final_score(components: ComponentScores, objective: str) -> float:
    """Compute final score by applying objective weights to component scores."""
    if objective not in OBJECTIVE_WEIGHTS:
        raise ValueError(f"Unknown objective: {objective}")

    weights = OBJECTIVE_WEIGHTS[objective]

    # Apply weights to components
    score = (
        weights["success_likelihood"] * components.success_likelihood
        + weights["impact"] * components.impact
        + weights["annotation_value"] * components.annotation_value
        + weights["subgoal_potential"] * components.subgoal_potential
        + weights["risk"] * components.risk
        - 0.15 * components.already_automated_penalty  # NEW: Penalty reduces score
    )

    # Clamp and round
    score = max(0.0, min(1.0, score))
    return round(score, 2)
```

**Behavior**:
- When `skip_already_automated=false`: Penalty applied, theorems ranked lower but still visible
- When `skip_already_automated=true`: Theorems filtered out entirely before ranking
- Penalty weight (-0.15) is fixed across all objectives for consistency


### D7: Configuration System Architecture

**Problem**: 100+ hardcoded magic numbers scattered across scoring logic.

**Solution**: Externalize all heuristic parameters to configuration file using hexagonal architecture.

**Port (Protocol)** (`core/config.py`):
```python
"""Configuration system for heuristic parameters.

Follows hexagonal architecture:
- Core logic depends on HeuristicsConfig protocol (port)
- YamlConfigLoader is an adapter (infrastructure detail)
- Configuration is immutable once loaded
- Validation happens at construction time
"""

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
        if not (0.0 <= self.base_score <= 1.0):
            raise ValueError(f"base_score must be in [0.0, 1.0], got {self.base_score}")
        # ... validate all fields


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
class AesopScoringConfig:
    """Configuration for aesop potential scoring."""
    base_score: float
    confidence_bonuses: list[ConfidenceBonusTier]
    structural_tactics_bonus_per_tactic: float
    structural_tactics_max_bonus: float
    term_mode_bonus_per_pattern: float
    term_mode_max_bonus: float
    proof_length_bonuses: list[tuple[int, float]]  # [(max_lines, bonus), ...]
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
        # ... validate all fields


# Similar dataclasses for:
# - GrindScoringConfig
# - AnnotationValueScoringConfig
# - SubgoalPotentialScoringConfig
# - RiskScoringConfig
# - ImpactScoringConfig
# - SuccessLikelihoodScoringConfig
# - ObjectiveConfig
# - TierConfig
# (Full definitions in implementation)
```


**Adapter (Implementation)** (`core/config.py`):
```python
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
            raise ValueError(
                f"Unsupported configuration version: {version}. "
                f"Expected version 1.0"
            )

        # Build and validate configuration
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "YamlHeuristicsConfig":
        """Build configuration from dictionary with validation."""
        try:
            # Parse confidence config
            confidence = ConfidenceConfig(
                base_score=data["confidence"]["base_score"],
                proof_structure_bonus=data["confidence"]["bonuses"]["proof_structure"],
                # ... parse all fields
            )

            # Parse aesop scoring config
            aesop_bonuses = [
                ConfidenceBonusTier(
                    threshold=tier["threshold"],
                    bonus=tier["bonus"]
                )
                for tier in data["aesop_scoring"]["confidence_bonuses"].values()
            ]
            aesop_scoring = AesopScoringConfig(
                base_score=data["aesop_scoring"]["base_score"],
                confidence_bonuses=aesop_bonuses,
                # ... parse all fields
            )

            # Parse all other configs...

            return cls(
                confidence=confidence,
                aesop_scoring=aesop_scoring,
                # ... all configs
                version=data["version"]
            )

        except KeyError as e:
            raise ValueError(f"Missing required configuration field: {e}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid configuration value: {e}")


def load_default_config() -> HeuristicsConfig:
    """Load default configuration from package.

    This is the composition root for configuration.
    """
    return YamlHeuristicsConfig.load()


def load_config(path: Path) -> HeuristicsConfig:
    """Load configuration from custom path.

    Args:
        path: Path to custom YAML configuration file

    Returns:
        Validated configuration object
    """
    return YamlHeuristicsConfig.load(path)
```

**Dependency Injection in Scoring Functions** (`core/scoring.py`):
```python
def score_aesop_potential(
    features: TheoremFeatures,
    config: HeuristicsConfig  # Injected dependency
) -> float:
    """Heuristic: aesop works well on structural proofs.

    Args:
        features: Theorem features to analyze
        config: Heuristic configuration (injected)

    Returns:
        Score between 0.0 and 1.0 indicating aesop potential
    """
    if features.proof_lines == 0:
        return 0.0

    # Use config values instead of hardcoded numbers
    score = config.aesop_scoring.base_score

    # Apply confidence bonuses from config
    for tier in config.aesop_scoring.confidence_bonuses:
        if features.confidence >= tier.threshold:
            score += tier.bonus
            break

    # Structural tactics bonus from config
    structural_tactics = {
        "intro", "intros", "constructor", "left", "right",
        "split", "ext", "funext", "use", "exists", "apply",
    }
    structural_count = len(features.tactic_kinds & structural_tactics)
    if structural_count > 0:
        bonus = min(
            config.aesop_scoring.structural_tactics_max_bonus,
            structural_count * config.aesop_scoring.structural_tactics_bonus_per_tactic
        )
        score += bonus

    # ... rest of scoring using config values

    return max(0.0, min(1.0, score))


def compute_profile(
    features: TheoremFeatures,
    structure: ProofStructure | None = None,
    config: HeuristicsConfig | None = None  # Optional, defaults to package config
) -> AutomationProfile:
    """Compute automation scores from features.

    Args:
        features: Extracted theorem features
        structure: Optional proof structure analysis
        config: Optional custom configuration (defaults to package config)

    Returns:
        AutomationProfile with computed scores and explanatory notes
    """
    if config is None:
        config = load_default_config()

    # Compute individual scores with config
    aesop_whole = score_aesop_potential(features, config)
    grind_whole = score_grind_potential(features, config)
    # ... rest of scoring
```


**Default Configuration File** (`src/lean_proof_auto_mcp/heuristics.yaml`):
```yaml
version: "1.0"

# Confidence calculation parameters
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

# Aesop scoring parameters
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

# Grind scoring parameters
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

# Annotation value scoring parameters
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

# Subgoal potential scoring parameters
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

# Risk scoring parameters
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

# Impact scoring parameters
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

# Success likelihood scoring parameters
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

# Objective configurations
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

# Already-automated detection parameters
already_automated:
  penalties:
    tactic_usage: 0.3
    attribute: 0.5
    trivial_proof: 0.8
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

# Tier threshold parameters
tiers:
  s_tier_percentile: 10
  a_tier_percentile: 25
  b_tier_percentile: 50
  c_tier_percentile: 75
```

**Usage in Tools**:
```python
# tools/rank_targets.py
def rank_targets(args: dict[str, Any]) -> dict[str, Any]:
    """Rank theorem automation targets in a Lean file."""
    # Configuration is REQUIRED (no fallback to defaults)
    config_path = args.get("config_path")
    if config_path:
        config = load_config(Path(config_path))
    else:
        # Load from environment variable or fail
        config_env = os.getenv("LEAN_PROOF_AUTO_MCP_CONFIG")
        if config_env:
            config = load_config(Path(config_env))
        else:
            # Use package default (explicit, not implicit)
            config = load_default_config()

    # Pass config to all scoring functions
    # ... rest of implementation
```

**Environment Variable Support**:
```bash
# Users can set default config via environment
export LEAN_PROOF_AUTO_MCP_CONFIG=/path/to/custom_heuristics.yaml

# Or pass explicitly per call
rank_targets({"file": "test.lean", "config_path": "/path/to/config.yaml"})
```


## API Changes

### rank_targets Tool

**Required Parameters** (BREAKING CHANGE):
- `file` (string): Path to Lean file
- `objective` (string): Ranking objective
- `skip_already_automated` (boolean): Must explicitly choose true/false

**Optional Parameters**:
- `limit` (integer, default: 30): Maximum theorems to return
- `min_confidence` (float, default: 0.0): Confidence threshold
- `include_components` (boolean, default: true): Include component breakdown
- `include_reasons` (boolean, default: true): Include human-readable reasons
- `use_deep_structure` (boolean, default: false): Use scan_theorem for enhanced scoring
- `config_path` (string, optional): Path to custom heuristics configuration

**Always-Present Response Fields** (BREAKING CHANGE):
- `tier` (string): S/A/B/C/D tier for each ranked theorem
- `available_objectives` (array): List of objective metadata
- `summary.skipped_already_automated` (integer): Count of filtered automated theorems
- `summary.tier_distribution` (object): Count of theorems in each tier
- `components.already_automated_penalty` (float): Penalty component score

**API Version**: 1.0 (BREAKING CHANGE from 0.1)

**Example Request** (BREAKING CHANGE - skip_already_automated now required):
```json
{
  "file": "test.lean",
  "objective": "maximize_success",
  "skip_already_automated": true,
  "limit": 30,
  "min_confidence": 0.0,
  "include_components": true,
  "include_reasons": true,
  "config_path": "/path/to/custom_heuristics.yaml"
}
```

**Example Response** (BREAKING CHANGE - new required fields):
```json
{
  "api_version": "1.0",
  "status": "success",
  "run_id": "rank-abc123",
  "tool": "rank_targets",
  "file": "test.lean",
  "objective": "maximize_success",
  "ranking": [
    {
      "theorem_id": "Polynomial.eval₂_mul_noncomm",
      "range": { "start_line": 140, "end_line": 143 },
      "score": 0.38,
      "tier": "S",
      "components": {
        "success_likelihood": 0.54,
        "impact": 0.33,
        "annotation_value": 0.63,
        "subgoal_potential": 0.41,
        "risk": 0.14,
        "already_automated_penalty": 0.0
      },
      "reasons": [
        "confidence: 0.85",
        "high confidence proof",
        "moderate proof length",
        "good aesop candidate",
        "has local lemmas"
      ],
      "signals": {
        "whole_goal_potential": { "aesop": 0.9, "grind": 0.56 },
        "subgoal_potential": { "aesop": 0.82, "grind": 0.48 },
        "annotation_value": 0.63,
        "proof_lines": 4,
        "confidence": 0.85
      }
    }
  ],
  "summary": {
    "total": 141,
    "returned": 30,
    "skipped_low_confidence": 0,
    "skipped_already_automated": 15,
    "tier_distribution": {
      "S": 14,
      "A": 21,
      "B": 35,
      "C": 35,
      "D": 36
    }
  },
  "diagnostics": [],
  "metadata": {
    "deep_structure_used": false,
    "computation_time_ms": 45.2,
    "config_source": "default"
  },
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate",
      "weights": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "annotation_value": 0.10,
        "subgoal_potential": 0.10,
        "risk": -0.20
      }
    }
  ]
}
```

### scan_file Tool

**Changes**: Inherits confidence fix from `core/scoring.py`

**BREAKING CHANGE**: All responses now include numeric confidence in notes

**New Note Format** (REQUIRED):
```json
{
  "notes": [
    "confidence: 0.85",
    "high confidence proof",
    "moderate proof length",
    "good aesop candidate"
  ]
}
```

**API Version**: 1.0 (BREAKING CHANGE from 0.1)

### scan_theorem Tool

**Changes**: Inherits confidence fix from `core/scoring.py`

**BREAKING CHANGE**: All responses now include numeric confidence in notes

**New Note Format** (REQUIRED): Same as scan_file

**API Version**: 1.0 (BREAKING CHANGE from 0.1)


## Testing Strategy

### Unit Tests

**Confidence Fix** (`tests/unit/core/test_scoring.py`):
```python
def test_generate_notes_includes_numeric_confidence():
    """Test that notes include numeric confidence value."""
    features = TheoremFeatures(
        proof_lines=10,
        tactic_kinds={"intro", "apply"},
        has_induction=False,
        has_cases=False,
        rewrite_count=0,
        simp_count=0,
        local_lemmas_count=0,
        confidence=0.85
    )

    profile = compute_profile(features, structure=None)

    # Check numeric confidence is in notes
    assert any("confidence: 0.85" in note for note in profile.notes)
    # Check qualitative note is also present
    assert any("high confidence" in note.lower() for note in profile.notes)


def test_generate_notes_no_confidence_when_zero():
    """Test that zero confidence doesn't add numeric note."""
    features = TheoremFeatures(
        proof_lines=0,
        tactic_kinds=set(),
        has_induction=False,
        has_cases=False,
        rewrite_count=0,
        simp_count=0,
        local_lemmas_count=0,
        confidence=0.0
    )

    profile = compute_profile(features, structure=None)

    # No numeric confidence note when zero
    assert not any("confidence:" in note for note in profile.notes)
```

**Already-Automated Detection** (`tests/unit/core/test_automation_detection.py`):
```python
def test_detect_automation_tactic():
    """Test detection of automation tactics."""
    detector = PatternBasedDetector(default_config())

    status = detector.detect(
        proof_text="by aesop",
        decl_text="theorem foo : P := by aesop",
        tactic_kinds={"aesop"}
    )

    assert status.is_automated
    assert status.automation_type == "tactic"
    assert status.penalty == 0.3
    assert "aesop" in status.detected_patterns


def test_detect_automation_attribute():
    """Test detection of automation attributes."""
    detector = PatternBasedDetector(default_config())

    status = detector.detect(
        proof_text="intro h\napply foo",
        decl_text="@[aesop safe] theorem foo : P := by ...",
        tactic_kinds={"intro", "apply"}
    )

    assert status.is_automated
    assert status.automation_type == "attribute"
    assert status.penalty == 0.5


def test_detect_trivial_proof():
    """Test detection of trivial proofs."""
    detector = PatternBasedDetector(default_config())

    status = detector.detect(
        proof_text=":= rfl",
        decl_text="theorem foo : x = x := rfl",
        tactic_kinds={"rfl"}
    )

    assert status.is_automated
    assert status.automation_type == "trivial"
    assert status.penalty == 0.8


def test_no_false_positives():
    """Test that manual proofs are not detected as automated."""
    detector = PatternBasedDetector(default_config())

    status = detector.detect(
        proof_text="intro h\napply foo\nexact bar",
        decl_text="theorem foo : P := by intro h; apply foo; exact bar",
        tactic_kinds={"intro", "apply", "exact"}
    )

    assert not status.is_automated
    assert status.automation_type == "none"
    assert status.penalty == 0.0
```

**Tier Assignment** (`tests/unit/core/test_ranking.py`):
```python
def test_assign_tiers_percentiles():
    """Test tier assignment based on percentiles."""
    # Create 100 theorems with descending scores
    theorems = [
        create_ranked_theorem(f"thm_{i}", score=1.0 - i/100)
        for i in range(100)
    ]

    tiers_with_theorems = assign_tiers(theorems)

    # Check tier distribution
    tiers = [tier for _, tier in tiers_with_theorems]
    assert tiers[:10] == ["S"] * 10  # Top 10%
    assert tiers[10:25] == ["A"] * 15  # 10-25%
    assert tiers[25:50] == ["B"] * 25  # 25-50%
    assert tiers[50:75] == ["C"] * 25  # 50-75%
    assert tiers[75:] == ["D"] * 25  # 75-100%


def test_assign_tiers_empty_list():
    """Test tier assignment with empty list."""
    result = assign_tiers([])
    assert result == []


def test_assign_tiers_single_theorem():
    """Test tier assignment with single theorem."""
    theorem = create_ranked_theorem("thm_1", score=0.5)
    result = assign_tiers([theorem])

    assert len(result) == 1
    assert result[0][1] == "S"  # Single theorem is S-tier
```

**Configuration Loading** (`tests/unit/core/test_config.py`):
```python
def test_load_default_config():
    """Test loading default configuration."""
    config = load_default_config()

    assert config.confidence.base_score == 0.3
    assert config.aesop_scoring.base_score == 0.2
    assert len(config.objectives) == 4


def test_load_custom_config(tmp_path):
    """Test loading custom configuration."""
    config_file = tmp_path / "custom.yaml"
    config_file.write_text("""
version: "1.0"
confidence:
  base_score: 0.5
# ... rest of config
""")

    config = load_config(config_file)
    assert config.confidence.base_score == 0.5


def test_invalid_config_version(tmp_path):
    """Test that invalid version raises error."""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("version: '2.0'")

    with pytest.raises(ValueError, match="Unsupported configuration version"):
        load_config(config_file)


def test_invalid_config_values(tmp_path):
    """Test that invalid values raise errors."""
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("""
version: "1.0"
confidence:
  base_score: 1.5  # Invalid: > 1.0
""")

    with pytest.raises(ValueError, match="base_score must be in"):
        load_config(config_file)
```

### Integration Tests

**End-to-End Confidence** (`tests/integration/test_confidence_flow.py`):
```python
def test_confidence_flows_through_tools():
    """Test that confidence flows from scan_file to rank_targets."""
    # Scan file
    scan_result = scan_file({"file": "test.lean"})
    assert scan_result["status"] == "success"

    # Check confidence in notes
    theorem = scan_result["theorems"][0]
    confidence_note = [n for n in theorem["notes"] if "confidence:" in n]
    assert len(confidence_note) == 1

    # Rank targets
    rank_result = rank_targets({
        "file": "test.lean",
        "min_confidence": 0.5
    })

    # Check confidence is extracted and used
    if rank_result["summary"]["returned"] > 0:
        ranked_theorem = rank_result["ranking"][0]
        assert ranked_theorem["signals"]["confidence"] > 0.0
```

### Property-Based Tests

**Configuration Validation** (`tests/property/test_config_properties.py`):
```python
@given(st.floats(min_value=-1.0, max_value=2.0))
def test_config_validates_score_ranges(score):
    """Property: All score fields must be in [0.0, 1.0]."""
    if 0.0 <= score <= 1.0:
        # Valid score should not raise
        config = ConfidenceConfig(base_score=score, ...)
    else:
        # Invalid score should raise
        with pytest.raises(ValueError):
            config = ConfidenceConfig(base_score=score, ...)
```


## Implementation Strategy

**Breaking Change Approach**: Since there are no users yet, implement all changes together as a single breaking release.

### Implementation Order

1. **Configuration System** (Foundation)
   - Create `core/config.py` with protocol and adapter
   - Create default `heuristics.yaml`
   - Refactor ALL scoring functions to require config parameter
   - Update `compute_profile()` to require config

2. **Confidence Fix** (Quick Win)
   - Add numeric confidence note in `_generate_notes()`
   - Update all tests to expect new note format

3. **Already-Automated Detection** (Core Feature)
   - Create `core/automation_detection.py`
   - Add `skip_already_automated` parameter (required, no default)
   - Add `already_automated_penalty` component
   - Update all tests

4. **Tier System** (UX Improvement)
   - Add `assign_tiers()` function
   - Add `tier` field to ALL responses
   - Add `tier_distribution` to summary
   - Update all tests and docs

5. **Objective Discovery** (UX Improvement)
   - Create `OBJECTIVE_METADATA`
   - Add `available_objectives` to ALL responses
   - Update error messages
   - Update all tests and docs

6. **Update All Documentation**
   - Rewrite tool contracts (schemas)
   - Rewrite all examples
   - Update README
   - Update architecture docs

7. **Update All Tests**
   - Rewrite unit tests for new signatures
   - Rewrite integration tests for new responses
   - Rewrite property tests for new invariants
   - Update test fixtures

### Breaking Changes

**API Version**: 0.1 → 1.0 (major version bump)

**Required Changes for All Calls**:
- `config` parameter now required (or use default via environment)
- `skip_already_automated` parameter now required (must explicitly choose)
- All responses include `tier` and `available_objectives`
- All responses include `already_automated_penalty` component

**No Fallbacks**:
- No optional config (must be explicit)
- No default for `skip_already_automated` (must be explicit)
- All magic numbers removed from code

## Performance Considerations

### Confidence Fix
- **Impact**: Negligible (<0.1ms per theorem)
- **Reason**: Single string append to notes list

### Configuration Loading
- **Impact**: ~5ms one-time cost at startup
- **Mitigation**: Load config once, reuse across all calls
- **Caching**: Config is immutable, can be cached globally

### Already-Automated Detection
- **Impact**: ~2-5ms per theorem
- **Reason**: Pattern matching on proof text and declaration
- **Mitigation**: Conservative patterns, early exit on match

### Tier Assignment
- **Impact**: ~1-2ms for 200 theorems
- **Reason**: Single pass over sorted list
- **Optimization**: O(n) algorithm, no sorting needed

### Total Overhead
- **Without config**: ~3-7ms per 200 theorems
- **With config**: ~8-12ms per 200 theorems (first call)
- **Subsequent calls**: ~3-7ms (config cached)
- **Target**: <50ms total for 200 theorems ✓

## Documentation Updates (BREAKING CHANGES)

### Tool Contracts (docs/mcp/schemas/)
- **REWRITE** `rank_targets.json` schema with new required fields
- **REWRITE** `scan_file.json` schema with new note format
- **REWRITE** `scan_theorem.json` schema with new note format
- **UPDATE** all examples to use new API version 1.0
- **ADD** configuration schema documentation

### User Guide (COMPLETE REWRITE)
- Explain configuration system (required reading)
- Explain confidence filtering (now actually works)
- Explain skip_already_automated usage (required parameter)
- Explain tier system interpretation
- Provide configuration customization guide
- Show example custom configurations
- Document environment variable usage

### API Changelog (BREAKING RELEASE)
- Document API version bump (0.1 → 1.0)
- List ALL breaking changes
- Provide migration guide from 0.1
- Note: No backward compatibility

### README Updates
- Update all examples to API 1.0
- Add configuration section
- Add tier system explanation
- Update quick start guide

## Open Questions

1. **Configuration file location**: Should users be able to specify config via environment variable?
   - **Decision**: Support both explicit path parameter and env var `LEAN_PROOF_AUTO_MCP_CONFIG`

2. **Tier threshold customization**: Should tier thresholds be configurable per-call or only via config file?
   - **Decision**: Config file only (keeps API simple, thresholds rarely change per-call)

3. **Already-automated penalty weight**: Should this be configurable per-objective or fixed?
   - **Decision**: Fixed at -0.15 for consistency (can be made configurable later if needed)

4. **Custom objectives**: Should users be able to define custom objectives in config?
   - **Decision**: Yes, config file can include custom objectives with validation

5. **Configuration validation**: Should we provide a CLI tool to validate config files?
   - **Decision**: Yes, add `python -m lean_proof_auto_mcp.config validate <path>` command

## Success Criteria

### Functional
- ✅ Confidence values are non-zero and usable for filtering
- ✅ Already-automated theorems can be filtered or down-ranked
- ✅ Clients can discover valid objectives without errors
- ✅ Tier system provides intuitive quality assessment
- ✅ Configuration system allows tuning without code changes
- ✅ All magic numbers removed from code
- ✅ Configuration is explicit (no hidden defaults)

### Non-Functional
- ✅ Performance overhead < 10ms for 200 theorems
- ✅ Configuration validation provides clear error messages
- ✅ Default configuration works well for typical Lean code
- ✅ All tests rewritten for new API
- ✅ All documentation rewritten for new API
- ✅ All schemas updated to version 1.0

### User Experience
- ✅ Configuration system is well-documented
- ✅ Power users can tune heuristics via config file
- ✅ Researchers can reproduce results by sharing config
- ✅ Error messages are helpful and actionable
- ✅ Tier system is more intuitive than raw scores
- ✅ skip_already_automated is explicit (no surprises)
