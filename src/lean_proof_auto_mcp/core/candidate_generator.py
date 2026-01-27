"""
Candidate hint generation service.

This module provides the CandidateGenerator service that extracts potential
hints from various sources (goal symbols, local context, namespace, nearby
declarations, original proof references) and ranks them for search priority.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10
"""

import re
from typing import Any

from .indexer import FileIndex, TheoremDecl
from .search_annotations_domain import Candidate, CandidateConfig, CandidateSource, Hint, HintType
from .source import SourceText


class CandidateGenerator:
    """
    Generate candidate hints from theorem and context.
    
    The CandidateGenerator extracts potential hints from multiple sources,
    ranks them by priority, and enforces per-source limits.
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10
    """
    
    def __init__(self, source: SourceText, index: FileIndex):
        """
        Initialize CandidateGenerator.
        
        Args:
            source: Source text of the file
            index: Theorem index for the file
        """
        self.source = source
        self.index = index
    
    def generate(
        self,
        theorem_decl: TheoremDecl,
        sources: list[CandidateSource],
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Generate candidates from configured sources.
        
        Extracts candidates from all enabled sources, ranks them, and
        enforces per-source limits.
        
        Args:
            theorem_decl: The theorem declaration to generate candidates for
            sources: List of candidate sources to use
            config: Candidate generation configuration
            
        Returns:
            List of ranked candidates (sorted by rank, descending)
            
        Requirements: 3.1, 3.9, 3.10
        """
        all_candidates: list[Candidate] = []
        
        # Extract from each enabled source
        for source_type in sources:
            source_candidates = self._extract_from_source(
                theorem_decl, source_type, config
            )
            
            # Limit candidates per source
            limited_candidates = source_candidates[:config.max_candidates_per_source]
            all_candidates.extend(limited_candidates)
        
        # Rank and deduplicate
        return self._rank_and_deduplicate(all_candidates, config)
    
    def _extract_from_source(
        self,
        theorem_decl: TheoremDecl,
        source: CandidateSource,
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Extract candidates from a specific source.
        
        Args:
            theorem_decl: The theorem declaration
            source: The candidate source to extract from
            config: Candidate generation configuration
            
        Returns:
            List of candidates from this source
        """
        if source == CandidateSource.GOAL_SYMBOLS:
            return self._extract_from_goal(theorem_decl, config)
        elif source == CandidateSource.LOCAL_CONTEXT:
            return self._extract_from_context(theorem_decl, config)
        elif source == CandidateSource.SAME_NAMESPACE:
            return self._extract_from_namespace(theorem_decl, config)
        elif source == CandidateSource.NEARBY_DECLS:
            return self._extract_nearby(theorem_decl, config)
        elif source == CandidateSource.ORIGINAL_PROOF_REFS:
            return self._extract_from_proof(theorem_decl, config)
        else:
            return []
    
    def _extract_from_goal(
        self,
        theorem_decl: TheoremDecl,
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Extract candidates from goal statement symbols.
        
        Parses the goal expression and collects constant names that appear.
        
        Args:
            theorem_decl: The theorem declaration
            config: Candidate generation configuration
            
        Returns:
            List of candidates from goal symbols
            
        Requirements: 3.2
        """
        candidates: list[Candidate] = []
        
        # Get the theorem type (goal) from the declaration
        decl_text = self.source.get_span_text(theorem_decl.decl_span)
        
        # Extract the type after the colon
        # Pattern: theorem name : TYPE := proof
        type_match = re.search(r':\s*(.+?)(?::=|$)', decl_text, re.DOTALL)
        if not type_match:
            return candidates
        
        goal_type = type_match.group(1).strip()
        
        # Extract identifiers from the goal type
        # Match qualified names (e.g., List.length, Nat.add)
        identifier_pattern = r'\b([A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*)\b'
        identifiers = re.findall(identifier_pattern, goal_type)
        
        # Create candidates for each identifier
        for identifier in identifiers:
            # Determine hint type based on naming conventions
            hint_type = self._infer_hint_type(identifier, config)
            if hint_type is None:
                continue
            
            hint = Hint(
                name=identifier,
                type=hint_type,
                source=CandidateSource.GOAL_SYMBOLS
            )
            
            # Base rank for goal symbols
            rank = 5.0
            
            candidate = Candidate(
                hint=hint,
                rank=rank,
                metadata={"extracted_from": "goal_type"}
            )
            candidates.append(candidate)
        
        return candidates
    
    def _extract_from_context(
        self,
        theorem_decl: TheoremDecl,
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Extract candidates from local context (hypotheses and local definitions).
        
        Args:
            theorem_decl: The theorem declaration
            config: Candidate generation configuration
            
        Returns:
            List of candidates from local context
            
        Requirements: 3.3
        """
        candidates: list[Candidate] = []
        
        # Get the theorem declaration text
        decl_text = self.source.get_span_text(theorem_decl.decl_span)
        
        # Extract parameter names and types
        # Pattern: (name : Type) or {name : Type} or [name : Type]
        param_pattern = r'[\(\{\[]([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^\)\}\]]+)[\)\}\]]'
        params = re.findall(param_pattern, decl_text)
        
        for param_name, param_type in params:
            # Extract type constructors from parameter types
            type_identifiers = re.findall(
                r'\b([A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*)\b',
                param_type
            )
            
            for identifier in type_identifiers:
                hint_type = self._infer_hint_type(identifier, config)
                if hint_type is None:
                    continue
                
                hint = Hint(
                    name=identifier,
                    type=hint_type,
                    source=CandidateSource.LOCAL_CONTEXT
                )
                
                # Base rank for local context
                rank = 4.0
                
                candidate = Candidate(
                    hint=hint,
                    rank=rank,
                    metadata={"extracted_from": "parameter_type", "param_name": param_name}
                )
                candidates.append(candidate)
        
        return candidates
    
    def _extract_from_namespace(
        self,
        theorem_decl: TheoremDecl,
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Extract candidates from same namespace.
        
        Gathers lemmas in the same namespace as the theorem.
        
        Args:
            theorem_decl: The theorem declaration
            config: Candidate generation configuration
            
        Returns:
            List of candidates from same namespace
            
        Requirements: 3.4
        """
        candidates: list[Candidate] = []
        
        # Extract namespace from theorem_id
        # e.g., "Polynomial.eval_zero" -> namespace is "Polynomial"
        theorem_namespace = None
        if '.' in theorem_decl.theorem_id:
            parts = theorem_decl.theorem_id.rsplit('.', 1)
            theorem_namespace = parts[0]
        
        if not theorem_namespace:
            return candidates
        
        # Find all declarations in the same namespace
        for decl in self.index.decls:
            # Skip the theorem itself
            if decl.theorem_id == theorem_decl.theorem_id:
                continue
            
            # Check if declaration is in the same namespace
            if decl.theorem_id.startswith(theorem_namespace + '.'):
                hint_type = self._infer_hint_type_from_decl(decl, config)
                if hint_type is None:
                    continue
                
                hint = Hint(
                    name=decl.theorem_id,
                    type=hint_type,
                    source=CandidateSource.SAME_NAMESPACE
                )
                
                # Base rank for same namespace
                rank = 3.0
                
                # Boost rank for .def lemmas
                if decl.name.endswith('_def') or decl.name.endswith('.def'):
                    rank += 2.0
                
                candidate = Candidate(
                    hint=hint,
                    rank=rank,
                    metadata={"decl_kind": decl.kind, "decl_name": decl.name}
                )
                candidates.append(candidate)
        
        return candidates
    
    def _extract_nearby(
        self,
        theorem_decl: TheoremDecl,
        config: CandidateConfig,
        distance: int = 50
    ) -> list[Candidate]:
        """
        Extract candidates from nearby declarations.
        
        Lemmas within ±N lines of the theorem.
        
        Args:
            theorem_decl: The theorem declaration
            config: Candidate generation configuration
            distance: Maximum line distance (default: 50)
            
        Returns:
            List of candidates from nearby declarations
            
        Requirements: 3.5
        """
        candidates: list[Candidate] = []
        
        theorem_line = theorem_decl.decl_span.start_line
        
        # Find declarations within distance
        for decl in self.index.decls:
            # Skip the theorem itself
            if decl.theorem_id == theorem_decl.theorem_id:
                continue
            
            decl_line = decl.decl_span.start_line
            line_distance = abs(decl_line - theorem_line)
            
            if line_distance <= distance:
                hint_type = self._infer_hint_type_from_decl(decl, config)
                if hint_type is None:
                    continue
                
                hint = Hint(
                    name=decl.theorem_id,
                    type=hint_type,
                    source=CandidateSource.NEARBY_DECLS
                )
                
                # Base rank for nearby declarations
                # Closer declarations get higher rank
                rank = 2.0 + (1.0 - (line_distance / distance))
                
                candidate = Candidate(
                    hint=hint,
                    rank=rank,
                    metadata={
                        "decl_kind": decl.kind,
                        "decl_name": decl.name,
                        "line_distance": line_distance
                    }
                )
                candidates.append(candidate)
        
        return candidates
    
    def _extract_from_proof(
        self,
        theorem_decl: TheoremDecl,
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Extract candidates from original proof references.
        
        Extracts lemmas referenced in the original proof.
        
        Args:
            theorem_decl: The theorem declaration
            config: Candidate generation configuration
            
        Returns:
            List of candidates from proof references
            
        Requirements: 3.6
        """
        candidates: list[Candidate] = []
        
        # Check if theorem has a proof
        if theorem_decl.proof_span is None:
            return candidates
        
        # Get proof text
        proof_text = self.source.get_span_text(theorem_decl.proof_span)
        
        # Extract identifiers from proof
        # Match qualified names (e.g., List.length_append, Nat.add_comm)
        identifier_pattern = r'\b([A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+)\b'
        identifiers = re.findall(identifier_pattern, proof_text)
        
        # Also match simple identifiers that might be lemmas
        simple_pattern = r'\b([a-z][a-zA-Z0-9_]*_(?:def|comm|assoc|zero|one|add|mul|sub|div|eq|ne|lt|le|gt|ge))\b'
        simple_identifiers = re.findall(simple_pattern, proof_text)
        
        all_identifiers = set(identifiers + simple_identifiers)
        
        for identifier in all_identifiers:
            hint_type = self._infer_hint_type(identifier, config)
            if hint_type is None:
                continue
            
            hint = Hint(
                name=identifier,
                type=hint_type,
                source=CandidateSource.ORIGINAL_PROOF_REFS
            )
            
            # High rank for proof references (they were used in the original proof)
            rank = 8.0
            
            # Boost rank for .def lemmas
            if identifier.endswith('_def') or identifier.endswith('.def'):
                rank += 2.0
            
            candidate = Candidate(
                hint=hint,
                rank=rank,
                metadata={"extracted_from": "proof_text"}
            )
            candidates.append(candidate)
        
        return candidates
    
    def _rank_and_deduplicate(
        self,
        candidates: list[Candidate],
        config: CandidateConfig
    ) -> list[Candidate]:
        """
        Rank and deduplicate candidates.
        
        Prioritizes:
        1. .def lemmas (higher rank)
        2. [simp] lemmas (higher rank)
        3. Original proof references (higher rank)
        4. Deterministic ordering by fully-qualified name
        
        Args:
            candidates: List of candidates to rank
            config: Candidate generation configuration
            
        Returns:
            Deduplicated and sorted list of candidates
            
        Requirements: 3.10, 13.2
        """
        # Deduplicate by hint name
        seen_names: dict[str, Candidate] = {}
        
        for candidate in candidates:
            hint_name = candidate.hint.name
            
            # If we've seen this hint before, keep the one with higher rank
            if hint_name in seen_names:
                existing = seen_names[hint_name]
                if candidate.rank > existing.rank:
                    seen_names[hint_name] = candidate
            else:
                seen_names[hint_name] = candidate
        
        # Convert back to list
        unique_candidates = list(seen_names.values())
        
        # Sort by rank (descending), then by name (ascending) for determinism
        unique_candidates.sort(
            key=lambda c: (-c.rank, c.hint.name)
        )
        
        return unique_candidates
    
    def _infer_hint_type(
        self,
        identifier: str,
        config: CandidateConfig
    ) -> HintType | None:
        """
        Infer hint type from identifier name.
        
        Uses naming conventions to determine the appropriate hint type.
        
        Args:
            identifier: The identifier name
            config: Candidate generation configuration
            
        Returns:
            Inferred hint type, or None if not allowed by config
            
        Requirements: 3.7, 3.8
        """
        # Check for definition hints
        if identifier.endswith('_def') or identifier.endswith('.def'):
            if config.allow_unfold_hints:
                return HintType.UNFOLD
            else:
                return None
        
        # Check for simp lemmas (heuristic: lemmas with certain patterns)
        simp_patterns = ['_comm', '_assoc', '_zero', '_one', '_add', '_mul', '_eq']
        if any(pattern in identifier for pattern in simp_patterns):
            if config.allow_simp_hints:
                return HintType.SIMP
            else:
                return None
        
        # Default to ADD_SAFE for other lemmas
        return HintType.ADD_SAFE
    
    def _infer_hint_type_from_decl(
        self,
        decl: TheoremDecl,
        config: CandidateConfig
    ) -> HintType | None:
        """
        Infer hint type from theorem declaration.
        
        Uses declaration attributes and naming conventions.
        
        Args:
            decl: The theorem declaration
            config: Candidate generation configuration
            
        Returns:
            Inferred hint type, or None if not allowed by config
        """
        # Check attributes for [simp]
        if '[simp]' in decl.attributes or 'simp' in decl.attributes:
            if config.allow_simp_hints:
                return HintType.SIMP
            else:
                return None
        
        # Use name-based inference
        return self._infer_hint_type(decl.theorem_id, config)
