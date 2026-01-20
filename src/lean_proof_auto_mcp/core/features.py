"""Per-theorem feature extraction from Lean proofs.

This module provides data structures and functions for extracting
features from theorem proofs, including tactic detection, proof metrics,
and confidence scoring.
"""

import re
from dataclasses import dataclass
from typing import Set

from .source import SourceText
from .indexer import TheoremDecl
from .lean_syntax import strip_comments, detect_string_literals


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
    tactic_kinds: Set[str]
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


def extract_features(source: SourceText, decl: TheoremDecl) -> TheoremFeatures:
    """Compute features from theorem proof span.
    
    Analyzes the proof text to extract various metrics and patterns
    that can be used for automation scoring and analysis.
    
    Args:
        source: The source text containing the theorem
        decl: The theorem declaration with proof span information
        
    Returns:
        TheoremFeatures object with extracted metrics
    """
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
            confidence=0.0
        )
    
    # Extract proof text
    proof_text = source.get_span_text(decl.proof_span)
    
    # Strip comments to avoid false positives
    clean_proof = strip_comments(proof_text)
    
    # Calculate basic metrics
    proof_lines = len([line for line in clean_proof.splitlines() if line.strip()])
    
    # Detect tactics
    tactic_kinds = detect_tactics(clean_proof)
    
    # Check for specific patterns
    has_induction = 'induction' in tactic_kinds
    has_cases = 'cases' in tactic_kinds
    
    # Count specific constructs
    rewrite_count = count_rewrites(clean_proof)
    simp_count = count_simps(clean_proof)
    local_lemmas_count = count_local_lemmas(clean_proof)
    
    # Calculate confidence based on proof structure
    confidence = _calculate_confidence(clean_proof, decl.proof_span, tactic_kinds)
    
    return TheoremFeatures(
        proof_lines=proof_lines,
        tactic_kinds=tactic_kinds,
        has_induction=has_induction,
        has_cases=has_cases,
        rewrite_count=rewrite_count,
        simp_count=simp_count,
        local_lemmas_count=local_lemmas_count,
        confidence=confidence
    )


def detect_tactics(proof_text: str) -> Set[str]:
    """Find tactic keywords in proof.
    
    Uses regex patterns to detect common Lean tactics while avoiding
    false positives in comments and strings.
    
    Args:
        proof_text: The proof text to analyze
        
    Returns:
        Set of detected tactic keywords
    """
    if not proof_text:
        return set()
    
    # Common Lean tactics to detect
    tactic_patterns = [
        r'\bintro\b',
        r'\bintros\b', 
        r'\binduction\b',
        r'\bcases\b',
        r'\brw\b',
        r'\brewrite\b',
        r'\bsimp\b',
        r'\bapply\b',
        r'\bexact\b',
        r'\brfl\b',
        r'\btrivial\b',
        r'\bsorry\b',
        r'\bdone\b',
        r'\buse\b',
        r'\bexists\b',
        r'\bconstructor\b',
        r'\bleft\b',
        r'\bright\b',
        r'\bsplit\b',
        r'\bext\b',
        r'\bfunext\b',
        r'\bconv\b',
        r'\bchange\b',
        r'\bshow\b',
        r'\bassumption\b',
        r'\bcontradiction\b',
        r'\bexfalso\b',
        r'\bby_contra\b',
        r'\btauto\b',
        r'\bomega\b',
        r'\blinarith\b',
        r'\bnorm_num\b',
        r'\bfield_simp\b',
        r'\bring_nf\b',
        r'\bsimp_all\b',
        r'\bsimp_rw\b',
        r'\brw_mod_cast\b',
        r'\bpush_neg\b',
        r'\bcontrapose\b',
        r'\bwlog\b',
        r'\bsuffices\b',
        r'\bhave\b',
        r'\blet\b',
        r'\bobtain\b',
        r'\bcalc\b',
        r'\bunfold\b',
        r'\bdsimp\b',
        r'\bsimp_only\b'
    ]
    
    detected = set()
    
    for pattern in tactic_patterns:
        matches = re.finditer(pattern, proof_text, re.IGNORECASE)
        for match in matches:
            # Extract the actual tactic name (remove word boundaries)
            tactic = match.group().lower()
            detected.add(tactic)
    
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
    rewrite_patterns = [
        r'\brw\b',
        r'\brewrite\b',
        r'\brw_mod_cast\b',
        r'\bsimp_rw\b'
    ]
    
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
        r'\bsimp\b',
        r'\bsimp_all\b',
        r'\bsimp_only\b',
        r'\bdsimp\b',
        r'\bfield_simp\b'
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
    local_lemma_patterns = [
        r'\bhave\b',
        r'\bsuffices\b',
        r'\blet\b',
        r'\bobtain\b'
    ]
    
    count = 0
    for pattern in local_lemma_patterns:
        matches = re.findall(pattern, proof_text, re.IGNORECASE)
        count += len(matches)
    
    return count


def _calculate_confidence(proof_text: str, proof_span, tactic_kinds: Set[str]) -> float:
    """Calculate confidence in proof detection.
    
    Uses heuristics to estimate how confident we are that we correctly
    identified the proof boundaries and content.
    
    Args:
        proof_text: The proof text
        proof_span: The proof span object
        tactic_kinds: Set of detected tactics
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not proof_text or not proof_span:
        return 0.0
    
    confidence = 0.5  # Base confidence
    
    # Boost confidence if we found common tactics
    if tactic_kinds:
        confidence += 0.2
        
        # Extra boost for structural tactics that indicate real proofs
        structural_tactics = {'intro', 'intros', 'induction', 'cases', 'apply', 'exact'}
        if tactic_kinds & structural_tactics:
            confidence += 0.2
    
    # Boost confidence if proof has reasonable length
    lines = len([line for line in proof_text.splitlines() if line.strip()])
    if 2 <= lines <= 50:
        confidence += 0.1
    elif lines > 50:
        confidence += 0.05  # Very long proofs might have parsing issues
    
    # Reduce confidence if proof looks suspicious
    if 'sorry' in tactic_kinds:
        confidence -= 0.3  # Incomplete proof
    
    # Check for 'by' keyword which indicates tactic mode
    if 'by' in proof_text.lower():
        confidence += 0.1
    
    # Ensure confidence is in valid range
    return max(0.0, min(1.0, confidence))