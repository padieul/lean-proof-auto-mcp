"""
MCP tool entry point for the try_automated_proof tool.

This module provides fast validation of LLM-generated proof attempts with
detailed feedback, tactical suggestions, and metadata collection.

Requirements: 7.1, 7.2, 7.8, 29.5, 29.6
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..lean.server_manager import ServerManagerImpl
from ..lean.validator import ProofValidatorImpl
from ..observability import SubprocessMetadataCollector

logger = logging.getLogger(__name__)

API_VERSION = "0.2.0"


def try_automated_proof(args: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a proof attempt with detailed feedback.

    This tool provides fast validation of LLM-generated proof attempts,
    returning structured feedback including:
    - Validation status (success, error, incomplete, timeout)
    - Error messages with location information
    - Remaining proof state for incomplete proofs
    - Tactical suggestions for next steps
    - Environment metadata for debugging

    Args:
        args: Dictionary with validation parameters:
            - file: Path to Lean file (required)
            - theorem_id: Theorem identifier (required)
            - proof_attempt: Proof code to validate (required)
            - timeout_s: Timeout in seconds (default: 10.0)
            - return_proof_state: Return proof state for incomplete proofs (default: True)

    Returns:
        Dictionary with fields:
        - api_version: API version string
        - status: "success", "error", "incomplete", or "timeout"
        - run_id: Unique run identifier
        - file: File path
        - theorem_id: Theorem identifier
        - validation_status: Validation result status
        - error_message: Error message (if any)
        - error_location: Error location as [line, column] (if any)
        - proof_state: Remaining proof state (if incomplete)
        - suggestions: List of tactical suggestions
        - metadata: Environment metadata (git commit, lean version, lake version)
        - timing: Timing information

    Requirements: 7.1, 7.2, 7.8, 29.5, 29.6
    """
    # Validate and coerce arguments
    try:
        file_path, theorem_id, proof_attempt, timeout_s, return_proof_state, run_id = (
            _validate_args(args)
        )
    except ValueError as e:
        # Return error response for invalid inputs
        return _build_error_response(
            file=args.get("file", "<invalid>"),
            theorem_id=args.get("theorem_id", "<invalid>"),
            error_message=str(e),
            error_code="input_validation_error",
        )

    # Execute validation with error handling wrapper
    try:
        # Create validator with real adapters (composition root)
        validator, querier = _create_validator(file_path)

        # Create SubprocessMetadataCollector at composition root
        metadata_collector = SubprocessMetadataCollector()

        # Extract theorem statement from file
        try:
            # Type assertion to help mypy understand querier has extract_declarations
            from ..lean.querier import LeanInteractQuerierImpl

            assert isinstance(querier, LeanInteractQuerierImpl)
            declarations = querier.extract_declarations(file_path)
            theorem = None
            for decl in declarations:
                if decl.full_name == theorem_id or decl.name == theorem_id:
                    theorem = decl
                    break

            if theorem is None:
                raise ValueError(f"Theorem not found: {theorem_id}")

            theorem_statement = theorem.type
        except Exception as e:
            logger.error(f"Failed to extract theorem {theorem_id} from {file_path}: {e}")
            return _build_error_response(
                file=file_path,
                theorem_id=theorem_id,
                error_message=f"Failed to extract theorem: {str(e)}",
                error_code="theorem_extraction_error",
            )

        # Execute validation
        result = validator.validate_proof(
            theorem_statement=theorem_statement,
            proof_attempt=proof_attempt,
            timeout_s=timeout_s,
            file_path=file_path,
            theorem_id=theorem_id,
        )

        # Collect metadata
        metadata = metadata_collector.collect_version_info()

        # Convert result to dict
        return _format_response(result, file_path, theorem_id, run_id, return_proof_state, metadata)

    except Exception as e:
        # Catch all exceptions and return error response
        logger.exception(f"Validation failed for {file_path}:{theorem_id}")
        return _build_error_response(
            file=file_path,
            theorem_id=theorem_id,
            error_message=f"Validation error: {str(e)}",
            error_code="internal_error",
        )


def _validate_args(args: dict[str, Any]) -> tuple[str, str, str, float, bool, str]:
    """
    Validate and extract arguments.

    Args:
        args: Raw arguments dict

    Returns:
        Tuple of (file_path, theorem_id, proof_attempt, timeout_s, return_proof_state, run_id)

    Raises:
        ValueError: If any argument is invalid

    Requirements: 7.1, 7.2
    """
    # Validate and extract file (required)
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("'file' must be a non-empty string")
    file_path = file.strip()

    # Validate and extract theorem_id (required)
    theorem_id = args.get("theorem_id")
    if not isinstance(theorem_id, str) or not theorem_id.strip():
        raise ValueError("'theorem_id' must be a non-empty string")
    theorem_id = theorem_id.strip()

    # Validate and extract proof_attempt (required)
    proof_attempt = args.get("proof_attempt")
    if not isinstance(proof_attempt, str) or not proof_attempt.strip():
        raise ValueError("'proof_attempt' must be a non-empty string")
    proof_attempt = proof_attempt.strip()

    # Validate and extract timeout_s (optional, default: 10.0)
    timeout_s = args.get("timeout_s", 10.0)
    if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
        raise ValueError("'timeout_s' must be a positive number")
    timeout_s = float(timeout_s)

    # Validate and extract return_proof_state (optional, default: True)
    return_proof_state = args.get("return_proof_state", True)
    if not isinstance(return_proof_state, bool):
        raise ValueError("'return_proof_state' must be a boolean")

    # Generate run_id
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
    random_suffix = uuid.uuid4().hex[:6]
    run_id = f"try-proof-{timestamp}-{file_hash}-{random_suffix}"

    return file_path, theorem_id, proof_attempt, timeout_s, return_proof_state, run_id


def _create_validator(file_path: str) -> tuple[ProofValidatorImpl, object]:
    """
    Create ProofValidator with real adapters (composition root).

    This function wires together all dependencies:
    - ServerManager for LeanInteract server lifecycle
    - LeanInteractQuerier for theorem extraction
    - ProofValidator for proof validation

    Args:
        file_path: Path to the file being validated (used to detect project root)

    Returns:
        Tuple of (ProofValidatorImpl, LeanInteractQuerierImpl)

    Raises:
        FileNotFoundError: If the file does not exist

    Requirements: 29.5, 29.6
    """
    from ..lean.querier import LeanInteractQuerierImpl

    # Detect project root from file path
    file_path_obj = Path(file_path).resolve()

    # Check if file exists
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    project_root = _find_lean_project_root(file_path_obj)

    # If no Lean project found, use the file's directory
    if project_root is None:
        project_root = file_path_obj.parent

    # Create ServerManager WITH workspace_path for proper Lake project context
    # This ensures all declarations are visible (fixes 116 vs 123 declaration issue)
    server_manager = ServerManagerImpl(workspace_path=project_root)

    # Create querier for theorem extraction
    querier = LeanInteractQuerierImpl(server_manager)

    # Get or create server for file
    server = server_manager.get_server(file_path)

    # Attach server_manager to server for harness construction
    # This allows the validator to access the harness constructor
    server.server_manager = server_manager  # type: ignore[attr-defined]

    # Create ProofValidator with server
    validator = ProofValidatorImpl(server=server)

    return validator, querier


def _find_lean_project_root(file_path: Path) -> Path | None:
    """
    Find the Lean project root by looking for lakefile.toml or lakefile.lean.

    Args:
        file_path: Path to a file in the project

    Returns:
        Path to project root, or None if not found
    """
    current = file_path if file_path.is_dir() else file_path.parent

    # Search up to 10 levels
    for _ in range(10):
        if (current / "lakefile.toml").exists() or (current / "lakefile.lean").exists():
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    return None


def _format_response(
    result: Any,  # ValidationResult
    file_path: str,
    theorem_id: str,
    run_id: str,
    return_proof_state: bool,
    metadata: dict[str, str],
) -> dict[str, Any]:
    """
    Format ValidationResult as JSON response.

    Args:
        result: ValidationResult from validator
        file_path: File path
        theorem_id: Theorem identifier
        run_id: Run identifier
        return_proof_state: Whether to include proof state
        metadata: Environment metadata

    Returns:
        JSON response dict

    Requirements: 7.3, 7.4, 7.5, 7.6, 7.7, 29.6
    """
    # Determine overall status
    status_map = {
        "success": "success",
        "error": "error",
        "incomplete": "incomplete",
        "timeout": "timeout",
    }
    status = status_map.get(result.status, "error")

    # Format error location
    error_location = None
    if result.error_location:
        error_location = list(result.error_location)

    # Format proof state
    proof_state_dict = None
    if return_proof_state and result.proof_state:
        proof_state_dict = {
            "goal": result.proof_state.goal,
            "hypotheses": result.proof_state.hypotheses,
            "type_context": result.proof_state.type_context,
            "goals_remaining": result.proof_state.goals_remaining,
        }

    return {
        "api_version": API_VERSION,
        "status": status,
        "run_id": run_id,
        "file": file_path,
        "theorem_id": theorem_id,
        "validation_status": result.status,
        "error_message": result.error_message,
        "error_location": error_location,
        "proof_state": proof_state_dict,
        "suggestions": result.suggestions,
        "metadata": metadata,
        "timing": {
            "validation_s": result.time_s,
            "total_s": result.time_s,
        },
    }


def _build_error_response(
    file: str,
    theorem_id: str,
    error_message: str,
    error_code: str,
) -> dict[str, Any]:
    """
    Build error response with consistent structure.

    Args:
        file: File path from request
        theorem_id: Theorem ID from request
        error_message: Human-readable error message
        error_code: Machine-readable error code

    Returns:
        Error response dict

    Requirements: 7.8
    """
    # Generate run_id for error response
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_str = str(file) if file is not None else "<invalid>"
    if not file_str or not file_str.strip():
        file_str = "<invalid>"
    file_hash = hashlib.md5(file_str.encode()).hexdigest()[:8]
    random_suffix = uuid.uuid4().hex[:6]
    run_id = f"try-proof-{timestamp}-{file_hash}-{random_suffix}"

    # Ensure theorem_id is non-empty string
    theorem_id_str = str(theorem_id) if theorem_id is not None else "<invalid>"
    if not theorem_id_str or not theorem_id_str.strip():
        theorem_id_str = "<invalid>"

    return {
        "api_version": API_VERSION,
        "status": "error",
        "run_id": run_id,
        "file": file_str,
        "theorem_id": theorem_id_str,
        "validation_status": "error",
        "error_message": error_message,
        "error_location": None,
        "proof_state": None,
        "suggestions": ["Fix input validation errors"],
        "metadata": {"error_code": error_code, "error_message": error_message},
        "timing": {"validation_s": 0.0, "total_s": 0.0},
    }
