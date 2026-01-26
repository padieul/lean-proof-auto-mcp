"""Per-theorem feature extraction from Lean proofs.

This module provides data structures and functions for extracting
features from theorem proofs, including tactic detection, proof metrics,
and confidence scoring.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .indexer import TheoremDecl
from .lean_syntax import strip_comments
from .source import SourceText

if TYPE_CHECKING:
    from .config import ConfidenceConfig


@dataclass(frozen=True)
class TheoremFeatures:
    """Features extracted from a theorem proof.

    Attributes:
        proof_lines: Number of lines in the proof
        tactic_kinds: Set of detected tactic keywords
        has_induction: Whether proof uses induction
        has_cases: Whether proof uses cases analysis
        rewrite_count: Number of rewrite/rw occurrences
        simp_count: Number of simp occurrences
        local_lemmas_count: Number of local lemmas (have, suffices, let)
        confidence: Confidence in proof detection (0.0-1.0)
    """

    proof_lines: int
    tactic_kinds: set[str]
    has_induction: bool
    has_cases: bool
    rewrite_count: int
    simp_count: int
    local_lemmas_count: int
    confidence: float

    def __post_init__(self) -> None:
        """Validate feature invariants."""
        if self.proof_lines < 0:
            raise ValueError(f"proof_lines must be >= 0, got {self.proof_lines}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if self.rewrite_count < 0:
            raise ValueError(f"rewrite_count must be >= 0, got {self.rewrite_count}")
        if self.simp_count < 0:
            raise ValueError(f"simp_count must be >= 0, got {self.simp_count}")
        if self.local_lemmas_count < 0:
            raise ValueError(f"local_lemmas_count must be >= 0, got {self.local_lemmas_count}")


def extract_features(
    source: SourceText, decl: TheoremDecl, config: "ConfidenceConfig | None" = None
) -> TheoremFeatures:
    """Compute features from theorem proof span with enhanced analysis.

    Analyzes the proof text to extract various metrics and patterns
    that can be used for automation scoring and analysis. Enhanced to
    better handle term-mode proofs and complex proof structures.

    Args:
        source: The source text containing the theorem
        decl: The theorem declaration with proof span information
        config: Optional confidence configuration. If None, loads default config.

    Returns:
        TheoremFeatures object with extracted metrics
    """
    # Load default config if not provided
    if config is None:
        from .config import load_default_config

        full_config = load_default_config()
        config = full_config.confidence
    if not decl.proof_span:
        # No proof found - return empty features
        return TheoremFeatures(
            proof_lines=0,
            tactic_kinds=set(),
            has_induction=False,
            has_cases=False,
            rewrite_count=0,
            simp_count=0,
            local_lemmas_count=0,
            confidence=0.0,
        )

    # Extract proof text with better context handling
    proof_text = source.get_span_text(decl.proof_span, normalize_for_proof=True)

    # Strip comments to avoid false positives, but preserve structure
    clean_proof = strip_comments(proof_text)

    # Calculate basic metrics with enhanced line counting
    proof_lines = len([line for line in clean_proof.splitlines() if line.strip()])

    # Enhanced tactic detection with context awareness
    tactic_kinds = detect_tactics_enhanced(clean_proof, source, decl.proof_span)

    # Check for specific patterns with enhanced detection
    has_induction = any(t in tactic_kinds for t in ["induction", "induction_on"])
    has_cases = (
        any(t in tactic_kinds for t in ["cases", "rcases"]) and "induction" not in tactic_kinds
    )

    # Count specific constructs with enhanced patterns
    rewrite_count = count_rewrites(clean_proof)
    simp_count = count_simps(clean_proof)
    local_lemmas_count = count_local_lemmas(clean_proof)

    # Calculate confidence with enhanced multi-signal approach
    confidence = _calculate_confidence_enhanced(
        clean_proof, decl.proof_span, tactic_kinds, decl, config
    )

    return TheoremFeatures(
        proof_lines=proof_lines,
        tactic_kinds=tactic_kinds,
        has_induction=has_induction,
        has_cases=has_cases,
        rewrite_count=rewrite_count,
        simp_count=simp_count,
        local_lemmas_count=local_lemmas_count,
        confidence=confidence,
    )


def detect_tactics_enhanced(proof_text: str, source_context: SourceText, proof_span) -> set[str]:
    """Enhanced tactic detection with context awareness.

    Improved tactic detection that handles context, multi-line tactics,
    and various proof patterns more effectively.

    Args:
        proof_text: The proof text to analyze
        source_context: The full source context (for better analysis)
        proof_span: The proof span (for location-aware analysis)

    Returns:
        Set of detected tactic keywords and patterns
    """
    if not proof_text:
        return set()

    # Start with basic tactic detection
    detected = detect_tactics(proof_text)

    # Add context-aware enhancements
    detected.update(_detect_multiline_tactics(proof_text))
    detected.update(_detect_custom_tactics(proof_text))
    detected.update(_detect_proof_structure_patterns(proof_text))

    return detected


def _detect_multiline_tactics(proof_text: str) -> set[str]:
    """Detect tactics that span multiple lines.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Set of detected multi-line tactic patterns
    """
    detected = set()

    # Multi-line tactic patterns
    multiline_patterns = [
        (r"induction\s+\w+\s+with\s*\n", "induction"),
        (r"cases\s+\w+\s+with\s*\n", "cases"),
        (r"simp\s*\[.*\n.*\]", "simp"),
        (r"rw\s*\[.*\n.*\]", "rw"),
        (r"have\s+\w+\s*:.*\n.*:=", "have"),
        (r"calc\s+.*\n.*=", "calc"),
    ]

    for pattern, tactic_name in multiline_patterns:
        if re.search(pattern, proof_text, re.MULTILINE | re.IGNORECASE):
            detected.add(tactic_name)

    return detected


def _detect_custom_tactics(proof_text: str) -> set[str]:
    """Detect custom tactics and macros.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Set of detected custom tactic patterns
    """
    detected = set()

    # Custom tactic patterns (common in Mathlib)
    custom_patterns = [
        (r"\bfield_simp\b", "field_simp"),
        (r"\bnorm_cast\b", "norm_cast"),
        (r"\bpush_cast\b", "push_cast"),
        (r"\bsimp_mod_cast\b", "simp_mod_cast"),
        (r"\bapply_mod_cast\b", "apply_mod_cast"),
        (r"\bexact_mod_cast\b", "exact_mod_cast"),
        (r"\bassumption_mod_cast\b", "assumption_mod_cast"),
        (r"\bconv_rhs\b", "conv_rhs"),
        (r"\bconv_lhs\b", "conv_lhs"),
        (r"\bsimp_all_only\b", "simp_all_only"),
        (r"\bring_nf\b", "ring_nf"),
        (r"\babel\b", "abel"),
        (r"\bgroup\b", "group"),
        (r"\bnoncomm_ring\b", "noncomm_ring"),
    ]

    for pattern, tactic_name in custom_patterns:
        if re.search(pattern, proof_text, re.IGNORECASE):
            detected.add(tactic_name)

    return detected


def _detect_proof_structure_patterns(proof_text: str) -> set[str]:
    """Detect proof structure patterns that indicate proof quality.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Set of detected proof structure indicators
    """
    detected = set()

    # Proof structure patterns
    structure_patterns = [
        (r"^\s*by\s*$", "tactic_mode"),
        (r":=\s*by\s+", "tactic_proof"),
        (r":=\s*\w+\.\w+", "term_proof"),
        (r"^\s*\|\s*\w+\s*=>", "pattern_match"),
        (r"^\s*·\s+", "bullet_point"),
        (r"next\s*=>", "next_case"),
        (r"this\s*:", "this_reference"),
        (r"@\[\w+\]", "attribute"),
    ]

    for pattern, structure_name in structure_patterns:
        if re.search(pattern, proof_text, re.MULTILINE | re.IGNORECASE):
            detected.add(structure_name)

    return detected


def _calculate_confidence_enhanced(
    proof_text: str,
    proof_span,
    tactic_kinds: set[str],
    decl: TheoremDecl,
    config: "ConfidenceConfig",
) -> float:
    """Enhanced confidence calculation with multiple signals.

    This is a wrapper that calls the main confidence calculation but could
    be extended with declaration-specific logic.

    Args:
        proof_text: The proof text
        proof_span: The proof span object
        tactic_kinds: Set of detected tactics
        decl: The theorem declaration
        config: Confidence configuration

    Returns:
        Confidence score between 0.0 and 1.0
    """
    base_confidence = _calculate_confidence(proof_text, proof_span, tactic_kinds, config)

    # Additional declaration-specific adjustments could go here
    # For now, just return the base confidence
    return base_confidence


def detect_tactics(proof_text: str) -> set[str]:
    """Find tactic keywords in proof with enhanced context awareness.

    Uses regex patterns to detect common Lean tactics while avoiding
    false positives in comments and strings. Enhanced to better handle
    tactic variants, aliases, and term-mode proof patterns.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Set of detected tactic keywords
    """
    if not proof_text:
        return set()

    # Enhanced tactic patterns with better coverage
    tactic_patterns = [
        # Core structural tactics
        r"\bintro\b",
        r"\bintros\b",
        r"\binduction\b",
        r"\bcases\b",
        r"\bapply\b",
        r"\bexact\b",
        r"\bconstructor\b",
        r"\bleft\b",
        r"\bright\b",
        r"\bsplit\b",
        # Rewriting tactics and variants
        r"\brw\b",
        r"\brewrite\b",
        r"\brw_mod_cast\b",
        r"\bsimp_rw\b",
        r"\bconv_rhs\b",
        r"\bconv_lhs\b",
        # Simplification tactics and variants
        r"\bsimp\b",
        r"\bsimp_all\b",
        r"\bsimp_only\b",
        r"\bdsimp\b",
        r"\bfield_simp\b",
        r"\bring_nf\b",
        # Reflexivity and trivial proofs
        r"\brfl\b",
        r"\btrivial\b",
        r"\bdone\b",
        # Proof by contradiction and negation
        r"\bby_contra\b",
        r"\bcontradiction\b",
        r"\bexfalso\b",
        r"\bpush_neg\b",
        r"\bcontrapose\b",
        # Automation tactics
        r"\btauto\b",
        r"\bomega\b",
        r"\blinarith\b",
        r"\bnorm_num\b",
        r"\bdecide\b",
        r"\baesop\b",
        r"\bgrind\b",
        # Local reasoning
        r"\bhave\b",
        r"\bsuffices\b",
        r"\blet\b",
        r"\bobtain\b",
        r"\buse\b",
        r"\bexists\b",
        r"\bwlog\b",
        # Advanced tactics
        r"\bext\b",
        r"\bfunext\b",
        r"\bconv\b",
        r"\bchange\b",
        r"\bshow\b",
        r"\bassumption\b",
        r"\bcalc\b",
        r"\bunfold\b",
        r"\bsorry\b",
        # Tactic combinators and modifiers
        r"\btry\b",
        r"\brepeat\b",
        r"\bfirst\b",
        r"\ball_goals\b",
        r"\bany_goals\b",
        r"\bfocus\b",
        r"\bskip\b",
        # Additional common tactics
        r"\brcases\b",
        r"\brintro\b",
        r"\bsimp_all_only\b",
        r"\bpush_cast\b",
        r"\bnorm_cast\b",
        r"\bassumption_mod_cast\b",
        r"\bexact_mod_cast\b",
        r"\bapply_mod_cast\b",
        r"\brw_mod_cast\b",
        r"\bsimp_mod_cast\b",
    ]

    detected = set()

    # Detect traditional tactic keywords
    for pattern in tactic_patterns:
        matches = re.finditer(pattern, proof_text, re.IGNORECASE)
        for match in matches:
            # Extract the actual tactic name (remove word boundaries)
            tactic = match.group().lower()
            detected.add(tactic)

    # Enhanced detection for term-mode proof patterns
    detected.update(_detect_term_mode_patterns(proof_text))

    # Enhanced detection for tactic combinators
    detected.update(_detect_tactic_combinators(proof_text))

    # Enhanced detection for proof structure patterns
    detected.update(_detect_proof_structure_patterns(proof_text))

    return detected


def _detect_term_mode_patterns(proof_text: str) -> set[str]:
    """Detect term-mode proof patterns that indicate valid proofs.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Set of detected term-mode proof indicators
    """
    detected = set()

    # Common term-mode proof patterns
    term_patterns = [
        # Function application patterns (common in Mathlib)
        (r"\w+\.\w+\s+\.\.\s*$", "term_application"),  # e.g., "eval₂_list_sum .."
        (r"\w+\s+_\s+_\s*$", "term_application"),  # e.g., "eval₂_X _ _"
        (
            r"\(\w+\s+_\s+_\)\.\w+\s+_\s+_",
            "term_application",
        ),  # e.g., "(eval₂RingHom _ _).map_pow _ _"
        # Direct proof terms
        (r"^\s*rfl\s*$", "rfl"),
        (r"^\s*trivial\s*$", "trivial"),
        (r"^\s*True\.intro\s*$", "term_proof"),
        (r"^\s*False\.elim\s+\w+\s*$", "term_proof"),
        # Constructor applications
        (r"⟨.*⟩", "constructor_term"),
        (r"Exists\.intro\s+\w+", "constructor_term"),
        # Ring homomorphism applications
        (r"\w+\.map_\w+", "map_application"),
        (r"RingHom\.\w+", "ring_hom_application"),
        # Inference placeholders (Lean 4 style)
        (r"\.\.\s*$", "inference_placeholder"),
        (r"‹.*›", "assumption_term"),
    ]

    for pattern, tactic_name in term_patterns:
        if re.search(pattern, proof_text, re.MULTILINE | re.IGNORECASE):
            detected.add(tactic_name)

    return detected


def _detect_tactic_combinators(proof_text: str) -> set[str]:
    """Detect tactic combinators and complex tactic expressions.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Set of detected tactic combinator patterns
    """
    detected = set()

    # Tactic combinator patterns
    combinator_patterns = [
        (r"<;>", "tactic_combinator"),
        (r";\s*\[", "tactic_list"),
        (r"try\s+\w+", "try_combinator"),
        (r"repeat\s+\w+", "repeat_combinator"),
        (r"first\s*\|", "first_combinator"),
        (r"·\s+\w+", "bullet_tactic"),  # Lean 4 bullet syntax
        (r"case\s+\w+\s*=>", "case_tactic"),
        (r"\|\s*\w+\s*=>", "match_case"),
    ]

    for pattern, combinator_name in combinator_patterns:
        if re.search(pattern, proof_text, re.IGNORECASE):
            detected.add(combinator_name)

    return detected


def count_rewrites(proof_text: str) -> int:
    """Count rw, rewrite occurrences.

    Counts both 'rw' and 'rewrite' tactic occurrences, including
    variants like 'rw_mod_cast' and 'simp_rw'.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Total count of rewrite-related tactics
    """
    if not proof_text:
        return 0

    # Patterns for rewrite tactics
    rewrite_patterns = [r"\brw\b", r"\brewrite\b", r"\brw_mod_cast\b", r"\bsimp_rw\b"]

    count = 0
    for pattern in rewrite_patterns:
        matches = re.findall(pattern, proof_text, re.IGNORECASE)
        count += len(matches)

    return count


def count_simps(proof_text: str) -> int:
    """Count simp occurrences.

    Counts 'simp' tactic occurrences, including variants like
    'simp_all', 'simp_only', 'dsimp', etc.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Total count of simp-related tactics
    """
    if not proof_text:
        return 0

    # Patterns for simp tactics
    simp_patterns = [
        r"\bsimp\b",
        r"\bsimp_all\b",
        r"\bsimp_only\b",
        r"\bdsimp\b",
        r"\bfield_simp\b",
    ]

    count = 0
    for pattern in simp_patterns:
        matches = re.findall(pattern, proof_text, re.IGNORECASE)
        count += len(matches)

    return count


def count_local_lemmas(proof_text: str) -> int:
    """Count have, suffices, let occurrences.

    Counts local lemma constructs that introduce intermediate results
    or assumptions within the proof.

    Args:
        proof_text: The proof text to analyze

    Returns:
        Total count of local lemma constructs
    """
    if not proof_text:
        return 0

    # Patterns for local lemma constructs
    local_lemma_patterns = [r"\bhave\b", r"\bsuffices\b", r"\blet\b", r"\bobtain\b"]

    count = 0
    for pattern in local_lemma_patterns:
        matches = re.findall(pattern, proof_text, re.IGNORECASE)
        count += len(matches)

    return count


def _calculate_confidence(
    proof_text: str, proof_span, tactic_kinds: set[str], config: "ConfidenceConfig"
) -> float:
    """Calculate confidence in proof detection with enhanced multi-signal approach.

    Uses multiple heuristics to estimate how confident we are that we correctly
    identified the proof boundaries and content. Enhanced to better handle
    term-mode proofs and various proof patterns.

    Args:
        proof_text: The proof text
        proof_span: The proof span object
        tactic_kinds: Set of detected tactics
        config: Confidence configuration

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not proof_text or not proof_span:
        return 0.0

    confidence = config.base_score  # Use configured base score

    # Signal 1: Proof structure quality
    lines = [line.strip() for line in proof_text.splitlines() if line.strip()]
    non_empty_lines = len(lines)

    if non_empty_lines > 0:
        confidence += config.proof_structure_bonus  # Use configured bonus

        # Check for proper proof keywords
        if any(keyword in proof_text.lower() for keyword in ["by", ":=", "proof"]):
            confidence += 0.1

    # Signal 2: Tactic diversity and appropriateness
    if tactic_kinds:
        confidence += config.tactic_detection_bonus  # Use configured bonus

        # Boost for structural tactics that indicate real proofs
        structural_tactics = {
            "intro",
            "intros",
            "induction",
            "cases",
            "apply",
            "exact",
            "constructor",
            "left",
            "right",
            "split",
        }
        if tactic_kinds & structural_tactics:
            confidence += config.structural_tactics_bonus  # Use configured bonus

        # Boost for term-mode proof patterns
        term_mode_patterns = {
            "term_application",
            "rfl",
            "term_proof",
            "constructor_term",
            "map_application",
            "ring_hom_application",
            "inference_placeholder",
        }
        if tactic_kinds & term_mode_patterns:
            confidence += config.term_mode_patterns_bonus  # Use configured bonus

        # Boost for automation tactics
        automation_tactics = {
            "simp",
            "simp_all",
            "simp_only",
            "tauto",
            "omega",
            "linarith",
            "norm_num",
            "decide",
            "aesop",
            "grind",
        }
        if tactic_kinds & automation_tactics:
            confidence += config.automation_tactics_bonus  # Use configured bonus

    # Signal 3: Proof length appropriateness
    if config.proof_length_min <= non_empty_lines <= config.proof_length_max:
        confidence += 0.1
    elif non_empty_lines > config.proof_length_max:
        confidence += config.proof_length_max_bonus  # Use configured bonus for very long proofs

    # Signal 4: Presence of proof keywords and markers
    proof_indicators = [
        "by",
        ":=",
        "proof",
        "qed",
        "begin",
        "end",
        "⟨",
        "⟩",
        "‹",
        "›",  # Lean brackets
        "..",
        "_ _",  # Inference patterns
    ]

    indicator_count = sum(1 for indicator in proof_indicators if indicator in proof_text.lower())
    if indicator_count > 0:
        confidence += min(0.1, indicator_count * 0.03)

    # Signal 5: Absence of suspicious patterns
    if "sorry" in tactic_kinds:
        confidence += config.sorry_penalty  # Use configured penalty (negative value)

    # Check for error patterns that might indicate parsing issues
    error_patterns = ["error", "failed", "unknown", "invalid"]
    if any(pattern in proof_text.lower() for pattern in error_patterns):
        confidence += config.error_patterns_penalty  # Use configured penalty (negative value)

    # Signal 6: Indentation and structure consistency
    if non_empty_lines > 1:
        # Check if proof has consistent indentation (indicates structure)
        indentations = [len(line) - len(line.lstrip()) for line in lines]
        if len(set(indentations)) <= 3:  # Reasonable indentation variety
            confidence += config.indentation_consistency_bonus  # Use configured bonus

    # Ensure confidence is in valid range
    return float(max(0.0, min(1.0, confidence)))
