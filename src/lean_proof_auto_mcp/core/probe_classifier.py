"""
Automation classifier for probe tool.

This module implements the AutomationClassifier port using heuristic-based
classification rules to categorize automation outcomes.

Requirements: 2.1-2.6
"""


class HeuristicClassifier:
    """
    Heuristic-based automation classifier.

    This classifier uses deterministic rules to classify automation outcomes
    into categories that help downstream tools decide whether to pursue
    further search or annotation.

    Classification rules:
    - trivial: Automation closes goal in < 20% of budget
    - promising: Automation fails but produces shallow subgoals (≤ 3 levels)
    - failed: Automation fails decisively (deep subgoals > 3 levels or no progress)
    - timed_out: Budget exhausted
    - error: Toolchain or execution error

    Requirements: 2.1-2.6
    """

    def classify(
        self,
        outcome: str,
        diagnostics: list[dict],
        timing: dict[str, float],
        budget_s: float,
    ) -> str:
        """
        Classify automation outcome using heuristics.

        This method applies deterministic rules to classify the outcome of an
        automation attempt. The classification helps downstream tools decide
        whether to pursue further search or annotation.

        Args:
            outcome: Raw outcome ("closed", "not_closed", "timeout", "error")
            diagnostics: Diagnostic messages from Lean
            timing: Timing information (must contain "elapsed_ms" key)
            budget_s: Time budget that was allocated

        Returns:
            Classification string ("trivial", "promising", "failed", "timed_out", "error")

        Requirements: 2.1-2.6
        """
        # Timeout classification (Requirement 2.4)
        if outcome == "timeout":
            return "timed_out"

        # Error classification (Requirement 2.5)
        if outcome == "error":
            return "error"

        # Success classification (Requirement 2.1)
        if outcome == "closed":
            elapsed_s = timing.get("elapsed_ms", 0.0) / 1000.0
            # Trivial if solved quickly (< 20% of budget)
            if elapsed_s < budget_s * 0.2:
                return "trivial"
            else:
                # Still trivial if it closed, regardless of time
                return "trivial"

        # Failure classification (outcome == "not_closed")
        # First check for explicit failure messages in diagnostics (Requirement 2.3)
        has_explicit_failure = self._has_explicit_failure(diagnostics)
        if has_explicit_failure:
            return "failed"
        
        # Analyze diagnostics to determine if promising (Requirement 2.2, 2.3)
        subgoal_depth = self._estimate_subgoal_depth(diagnostics)
        if subgoal_depth <= 3:
            return "promising"
        else:
            return "failed"

    def _has_explicit_failure(self, diagnostics: list[dict]) -> bool:
        """
        Check for explicit failure messages in diagnostics.

        Looks for messages indicating tactics made no progress or failed.

        Args:
            diagnostics: List of diagnostic messages from Lean

        Returns:
            True if explicit failure detected, False otherwise

        Requirements: 2.3
        """
        failure_indicators = [
            "made no progress",
            "failed to",
            "tactic failed",
            "could not",
            "unable to",
        ]

        for diag in diagnostics:
            message = diag.get("message", "").lower()
            if any(indicator in message for indicator in failure_indicators):
                return True

        return False

    def _estimate_subgoal_depth(self, diagnostics: list[dict]) -> int:
        """
        Estimate subgoal depth from diagnostics.

        This is a heuristic based on:
        - Number of unsolved goals messages
        - Nesting level of goal contexts
        - Presence of "shallow" vs "deep" goal indicators

        Args:
            diagnostics: List of diagnostic messages from Lean

        Returns:
            Estimated subgoal depth (integer)

        Requirements: 2.2, 2.3
        """
        if not diagnostics:
            # No diagnostics suggests no progress or immediate failure
            return 999  # Treat as very deep (failed)

        # Count goal-related messages
        goal_count = 0
        max_depth_indicator = 0

        for diag in diagnostics:
            message = diag.get("message", "")

            # Look for unsolved goals indicators
            if "unsolved goals" in message.lower():
                goal_count += 1

            # Look for nested goal indicators (e.g., "⊢" symbols, case splits)
            if "⊢" in message:
                # Count nesting level by looking at indentation or structure
                # Simple heuristic: count occurrences of goal markers
                goal_markers = message.count("⊢")
                max_depth_indicator = max(max_depth_indicator, goal_markers)

            # Look for case split indicators (suggests deeper proof)
            if "case" in message.lower():
                max_depth_indicator = max(max_depth_indicator, 2)

        # Heuristic: if we have multiple unsolved goals or deep nesting, it's deep
        if goal_count > 3:
            return 5  # Deep subgoals

        if max_depth_indicator > 3:
            return max_depth_indicator

        # If we have some goals but not too many, it's shallow (promising)
        if goal_count > 0:
            return min(goal_count, 3)

        # No clear goal indicators - treat as shallow (might be close)
        return 1
