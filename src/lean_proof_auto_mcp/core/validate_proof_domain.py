"""
Core domain structures and handler for proof validation.

This module defines the Command/Handler pattern for proof validation operations,
following hexagonal architecture principles and dependency injection.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..lean.ports import (
        ProofStateInspector,
        ProofValidator,
        Querier,
        ValidationResult,
    )
    from ..observability.ports import MetadataCollector
    from .harness_construction import HarnessConstructor

logger = logging.getLogger(__name__)


# ============================================================================
# Command Data Structure (Immutable)
# ============================================================================


@dataclass(frozen=True)
class ValidateProofCommand:
    """
    Immutable command representing a proof validation request.

    Attributes:
        file_path: Path to Lean file containing the theorem
        theorem_id: Identifier of the theorem to validate
        proof_attempt: Proof code to validate
        timeout_s: Timeout in seconds (default: 10.0)
        return_proof_state: Whether to return proof state for incomplete proofs
    """

    file_path: str
    theorem_id: str
    proof_attempt: str
    timeout_s: float = 10.0
    return_proof_state: bool = True

    def __post_init__(self) -> None:
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")
        if not self.proof_attempt:
            raise ValueError("proof_attempt must be non-empty")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")


# ============================================================================
# Command Handler (Core Orchestrator)
# ============================================================================


class ValidateProofCommandHandler:
    """
    Orchestrates proof validation operations.

    Workflow:
    1. Extract theorem declaration using querier.
    2. Construct harness code exactly once.
    3. Validate that exact prebuilt harness code.
    4. Enrich with proof state if incomplete (optional).
    """

    def __init__(
        self,
        querier: "Querier",
        validator: "ProofValidator",
        constructor: "HarnessConstructor",
        proof_state_inspector: "ProofStateInspector | None" = None,
        metadata_collector: "MetadataCollector | None" = None,
    ):
        self.querier = querier
        self.validator = validator
        self.constructor = constructor
        self.proof_state_inspector = proof_state_inspector
        self.metadata_collector = metadata_collector

    def handle(self, cmd: ValidateProofCommand) -> "ValidationResult":
        """Execute proof validation workflow."""
        logger.info(f"Validating proof for theorem {cmd.theorem_id} in {cmd.file_path}")

        # Step 1: Extract theorem using deterministic matching
        try:
            declarations = self.querier.extract_declarations(cmd.file_path)
            theorem = self._find_theorem(declarations, cmd.theorem_id)
        except Exception as e:
            logger.error(f"Failed to extract theorem: {e}")
            raise ValueError(f"Theorem {cmd.theorem_id} not found: {e}") from e

        # Step 2: Construct harness once
        from .harness_construction import HarnessConfig, HarnessError

        file_content = self.querier.read_source_file(cmd.file_path)
        harness_config = HarnessConfig(
            theorem_id=cmd.theorem_id,
            file_path=cmd.file_path,
            proof_attempt=cmd.proof_attempt,
            file_content=file_content,
            declarations=declarations,
        )
        harness_result = self.constructor.construct(harness_config)
        if isinstance(harness_result, HarnessError):
            logger.error(f"Harness construction failed: {harness_result.message}")
            raise RuntimeError(f"Failed to construct harness: {harness_result.message}")

        # Step 3: Validate exactly the prebuilt harness code
        try:
            if hasattr(self.validator, "validate_harness_code"):
                result = self.validator.validate_harness_code(
                    harness_code=harness_result.code,
                    timeout_s=cmd.timeout_s,
                    file_path=cmd.file_path,
                )
            else:
                # Backward-compatible fallback for custom validators that do
                # not yet implement validate_harness_code.
                logger.warning(
                    "ProofValidator lacks validate_harness_code; falling back to validate_proof"
                )
                result = self.validator.validate_proof(
                    theorem_statement=theorem.type,
                    proof_attempt=cmd.proof_attempt,
                    timeout_s=cmd.timeout_s,
                    file_path=cmd.file_path,
                    theorem_id=cmd.theorem_id,
                )
        except Exception as e:
            logger.error(f"Proof validation failed: {e}")
            from ..lean.ports import ValidationResult

            result = ValidationResult(
                status="error",
                error_message=str(e),
                error_location=None,
                proof_state=None,
                suggestions=[],
                time_s=0.0,
            )

        # Step 4: Optional proof-state enrichment
        if (
            result.status == "incomplete"
            and cmd.return_proof_state
            and self.proof_state_inspector
        ):
            try:
                proof_state = self.proof_state_inspector.get_initial_proof_state(theorem)
                from ..lean.ports import ValidationResult

                result = ValidationResult(
                    status=result.status,
                    error_message=result.error_message,
                    error_location=result.error_location,
                    proof_state=proof_state,
                    suggestions=result.suggestions,
                    time_s=result.time_s,
                )
            except Exception as e:
                logger.warning(f"Failed to get proof state: {e}")

        logger.info(f"Validation complete: status={result.status}")
        return result

    def _find_theorem(self, declarations: list, theorem_id: str):
        """
        Find theorem in declarations list with deterministic matching.

        Priority:
        1. exact full_name
        2. exact name
        3. local-name fallback (only if unique)
        """
        theorem_decls = [
            d for d in declarations if getattr(d, "kind", "") in ("theorem", "lemma")
        ]

        def _select_unique(matches: list, label: str):
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                names = ", ".join(
                    getattr(d, "full_name", getattr(d, "name", "<unknown>"))
                    for d in matches[:5]
                )
                raise ValueError(f"Ambiguous theorem_id '{theorem_id}' ({label}): {names}")
            return None

        full_exact = [d for d in theorem_decls if d.full_name == theorem_id]
        selected = _select_unique(full_exact, "exact_full_name")
        if selected is not None:
            return selected

        name_exact = [d for d in theorem_decls if d.name == theorem_id]
        selected = _select_unique(name_exact, "exact_name")
        if selected is not None:
            return selected

        local_name = theorem_id.split(".")[-1]
        local_matches = [
            d
            for d in theorem_decls
            if d.name == local_name
            or d.full_name == local_name
            or d.full_name.endswith(f".{local_name}")
        ]
        selected = _select_unique(local_matches, "local_name_fallback")
        if selected is not None:
            return selected

        raise ValueError(f"Theorem {theorem_id} not found in declarations")
