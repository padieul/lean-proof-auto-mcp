"""
Context extraction service for theorem analysis.

This module provides the ContextExtractor service that extracts rich context
about theorems including statement, original proof, hypotheses, in-scope
declarations, and similar proofs.

Requirements: 8.2, 8.3, 8.4, 8.5, 8.6
"""

import logging
from dataclasses import dataclass

from ..lean.ports import Declaration, Querier, ProofStateInspector, TheoremContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimilarProof:
    """
    Similar proof with similarity score.

    Requirements: 18.1, 18.2, 18.3, 18.4
    """

    theorem_id: str
    similarity: float
    theorem_statement: str
    proof: str
    hints_used: list[str]


@dataclass(frozen=True)
class ProofContext:
    """
    Rich context about a theorem.

    This includes the theorem statement, original proof, hypotheses,
    in-scope declarations, namespace, and similar proofs.

    Requirements: 8.2, 8.3, 8.4, 8.5, 8.6
    """

    theorem_statement: str
    original_proof: str
    hypotheses: list[str]
    in_scope: list[str]  # Declarations in scope
    namespace: str
    similar_proofs: list[SimilarProof]


class ContextExtractor:
    """
    Extract rich context for theorem analysis.

    The ContextExtractor provides comprehensive context about theorems
    including statement, proof, hypotheses, scope, and similar proofs
    for LLM reasoning and pattern matching.

    Requirements: 8.2, 8.3, 8.4, 8.5, 8.6
    """

    def __init__(
        self,
        querier: Querier,
        proof_state_inspector: ProofStateInspector | None = None,
    ):
        """
        Initialize ContextExtractor with dependency injection.

        Args:
            querier: Querier for extracting declarations and context
            proof_state_inspector: Optional ProofStateInspector for extracting proof states

        Requirements: 8.1, 9.2, 9.5
        """
        self.querier = querier
        self.proof_state_inspector = proof_state_inspector
        self._context_cache: dict[tuple[str, str], ProofContext] = {}

    def extract_context(
        self,
        file_path: str,
        theorem_id: str,
        include_similar: bool = False,
        similarity_threshold: float = 0.7,
    ) -> ProofContext:
        """
        Extract full context for a theorem.

        This method extracts:
        - Theorem statement from declaration.type
        - Original proof from declaration.value.pp
        - Hypotheses from initial proof state
        - In-scope declarations
        - Current namespace
        - Similar proofs (if requested)

        Args:
            file_path: Path to Lean file
            theorem_id: Theorem identifier
            include_similar: Whether to include similar proofs
            similarity_threshold: Minimum similarity score for similar proofs (default: 0.7)

        Returns:
            ProofContext with complete information

        Raises:
            ValueError: If theorem not found
            RuntimeError: If LeanInteract fails

        Requirements: 8.2, 8.3, 8.4, 8.5, 8.6
        """
        # Check cache
        cache_key = (file_path, theorem_id)
        if cache_key in self._context_cache and not include_similar:
            return self._context_cache[cache_key]

        try:
            # Get theorem context from LeanInteract
            theorem_context = self.querier.get_theorem_context(file_path, theorem_id)

            # Extract hypotheses from proof state if inspector is available
            hypotheses = theorem_context.hypotheses
            if self.proof_state_inspector and not hypotheses:
                try:
                    # Get declarations to find the theorem
                    declarations = self.querier.extract_declarations(file_path)
                    theorem_decl = self._find_declaration(theorem_id, declarations)

                    if theorem_decl:
                        proof_state = self.proof_state_inspector.get_initial_proof_state(
                            theorem_decl
                        )
                        hypotheses = proof_state.hypotheses
                except Exception as e:
                    logger.warning(f"Failed to extract proof state hypotheses: {e}")

            # Find similar proofs if requested
            similar_proofs: list[SimilarProof] = []
            if include_similar:
                similar_proofs = self._find_similar_proofs(
                    file_path, theorem_id, theorem_context, similarity_threshold
                )

            # Build context
            context = ProofContext(
                theorem_statement=theorem_context.theorem_statement,
                original_proof=theorem_context.original_proof,
                hypotheses=hypotheses,
                in_scope=theorem_context.in_scope,
                namespace=theorem_context.namespace,
                similar_proofs=similar_proofs,
            )

            # Cache context (without similar proofs)
            if not include_similar:
                self._context_cache[cache_key] = context

            logger.info(f"Extracted context for {theorem_id}")
            return context

        except Exception as e:
            logger.error(f"Failed to extract context for {theorem_id}: {e}")
            raise

    def _find_similar_proofs(
        self,
        file_path: str,
        theorem_id: str,
        theorem_context: TheoremContext,
        similarity_threshold: float,
    ) -> list[SimilarProof]:
        """
        Find similar proofs based on theorem structure and type signatures.

        This method computes similarity scores based on:
        - Type signature similarity
        - Namespace similarity
        - Proof structure similarity

        Args:
            file_path: Path to Lean file
            theorem_id: Theorem identifier
            theorem_context: Context of the theorem
            similarity_threshold: Minimum similarity score

        Returns:
            List of similar proofs with scores >= threshold, sorted by similarity

        Requirements: 18.1, 18.2, 18.3, 18.4
        """
        similar_proofs: list[SimilarProof] = []

        try:
            # Get all declarations
            declarations = self.querier.extract_declarations(file_path)

            # Find theorems with similar structure
            for decl in declarations:
                # Skip the theorem itself
                if decl.full_name == theorem_id:
                    continue

                # Only consider theorems/lemmas with proofs
                if not decl.is_theorem or not decl.value:
                    continue

                # Compute similarity score
                similarity = self._compute_similarity(theorem_context, decl)

                # Include if above threshold
                if similarity >= similarity_threshold:
                    # Extract hints used (if available)
                    hints_used = decl.value.constants if decl.value else []

                    similar_proof = SimilarProof(
                        theorem_id=decl.full_name,
                        similarity=similarity,
                        theorem_statement=decl.type,
                        proof=decl.value.pp if decl.value else "",
                        hints_used=hints_used,
                    )
                    similar_proofs.append(similar_proof)

            # Sort by similarity (descending)
            similar_proofs.sort(key=lambda p: p.similarity, reverse=True)

            logger.info(
                f"Found {len(similar_proofs)} similar proofs for {theorem_id} "
                f"(threshold: {similarity_threshold})"
            )

        except Exception as e:
            logger.warning(f"Failed to find similar proofs: {e}")

        return similar_proofs

    def _compute_similarity(self, theorem_context: TheoremContext, candidate: Declaration) -> float:
        """
        Compute similarity score between theorem and candidate.

        This is a simple heuristic based on:
        - Namespace match (0.3 weight)
        - Type signature similarity (0.4 weight)
        - Proof length similarity (0.3 weight)

        Args:
            theorem_context: Context of the theorem
            candidate: Candidate declaration

        Returns:
            Similarity score between 0.0 and 1.0

        Requirements: 18.1
        """
        score = 0.0

        # Namespace similarity (0.3 weight)
        if candidate.namespace == theorem_context.namespace:
            score += 0.3
        elif candidate.namespace.startswith(
            theorem_context.namespace + "."
        ) or theorem_context.namespace.startswith(candidate.namespace + "."):
            score += 0.15

        # Type signature similarity (0.4 weight)
        # Simple heuristic: count common tokens
        theorem_tokens = set(theorem_context.theorem_statement.split())
        candidate_tokens = set(candidate.type.split())
        if theorem_tokens and candidate_tokens:
            common_tokens = theorem_tokens & candidate_tokens
            type_similarity = len(common_tokens) / max(len(theorem_tokens), len(candidate_tokens))
            score += 0.4 * type_similarity

        # Proof length similarity (0.3 weight)
        if candidate.value and theorem_context.original_proof:
            theorem_length = len(theorem_context.original_proof)
            candidate_length = len(candidate.value.pp)
            if theorem_length > 0 and candidate_length > 0:
                length_ratio = min(theorem_length, candidate_length) / max(
                    theorem_length, candidate_length
                )
                score += 0.3 * length_ratio

        return score

    def _find_declaration(
        self, identifier: str, declarations: list[Declaration]
    ) -> Declaration | None:
        """
        Find a declaration by identifier.

        Args:
            identifier: Identifier to find
            declarations: List of declarations to search

        Returns:
            Declaration if found, None otherwise
        """
        for decl in declarations:
            if decl.full_name == identifier or decl.name == identifier:
                return decl
        return None

    def clear_cache(self) -> None:
        """
        Clear the context cache.

        This should be called when the file changes to ensure fresh context.
        """
        self._context_cache.clear()
        logger.debug("Cleared context cache")
