"""
Unit tests for automation classifier.

These tests verify specific examples and edge cases for the HeuristicClassifier.

Requirements: 2.1-2.6
"""

from lean_proof_auto_mcp.core.probe_classifier import HeuristicClassifier


class TestHeuristicClassifier:
    """Unit tests for HeuristicClassifier."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = HeuristicClassifier()

    # ========================================================================
    # Trivial Classification Tests (Requirement 2.1)
    # ========================================================================

    def test_trivial_classification_quick_success(self):
        """Test trivial classification with quick success (< 20% budget)."""
        # Setup: Quick success (1s out of 10s budget = 10%)
        outcome = "closed"
        diagnostics = []
        timing = {"elapsed_ms": 1000.0}  # 1 second
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "trivial"

    def test_trivial_classification_slow_success(self):
        """Test trivial classification with slow success (> 20% budget but still closed)."""
        # Setup: Slow success (8s out of 10s budget = 80%)
        outcome = "closed"
        diagnostics = []
        timing = {"elapsed_ms": 8000.0}  # 8 seconds
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: Still trivial because it closed
        assert result == "trivial"

    def test_trivial_classification_boundary_20_percent(self):
        """Test trivial classification at exactly 20% budget boundary."""
        # Setup: Exactly 20% of budget
        outcome = "closed"
        diagnostics = []
        timing = {"elapsed_ms": 2000.0}  # 2 seconds
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: At boundary, should be trivial (>= 20% but closed)
        assert result == "trivial"

    # ========================================================================
    # Promising Classification Tests (Requirement 2.2)
    # ========================================================================

    def test_promising_classification_shallow_subgoals(self):
        """Test promising classification with shallow subgoals (≤ 3 levels)."""
        # Setup: Failed with shallow subgoals
        outcome = "not_closed"
        diagnostics = [
            {"message": "unsolved goals\n⊢ P → Q"},
            {"message": "case left\n⊢ P"},
        ]
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "promising"

    def test_promising_classification_few_goals(self):
        """Test promising classification with few unsolved goals."""
        # Setup: Failed with 2 unsolved goals
        outcome = "not_closed"
        diagnostics = [
            {"message": "unsolved goals\n⊢ A"},
            {"message": "unsolved goals\n⊢ B"},
        ]
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "promising"

    def test_promising_classification_exactly_3_goals(self):
        """Test promising classification at boundary (exactly 3 goals)."""
        # Setup: Failed with exactly 3 unsolved goals
        outcome = "not_closed"
        diagnostics = [
            {"message": "unsolved goals\n⊢ A"},
            {"message": "unsolved goals\n⊢ B"},
            {"message": "unsolved goals\n⊢ C"},
        ]
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: At boundary (3 goals), should be promising
        assert result == "promising"

    # ========================================================================
    # Failed Classification Tests (Requirement 2.3)
    # ========================================================================

    def test_failed_classification_deep_subgoals(self):
        """Test failed classification with deep subgoals (> 3 levels)."""
        # Setup: Failed with many unsolved goals (> 3)
        outcome = "not_closed"
        diagnostics = [
            {"message": "unsolved goals\n⊢ A"},
            {"message": "unsolved goals\n⊢ B"},
            {"message": "unsolved goals\n⊢ C"},
            {"message": "unsolved goals\n⊢ D"},
            {"message": "unsolved goals\n⊢ E"},
        ]
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "failed"

    def test_failed_classification_no_diagnostics(self):
        """Test failed classification with no diagnostics (no progress)."""
        # Setup: Failed with no diagnostics
        outcome = "not_closed"
        diagnostics = []
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: No diagnostics suggests no progress
        assert result == "failed"

    def test_failed_classification_deep_nesting(self):
        """Test failed classification with deep goal nesting."""
        # Setup: Failed with deeply nested goals
        outcome = "not_closed"
        diagnostics = [
            {"message": "case a.b.c.d\n⊢ P ⊢ Q ⊢ R ⊢ S"},
        ]
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: Deep nesting indicates failed
        assert result == "failed"

    # ========================================================================
    # Timeout Classification Tests (Requirement 2.4)
    # ========================================================================

    def test_timeout_classification(self):
        """Test timeout classification when budget exhausted."""
        # Setup: Timeout outcome
        outcome = "timeout"
        diagnostics = []
        timing = {"elapsed_ms": 10000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "timed_out"

    def test_timeout_classification_with_diagnostics(self):
        """Test timeout classification with partial diagnostics."""
        # Setup: Timeout with some diagnostics
        outcome = "timeout"
        diagnostics = [{"message": "unsolved goals\n⊢ P"}]
        timing = {"elapsed_ms": 10000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: Timeout takes precedence
        assert result == "timed_out"

    # ========================================================================
    # Error Classification Tests (Requirement 2.5)
    # ========================================================================

    def test_error_classification(self):
        """Test error classification for toolchain errors."""
        # Setup: Error outcome
        outcome = "error"
        diagnostics = [{"message": "error: unknown identifier 'foo'"}]
        timing = {"elapsed_ms": 100.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "error"

    def test_error_classification_no_diagnostics(self):
        """Test error classification without diagnostics."""
        # Setup: Error outcome with no diagnostics
        outcome = "error"
        diagnostics = []
        timing = {"elapsed_ms": 100.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify
        assert result == "error"

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_missing_elapsed_ms_defaults_to_zero(self):
        """Test that missing elapsed_ms in timing defaults to 0."""
        # Setup: Closed outcome with missing elapsed_ms
        outcome = "closed"
        diagnostics = []
        timing = {}  # No elapsed_ms
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: Should still classify as trivial (0 < 20% of budget)
        assert result == "trivial"

    def test_case_split_indicators_suggest_depth(self):
        """Test that case split indicators suggest deeper proof."""
        # Setup: Failed with case split indicators
        outcome = "not_closed"
        diagnostics = [
            {"message": "case left\n⊢ P"},
            {"message": "case right\n⊢ Q"},
        ]
        timing = {"elapsed_ms": 5000.0}
        budget_s = 10.0

        # Execute
        result = self.classifier.classify(outcome, diagnostics, timing, budget_s)

        # Verify: Case splits suggest some depth, but only 2 cases is still promising
        assert result == "promising"
