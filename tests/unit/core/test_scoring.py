"""Unit tests for core.scoring module."""

import pytest

from lean_proof_auto_mcp.core.features import TheoremFeatures
from lean_proof_auto_mcp.core.scoring import (
    AutomationProfile,
    compute_profile,
    score_aesop_potential,
    score_annotation_value,
    score_grind_potential,
)
from lean_proof_auto_mcp.core.segmenter import CaseBlock, ProofBlock, ProofStructure
from lean_proof_auto_mcp.core.source import Span


class TestAutomationProfile:
    """Test cases for AutomationProfile dataclass."""

    def test_valid_profile(self):
        """Test creating valid AutomationProfile."""
        profile = AutomationProfile(
            whole_goal_potential={"aesop": 0.8, "grind": 0.3},
            subgoal_potential={"aesop": 0.6, "grind": 0.7},
            annotation_value=0.75,
            notes=["short proof", "uses induction"],
        )

        assert profile.whole_goal_potential["aesop"] == 0.8
        assert profile.whole_goal_potential["grind"] == 0.3
        assert profile.subgoal_potential["aesop"] == 0.6
        assert profile.subgoal_potential["grind"] == 0.7
        assert profile.annotation_value == 0.75
        assert profile.notes == ["short proof", "uses induction"]

    def test_invalid_whole_goal_score_low(self):
        """Test validation of whole_goal_potential (too low)."""
        with pytest.raises(
            ValueError, match="whole_goal_potential\\[aesop\\] must be in \\[0.0, 1.0\\]"
        ):
            AutomationProfile(
                whole_goal_potential={"aesop": -0.1, "grind": 0.3},
                subgoal_potential={"aesop": 0.6, "grind": 0.7},
                annotation_value=0.75,
                notes=[],
            )

    def test_invalid_whole_goal_score_high(self):
        """Test validation of whole_goal_potential (too high)."""
        with pytest.raises(
            ValueError, match="whole_goal_potential\\[grind\\] must be in \\[0.0, 1.0\\]"
        ):
            AutomationProfile(
                whole_goal_potential={"aesop": 0.8, "grind": 1.1},
                subgoal_potential={"aesop": 0.6, "grind": 0.7},
                annotation_value=0.75,
                notes=[],
            )

    def test_invalid_subgoal_score(self):
        """Test validation of subgoal_potential."""
        with pytest.raises(
            ValueError, match="subgoal_potential\\[aesop\\] must be in \\[0.0, 1.0\\]"
        ):
            AutomationProfile(
                whole_goal_potential={"aesop": 0.8, "grind": 0.3},
                subgoal_potential={"aesop": 1.5, "grind": 0.7},
                annotation_value=0.75,
                notes=[],
            )

    def test_invalid_annotation_value(self):
        """Test validation of annotation_value."""
        with pytest.raises(ValueError, match="annotation_value must be in \\[0.0, 1.0\\]"):
            AutomationProfile(
                whole_goal_potential={"aesop": 0.8, "grind": 0.3},
                subgoal_potential={"aesop": 0.6, "grind": 0.7},
                annotation_value=1.2,
                notes=[],
            )

    def test_too_many_notes(self):
        """Test validation of notes count."""
        with pytest.raises(ValueError, match="Too many notes: 11. Maximum is 10."):
            AutomationProfile(
                whole_goal_potential={"aesop": 0.8, "grind": 0.3},
                subgoal_potential={"aesop": 0.6, "grind": 0.7},
                annotation_value=0.75,
                notes=["note"] * 11,  # 11 notes, max is 10
            )

    def test_note_too_long(self):
        """Test validation of note length."""
        long_note = "x" * 201  # 201 chars, max is 200
        with pytest.raises(ValueError, match="Note too long: 201 chars. Maximum is 200."):
            AutomationProfile(
                whole_goal_potential={"aesop": 0.8, "grind": 0.3},
                subgoal_potential={"aesop": 0.6, "grind": 0.7},
                annotation_value=0.75,
                notes=[long_note],
            )


class TestScoreAesopPotential:
    """Test cases for score_aesop_potential function."""

    def test_no_proof(self):
        """Test scoring theorem with no proof."""
        features = TheoremFeatures(
            proof_lines=0,
            tactic_kinds=set(),
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.0,
        )

        score = score_aesop_potential(features)
        assert score == 0.0

    def test_structural_proof_short(self):
        """Test scoring short structural proof (good for aesop)."""
        features = TheoremFeatures(
            proof_lines=3,
            tactic_kinds={"intro", "constructor", "exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.9,
        )

        score = score_aesop_potential(features)
        assert score > 0.7  # Should be high for short structural proof
        assert score <= 1.0

    def test_rewrite_heavy_proof(self):
        """Test scoring rewrite-heavy proof (bad for aesop)."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"rw", "simp"},
            has_induction=False,
            has_cases=False,
            rewrite_count=8,
            simp_count=5,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score = score_aesop_potential(features)
        assert score < 0.5  # Should be low due to heavy rewriting
        assert score >= 0.0

    def test_medium_length_proof(self):
        """Test scoring medium-length proof."""
        features = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"intro", "apply", "cases"},
            has_induction=False,
            has_cases=True,
            rewrite_count=1,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.7,
        )

        score = score_aesop_potential(features)
        assert 0.3 <= score <= 0.8  # Medium score for medium complexity

    def test_long_proof(self):
        """Test scoring long proof (less suitable for aesop)."""
        features = TheoremFeatures(
            proof_lines=50,
            tactic_kinds={"intro", "apply"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score = score_aesop_potential(features)
        assert score < 0.7  # Should be lower for long proofs

    def test_high_confidence_boost(self):
        """Test that high confidence boosts aesop score."""
        features_low_conf = TheoremFeatures(
            proof_lines=5,
            tactic_kinds={"intro"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.5,
        )

        features_high_conf = TheoremFeatures(
            proof_lines=5,
            tactic_kinds={"intro"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.9,
        )

        score_low = score_aesop_potential(features_low_conf)
        score_high = score_aesop_potential(features_high_conf)

        assert score_high > score_low


class TestScoreGrindPotential:
    """Test cases for score_grind_potential function."""

    def test_no_proof(self):
        """Test scoring theorem with no proof."""
        features = TheoremFeatures(
            proof_lines=0,
            tactic_kinds=set(),
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.0,
        )

        score = score_grind_potential(features)
        assert score == 0.0

    def test_rewrite_heavy_proof(self):
        """Test scoring rewrite-heavy proof (good for grind)."""
        features = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"rw", "simp", "ring_nf"},
            has_induction=False,
            has_cases=False,
            rewrite_count=10,
            simp_count=5,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score = score_grind_potential(features)
        assert score > 0.6  # Should be high for rewrite-heavy proof
        assert score <= 1.0

    def test_structural_proof_with_induction(self):
        """Test scoring structural proof with induction (bad for grind)."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "induction", "cases"},
            has_induction=True,
            has_cases=True,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score = score_grind_potential(features)
        assert score < 0.4  # Should be low due to induction/cases
        assert score >= 0.0

    def test_algebraic_tactics_boost(self):
        """Test that algebraic tactics boost grind score."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"linarith", "omega", "norm_num"},
            has_induction=False,
            has_cases=False,
            rewrite_count=2,
            simp_count=1,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score = score_grind_potential(features)
        assert score > 0.5  # Should be boosted by algebraic tactics

    def test_medium_length_optimal(self):
        """Test that medium-length proofs are optimal for grind."""
        features_short = TheoremFeatures(
            proof_lines=3,
            tactic_kinds={"rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=2,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        features_medium = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=2,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score_short = score_grind_potential(features_short)
        score_medium = score_grind_potential(features_medium)

        assert score_medium > score_short


class TestScoreAnnotationValue:
    """Test cases for score_annotation_value function."""

    def test_no_proof(self):
        """Test scoring theorem with no proof."""
        features = TheoremFeatures(
            proof_lines=0,
            tactic_kinds=set(),
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.0,
        )

        score = score_annotation_value(features)
        assert score == 0.0

    def test_long_proof_high_value(self):
        """Test that long proofs have high annotation value."""
        features = TheoremFeatures(
            proof_lines=25,
            tactic_kinds={"intro", "rw", "simp", "apply"},
            has_induction=False,
            has_cases=False,
            rewrite_count=5,
            simp_count=3,
            local_lemmas_count=2,
            confidence=0.8,
        )

        score = score_annotation_value(features)
        assert score > 0.7  # Should be high for long, complex proof
        assert score <= 1.0

    def test_short_proof_low_value(self):
        """Test that short proofs have lower annotation value."""
        features = TheoremFeatures(
            proof_lines=2,
            tactic_kinds={"exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score = score_annotation_value(features)
        assert score < 0.5  # Should be low for short proof

    def test_local_lemmas_boost(self):
        """Test that local lemmas boost annotation value."""
        features_no_local = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=2,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        features_with_local = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "rw", "have"},
            has_induction=False,
            has_cases=False,
            rewrite_count=2,
            simp_count=0,
            local_lemmas_count=3,
            confidence=0.8,
        )

        score_no_local = score_annotation_value(features_no_local)
        score_with_local = score_annotation_value(features_with_local)

        assert score_with_local > score_no_local

    def test_tactic_diversity_boost(self):
        """Test that tactic diversity boosts annotation value."""
        features_simple = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=5,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.8,
        )

        features_diverse = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "rw", "simp", "apply", "exact", "cases"},
            has_induction=False,
            has_cases=True,
            rewrite_count=2,
            simp_count=1,
            local_lemmas_count=0,
            confidence=0.8,
        )

        score_simple = score_annotation_value(features_simple)
        score_diverse = score_annotation_value(features_diverse)

        assert score_diverse > score_simple

    def test_low_confidence_penalty(self):
        """Test that low confidence reduces annotation value."""
        features_low_conf = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"intro", "rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=3,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.3,
        )

        features_high_conf = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"intro", "rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=3,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.9,
        )

        score_low = score_annotation_value(features_low_conf)
        score_high = score_annotation_value(features_high_conf)

        assert score_high > score_low


class TestComputeProfile:
    """Test cases for compute_profile function."""

    def test_basic_profile_computation(self):
        """Test basic profile computation without structure."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "rw", "exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=3,
            simp_count=1,
            local_lemmas_count=1,
            confidence=0.8,
        )

        profile = compute_profile(features)

        # Check that all required fields are present
        assert "aesop" in profile.whole_goal_potential
        assert "grind" in profile.whole_goal_potential
        assert "aesop" in profile.subgoal_potential
        assert "grind" in profile.subgoal_potential

        # Check score ranges
        assert 0.0 <= profile.whole_goal_potential["aesop"] <= 1.0
        assert 0.0 <= profile.whole_goal_potential["grind"] <= 1.0
        assert 0.0 <= profile.subgoal_potential["aesop"] <= 1.0
        assert 0.0 <= profile.subgoal_potential["grind"] <= 1.0
        assert 0.0 <= profile.annotation_value <= 1.0

        # Check that scores are rounded to 2 decimal places
        assert len(str(profile.whole_goal_potential["aesop"]).split(".")[-1]) <= 2
        assert len(str(profile.annotation_value).split(".")[-1]) <= 2

        # Check that notes are generated
        assert isinstance(profile.notes, list)
        assert len(profile.notes) <= 10

    def test_profile_with_structure(self):
        """Test profile computation with proof structure."""
        features = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"induction", "cases", "rw", "simp"},
            has_induction=True,
            has_cases=True,
            rewrite_count=5,
            simp_count=3,
            local_lemmas_count=0,
            confidence=0.8,
        )

        structure = ProofStructure(
            skeleton=["induction", "cases"],
            blocks=[
                ProofBlock("skeleton", Span(1, 0, 5, 0)),
                ProofBlock("rewrite_simp", Span(6, 0, 10, 0)),
                ProofBlock("closing", Span(11, 0, 15, 0)),
            ],
            cases=[CaseBlock("zero", Span(2, 0, 4, 0)), CaseBlock("succ", Span(6, 0, 14, 0))],
        )

        profile = compute_profile(features, structure)

        # Subgoal scores should be enhanced due to structure
        assert profile.subgoal_potential["aesop"] > 0.0  # Should be boosted by cases

        # Notes should mention structural elements
        notes_text = " ".join(profile.notes)
        assert any(keyword in notes_text for keyword in ["induction", "cases", "rewrite"])

    def test_empty_proof_profile(self):
        """Test profile computation for empty proof."""
        features = TheoremFeatures(
            proof_lines=0,
            tactic_kinds=set(),
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.0,
        )

        profile = compute_profile(features)

        # All scores should be 0.0 for empty proof
        assert profile.whole_goal_potential["aesop"] == 0.0
        assert profile.whole_goal_potential["grind"] == 0.0
        assert profile.subgoal_potential["aesop"] == 0.0
        assert profile.subgoal_potential["grind"] == 0.0
        assert profile.annotation_value == 0.0

        # Should have note about no proof
        assert "no proof found" in profile.notes

    def test_structural_proof_profile(self):
        """Test profile for structural proof (good for aesop)."""
        features = TheoremFeatures(
            proof_lines=5,
            tactic_kinds={"intro", "constructor", "exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.9,
        )

        profile = compute_profile(features)

        # Aesop should score higher than grind for structural proof
        assert profile.whole_goal_potential["aesop"] > profile.whole_goal_potential["grind"]

        # Should have appropriate notes (5 lines doesn't qualify as "short proof" which is ≤ 3)
        notes_text = " ".join(profile.notes)
        assert "good aesop candidate" in notes_text

    def test_rewrite_heavy_profile(self):
        """Test profile for rewrite-heavy proof (good for grind)."""
        features = TheoremFeatures(
            proof_lines=20,
            tactic_kinds={"rw", "simp", "ring_nf"},
            has_induction=False,
            has_cases=False,
            rewrite_count=15,
            simp_count=8,
            local_lemmas_count=0,
            confidence=0.8,
        )

        profile = compute_profile(features)

        # Grind should score higher than aesop for rewrite-heavy proof
        assert profile.whole_goal_potential["grind"] > profile.whole_goal_potential["aesop"]

        # Should have appropriate notes
        notes_text = " ".join(profile.notes)
        assert any(keyword in notes_text for keyword in ["rewrite", "simp"])

    def test_high_annotation_value_profile(self):
        """Test profile with high annotation value."""
        features = TheoremFeatures(
            proof_lines=30,
            tactic_kinds={"intro", "have", "rw", "simp", "apply", "exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=8,
            simp_count=4,
            local_lemmas_count=5,
            confidence=0.9,
        )

        profile = compute_profile(features)

        # Should have high annotation value
        assert profile.annotation_value > 0.7

        # Should have appropriate notes
        notes_text = " ".join(profile.notes)
        assert any(keyword in notes_text for keyword in ["long proof", "local lemmas"])


class TestIntegrationScenarios:
    """Test integration scenarios with realistic theorem features."""

    def test_mathlib_induction_proof(self):
        """Test scoring for typical Mathlib induction proof."""
        features = TheoremFeatures(
            proof_lines=12,
            tactic_kinds={"induction", "simp", "rw", "exact"},
            has_induction=True,
            has_cases=False,
            rewrite_count=3,
            simp_count=4,
            local_lemmas_count=0,
            confidence=0.85,
        )

        structure = ProofStructure(
            skeleton=["induction"],
            blocks=[
                ProofBlock("skeleton", Span(1, 0, 3, 0)),
                ProofBlock("rewrite_simp", Span(4, 0, 8, 0)),
                ProofBlock("closing", Span(9, 0, 12, 0)),
            ],
            cases=[CaseBlock("zero", Span(2, 0, 5, 0)), CaseBlock("succ", Span(6, 0, 11, 0))],
        )

        profile = compute_profile(features, structure)

        # Aesop subgoal should be boosted due to induction cases
        assert profile.subgoal_potential["aesop"] > profile.whole_goal_potential["aesop"]

        # Should have reasonable annotation value for medium complexity (enhanced scoring)
        assert 0.3 <= profile.annotation_value <= 0.9

        # Should mention key characteristics
        notes_text = " ".join(profile.notes)
        assert "induction" in notes_text
        assert "case branches" in notes_text

    def test_algebraic_manipulation_proof(self):
        """Test scoring for algebraic manipulation proof."""
        features = TheoremFeatures(
            proof_lines=18,
            tactic_kinds={"rw", "simp", "ring_nf", "linarith"},
            has_induction=False,
            has_cases=False,
            rewrite_count=12,
            simp_count=6,
            local_lemmas_count=2,
            confidence=0.8,
        )

        structure = ProofStructure(
            skeleton=[],
            blocks=[
                ProofBlock("rewrite_simp", Span(1, 0, 15, 0)),
                ProofBlock("closing", Span(16, 0, 18, 0)),
            ],
            cases=[],
        )

        profile = compute_profile(features, structure)

        # Grind should score much higher than aesop
        assert profile.whole_goal_potential["grind"] > 0.6
        assert profile.whole_goal_potential["grind"] > profile.whole_goal_potential["aesop"] + 0.2

        # Should have good annotation value due to complexity
        assert profile.annotation_value > 0.5

        # Should mention rewrite characteristics
        notes_text = " ".join(profile.notes)
        assert "rewrite" in notes_text

    def test_simple_constructor_proof(self):
        """Test scoring for simple constructor proof."""
        features = TheoremFeatures(
            proof_lines=3,
            tactic_kinds={"constructor", "exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.9,
        )

        profile = compute_profile(features)

        # Aesop should score high for simple structural proof
        assert profile.whole_goal_potential["aesop"] > 0.6

        # Annotation value should be moderate for simple but high-confidence proof
        assert profile.annotation_value < 0.5

        # Should mention short proof
        notes_text = " ".join(profile.notes)
        assert "short proof" in notes_text

    def test_complex_mixed_proof(self):
        """Test scoring for complex proof with mixed tactics."""
        features = TheoremFeatures(
            proof_lines=35,
            tactic_kinds={"intro", "induction", "cases", "rw", "simp", "have", "apply", "exact"},
            has_induction=True,
            has_cases=True,
            rewrite_count=8,
            simp_count=5,
            local_lemmas_count=4,
            confidence=0.75,
        )

        structure = ProofStructure(
            skeleton=["intro", "induction", "cases"],
            blocks=[
                ProofBlock("skeleton", Span(1, 0, 10, 0)),
                ProofBlock("rewrite_simp", Span(11, 0, 25, 0)),
                ProofBlock("closing", Span(26, 0, 35, 0)),
            ],
            cases=[CaseBlock("base", Span(5, 0, 12, 0)), CaseBlock("step", Span(13, 0, 30, 0))],
        )

        profile = compute_profile(features, structure)

        # Should have high annotation value due to complexity
        assert profile.annotation_value > 0.7

        # Both automation tools should have reasonable subgoal potential
        assert profile.subgoal_potential["aesop"] > 0.3
        assert profile.subgoal_potential["grind"] > 0.3

        # Should mention complexity indicators
        notes_text = " ".join(profile.notes)
        assert any(keyword in notes_text for keyword in ["long proof", "complex", "local lemmas"])


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_maximum_scores(self):
        """Test that scores can reach maximum values."""
        # Create features that should maximize aesop score
        aesop_features = TheoremFeatures(
            proof_lines=3,
            tactic_kinds={"intro", "constructor", "apply", "exact"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=1.0,
        )

        aesop_score = score_aesop_potential(aesop_features)
        assert aesop_score > 0.8  # Should be very high

        # Create features that should maximize grind score
        grind_features = TheoremFeatures(
            proof_lines=15,
            tactic_kinds={"rw", "simp", "linarith", "omega"},
            has_induction=False,
            has_cases=False,
            rewrite_count=10,
            simp_count=8,
            local_lemmas_count=0,
            confidence=1.0,
        )

        grind_score = score_grind_potential(grind_features)
        assert grind_score > 0.7  # Should be very high

    def test_minimum_scores(self):
        """Test that scores can reach minimum values."""
        # Empty proof should give minimum scores
        empty_features = TheoremFeatures(
            proof_lines=0,
            tactic_kinds=set(),
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.0,
        )

        assert score_aesop_potential(empty_features) == 0.0
        assert score_grind_potential(empty_features) == 0.0
        assert score_annotation_value(empty_features) == 0.0

    def test_score_bounds_enforcement(self):
        """Test that all scores stay within [0.0, 1.0] bounds."""
        # Create extreme features that might push scores out of bounds
        extreme_features = TheoremFeatures(
            proof_lines=1000,  # Very long
            tactic_kinds={"intro", "rw", "simp", "apply", "exact", "have", "cases", "induction"},
            has_induction=True,
            has_cases=True,
            rewrite_count=100,
            simp_count=50,
            local_lemmas_count=20,
            confidence=1.0,
        )

        profile = compute_profile(extreme_features)

        # All scores must be in valid range
        assert 0.0 <= profile.whole_goal_potential["aesop"] <= 1.0
        assert 0.0 <= profile.whole_goal_potential["grind"] <= 1.0
        assert 0.0 <= profile.subgoal_potential["aesop"] <= 1.0
        assert 0.0 <= profile.subgoal_potential["grind"] <= 1.0
        assert 0.0 <= profile.annotation_value <= 1.0

    def test_rounding_precision(self):
        """Test that scores are properly rounded to 2 decimal places."""
        features = TheoremFeatures(
            proof_lines=7,  # Chosen to create non-round scores
            tactic_kinds={"intro", "rw"},
            has_induction=False,
            has_cases=False,
            rewrite_count=3,
            simp_count=1,
            local_lemmas_count=1,
            confidence=0.777,  # Non-round confidence
        )

        profile = compute_profile(features)

        # Check that all scores are rounded to 2 decimal places
        for score in profile.whole_goal_potential.values():
            decimal_part = str(score).split(".")[-1] if "." in str(score) else ""
            assert len(decimal_part) <= 2

        for score in profile.subgoal_potential.values():
            decimal_part = str(score).split(".")[-1] if "." in str(score) else ""
            assert len(decimal_part) <= 2

        decimal_part = (
            str(profile.annotation_value).split(".")[-1]
            if "." in str(profile.annotation_value)
            else ""
        )
        assert len(decimal_part) <= 2
