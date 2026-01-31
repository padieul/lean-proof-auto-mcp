"""
GlobalSuggestionAnalyzer service for analyzing minimized hint sets.

This service analyzes minimized hint sets to identify candidates for
global annotations (@[aesop], @[simp]) that could improve automation
across the entire project.

Requirements: 7.1, 7.2, 7.3, 7.4
"""

from dataclasses import dataclass
from typing import Literal

from lean_proof_auto_mcp.core.search_automated_proof_domain import (
    GlobalSuggestion,
    Hint,
    HintSet,
    HintType,
)


@dataclass(frozen=True)
class AnalysisConfig:
    """
    Configuration for global suggestion analysis.

    Attributes:
        min_effectiveness_threshold: Minimum effectiveness score (0.0-1.0)
        prefer_safe_rules: Prefer safe aesop rules over unsafe
        suggest_simp_for_equations: Suggest @[simp] for equation lemmas
    """

    min_effectiveness_threshold: float = 0.7
    prefer_safe_rules: bool = True
    suggest_simp_for_equations: bool = True

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not 0.0 <= self.min_effectiveness_threshold <= 1.0:
            raise ValueError("min_effectiveness_threshold must be between 0.0 and 1.0")


class GlobalSuggestionAnalyzer:
    """
    Analyze minimized hint sets for global annotation candidates.

    This service examines hints that were effective in closing goals
    and generates suggestions for adding global annotations that could
    improve automation across the entire project.

    Requirements: 7.1, 7.2, 7.3, 7.4
    """

    def __init__(self, config: AnalysisConfig | None = None):
        """
        Initialize analyzer with configuration.

        Args:
            config: Analysis configuration (uses defaults if None)
        """
        self.config = config or AnalysisConfig()

    def analyze(
        self, minimized_hint_set: HintSet, mode: Literal["local_only", "suggest_global"]
    ) -> list[GlobalSuggestion]:
        """
        Analyze minimized hint set and generate global suggestions.

        Args:
            minimized_hint_set: The minimized hint set that closed the goal
            mode: Analysis mode (local_only or suggest_global)

        Returns:
            List of global annotation suggestions (empty if mode is local_only)

        Requirements: 7.1, 7.2, 7.3, 7.4
        """
        # Requirement 7.1: When mode is local_only, return empty list
        if mode == "local_only":
            return []

        # Requirement 7.2: When mode is suggest_global, analyze hints
        suggestions = []

        for hint in minimized_hint_set.hints:
            # Analyze each hint for globalization potential
            suggestion = self._analyze_hint(hint)
            if suggestion is not None:
                suggestions.append(suggestion)

        # Filter by effectiveness criteria
        filtered_suggestions = self._filter_by_effectiveness(suggestions)

        return filtered_suggestions

    def _analyze_hint(self, hint: Hint) -> GlobalSuggestion | None:
        """
        Analyze a single hint for global annotation potential.

        Args:
            hint: Hint to analyze

        Returns:
            GlobalSuggestion if hint is a good candidate, None otherwise

        Requirements: 7.3, 7.4
        """
        # RULE_SET hints never generate suggestions (Requirement 7.3)
        if hint.type == HintType.RULE_SET:
            return None

        # Determine appropriate attribute based on hint type
        if hint.type == HintType.SIMP:
            # Already a simp lemma, suggest making it global if not already
            attribute = "@[simp]"
            rationale = (
                f"Hint '{hint.name}' was effective as a simp lemma in local proof. "
                f"Adding global @[simp] attribute could improve automation across the project."
            )
            confidence = self._calculate_confidence(hint, "simp")

        elif hint.type == HintType.ADD_SAFE:
            # Safe aesop rule, good candidate for global annotation
            attribute = "@[aesop safe]"
            rationale = (
                f"Hint '{hint.name}' was effective as a safe aesop rule in local proof. "
                f"Adding global @[aesop safe] attribute could improve automation "
                f"across the project."
            )
            confidence = self._calculate_confidence(hint, "aesop_safe")

        elif hint.type == HintType.ADD_UNSAFE:
            # Unsafe aesop rule, be more cautious
            if self.config.prefer_safe_rules:
                # Skip unsafe rules if config prefers safe
                return None
            attribute = "@[aesop unsafe]"
            rationale = (
                f"Hint '{hint.name}' was effective as an unsafe aesop rule in local proof. "
                f"Consider adding global @[aesop unsafe] attribute, but review carefully "
                f"as unsafe rules can cause performance issues."
            )
            confidence = "low"  # Always low confidence for unsafe rules

        elif hint.type == HintType.UNFOLD:
            # Definition unfolding, suggest aesop unfold
            attribute = "@[aesop unfold]"
            rationale = (
                f"Hint '{hint.name}' required unfolding in local proof. "
                f"Adding global @[aesop unfold] attribute could help automation "
                f"automatically unfold this definition when needed."
            )
            confidence = self._calculate_confidence(hint, "unfold")

        else:
            # Unknown hint type, should not happen
            return None

        return GlobalSuggestion(
            hint_name=hint.name, attribute=attribute, rationale=rationale, confidence=confidence
        )

    def _calculate_confidence(
        self, hint: Hint, category: Literal["simp", "aesop_safe", "unfold"]
    ) -> Literal["high", "medium", "low"]:
        """
        Calculate confidence level for a global suggestion.

        Args:
            hint: Hint being analyzed
            category: Category of suggestion

        Returns:
            Confidence level (high, medium, or low)

        Requirements: 7.3, 7.4
        """
        # Simple heuristic-based confidence calculation
        # In a real implementation, this would consider:
        # - How many times the hint appeared in successful proofs
        # - The hint's source (original_proof_refs = higher confidence)
        # - The hint's type (safe rules = higher confidence)
        # - Project-wide usage patterns

        # For now, use simple rules:
        confidence_map: dict[str, Literal["high", "medium", "low"]] = {
            "simp": "high",  # Simp lemmas are generally safe to make global
            "aesop_safe": (
                "high" if self.config.prefer_safe_rules else "medium"
            ),  # Safe aesop rules are good candidates
            "unfold": "medium",  # Unfold hints are more situational
        }
        result = confidence_map.get(category, "low")
        # Ensure we return a Literal type
        return result if result in ("high", "medium", "low") else "low"

    def _filter_by_effectiveness(
        self, suggestions: list[GlobalSuggestion]
    ) -> list[GlobalSuggestion]:
        """
        Filter suggestions by effectiveness criteria.

        Args:
            suggestions: List of suggestions to filter

        Returns:
            Filtered list of suggestions

        Requirements: 7.3
        """
        # Filter out low-confidence suggestions if threshold is high
        if self.config.min_effectiveness_threshold >= 0.7:
            # High threshold: only keep high confidence
            return [s for s in suggestions if s.confidence == "high"]
        elif self.config.min_effectiveness_threshold >= 0.4:
            # Medium threshold: keep high and medium confidence
            return [s for s in suggestions if s.confidence in ("high", "medium")]
        else:
            # Low threshold: keep all suggestions
            return suggestions
