"""

MCP tool entry point for the get_proof_context tool.


This module provides rich context extraction for theorems including statement,

original proof, hypotheses, in-scope declarations, and similar proofs for

LLM reasoning and pattern matching.


Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 29.5, 29.6
"""


import hashlib

import logging
import uuid

from datetime import datetime, timezone

from pathlib import Path

from typing import Any


from ..core.context_extractor import ContextExtractor

from ..lean.proof_state import LeanInteractProofStateInspector

from ..lean.querier import LeanInteractQuerier

from ..observability import SubprocessMetadataCollector


logger = logging.getLogger(__name__)


API_VERSION = "0.2.0"



def get_proof_context(args: dict[str, Any]) -> dict[str, Any]:
    """

    Get rich context about a theorem.


    This tool extracts comprehensive context for LLM reasoning including:

    - Complete theorem statement

    - Original proof body

    - Available hypotheses

    - In-scope declarations

    - Current namespace

    - Similar proofs with similarity scores (optional)

    - Environment metadata for debugging


    Args:

        args: Dictionary with context parameters:

            - file: Path to Lean file (required)

            - theorem_id: Theorem identifier (required)

            - include_similar_proofs: Include similar proofs (default: True)

            - similarity_threshold: Minimum similarity score (default: 0.7)


    Returns:

        Dictionary with fields:

        - api_version: API version string

        - status: "success" or "error"

        - run_id: Unique run identifier

        - file: File path

        - theorem_id: Theorem identifier

        - theorem_statement: Complete theorem statement

        - original_proof: Original proof body

        - hypotheses: List of available hypotheses

        - in_scope: List of in-scope declarations

        - namespace: Current namespace

        - similar_proofs: List of similar proofs (if requested)

        - metadata: Environment metadata (git commit, lean version, lake version)

        - timing: Timing information


    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 29.5, 29.6
    """

    # Validate and coerce arguments

    try:

        file_path, theorem_id, include_similar, similarity_threshold, run_id = _validate_args(args)

    except ValueError as e:

        # Return error response for invalid inputs

        return _build_error_response(

            file=args.get("file", "<invalid>"),

            theorem_id=args.get("theorem_id", "<invalid>"),

            error_message=str(e),

            error_code="input_validation_error",

        )


    # Execute context extraction with error handling wrapper

    try:

        # Create extractor with real adapters (composition root)

        extractor = _create_extractor(file_path)


        # Create SubprocessMetadataCollector at composition root

        metadata_collector = SubprocessMetadataCollector()


        # Execute context extraction

        context = extractor.extract_context(

            file_path=file_path,

            theorem_id=theorem_id,

            include_similar=include_similar,

            similarity_threshold=similarity_threshold,

        )


        # Collect metadata

        metadata = metadata_collector.collect_version_info()


        # Convert result to dict

        return _format_response(context, file_path, theorem_id, run_id, metadata)


    except Exception as e:

        # Catch all exceptions and return error response

        logger.exception(f"Context extraction failed for {file_path}:{theorem_id}")

        return _build_error_response(

            file=file_path,

            theorem_id=theorem_id,

            error_message=f"Context extraction error: {str(e)}",

            error_code="internal_error",

        )



def _validate_args(args: dict[str, Any]) -> tuple[str, str, bool, float, str]:
    """

    Validate and extract arguments.


    Args:

        args: Raw arguments dict


    Returns:

        Tuple of (file_path, theorem_id, include_similar, similarity_threshold, run_id)


    Raises:

        ValueError: If any argument is invalid


    Requirements: 8.1
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


    # Validate and extract include_similar_proofs (optional, default: True)

    include_similar = args.get("include_similar_proofs", True)

    if not isinstance(include_similar, bool):

        raise ValueError("'include_similar_proofs' must be a boolean")


    # Validate and extract similarity_threshold (optional, default: 0.7)

    similarity_threshold = args.get("similarity_threshold", 0.7)

    if not isinstance(similarity_threshold, (int, float)):

        raise ValueError("'similarity_threshold' must be a number")

    if not 0.0 <= similarity_threshold <= 1.0:

        raise ValueError("'similarity_threshold' must be between 0.0 and 1.0")

    similarity_threshold = float(similarity_threshold)


    # Generate run_id

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]

    random_suffix = uuid.uuid4().hex[:6]

    run_id = f"context-{timestamp}-{file_hash}-{random_suffix}"


    return file_path, theorem_id, include_similar, similarity_threshold, run_id



def _create_extractor(file_path: str) -> ContextExtractor:
    """

    Create ContextExtractor with real adapters (composition root).


    This function wires together all dependencies:

    - Querier for declaration extraction

    - ProofStateInspector for proof state inspection

    - ContextExtractor for context extraction


    Args:

        file_path: Path to the file being analyzed (used to detect project root)


    Returns:

        Configured ContextExtractor


    Raises:

        FileNotFoundError: If the file does not exist


    Requirements: 29.5, 29.6
    """

    # Detect project root from file path

    file_path_obj = Path(file_path).resolve()


    # Check if file exists

    if not file_path_obj.exists():

        raise FileNotFoundError(f"File not found: {file_path}")


    project_root = _find_lean_project_root(file_path_obj)


    # If no Lean project found, use the file's directory

    if project_root is None:

        project_root = file_path_obj.parent


    # Create ServerManager with workspace context

    from ..lean.server_manager import LeanInteractServerManager

    server_manager = LeanInteractServerManager(workspace_path=project_root)


    # Create Querier with ServerManager

    querier = LeanInteractQuerier(server_manager=server_manager)


    # Create ProofStateInspector with ServerManager

    proof_state_inspector = LeanInteractProofStateInspector(server_manager=server_manager)


    # Create ContextExtractor

    return ContextExtractor(querier=querier, proof_state_inspector=proof_state_inspector)



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

    context: Any,  # ProofContext
    file_path: str,
    theorem_id: str,
    run_id: str,

    metadata: dict[str, str],

) -> dict[str, Any]:
    """

    Format ProofContext as JSON response.


    Args:

        context: ProofContext from extractor

        file_path: File path

        theorem_id: Theorem identifier

        run_id: Run identifier

        metadata: Environment metadata


    Returns:

        JSON response dict


    Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 29.6
    """

    # Format similar proofs

    similar_proofs_list = []

    for similar in context.similar_proofs:

        similar_proofs_list.append(

            {
                "theorem_id": similar.theorem_id,

                "similarity": similar.similarity,
                "theorem_statement": similar.theorem_statement,
                "proof": similar.proof,
                "hints_used": similar.hints_used,

            }

        )


    return {

        "api_version": API_VERSION,
        "status": "success",
        "run_id": run_id,
        "file": file_path,
        "theorem_id": theorem_id,

        "theorem_statement": context.theorem_statement,

        "original_proof": context.original_proof,

        "hypotheses": context.hypotheses,

        "in_scope": context.in_scope,

        "namespace": context.namespace,
        "similar_proofs": similar_proofs_list,
        "metadata": metadata,

        "timing": {

            "total_s": 0.0,  # TODO: Add actual timing

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


    Requirements: 8.1
    """

    # Generate run_id for error response

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    file_str = str(file) if file is not None else "<invalid>"

    if not file_str or not file_str.strip():

        file_str = "<invalid>"

    file_hash = hashlib.md5(file_str.encode()).hexdigest()[:8]

    random_suffix = uuid.uuid4().hex[:6]

    run_id = f"context-{timestamp}-{file_hash}-{random_suffix}"


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
        "theorem_statement": "",

        "original_proof": "",

        "hypotheses": [],

        "in_scope": [],
        "namespace": "",

        "similar_proofs": [],

        "metadata": {"error_code": error_code, "error_message": error_message},

        "timing": {"total_s": 0.0},

    }

