"""Proof segmentation for structural analysis.

This module provides data structures and functions for segmenting
Lean proofs into coarse blocks and extracting structural information
like skeleton tactics and case analysis.
"""

import re
from dataclasses import dataclass
from typing import List

from .source import SourceText, Span
from .indexer import TheoremDecl
from .lean_syntax import strip_comments


@dataclass(frozen=True)
class ProofBlock:
    """Represents a contiguous block within a proof.
    
    Attributes:
        kind: Block classification ("skeleton" | "rewrite_simp" | "closing" | "unknown")
        span: Location span of the block
    """
    kind: str
    span: Span
    
    def __post_init__(self) -> None:
        """Validate proof block invariants."""
        valid_kinds = {"skeleton", "rewrite_simp", "closing", "unknown"}
        if self.kind not in valid_kinds:
            raise ValueError(f"Invalid block kind: {self.kind}. Must be one of {valid_kinds}")


@dataclass(frozen=True)
class CaseBlock:
    """Represents a case analysis branch within a proof.
    
    Attributes:
        label: Case label (e.g., "zero", "succ", "base", "step")
        span: Location span of the case block
    """
    label: str
    span: Span
    
    def __post_init__(self) -> None:
        """Validate case block invariants."""
        if not self.label:
            raise ValueError("Case label cannot be empty")


@dataclass(frozen=True)
class ProofStructure:
    """Complete structural analysis of a proof.
    
    Attributes:
        skeleton: Ordered list of key structural tactics
        blocks: List of classified proof blocks
        cases: List of case analysis branches (shallow nesting only)
    """
    skeleton: List[str]
    blocks: List[ProofBlock]
    cases: List[CaseBlock]


def segment_proof(source: SourceText, decl: TheoremDecl) -> ProofStructure:
    """Segment proof into skeleton + blocks.
    
    Analyzes the proof structure to extract the skeleton of key tactics,
    classify contiguous blocks by their dominant patterns, and identify
    case analysis branches.
    
    Args:
        source: The source text containing the theorem
        decl: The theorem declaration with proof span information
        
    Returns:
        ProofStructure with skeleton, blocks, and cases
    """
    if not decl.proof_span:
        # No proof found - return empty structure
        return ProofStructure(
            skeleton=[],
            blocks=[],
            cases=[]
        )
    
    # Extract proof text
    proof_text = source.get_span_text(decl.proof_span, normalize_for_proof=True)
    
    # Strip comments to avoid false positives
    clean_proof = strip_comments(proof_text)
    
    # Extract skeleton tactics
    skeleton = extract_skeleton(clean_proof)
    
    # Get proof lines for block analysis
    proof_lines = clean_proof.splitlines()
    
    # Identify blocks
    blocks = identify_blocks(proof_lines, decl.proof_span.start_line)
    
    # Extract case analysis
    cases = extract_cases(clean_proof, decl.proof_span.start_line)
    
    return ProofStructure(
        skeleton=skeleton,
        blocks=blocks,
        cases=cases
    )


def extract_skeleton(proof_text: str) -> List[str]:
    """Find top-level structural tactics.
    
    Extracts the main structural tactics that form the "skeleton" of the proof.
    These are typically the high-level tactics that organize the proof structure.
    
    Args:
        proof_text: The proof text to analyze
        
    Returns:
        Ordered list of skeleton tactics found in the proof
    """
    if not proof_text:
        return []
    
    # Structural tactics that form the proof skeleton
    structural_tactics = [
        'intro', 'intros', 'induction', 'cases', 'apply', 'constructor',
        'left', 'right', 'split', 'ext', 'funext', 'use', 'exists',
        'by_contra', 'contrapose', 'wlog', 'suffices'
    ]
    
    skeleton = []
    
    # Look for structural tactics in order of appearance
    for tactic in structural_tactics:
        pattern = rf'\b{re.escape(tactic)}\b'
        matches = list(re.finditer(pattern, proof_text, re.IGNORECASE))
        
        for match in matches:
            # Add to skeleton if not already present (preserve order, avoid duplicates)
            tactic_lower = tactic.lower()
            if tactic_lower not in skeleton:
                skeleton.append(tactic_lower)
    
    return skeleton


def identify_blocks(proof_lines: List[str], proof_start_line: int) -> List[ProofBlock]:
    """Classify contiguous regions by dominant tactic type.
    
    Analyzes proof lines to identify contiguous blocks and classify them
    based on the dominant pattern of tactics used.
    
    Args:
        proof_lines: Lines of the proof text
        proof_start_line: Starting line number of the proof (1-indexed)
        
    Returns:
        List of classified proof blocks
    """
    if not proof_lines:
        return []
    
    blocks = []
    current_block_start = 0
    current_block_kind = "unknown"
    
    i = 0
    while i < len(proof_lines):
        line = proof_lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Determine the kind of this line
        line_kind = _classify_line(line)
        
        # If this is the start or the kind changed, finalize previous block
        if i == 0 or (line_kind != current_block_kind and current_block_kind != "unknown"):
            if i > 0:
                # Finalize previous block
                block_span = Span(
                    start_line=proof_start_line + current_block_start,
                    end_line=proof_start_line + i - 1
                )
                blocks.append(ProofBlock(kind=current_block_kind, span=block_span))
            
            # Start new block
            current_block_start = i
            current_block_kind = line_kind
        elif current_block_kind == "unknown":
            # Update unknown blocks to a specific kind when we find one
            current_block_kind = line_kind
        
        i += 1
    
    # Finalize the last block
    if proof_lines:
        block_span = Span(
            start_line=proof_start_line + current_block_start,
            end_line=proof_start_line + len(proof_lines) - 1
        )
        blocks.append(ProofBlock(kind=current_block_kind, span=block_span))
    
    return blocks


def extract_cases(proof_text: str, proof_start_line: int) -> List[CaseBlock]:
    """Find case/induction branches (shallow only).
    
    Identifies case analysis branches in the proof, extracting labels
    and approximate spans. Only does shallow analysis - no deep nesting.
    
    Args:
        proof_text: The proof text to analyze
        proof_start_line: Starting line number of the proof (1-indexed)
        
    Returns:
        List of case blocks found in the proof
    """
    if not proof_text:
        return []
    
    cases = []
    lines = proof_text.splitlines()
    
    # Pattern to match case labels
    # Matches various case syntax patterns in Lean
    case_patterns = [
        r'\|\s*([a-zA-Z_][a-zA-Z0-9_\']*)\s*=>',     # | label =>
        r'\|\s*([a-zA-Z_][a-zA-Z0-9_\']*)\s*\w*\s*=>', # | label n =>
        r'case\s+([a-zA-Z_][a-zA-Z0-9_\']*)(?:\s+\w+)*\s*:', # case label [args]:
        r'case\s+([a-zA-Z_][a-zA-Z0-9_\']*)\s*=>?',  # case label =>
        r'·\s*--\s*([a-zA-Z_][a-zA-Z0-9_\']*)',      # · -- label
        r'·\s*([a-zA-Z_][a-zA-Z0-9_\']*)',           # · label
    ]
    
    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        
        for pattern in case_patterns:
            match = re.search(pattern, line_stripped, re.IGNORECASE)
            if match:
                label = match.group(1)
                
                # Find the end of this case (heuristic: next case or end of proof)
                case_start = line_idx
                case_end = len(lines) - 1  # Default to end of proof
                
                # Look for the next case to determine the end
                for next_line_idx in range(line_idx + 1, len(lines)):
                    next_line = lines[next_line_idx].strip()
                    
                    # Check if this line starts a new case
                    for next_pattern in case_patterns:
                        if re.search(next_pattern, next_line, re.IGNORECASE):
                            case_end = next_line_idx - 1
                            break
                    
                    if case_end < len(lines) - 1:
                        break
                
                # Create case block
                case_span = Span(
                    start_line=proof_start_line + case_start,
                    end_line=proof_start_line + case_end
                )
                cases.append(CaseBlock(label=label, span=case_span))
                break  # Only match one pattern per line
    
    return cases


def _classify_line(line: str) -> str:
    """Classify a proof line by its dominant tactic type.
    
    Args:
        line: The proof line to classify
        
    Returns:
        Block kind: "skeleton", "rewrite_simp", "closing", or "unknown"
    """
    if not line.strip():
        return "unknown"
    
    line_lower = line.lower()
    
    # Structural tactics - check these first as they take precedence
    # These organize the proof structure
    structural_tactics = [
        'intro', 'intros', 'induction', 'cases', 'apply', 'constructor',
        'left', 'right', 'split', 'ext', 'funext', 'use', 'exists',
        'have', 'suffices', 'let', 'obtain', 'by_contra', 'contrapose',
        'wlog', 'conv', 'change', 'show', 'unfold'
    ]
    
    for tactic in structural_tactics:
        if re.search(rf'\b{re.escape(tactic)}\b', line_lower):
            return "skeleton"
    
    # Closing tactics - typically end goals or subgoals
    closing_tactics = [
        'exact', 'rfl', 'trivial', 'done', 'assumption', 'contradiction',
        'exfalso', 'tauto', 'omega', 'linarith', 'norm_num', 'simp_all'
    ]
    
    for tactic in closing_tactics:
        if re.search(rf'\b{re.escape(tactic)}\b', line_lower):
            return "closing"
    
    # Rewrite/simp tactics - transformation-heavy
    rewrite_simp_tactics = [
        'rw', 'rewrite', 'simp', 'simp_only', 'simp_rw', 'dsimp',
        'field_simp', 'ring_nf', 'rw_mod_cast', 'push_neg'
    ]
    
    for tactic in rewrite_simp_tactics:
        if re.search(rf'\b{re.escape(tactic)}\b', line_lower):
            return "rewrite_simp"
    
    return "unknown"