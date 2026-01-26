"""
Core domain structures and ports for the probe and probe_file tools.

This module defines the immutable data structures and abstract interfaces (ports)
for automation probing following hexagonal architecture principles.

Requirements: 1.1, 1.8, 2.1-2.6, 3.1-3.8, 4.1-4.7, 5.1-5.6
"""

from dataclasses import dataclass
from typing import Any, Protocol

# ============================================================================
# Command and Result Data Structures (Immutable)
# ============================================================================


@dataclass(frozen=True)
class ProbeCommand:
    """
    Immutable command representing a probe request.

    This command encapsulates a single-theorem automation attempt with
    controlled conditions (mode, budget, trace configuration).

    Requirements: 1.1, 1.8, 3.1

    Attributes:
        file_path: Path to Lean file
        theorem_id: Theorem identifier to probe
        mode: Automation mode ("aesop", "aesop?", or "grind")
        budget_s: Time budget in seconds (default: 10.0)
        trace_config: Optional trace configuration for debugging
    """

    file_path: str
    theorem_id: str
    mode: str
    budget_s: float = 10.0
    trace_config: dict[str, bool] | None = None

    def __post_init__(self) -> None:
        """
        Validate command parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 1.8, 3.1, 10.3, 10.5
        """
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")
        if self.mode not in ("aesop", "aesop?", "grind"):
            raise ValueError("mode must be 'aesop', 'aesop?', or 'grind'")
        if self.budget_s <= 0:
            raise ValueError("budget_s must be positive")


@dataclass(frozen=True)
class ProbeOutcome:
    """
    Structured outcome of automation attempt.

    This dataclass encapsulates the result of running automation on a theorem,
    including the raw outcome, deterministic classification, and optional
    suggested script (for aesop? mode).

    Requirements: 2.1-2.6, 3.3, 3.4, 3.5

    Attributes:
        mode: Automation mode used
        outcome: Raw outcome ("closed", "not_closed", "timeout", "error")
        classification: Deterministic classification ("trivial", "promising", "failed", "timed_out", "error")
        suggested_script: Optional suggested script (for aesop? mode)
    """

    mode: str
    outcome: str
    classification: str
    suggested_script: str | None = None


@dataclass(frozen=True)
class ProbeResult:
    """
    Final result from single-theorem automation probe.

    This is the complete result returned to the user, containing all
    information about the probe attempt including outcome, diagnostics,
    timing, and metadata.

    Requirements: 1.5, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8

    Attributes:
        api_version: API version string
        status: Overall status ("success", "fail", "timeout", "error")
        run_id: Unique identifier for this probe run
        probe_result: Detailed probe outcome
        diagnostics: List of diagnostic messages
        timing: Timing information
        metadata: Metadata about execution environment
    """

    api_version: str
    status: str
    run_id: str
    probe_result: ProbeOutcome
    diagnostics: list[dict]
    timing: dict[str, float]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProbeFileCommand:
    """
    Immutable command for batch automation probing.

    This command encapsulates a batch probe request across multiple theorems
    in a file, with controlled conditions and ordering.

    Requirements: 4.1-4.7, 5.1-5.6

    Attributes:
        file_path: Path to Lean file
        mode: Automation mode ("aesop", "aesop?", or "grind")
        budget_s_per: Time budget per theorem in seconds (default: 5.0)
        limit: Maximum number of theorems to probe (default: 50)
        ordering: Ordering mode ("file_order" or "rank_targets", default: "file_order")
    """

    file_path: str
    mode: str
    budget_s_per: float = 5.0
    limit: int = 50
    ordering: str = "file_order"

    def __post_init__(self) -> None:
        """
        Validate command parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 5.1, 5.5, 5.6, 10.3, 10.5
        """
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if self.mode not in ("aesop", "aesop?", "grind"):
            raise ValueError("mode must be 'aesop', 'aesop?', or 'grind'")
        if self.budget_s_per <= 0:
            raise ValueError("budget_s_per must be positive")
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.ordering not in ("file_order", "rank_targets"):
            raise ValueError("ordering must be 'file_order' or 'rank_targets'")


@dataclass(frozen=True)
class ProbeFileResult:
    """
    Final result from batch automation probing.

    This is the complete result returned to the user, containing both
    per-theorem results and file-level summary statistics.

    Requirements: 4.5, 5.2, 5.3, 5.4

    Attributes:
        api_version: API version string
        status: Overall status ("success", "partial", "error")
        file: Path to probed file
        summary: Summary statistics (total, closed, promising, failed, timed_out)
        results: Per-theorem results
        metadata: Metadata about execution
    """

    api_version: str
    status: str
    file: str
    summary: dict[str, int]
    results: list[dict]
    metadata: dict[str, Any]


# ============================================================================
# Port Interfaces (Abstract)
# ============================================================================


class AutomationClassifier(Protocol):
    """
    Abstract interface for classifying automation outcomes.

    This port encapsulates the logic for deterministically classifying
    automation attempts into categories (trivial, promising, failed, timed_out, error).

    The classifier uses heuristics based on outcome, diagnostics, timing, and budget
    to determine the classification.

    Requirements: 2.1-2.6

    Methods:
        classify: Classify automation outcome based on execution results
    """

    def classify(
        self,
        outcome: str,
        diagnostics: list[dict],
        timing: dict[str, float],
        budget_s: float,
    ) -> str:
        """
        Classify automation outcome.

        This method applies deterministic rules to classify the outcome of an
        automation attempt. The classification helps downstream tools decide
        whether to pursue further search or annotation.

        Args:
            outcome: Raw outcome ("closed", "not_closed", "timeout", "error")
            diagnostics: Diagnostic messages from Lean
            timing: Timing information
            budget_s: Time budget that was allocated

        Returns:
            Classification string ("trivial", "promising", "failed", "timed_out", "error")

        Requirements: 2.1-2.6
        """
        ...
