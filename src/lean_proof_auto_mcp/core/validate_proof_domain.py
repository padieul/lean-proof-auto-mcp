"""
Core domain structures and handler for proof validation.

This module defines the Command/Handler pattern for proof validation operations,
following hexagonal architecture principles and dependency injection.

Requirements: 4.1, 4.2, 4.6
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

    This command encapsulates all parameters needed to validate a proof attempt
    against a theorem statement, following the Command pattern for clean entry points.

    Requirements: 4.1

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
        """
        Validate command parameters.

        Raises:
            ValueError: If any parameter is invalid

        Requirements: 4.1
        """
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

    This handler implements the proof validation workflow following hexagonal
    architecture principles. It depends only on abstract ports (Querier,
    ProofValidator, HarnessConstructor, ProofStateInspector) and contains
    no infrastructure logic.

    The workflow:
    1. Extract theorem declaration using querier
    2. Construct test harness with proof attempt
    3. Validate proof using validator
    4. Enrich with proof state if incomplete (optional)
    5. Return structured validation result

    Requirements: 4.2, 4.6
    """

    def __init__(
        self,
        querier: "Querier",
        validator: "ProofValidator",
        constructor: "HarnessConstructor",
        proof_state_inspector: "ProofStateInspector | None" = None,
        metadata_collector: "MetadataCollector | None" = None,
    ):
        """
        Initialize handler with dependency injection.

        All dependencies are injected at construction time, following
        dependency injection principles. No infrastructure is created internally.

        Args:
            querier: Port for querying Lean files to extract declarations
            validator: Port for validating proof attempts
            constructor: Port for constructing test harnesses
            proof_state_inspector: Optional port for inspecting proof states
            metadata_collector: Optional port for collecting environment metadata

        Requirements: 4.2
        """
        self.querier = querier
        self.validator = validator
        self.constructor = constructor
        self.proof_state_inspector = proof_state_inspector
        self.metadata_collector = metadata_collector

    def handle(self, cmd: ValidateProofCommand) -> "ValidationResult":
        """
        Execute proof validation workflow.

        This method orchestrates the entire validation process with explicit
        error handling at each stage following the Result/Either pattern.

        Error handling strategy:
        - Theorem not found: Raise ValueError
        - Harness construction errors: Raise RuntimeError
        - Validation errors: Return ValidationResult with error status
        - Proof state inspection: Best effort, log errors but don't fail

        Args:
            cmd: Validation command with all parameters

        Returns:
            ValidationResult with status, error information, and optional proof state

        Raises:
            ValueError: If theorem not found
            RuntimeError: If harness construction fails

        Requirements: 4.2, 4.6
        """
        logger.info(
            f"Validating proof for theorem {cmd.theorem_id} in {cmd.file_path}"
        )

        # Step 1: Extract theorem using querier
        try:
            declarations = self.querier.extract_declarations(cmd.file_path)
            theorem = self._find_theorem(declarations, cmd.theorem_id)
        except Exception as e:
            logger.error(f"Failed to extract theorem: {e}")
            raise ValueError(f"Theorem {cmd.theorem_id} not found: {e}") from e

        # Step 2: Construct harness with proof attempt
        from .harness_construction import HarnessConfig, HarnessError

        harness_config = HarnessConfig(
            theorem_id=cmd.theorem_id,
            file_path=cmd.file_path,
            proof_attempt=cmd.proof_attempt,
        )

        harness_result = self.constructor.construct(harness_config)

        # Check if construction was successful
        if isinstance(harness_result, HarnessError):
            logger.error(f"Harness construction failed: {harness_result.message}")
            raise RuntimeError(
                f"Failed to construct harness: {harness_result.message}"
            )

        # Step 3: Validate proof using ProofValidator port
        #
        # Pass file_path and theorem_id so the validator uses the import-based
        # harness path (which re-uses the constructor's caches) instead of the
        # standalone fallback that wraps proof_attempt in a bare
        # "theorem ... := by\n{proof_attempt}" — which would double-wrap the
        # already-constructed harness code and produce invalid Lean.
        try:
            result = self.validator.validate_proof(
                theorem_statement=theorem.type,
                proof_attempt=cmd.proof_attempt,
                timeout_s=cmd.timeout_s,
                file_path=cmd.file_path,
                theorem_id=cmd.theorem_id,
            )
        except Exception as e:
            logger.error(f"Proof validation failed: {e}")
            # Convert to ValidationResult with error status
            from ..lean.ports import ValidationResult

            result = ValidationResult(
                status="error",
                error_message=str(e),
                error_location=None,
                proof_state=None,
                suggestions=[],
                time_s=0.0,
            )

        # Step 4: Enrich with proof state if incomplete and requested
        if (
            result.status == "incomplete"
            and cmd.return_proof_state
            and self.proof_state_inspector
        ):
            try:
                proof_state = self.proof_state_inspector.get_initial_proof_state(
                    theorem
                )
                # Create enriched result with proof state
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
                # Log but don't fail - proof state is optional enrichment
                logger.warning(f"Failed to get proof state: {e}")

        logger.info(f"Validation complete: status={result.status}")
        return result

    def _find_theorem(self, declarations: list, theorem_id: str):
        """
        Find theorem in declarations list.

        Matches by name or full_name, handling both simple names and
        namespaced names (e.g., "Subgroup.mem_prod").

        Args:
            declarations: List of Declaration objects
            theorem_id: Theorem identifier to find

        Returns:
            Declaration object for the theorem

        Raises:
            ValueError: If theorem not found

        Requirements: 4.2
        """
        # Extract local name (without namespace) for matching
        local_name = theorem_id.split(".")[-1] if "." in theorem_id else theorem_id

        for decl in declarations:
            if (
                decl.name == theorem_id
                or decl.full_name == theorem_id
                or decl.name == local_name
                or decl.full_name == local_name
            ):
                return decl

        raise ValueError(f"Theorem {theorem_id} not found in declarations")
