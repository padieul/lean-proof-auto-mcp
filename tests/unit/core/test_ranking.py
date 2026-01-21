"""Unit tests for core.ranking module."""

import pytest

from lean_proof_auto_mcp.core.ranking import (
    ComponentScores,
    TheoremData,
    compute_impact,
    compute_risk,
    compute_subgoal_potential,
    compute_success_likelihood,
)


class TestComponentScores:
    """Test cases for ComponentScores dataclass."""

    def test_valid_component_scores(self):
        """Test creating valid ComponentScores."""
        scores = ComponentScores(
            success_likelihood=0.75,
            impact=0.60,
            annotation_value=0.70,
            subgoal_potential=0.65,
            risk=0.20,
        )

        assert scores.success_likelihood == 0.75
        assert scores.impact == 0.60
        assert scores.annotation_value == 0.70
        assert scores.subgoal_potential == 0.65
        assert scores.risk == 0.20

    def test_invalid_success_likelihood_low(self):
        """Test validation of success_likelihood (too low)."""
        with pytest.raises(ValueError, match="success_likelihood must be in \\[0.0, 1.0\\]"):
            ComponentScores(
                success_likelihood=-0.1,
                impact=0.60,
                annotation_value=0.70,
                subgoal_potential=0.65,
                risk=0.20,
            )

    def test_invalid_success_likelihood_high(self):
        """Test validation of success_likelihood (too high)."""
        with pytest.raises(ValueError, match="success_likelihood must be in \\[0.0, 1.0\\]"):
            ComponentScores(
                success_likelihood=1.1,
                impact=0.60,
                annotation_value=0.70,
                subgoal_potential=0.65,
                risk=0.20,
            )

    def test_invalid_impact(self):
        """Test validation of impact."""
        with pytest.raises(ValueError, match="impact must be in \\[0.0, 1.0\\]"):
            ComponentScores(
                success_likelihood=0.75,
                impact=1.5,
                annotation_value=0.70,
                subgoal_potential=0.65,
                risk=0.20,
            )

    def test_invalid_risk(self):
        """Test validation of risk."""
        with pytest.raises(ValueError, match="risk must be in \\[0.0, 1.0\\]"):
            ComponentScores(
                success_likelihood=0.75,
                impact=0.60,
                annotation_value=0.70,
                subgoal_potential=0.65,
                risk=-0.1,
            )


class TestTheoremData:
    """Test cases for TheoremData dataclass."""

    def test_valid_theorem_data(self):
        """Test creating valid TheoremData."""
        data = TheoremData(
            theorem_id="File.theorem_name",
            range={"start_line": 10, "end_line": 25},
            signals={"confidence": 0.8, "proof_lines": 15},
            structure=None,
        )

        assert data.theorem_id == "File.theorem_name"
        assert data.range["start_line"] == 10
        assert data.range["end_line"] == 25
        assert data.signals["confidence"] == 0.8
        assert data.structure is None

    def test_invalid_empty_theorem_id(self):
        """Test validation of empty theorem_id."""
        with pytest.raises(ValueError, match="theorem_id must be non-empty"):
            TheoremData(
                theorem_id="",
                range={"start_line": 10, "end_line": 25},
                signals={},
            )

    def test_invalid_range_missing_fields(self):
        """Test validation of range missing fields."""
        with pytest.raises(ValueError, match="range must contain start_line and end_line"):
            TheoremData(
                theorem_id="test",
                range={"start_line": 10},
                signals={},
            )

    def test_invalid_range_negative_lines(self):
        """Test validation of negative line numbers."""
        with pytest.raises(ValueError, match="line numbers must be non-negative"):
            TheoremData(
                theorem_id="test",
                range={"start_line": -1, "end_line": 25},
                signals={},
            )

    def test_invalid_range_start_after_end(self):
        """Test validation of start_line > end_line."""
        with pytest.raises(ValueError, match="start_line must be <= end_line"):
            TheoremData(
                theorem_id="test",
                range={"start_line": 30, "end_line": 25},
                signals={},
            )


class TestComputeSuccessLikelihood:
    """Test cases for compute_success_likelihood function."""

    def test_high_confidence_high_potential(self):
        """Test scoring with high confidence and high automation potential."""
        signals = {
            "whole_goal_potential": {"aesop": 0.9, "grind": 0.5},
            "confidence": 0.9,
            "proof_lines": 10,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 1,
        }

        score = compute_success_likelihood(signals)
        assert score > 0.7  # Should be high
        assert score <= 1.0

    def test_low_confidence_low_potential(self):
        """Test scoring with low confidence and low automation potential."""
        signals = {
            "whole_goal_potential": {"aesop": 0.2, "grind": 0.1},
            "confidence": 0.3,
            "proof_lines": 5,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 0,
        }

        score = compute_success_likelihood(signals)
        assert score < 0.4  # Should be low
        assert score >= 0.0

    def test_complexity_penalty_induction(self):
        """Test complexity penalty for induction."""
        signals_no_induction = {
            "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
            "confidence": 0.8,
            "proof_lines": 10,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 1,
        }

        signals_with_induction = {
            "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
            "confidence": 0.8,
            "proof_lines": 10,
            "has_induction": True,
            "has_cases": False,
            "local_lemmas_count": 1,
        }

        score_no = compute_success_likelihood(signals_no_induction)
        score_with = compute_success_likelihood(signals_with_induction)

        assert score_with < score_no  # Induction should reduce score

    def test_complexity_penalty_long_proof(self):
        """Test complexity penalty for long proofs."""
        signals_short = {
            "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
            "confidence": 0.8,
            "proof_lines": 20,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 1,
        }

        signals_long = {
            "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
            "confidence": 0.8,
            "proof_lines": 40,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 1,
        }

        score_short = compute_success_likelihood(signals_short)
        score_long = compute_success_likelihood(signals_long)

        assert score_long < score_short  # Long proof should reduce score

    def test_complexity_penalty_many_local_lemmas(self):
        """Test complexity penalty for many local lemmas."""
        signals_few = {
            "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
            "confidence": 0.8,
            "proof_lines": 10,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 2,
        }

        signals_many = {
            "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
            "confidence": 0.8,
            "proof_lines": 10,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 5,
        }

        score_few = compute_success_likelihood(signals_few)
        score_many = compute_success_likelihood(signals_many)

        assert score_many < score_few  # Many local lemmas should reduce score

    def test_score_bounds(self):
        """Test that scores stay within [0.0, 1.0] bounds."""
        # Extreme high values
        signals_high = {
            "whole_goal_potential": {"aesop": 1.0, "grind": 1.0},
            "confidence": 1.0,
            "proof_lines": 5,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 0,
        }

        score_high = compute_success_likelihood(signals_high)
        assert 0.0 <= score_high <= 1.0

        # Extreme low values with high penalties
        signals_low = {
            "whole_goal_potential": {"aesop": 0.0, "grind": 0.0},
            "confidence": 0.0,
            "proof_lines": 100,
            "has_induction": True,
            "has_cases": True,
            "local_lemmas_count": 10,
        }

        score_low = compute_success_likelihood(signals_low)
        assert 0.0 <= score_low <= 1.0

    def test_missing_signals_defaults(self):
        """Test handling of missing signals with defaults."""
        signals = {}  # Empty signals

        score = compute_success_likelihood(signals)
        assert 0.0 <= score <= 1.0  # Should handle gracefully


class TestComputeImpact:
    """Test cases for compute_impact function."""

    def test_short_proof_low_impact(self):
        """Test that short proofs have low impact."""
        signals = {
            "proof_lines": 3,
            "annotation_value": 0.3,
            "local_lemmas_count": 0,
        }

        score = compute_impact(signals)
        assert score < 0.5  # Should be low for short proof
        assert score >= 0.0

    def test_long_proof_high_impact(self):
        """Test that long proofs have high impact."""
        signals = {
            "proof_lines": 50,
            "annotation_value": 0.8,
            "local_lemmas_count": 3,
        }

        score = compute_impact(signals)
        assert score > 0.7  # Should be high for long proof
        assert score <= 1.0

    def test_proof_length_score_saturation(self):
        """Test proof length score saturation at different thresholds."""
        # 0-5 lines: 0.2
        signals_5 = {"proof_lines": 5, "annotation_value": 0.0, "local_lemmas_count": 0}
        score_5 = compute_impact(signals_5)
        assert abs(score_5 - 0.1) < 0.05  # 0.5 * 0.2 = 0.1

        # 6-10 lines: 0.4
        signals_10 = {"proof_lines": 10, "annotation_value": 0.0, "local_lemmas_count": 0}
        score_10 = compute_impact(signals_10)
        assert abs(score_10 - 0.2) < 0.05  # 0.5 * 0.4 = 0.2

        # 11-20 lines: 0.6
        signals_20 = {"proof_lines": 20, "annotation_value": 0.0, "local_lemmas_count": 0}
        score_20 = compute_impact(signals_20)
        assert abs(score_20 - 0.3) < 0.05  # 0.5 * 0.6 = 0.3

        # 21-40 lines: 0.8
        signals_40 = {"proof_lines": 40, "annotation_value": 0.0, "local_lemmas_count": 0}
        score_40 = compute_impact(signals_40)
        assert abs(score_40 - 0.4) < 0.05  # 0.5 * 0.8 = 0.4

        # 40+ lines: 1.0
        signals_50 = {"proof_lines": 50, "annotation_value": 0.0, "local_lemmas_count": 0}
        score_50 = compute_impact(signals_50)
        assert abs(score_50 - 0.5) < 0.05  # 0.5 * 1.0 = 0.5

    def test_annotation_value_contribution(self):
        """Test annotation value contribution to impact."""
        signals_low = {
            "proof_lines": 15,
            "annotation_value": 0.2,
            "local_lemmas_count": 0,
        }

        signals_high = {
            "proof_lines": 15,
            "annotation_value": 0.9,
            "local_lemmas_count": 0,
        }

        score_low = compute_impact(signals_low)
        score_high = compute_impact(signals_high)

        assert score_high > score_low  # Higher annotation value should increase impact

    def test_reusability_score_contribution(self):
        """Test reusability score contribution from local lemmas."""
        signals_no_local = {
            "proof_lines": 15,
            "annotation_value": 0.5,
            "local_lemmas_count": 0,
        }

        signals_with_local = {
            "proof_lines": 15,
            "annotation_value": 0.5,
            "local_lemmas_count": 3,
        }

        score_no = compute_impact(signals_no_local)
        score_with = compute_impact(signals_with_local)

        assert score_with > score_no  # Local lemmas should increase impact

    def test_zero_proof_lines(self):
        """Test impact with zero proof lines."""
        signals = {
            "proof_lines": 0,
            "annotation_value": 0.5,
            "local_lemmas_count": 0,
        }

        score = compute_impact(signals)
        assert score < 0.3  # Should be low for no proof

    def test_score_bounds(self):
        """Test that scores stay within [0.0, 1.0] bounds."""
        signals = {
            "proof_lines": 100,
            "annotation_value": 1.0,
            "local_lemmas_count": 10,
        }

        score = compute_impact(signals)
        assert 0.0 <= score <= 1.0


class TestComputeSubgoalPotential:
    """Test cases for compute_subgoal_potential function."""

    def test_without_structure(self):
        """Test subgoal potential without deep structure."""
        signals = {
            "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
            "confidence": 0.8,
        }

        score = compute_subgoal_potential(signals, structure=None)
        assert score > 0.4  # Should be based on signals only
        assert score <= 1.0

    def test_with_structure_cases(self):
        """Test subgoal potential with cases in structure."""
        signals = {
            "subgoal_potential": {"aesop": 0.6, "grind": 0.5},
            "confidence": 0.8,
        }

        structure = {
            "cases": [{"name": "zero"}, {"name": "succ"}],
            "blocks": [],
        }

        score_without = compute_subgoal_potential(signals, structure=None)
        score_with = compute_subgoal_potential(signals, structure=structure)

        assert score_with > score_without  # Cases should boost score

    def test_with_structure_rewrite_simp_blocks(self):
        """Test subgoal potential with rewrite_simp blocks."""
        signals = {
            "subgoal_potential": {"aesop": 0.6, "grind": 0.5},
            "confidence": 0.8,
        }

        structure = {
            "cases": [],
            "blocks": [{"kind": "rewrite_simp"}, {"kind": "closing"}],
        }

        score_without = compute_subgoal_potential(signals, structure=None)
        score_with = compute_subgoal_potential(signals, structure=structure)

        assert score_with > score_without  # Rewrite_simp blocks should boost score

    def test_with_structure_multiple_blocks(self):
        """Test subgoal potential with multiple blocks."""
        signals = {
            "subgoal_potential": {"aesop": 0.6, "grind": 0.5},
            "confidence": 0.8,
        }

        structure = {
            "cases": [],
            "blocks": [{"kind": "skeleton"}, {"kind": "rewrite_simp"}, {"kind": "closing"}],
        }

        score = compute_subgoal_potential(signals, structure=structure)
        assert score > 0.5  # Multiple blocks should boost score

    def test_low_confidence_penalty(self):
        """Test that low confidence reduces subgoal potential."""
        signals_low = {
            "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
            "confidence": 0.3,
        }

        signals_high = {
            "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
            "confidence": 0.9,
        }

        score_low = compute_subgoal_potential(signals_low)
        score_high = compute_subgoal_potential(signals_high)

        assert score_high > score_low

    def test_score_bounds(self):
        """Test that scores stay within [0.0, 1.0] bounds."""
        signals = {
            "subgoal_potential": {"aesop": 1.0, "grind": 1.0},
            "confidence": 1.0,
        }

        structure = {
            "cases": [{"name": "a"}, {"name": "b"}],
            "blocks": [{"kind": "rewrite_simp"}, {"kind": "closing"}],
        }

        score = compute_subgoal_potential(signals, structure=structure)
        assert 0.0 <= score <= 1.0


class TestComputeRisk:
    """Test cases for compute_risk function."""

    def test_low_risk_simple_proof(self):
        """Test low risk for simple proof."""
        signals = {
            "rewrite_count": 1,
            "simp_count": 0,
            "local_lemmas_count": 0,
            "confidence": 0.9,
            "notes": [],
        }

        score = compute_risk(signals)
        assert score < 0.3  # Should be low risk
        assert score >= 0.0

    def test_high_risk_many_rewrites(self):
        """Test high risk for many rewrites."""
        signals = {
            "rewrite_count": 10,
            "simp_count": 1,
            "local_lemmas_count": 0,
            "confidence": 0.8,
            "notes": [],
        }

        score = compute_risk(signals)
        assert score > 0.1  # Should have some risk
        assert score <= 1.0

    def test_high_risk_many_simps(self):
        """Test high risk for many simps."""
        signals = {
            "rewrite_count": 1,
            "simp_count": 5,
            "local_lemmas_count": 0,
            "confidence": 0.8,
            "notes": [],
        }

        score = compute_risk(signals)
        assert score > 0.1  # Should have some risk

    def test_high_risk_simp_question_mark(self):
        """Test high risk for simp? in notes."""
        signals = {
            "rewrite_count": 1,
            "simp_count": 1,
            "local_lemmas_count": 0,
            "confidence": 0.8,
            "notes": ["consider using simp?"],
        }

        score = compute_risk(signals)
        assert score > 0.2  # Should have elevated risk due to simp?

    def test_high_risk_many_local_lemmas(self):
        """Test high risk for many local lemmas."""
        signals = {
            "rewrite_count": 1,
            "simp_count": 1,
            "local_lemmas_count": 5,
            "confidence": 0.8,
            "notes": [],
        }

        score = compute_risk(signals)
        assert score > 0.05  # Should have some risk

    def test_high_risk_low_confidence(self):
        """Test high risk for low confidence."""
        signals = {
            "rewrite_count": 1,
            "simp_count": 1,
            "local_lemmas_count": 0,
            "confidence": 0.3,
            "notes": [],
        }

        score = compute_risk(signals)
        assert score > 0.1  # Should have elevated risk

    def test_combined_risk_factors(self):
        """Test combined risk factors."""
        signals = {
            "rewrite_count": 8,
            "simp_count": 5,
            "local_lemmas_count": 4,
            "confidence": 0.4,
            "notes": ["simp? might help"],
        }

        score = compute_risk(signals)
        assert score > 0.3  # Should have high risk with multiple factors

    def test_score_bounds(self):
        """Test that scores stay within [0.0, 1.0] bounds."""
        # Extreme risk factors
        signals = {
            "rewrite_count": 100,
            "simp_count": 50,
            "local_lemmas_count": 20,
            "confidence": 0.1,
            "notes": ["simp?", "SIMP?", "use simp?"],
        }

        score = compute_risk(signals)
        assert 0.0 <= score <= 1.0


class TestScoreRounding:
    """Test that all component scores are properly rounded to 2 decimal places."""

    def test_success_likelihood_rounding(self):
        """Test success likelihood rounding."""
        signals = {
            "whole_goal_potential": {"aesop": 0.777, "grind": 0.333},
            "confidence": 0.666,
            "proof_lines": 7,
            "has_induction": False,
            "has_cases": False,
            "local_lemmas_count": 1,
        }

        score = compute_success_likelihood(signals)
        # Check that score has at most 2 decimal places
        assert len(str(score).split(".")[-1]) <= 2

    def test_impact_rounding(self):
        """Test impact rounding."""
        signals = {
            "proof_lines": 17,
            "annotation_value": 0.777,
            "local_lemmas_count": 2,
        }

        score = compute_impact(signals)
        assert len(str(score).split(".")[-1]) <= 2

    def test_subgoal_potential_rounding(self):
        """Test subgoal potential rounding."""
        signals = {
            "subgoal_potential": {"aesop": 0.666, "grind": 0.555},
            "confidence": 0.777,
        }

        score = compute_subgoal_potential(signals)
        assert len(str(score).split(".")[-1]) <= 2

    def test_risk_rounding(self):
        """Test risk rounding."""
        signals = {
            "rewrite_count": 3,
            "simp_count": 2,
            "local_lemmas_count": 1,
            "confidence": 0.777,
            "notes": [],
        }

        score = compute_risk(signals)
        assert len(str(score).split(".")[-1]) <= 2


class TestObjectiveWeights:
    """Test cases for objective weight configurations."""

    def test_maximize_success_weights(self):
        """Test maximize_success objective weights."""
        from lean_proof_auto_mcp.core.ranking import OBJECTIVE_WEIGHTS

        weights = OBJECTIVE_WEIGHTS["maximize_success"]

        assert weights["success_likelihood"] == 0.50
        assert weights["impact"] == 0.10
        assert weights["annotation_value"] == 0.10
        assert weights["subgoal_potential"] == 0.10
        assert weights["risk"] == -0.20

    def test_maximize_impact_weights(self):
        """Test maximize_impact objective weights."""
        from lean_proof_auto_mcp.core.ranking import OBJECTIVE_WEIGHTS

        weights = OBJECTIVE_WEIGHTS["maximize_impact"]

        assert weights["success_likelihood"] == 0.20
        assert weights["impact"] == 0.40
        assert weights["annotation_value"] == 0.30
        assert weights["subgoal_potential"] == 0.05
        assert weights["risk"] == -0.05

    def test_maximize_subgoal_automation_weights(self):
        """Test maximize_subgoal_automation objective weights."""
        from lean_proof_auto_mcp.core.ranking import OBJECTIVE_WEIGHTS

        weights = OBJECTIVE_WEIGHTS["maximize_subgoal_automation"]

        assert weights["success_likelihood"] == 0.15
        assert weights["impact"] == 0.15
        assert weights["annotation_value"] == 0.20
        assert weights["subgoal_potential"] == 0.40
        assert weights["risk"] == -0.10

    def test_balanced_weights(self):
        """Test balanced objective weights."""
        from lean_proof_auto_mcp.core.ranking import OBJECTIVE_WEIGHTS

        weights = OBJECTIVE_WEIGHTS["balanced"]

        assert weights["success_likelihood"] == 0.25
        assert weights["impact"] == 0.25
        assert weights["annotation_value"] == 0.20
        assert weights["subgoal_potential"] == 0.20
        assert weights["risk"] == -0.10

    def test_all_objectives_present(self):
        """Test that all expected objectives are present."""
        from lean_proof_auto_mcp.core.ranking import OBJECTIVE_WEIGHTS

        expected_objectives = [
            "maximize_success",
            "maximize_impact",
            "maximize_subgoal_automation",
            "balanced",
        ]

        for objective in expected_objectives:
            assert objective in OBJECTIVE_WEIGHTS


class TestComputeFinalScore:
    """Test cases for compute_final_score function."""

    def test_basic_score_computation(self):
        """Test basic final score computation."""
        from lean_proof_auto_mcp.core.ranking import compute_final_score

        components = ComponentScores(
            success_likelihood=0.8,
            impact=0.6,
            annotation_value=0.7,
            subgoal_potential=0.5,
            risk=0.2,
        )

        score = compute_final_score(components, "balanced")
        assert 0.0 <= score <= 1.0
        assert len(str(score).split(".")[-1]) <= 2  # Rounded to 2 decimals

    def test_maximize_success_objective(self):
        """Test final score with maximize_success objective."""
        from lean_proof_auto_mcp.core.ranking import compute_final_score

        components = ComponentScores(
            success_likelihood=0.9,
            impact=0.3,
            annotation_value=0.3,
            subgoal_potential=0.3,
            risk=0.1,
        )

        score = compute_final_score(components, "maximize_success")
        # Should be high due to high success_likelihood (weight 0.50)
        assert score > 0.4

    def test_maximize_impact_objective(self):
        """Test final score with maximize_impact objective."""
        from lean_proof_auto_mcp.core.ranking import compute_final_score

        components = ComponentScores(
            success_likelihood=0.3,
            impact=0.9,
            annotation_value=0.8,
            subgoal_potential=0.3,
            risk=0.1,
        )

        score = compute_final_score(components, "maximize_impact")
        # Should be high due to high impact (weight 0.40) and annotation_value (weight 0.30)
        assert score > 0.6

    def test_risk_penalty(self):
        """Test that risk reduces final score."""
        from lean_proof_auto_mcp.core.ranking import compute_final_score

        components_low_risk = ComponentScores(
            success_likelihood=0.8,
            impact=0.6,
            annotation_value=0.7,
            subgoal_potential=0.5,
            risk=0.1,
        )

        components_high_risk = ComponentScores(
            success_likelihood=0.8,
            impact=0.6,
            annotation_value=0.7,
            subgoal_potential=0.5,
            risk=0.8,
        )

        score_low = compute_final_score(components_low_risk, "balanced")
        score_high = compute_final_score(components_high_risk, "balanced")

        assert score_low > score_high  # Higher risk should reduce score

    def test_invalid_objective(self):
        """Test error handling for invalid objective."""
        from lean_proof_auto_mcp.core.ranking import compute_final_score

        components = ComponentScores(
            success_likelihood=0.8,
            impact=0.6,
            annotation_value=0.7,
            subgoal_potential=0.5,
            risk=0.2,
        )

        with pytest.raises(ValueError, match="Unknown objective"):
            compute_final_score(components, "invalid_objective")

    def test_score_bounds(self):
        """Test that final scores stay within [0.0, 1.0] bounds."""
        from lean_proof_auto_mcp.core.ranking import compute_final_score

        # Extreme high values
        components_high = ComponentScores(
            success_likelihood=1.0,
            impact=1.0,
            annotation_value=1.0,
            subgoal_potential=1.0,
            risk=0.0,
        )

        score_high = compute_final_score(components_high, "balanced")
        assert 0.0 <= score_high <= 1.0

        # Extreme low values
        components_low = ComponentScores(
            success_likelihood=0.0,
            impact=0.0,
            annotation_value=0.0,
            subgoal_potential=0.0,
            risk=1.0,
        )

        score_low = compute_final_score(components_low, "balanced")
        assert 0.0 <= score_low <= 1.0


class TestRankTheorems:
    """Test cases for rank_theorems function."""

    def test_basic_ranking(self):
        """Test basic theorem ranking."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        theorems = [
            TheoremData(
                theorem_id="theorem1",
                range={"start_line": 10, "end_line": 20},
                signals={
                    "whole_goal_potential": {"aesop": 0.9, "grind": 0.5},
                    "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
                    "annotation_value": 0.8,
                    "confidence": 0.9,
                    "proof_lines": 10,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 0,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="theorem2",
                range={"start_line": 30, "end_line": 40},
                signals={
                    "whole_goal_potential": {"aesop": 0.3, "grind": 0.2},
                    "subgoal_potential": {"aesop": 0.2, "grind": 0.3},
                    "annotation_value": 0.3,
                    "confidence": 0.5,
                    "proof_lines": 5,
                    "rewrite_count": 0,
                    "simp_count": 0,
                    "local_lemmas_count": 0,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
        ]

        ranked = rank_theorems(theorems, "balanced")

        assert len(ranked) == 2
        # theorem1 should rank higher than theorem2
        assert ranked[0].theorem_data.theorem_id == "theorem1"
        assert ranked[1].theorem_data.theorem_id == "theorem2"
        # Scores should be descending
        assert ranked[0].score >= ranked[1].score

    def test_stable_sorting_by_score(self):
        """Test that theorems are sorted by score descending."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        theorems = [
            TheoremData(
                theorem_id="low",
                range={"start_line": 10, "end_line": 20},
                signals={
                    "whole_goal_potential": {"aesop": 0.2, "grind": 0.1},
                    "subgoal_potential": {"aesop": 0.2, "grind": 0.1},
                    "annotation_value": 0.2,
                    "confidence": 0.5,
                    "proof_lines": 5,
                    "rewrite_count": 0,
                    "simp_count": 0,
                    "local_lemmas_count": 0,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="high",
                range={"start_line": 30, "end_line": 40},
                signals={
                    "whole_goal_potential": {"aesop": 0.9, "grind": 0.8},
                    "subgoal_potential": {"aesop": 0.8, "grind": 0.7},
                    "annotation_value": 0.9,
                    "confidence": 0.9,
                    "proof_lines": 20,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 2,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="medium",
                range={"start_line": 50, "end_line": 60},
                signals={
                    "whole_goal_potential": {"aesop": 0.6, "grind": 0.5},
                    "subgoal_potential": {"aesop": 0.5, "grind": 0.5},
                    "annotation_value": 0.6,
                    "confidence": 0.7,
                    "proof_lines": 12,
                    "rewrite_count": 1,
                    "simp_count": 1,
                    "local_lemmas_count": 1,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
        ]

        ranked = rank_theorems(theorems, "balanced")

        # Verify descending order
        for i in range(len(ranked) - 1):
            assert ranked[i].score >= ranked[i + 1].score

    def test_tie_breaking_by_theorem_id(self):
        """Test tie-breaking by theorem_id when scores are equal."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        # Create theorems with identical signals (should produce same scores)
        signals = {
            "whole_goal_potential": {"aesop": 0.5, "grind": 0.5},
            "subgoal_potential": {"aesop": 0.5, "grind": 0.5},
            "annotation_value": 0.5,
            "confidence": 0.7,
            "proof_lines": 10,
            "rewrite_count": 1,
            "simp_count": 1,
            "local_lemmas_count": 1,
            "has_induction": False,
            "has_cases": False,
            "notes": [],
        }

        theorems = [
            TheoremData(
                theorem_id="zebra",
                range={"start_line": 10, "end_line": 20},
                signals=signals.copy(),
            ),
            TheoremData(
                theorem_id="apple",
                range={"start_line": 30, "end_line": 40},
                signals=signals.copy(),
            ),
            TheoremData(
                theorem_id="middle",
                range={"start_line": 50, "end_line": 60},
                signals=signals.copy(),
            ),
        ]

        ranked = rank_theorems(theorems, "balanced")

        # Should be sorted by theorem_id lexicographically
        assert ranked[0].theorem_data.theorem_id == "apple"
        assert ranked[1].theorem_data.theorem_id == "middle"
        assert ranked[2].theorem_data.theorem_id == "zebra"

    def test_tie_breaking_by_start_line(self):
        """Test tie-breaking by start_line when scores and theorem_id are equal."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        signals = {
            "whole_goal_potential": {"aesop": 0.5, "grind": 0.5},
            "subgoal_potential": {"aesop": 0.5, "grind": 0.5},
            "annotation_value": 0.5,
            "confidence": 0.7,
            "proof_lines": 10,
            "rewrite_count": 1,
            "simp_count": 1,
            "local_lemmas_count": 1,
            "has_induction": False,
            "has_cases": False,
            "notes": [],
        }

        theorems = [
            TheoremData(
                theorem_id="same_name",
                range={"start_line": 50, "end_line": 60},
                signals=signals.copy(),
            ),
            TheoremData(
                theorem_id="same_name",
                range={"start_line": 10, "end_line": 20},
                signals=signals.copy(),
            ),
            TheoremData(
                theorem_id="same_name",
                range={"start_line": 30, "end_line": 40},
                signals=signals.copy(),
            ),
        ]

        ranked = rank_theorems(theorems, "balanced")

        # Should be sorted by start_line ascending
        assert ranked[0].theorem_data.range["start_line"] == 10
        assert ranked[1].theorem_data.range["start_line"] == 30
        assert ranked[2].theorem_data.range["start_line"] == 50

    def test_confidence_filtering(self):
        """Test confidence-based filtering."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        theorems = [
            TheoremData(
                theorem_id="high_conf",
                range={"start_line": 10, "end_line": 20},
                signals={
                    "whole_goal_potential": {"aesop": 0.8, "grind": 0.5},
                    "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
                    "annotation_value": 0.8,
                    "confidence": 0.9,
                    "proof_lines": 10,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 0,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="low_conf",
                range={"start_line": 30, "end_line": 40},
                signals={
                    "whole_goal_potential": {"aesop": 0.9, "grind": 0.8},
                    "subgoal_potential": {"aesop": 0.8, "grind": 0.7},
                    "annotation_value": 0.9,
                    "confidence": 0.3,  # Below threshold
                    "proof_lines": 15,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 1,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
        ]

        ranked = rank_theorems(theorems, "balanced", min_confidence=0.5)

        # Only high_conf should be included
        assert len(ranked) == 1
        assert ranked[0].theorem_data.theorem_id == "high_conf"

    def test_invalid_min_confidence(self):
        """Test error handling for invalid min_confidence."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        theorems = [
            TheoremData(
                theorem_id="test",
                range={"start_line": 10, "end_line": 20},
                signals={"confidence": 0.8},
            ),
        ]

        with pytest.raises(ValueError, match="min_confidence must be in \\[0.0, 1.0\\]"):
            rank_theorems(theorems, "balanced", min_confidence=1.5)

    def test_empty_theorem_list(self):
        """Test ranking empty theorem list."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        ranked = rank_theorems([], "balanced")
        assert len(ranked) == 0

    def test_different_objectives_produce_different_rankings(self):
        """Test that different objectives produce different rankings."""
        from lean_proof_auto_mcp.core.ranking import rank_theorems

        # Create theorems with different strengths
        theorems = [
            TheoremData(
                theorem_id="high_success",
                range={"start_line": 10, "end_line": 20},
                signals={
                    "whole_goal_potential": {"aesop": 0.9, "grind": 0.5},
                    "subgoal_potential": {"aesop": 0.7, "grind": 0.6},
                    "annotation_value": 0.3,
                    "confidence": 0.9,
                    "proof_lines": 5,
                    "rewrite_count": 0,
                    "simp_count": 0,
                    "local_lemmas_count": 0,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
            TheoremData(
                theorem_id="high_impact",
                range={"start_line": 30, "end_line": 40},
                signals={
                    "whole_goal_potential": {"aesop": 0.3, "grind": 0.2},
                    "subgoal_potential": {"aesop": 0.2, "grind": 0.3},
                    "annotation_value": 0.9,
                    "confidence": 0.7,
                    "proof_lines": 50,
                    "rewrite_count": 1,
                    "simp_count": 0,
                    "local_lemmas_count": 5,
                    "has_induction": False,
                    "has_cases": False,
                    "notes": [],
                },
            ),
        ]

        ranked_success = rank_theorems(theorems, "maximize_success")
        ranked_impact = rank_theorems(theorems, "maximize_impact")

        # Different objectives should produce different rankings
        assert ranked_success[0].theorem_data.theorem_id != ranked_impact[0].theorem_data.theorem_id


class TestRankedTheorem:
    """Test cases for RankedTheorem dataclass."""

    def test_valid_ranked_theorem(self):
        """Test creating valid RankedTheorem."""
        from lean_proof_auto_mcp.core.ranking import RankedTheorem

        theorem_data = TheoremData(
            theorem_id="test",
            range={"start_line": 10, "end_line": 20},
            signals={"confidence": 0.8},
        )

        components = ComponentScores(
            success_likelihood=0.75,
            impact=0.60,
            annotation_value=0.70,
            subgoal_potential=0.65,
            risk=0.20,
        )

        ranked = RankedTheorem(
            theorem_data=theorem_data,
            score=0.68,
            components=components,
        )

        assert ranked.theorem_data.theorem_id == "test"
        assert ranked.score == 0.68
        assert ranked.components.success_likelihood == 0.75

    def test_invalid_score_low(self):
        """Test validation of score (too low)."""
        from lean_proof_auto_mcp.core.ranking import RankedTheorem

        theorem_data = TheoremData(
            theorem_id="test",
            range={"start_line": 10, "end_line": 20},
            signals={},
        )

        components = ComponentScores(
            success_likelihood=0.75,
            impact=0.60,
            annotation_value=0.70,
            subgoal_potential=0.65,
            risk=0.20,
        )

        with pytest.raises(ValueError, match="score must be in \\[0.0, 1.0\\]"):
            RankedTheorem(
                theorem_data=theorem_data,
                score=-0.1,
                components=components,
            )

    def test_invalid_score_high(self):
        """Test validation of score (too high)."""
        from lean_proof_auto_mcp.core.ranking import RankedTheorem

        theorem_data = TheoremData(
            theorem_id="test",
            range={"start_line": 10, "end_line": 20},
            signals={},
        )

        components = ComponentScores(
            success_likelihood=0.75,
            impact=0.60,
            annotation_value=0.70,
            subgoal_potential=0.65,
            risk=0.20,
        )

        with pytest.raises(ValueError, match="score must be in \\[0.0, 1.0\\]"):
            RankedTheorem(
                theorem_data=theorem_data,
                score=1.5,
                components=components,
            )
