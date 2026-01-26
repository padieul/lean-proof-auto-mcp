"""Detection of already-automated theorems.

Conservative detection: prefer false negatives over false positives.
Better to recommend an automated theorem than skip a manual one.

This module follows hexagonal architecture:
- AutomationDetector is a port (protocol)
- PatternBasedDetector is an adapter (implementation)
- Detection logic is injected via configuration
"""

from dataclasses import dataclass
from typing import Protocol

from lean_proof_auto_mcp.core.config import AutomationDetectionConfig


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
                f"automation_type must be one of {valid_types}, got '{self.automation_type}'"
            )


class AutomationDetector(Protocol):
    """Port for automation detection strategies."""

    def detect(self, proof_text: str, decl_text: str, tactic_kinds: set[str]) -> AutomationStatus:
        """Detect if theorem already uses automation.

        Args:
            proof_text: The proof body text
            decl_text: The full declaration text (including attributes)
            tactic_kinds: Set of detected tactic names

        Returns:
            AutomationStatus indicating detection result
        """
        ...


class PatternBasedDetector:
    """Conservative pattern-based automation detection.

    Uses explicit pattern matching to detect automation tactics,
    attributes, and trivial proofs. Prefers false negatives over
    false positives.

    This is an adapter that implements the AutomationDetector port.
    """

    def __init__(self, config: AutomationDetectionConfig):
        """Initialize detector with configuration.

        Args:
            config: Configuration for detection patterns and penalties
        """
        self.config = config

    def detect(self, proof_text: str, decl_text: str, tactic_kinds: set[str]) -> AutomationStatus:
        """Detect automation with conservative pattern matching.

        Detection priority (highest to lowest penalty):
        1. Trivial proofs (rfl, trivial) - highest penalty
        2. Automation attributes (@[aesop], @[simp]) - high penalty
        3. Automation tactics (aesop, grind, simp) - moderate penalty

        Args:
            proof_text: The proof body text
            decl_text: The full declaration text (including attributes)
            tactic_kinds: Set of detected tactic names

        Returns:
            AutomationStatus with detection result
        """
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
            is_automated=False, automation_type="none", penalty=0.0, detected_patterns=[]
        )

    def _check_trivial(self, proof_text: str) -> AutomationStatus:
        """Check for trivial proofs (rfl, trivial).

        Args:
            proof_text: The proof body text

        Returns:
            AutomationStatus indicating if trivial proof detected
        """
        proof_lower = proof_text.lower().strip()

        for pattern in self.config.trivial_patterns:
            if pattern in proof_lower:
                return AutomationStatus(
                    is_automated=True,
                    automation_type="trivial",
                    penalty=self.config.trivial_penalty,
                    detected_patterns=[pattern],
                )

        return AutomationStatus(False, "none", 0.0, [])

    def _check_attributes(self, decl_text: str) -> AutomationStatus:
        """Check for automation attributes (@[aesop], @[simp]).

        Args:
            decl_text: The full declaration text (including attributes)

        Returns:
            AutomationStatus indicating if automation attributes detected
        """
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
                detected_patterns=detected,
            )

        return AutomationStatus(False, "none", 0.0, [])

    def _check_tactics(self, proof_text: str, tactic_kinds: set[str]) -> AutomationStatus:
        """Check for automation tactics (aesop, grind, simp).

        Args:
            proof_text: The proof body text
            tactic_kinds: Set of detected tactic names

        Returns:
            AutomationStatus indicating if automation tactics detected
        """
        proof_lower = proof_text.lower()
        detected = []

        # Check tactic patterns in proof text
        for pattern in self.config.tactic_patterns:
            if pattern in proof_lower:
                detected.append(pattern)

        # Check detected tactic kinds
        automation_tactics = {"aesop", "grind", "simp", "simp_all", "omega", "decide", "tauto"}
        detected_tactics = tactic_kinds & automation_tactics
        detected.extend(detected_tactics)

        if detected:
            return AutomationStatus(
                is_automated=True,
                automation_type="tactic",
                penalty=self.config.tactic_penalty,
                detected_patterns=detected,
            )

        return AutomationStatus(False, "none", 0.0, [])
