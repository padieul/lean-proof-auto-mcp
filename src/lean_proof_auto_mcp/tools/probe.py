"""

MCP tool entry point for the probe tool.


This module provides the MCP tool interface for automation probing, implementing

argument validation, composition root, error handling, and response formatting.


Requirements: 1.1, 3.1-3.8, 10.1-10.3, 10.5
"""

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..adapters.artifact_store import FilesystemArtifactStore
from ..adapters.workspace_provider import create_workspace_provider
from ..core.probe_classifier import HeuristicClassifier
from ..core.probe_domain import ProbeCommand, ProbeCommandHandler

logger = logging.getLogger(__name__)


API_VERSION = "0.1.0"


# Artifacts directory for storing probe logs

ARTIFACTS_DIR = Path(".artifacts")


def probe(args: dict[str, Any]) -> dict[str, Any]:
    """

    Run single-theorem automation probe with deterministic classification.


    This is the main MCP tool entry point that:

    1. Validates and coerces arguments

    2. Builds ProbeCommand from args

    3. Creates handler with real adapters (composition root)

    4. Calls handler.handle(command)

    5. Returns ProbeResult as dict

    6. Handles all errors gracefully


    Args:

        args: Dictionary with probe parameters:

            - file: Path to Lean file (required)

            - theorem_id: Theorem identifier (required)

            - mode: Automation mode - "aesop", "aesop?", or "grind" (required)

            - budget_s: Time budget in seconds (default: 30.0)

            - trace_config: Optional trace configuration dict


    Returns:

        Dictionary conforming to probe output schema with fields:

        - api_version, status, run_id, probe_result

        - diagnostics, timing, metadata


    Requirements: 1.1, 3.1-3.8, 10.1-10.3, 10.5
    """

    # Validate and coerce arguments

    try:
        command = _build_command(args)

    except ValueError as e:
        # Return error response for invalid inputs

        return _build_error_response(
            file=args.get("file", "<invalid>"),
            theorem_id=args.get("theorem_id", "<invalid>"),
            mode=args.get("mode", "<invalid>"),
            error_message=str(e),
            error_code="input_validation_error",
        )

    # Execute probe with error handling wrapper

    try:
        # Create handler with real adapters (composition root)

        handler = _create_handler(command.file_path)

        # Execute probe

        result = handler.handle(command)

        # Convert result to dict

        return asdict(result)

    except Exception as e:
        # Catch all exceptions and return error response

        logger.exception(f"Probe failed for {command.file_path}:{command.theorem_id}")

        return _build_error_response(
            file=command.file_path,
            theorem_id=command.theorem_id,
            mode=command.mode,
            error_message=f"Probe error: {str(e)}",
            error_code="internal_error",
        )


def _build_command(args: dict[str, Any]) -> ProbeCommand:
    """

    Build ProbeCommand from args dict with validation and coercion.


    This function:

    - Validates file is non-empty string

    - Validates theorem_id is non-empty string

    - Validates mode is one of "aesop", "aesop?", or "grind"

    - Validates budget_s is positive number

    - Validates trace_config is dict or None

    - Provides defaults for optional parameters

    - Raises ValueError for invalid inputs


    Args:

        args: Raw arguments dict


    Returns:

        Validated ProbeCommand


    Raises:

        ValueError: If any argument is invalid


    Requirements: 1.1, 3.1, 10.3
    """

    # Validate and extract file (required)

    file = args.get("file")

    if not isinstance(file, str) or not file.strip():
        raise ValueError("'file' must be a non-empty string")

    # Validate and extract theorem_id (required)

    theorem_id = args.get("theorem_id")

    if not isinstance(theorem_id, str) or not theorem_id.strip():
        raise ValueError("'theorem_id' must be a non-empty string")

    # Validate and extract mode (required)

    mode = args.get("mode")

    if not isinstance(mode, str):
        raise ValueError("'mode' must be a string")

    if mode not in ("aesop", "aesop?", "grind"):
        raise ValueError("'mode' must be 'aesop', 'aesop?', or 'grind'")

    # Validate and extract budget_s (optional, default: 30.0)
    # 30s accommodates Mathlib-scale projects where the Lean REPL needs
    # 10-20s to load the environment on first use.
    budget_s = args.get("budget_s", 30.0)

    if not isinstance(budget_s, int | float):
        raise ValueError("'budget_s' must be a number")

    budget_s = float(budget_s)

    if budget_s <= 0:
        raise ValueError("'budget_s' must be positive")

    # Validate and extract trace_config (optional, default: None)

    trace_config = args.get("trace_config")

    if trace_config is not None and not isinstance(trace_config, dict):
        raise ValueError("'trace_config' must be a dict or null")

    # Build and return command (validation happens in __post_init__)

    return ProbeCommand(
        file_path=file.strip(),
        theorem_id=theorem_id.strip(),
        mode=mode,
        budget_s=budget_s,
        trace_config=trace_config,
    )


def _create_handler(file_path: str) -> ProbeCommandHandler:
    """

    Create ProbeCommandHandler with real adapters (composition root).


    This function wires together all dependencies following hexagonal architecture:

    - Single LeanInteractServerManager instance

    - LeanInteractQuerier for querying Lean files

    - LeanInteractProofValidator for proof validation

    - RangeBasedHarnessConstructor for harness construction

    - GitWorktreeProvider or TempCopyProvider for workspace isolation

    - HeuristicClassifier for outcome classification


    Args:

        file_path: Path to the file being probed (used to detect project root)


    Returns:

        Configured ProbeCommandHandler


    Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 7.5, 7.6
    """

    # Detect project root from file path

    # Look for lakefile.toml or lakefile.lean in parent directories

    file_path_obj = Path(file_path).resolve()

    project_root = _find_lean_project_root(file_path_obj)

    # If no Lean project found, use the file's directory

    if project_root is None:
        project_root = file_path_obj.parent

    # 1. Get shared ServerManager (persists across tool calls, project-keyed)

    from ..lean.server_manager import get_shared_server_manager

    server_manager = get_shared_server_manager(project_root)

    # 2. Create LeanInteractQuerier with ServerManager

    from ..lean.querier import LeanInteractQuerier

    querier = LeanInteractQuerier(server_manager=server_manager)

    # 3. Create RangeBasedHarnessConstructor (zero dependencies — pure core)
    from ..core.harness_construction import RangeBasedHarnessConstructor

    constructor = RangeBasedHarnessConstructor()

    # 4. Create LeanInteractProofValidator with ServerManager, HarnessConstructor, and Querier

    from ..lean.validator import LeanInteractProofValidator

    validator = LeanInteractProofValidator(
        server_manager=server_manager, harness_constructor=constructor, querier=querier
    )

    # 5. Create workspace provider (auto-detect mode)

    workspace_provider = create_workspace_provider(
        workspace_mode=None,  # Auto-detect
        project_root=project_root,
        worktree_dir=project_root / ".worktrees",
    )

    # 6. Create classifier

    classifier = HeuristicClassifier()

    # 7. Create artifact store

    artifact_store = FilesystemArtifactStore(ARTIFACTS_DIR)

    # 8. Create metadata collector

    from ..observability import SubprocessMetadataCollector

    metadata_collector = SubprocessMetadataCollector()

    # 9. Wire all dependencies into ProbeCommandHandler

    return ProbeCommandHandler(
        validator=validator,
        querier=querier,
        workspace_provider=workspace_provider,
        classifier=classifier,
        harness_constructor=constructor,
        artifact_store=artifact_store,
        metadata_collector=metadata_collector,
    )


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


def _build_error_response(
    file: str,
    theorem_id: str,
    mode: str,
    error_message: str,
    error_code: str,
) -> dict[str, Any]:
    """

    Build error response with consistent structure.


    This function ensures all errors return valid JSON with the correct schema,

    including error diagnostics and metadata with error codes.


    Args:

        file: File path from request

        theorem_id: Theorem ID from request

        mode: Mode from request

        error_message: Human-readable error message

        error_code: Machine-readable error code


    Returns:

        Error response dict conforming to probe output schema


    Requirements: 10.1, 10.2, 10.3, 10.5
    """

    import hashlib
    import uuid
    from datetime import datetime, timezone

    # Generate run_id for error response

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # Ensure file is a string for hashing

    file_str = str(file) if file is not None else "<invalid>"

    # Ensure file is non-empty for schema compliance

    if not file_str or not file_str.strip():
        file_str = "<invalid>"

    file_hash = hashlib.md5(file_str.encode()).hexdigest()[:8]

    # Add random suffix for uniqueness (same format as success responses)

    random_suffix = uuid.uuid4().hex[:6]

    run_id = f"probe-{timestamp}-{file_hash}-{random_suffix}"

    # Ensure theorem_id is non-empty string

    theorem_id_str = str(theorem_id) if theorem_id is not None else "<invalid>"

    if not theorem_id_str or not theorem_id_str.strip():
        theorem_id_str = "<invalid>"

    # Ensure mode is valid

    mode_str = str(mode) if mode is not None else "<invalid>"

    if mode_str not in ("aesop", "aesop?", "grind"):
        mode_str = "<invalid>"

    return {
        "api_version": API_VERSION,
        "status": "error",
        "run_id": run_id,
        "probe_result": {
            "mode": mode_str,
            "outcome": "error",
            "classification": "error",
            "suggested_script": None,
        },
        "diagnostics": [
            {
                "severity": "error",
                "message": error_message,
                "location": None,
            }
        ],
        "timing": {
            "elapsed_ms": 0.0,
            "budget_s": 0.0,
        },
        "metadata": {
            "error_code": error_code,
        },
    }
