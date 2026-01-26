"""Unit tests for core.scoring module."""

import pytest

from lean_proof_auto_mcp.core.config import load_default_config
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

# Load default config once for all tests
DEFAULT_CONFIG = load_default_config()


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

        score = score_aesop_potential(features, DEFAULT_CONFIG.aesop_scoring)
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

        score = score_aesop_potential(features, DEFAULT_CONFIG.aesop_scoring)
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

        score = score_aesop_potential(features, DEFAULT_CONFIG.aesop_scoring)
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

        score = score_aesop_potential(features, DEFAULT_CONFIG.aesop_scoring)
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

        score = score_aesop_potential(features, DEFAULT_CONFIG.aesop_scoring)
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

        score_low = score_aesop_potential(features_low_conf, DEFAULT_CONFIG.aesop_scoring)
        score_high = score_aesop_potential(features_high_conf, DEFAULT_CONFIG.aesop_scoring)

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

        score = score_grind_potential(features, DEFAULT_CONFIG.grind_scoring)
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

        score = score_grind_potential(features, DEFAULT_CONFIG.grind_scoring)
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

        score = score_grind_potential(features, DEFAULT_CONFIG.grind_scoring)
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

        score = score_grind_potential(features, DEFAULT_CONFIG.grind_scoring)
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

        score_short = score_grind_potential(features_short, DEFAULT_CONFIG.grind_scoring)
        score_medium = score_grind_potential(features_medium, DEFAULT_CONFIG.grind_scoring)

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

        score = score_annotation_value(features, DEFAULT_CONFIG.annotation_value_scoring)
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

        score = score_annotation_value(features, DEFAULT_CONFIG.annotation_value_scoring)
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

        score = score_annotation_value(features, DEFAULT_CONFIG.annotation_value_scoring)
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

        score_no_local = score_annotation_value(
            features_no_local, DEFAULT_CONFIG.annotation_value_scoring
        )
        score_with_local = score_annotation_value(
            features_with_local, DEFAULT_CONFIG.annotation_value_scoring
        )

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

        score_simple = score_annotation_value(
            features_simple, DEFAULT_CONFIG.annotation_value_scoring
        )
        score_diverse = score_annotation_value(
            features_diverse, DEFAULT_CONFIG.annotation_value_scoring
        )

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

        score_low = score_annotation_value(
            features_low_conf, DEFAULT_CONFIG.annotation_value_scoring
        )
        score_high = score_annotation_value(
            features_high_conf, DEFAULT_CONFIG.annotation_value_scoring
        )

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, structure, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, structure, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, structure, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, structure, config=DEFAULT_CONFIG)

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

        aesop_score = score_aesop_potential(aesop_features, DEFAULT_CONFIG.aesop_scoring)
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

        grind_score = score_grind_potential(grind_features, DEFAULT_CONFIG.grind_scoring)
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

        assert score_aesop_potential(empty_features, DEFAULT_CONFIG.aesop_scoring) == 0.0
        assert score_grind_potential(empty_features, DEFAULT_CONFIG.grind_scoring) == 0.0
        assert (
            score_annotation_value(empty_features, DEFAULT_CONFIG.annotation_value_scoring) == 0.0
        )

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

        profile = compute_profile(extreme_features, config=DEFAULT_CONFIG)

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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

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


class TestConfidenceInNotes:
    """Test that numeric confidence is included in notes."""

    def test_generate_notes_includes_numeric_confidence(self):
        """Test that notes include numeric confidence value."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "apply"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.85,
        )

        profile = compute_profile(features, config=DEFAULT_CONFIG)

        # Check numeric confidence is in notes
        assert any("confidence: 0.85" in note for note in profile.notes), (
            f"Expected 'confidence: 0.85' in notes, got: {profile.notes}"
        )
        # Check qualitative note is also present
        assert any("high confidence" in note.lower() for note in profile.notes), (
            f"Expected 'high confidence' in notes, got: {profile.notes}"
        )

    def test_generate_notes_no_confidence_when_zero(self):
        """Test that zero confidence doesn't add numeric note."""
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

        profile = compute_profile(features, config=DEFAULT_CONFIG)

        # No numeric confidence note when zero
        assert not any("confidence:" in note for note in profile.notes), (
            f"Expected no 'confidence:' in notes for zero confidence, got: {profile.notes}"
        )

    def test_confidence_note_is_first(self):
        """Test that confidence note appears first when present."""
        features = TheoremFeatures(
            proof_lines=10,
            tactic_kinds={"intro", "apply"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.75,
        )

        profile = compute_profile(features, config=DEFAULT_CONFIG)

        # Find confidence note
        confidence_notes = [note for note in profile.notes if "confidence:" in note]
        assert len(confidence_notes) == 1, (
            f"Expected exactly one confidence note, got: {confidence_notes}"
        )

        # Check it's the first note
        assert profile.notes[0] == confidence_notes[0], (
            f"Expected confidence note to be first, got: {profile.notes}"
        )

    def test_confidence_values_are_formatted_correctly(self):
        """Test that confidence values are formatted to 2 decimal places."""
        test_cases = [
            (0.123456, "0.12"),
            (0.876543, "0.88"),
            (0.5, "0.50"),
            (1.0, "1.00"),
        ]

        for confidence_value, expected_str in test_cases:
            features = TheoremFeatures(
                proof_lines=5,
                tactic_kinds={"intro"},
                has_induction=False,
                has_cases=False,
                rewrite_count=0,
                simp_count=0,
                local_lemmas_count=0,
                confidence=confidence_value,
            )

            profile = compute_profile(features, config=DEFAULT_CONFIG)

            # Check formatted confidence is in notes
            assert any(f"confidence: {expected_str}" in note for note in profile.notes), (
                f"Expected 'confidence: {expected_str}' for input {confidence_value}, "
                f"got: {profile.notes}"
            )


class TestConfigUsage:
    """Test that config values are actually used (not hardcoded)."""

    def test_config_base_score_affects_aesop_scoring(self, tmp_path):
        """Test that changing config base_score affects aesop scoring."""
        from lean_proof_auto_mcp.core.config import load_config

        # Create custom config with different base score
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("""
version: "1.0"

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

aesop_scoring:
  base_score: 0.9
  confidence_bonuses:
    high: { threshold: 0.8, bonus: 0.05 }
    good: { threshold: 0.6, bonus: 0.03 }
    moderate: { threshold: 0.4, bonus: 0.01 }
    low: { threshold: 0.0, bonus: 0.0 }
  structural_tactics:
    bonus_per_tactic: 0.01
    max_bonus: 0.05
  term_mode:
    bonus_per_pattern: 0.01
    max_bonus: 0.05
  proof_length_bonuses:
    - { max_lines: 5, bonus: 0.01 }
    - { max_lines: 10, bonus: 0.01 }
    - { max_lines: 20, bonus: 0.01 }
  penalties:
    rewrite_heavy: { threshold: 5, penalty: -0.01 }
    rewrite_moderate: { threshold: 2, penalty: -0.01 }
    simp_heavy: { threshold: 3, penalty: -0.01 }
  bonuses:
    tactic_mode: 0.01

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

already_automated:
  penalties:
    tactic_usage: 0.3
    attribute: 0.5
    trivial_proof: 0.8
  tactic_patterns:
    - "by aesop"
  attribute_patterns:
    - "@[aesop"
  trivial_patterns:
    - ":= rfl"

tiers:
  s_tier_percentile: 10
  a_tier_percentile: 25
  b_tier_percentile: 50
  c_tier_percentile: 75
""")

        custom_config = load_config(config_file)

        features = TheoremFeatures(
            proof_lines=5,
            tactic_kinds={"intro"},
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.5,
        )

        # Score with default config
        score_default = score_aesop_potential(features, DEFAULT_CONFIG.aesop_scoring)

        # Score with custom config (base_score = 0.9)
        score_custom = score_aesop_potential(features, custom_config.aesop_scoring)

        # Custom config should give much higher score due to high base_score
        assert score_custom > score_default + 0.3, (
            f"Expected custom config (base=0.9) to give higher score than default "
            f"(base=0.2), got {score_custom} vs {score_default}"
        )
