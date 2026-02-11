"""
MCP tool entry point for the probe_file tool.

This module provides the MCP tool interface for batch automation probing,
implementing argument validation, composition root, error handling, and
response formatting.

Requirements: 5.1-5.6, 10.4-10.5
"""

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..adapters.artifact_store import FilesystemArtifactStore
from ..adapters.workspace_provider import create_workspace_provider
from ..core.probe_classifier import HeuristicClassifier
from ..core.probe_domain import (
    ProbeCommandHandler,
    ProbeFileCommand,
    ProbeFileCommandHandler,
)
from .probe import _find_lean_project_root
from .rank_targets import rank_targets
from .scan_file import scan_file

if TYPE_CHECKING:
    from ..core.harness_construction import HarnessConstructor

logger = logging.getLogger(__name__)

API_VERSION = "0.1.0"

# Artifacts directory for storing probe logs
ARTIFACTS_DIR = Path(".artifacts")


def probe_file(args: dict[str, Any]) -> dict[str, Any]:
    """
    Run batch automation probing across multiple theorems in a file.

    This is the main MCP tool entry point that:
    1. Validates and coerces arguments
    2. Builds ProbeFileCommand from args
    3. Creates handler with real adapters (composition root)
    4. Calls handler.handle(command)
    5. Returns ProbeFileResult as dict
    6. Handles all errors gracefully

    Args:
        args: Dictionary with probe_file parameters:
            - file: Path to Lean file (required)
            - mode: Automation mode - "aesop", "aesop?", or "grind" (required)
            - budget_s_per: Time budget per theorem in seconds (default: 30.0)
            - limit: Maximum number of theorems to probe (default: 50)
            - ordering: Ordering mode - "file_order" or "rank_targets" (default: "file_order")

    Returns:
        Dictionary conforming to probe_file output schema with fields:
        - api_version, status, file, summary, results, metadata

    Requirements: 5.1-5.6, 10.4-10.5
    """
    # Validate and coerce arguments
    try:
        command = _build_command(args)
    except ValueError as e:
        # Return error response for invalid inputs
        return _build_error_response(
            file=args.get("file", "<invalid>"),
            error_message=str(e),
            error_code="input_validation_error",
        )

    # Execute probe_file with error handling wrapper
    try:
        # Create handler with real adapters (composition root)
        handler, constructor = _create_handler(command.file_path)

        # Execute probe_file
        result = handler.handle(command)

        # Clear cache after batch completes
        constructor.clear_cache()

        # Convert result to dict
        return asdict(result)

    except Exception as e:
        # Catch all exceptions and return error response
        logger.exception(f"Probe_file failed for {command.file_path}")
        return _build_error_response(
            file=command.file_path,
            error_message=f"Probe_file error: {str(e)}",
            error_code="internal_error",
        )


def _build_command(args: dict[str, Any]) -> ProbeFileCommand:
    """
    Build ProbeFileCommand from args dict with validation and coercion.

    This function:
    - Validates file is non-empty string
    - Validates mode is one of "aesop", "aesop?", or "grind"
    - Validates budget_s_per is positive number
    - Validates limit is positive integer
    - Validates ordering is "file_order" or "rank_targets"
    - Provides defaults for optional parameters
    - Raises ValueError for invalid inputs

    Args:
        args: Raw arguments dict

    Returns:
        Validated ProbeFileCommand

    Raises:
        ValueError: If any argument is invalid

    Requirements: 5.1, 5.5, 5.6, 10.4
    """
    # Validate and extract file (required)
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("'file' must be a non-empty string")

    # Validate and extract mode (required)
    mode = args.get("mode")
    if not isinstance(mode, str):
        raise ValueError("'mode' must be a string")
    if mode not in ("aesop", "aesop?", "grind"):
        raise ValueError("'mode' must be 'aesop', 'aesop?', or 'grind'")

    # Validate and extract budget_s_per (optional, default: 30.0)
    # 30s accommodates Mathlib-scale projects where the Lean REPL needs
    # 10-20s to load the environment on first use. A 5s budget causes a
    # timeout death spiral: timeout → kill REPL → cold restart → timeout.
    budget_s_per = args.get("budget_s_per", 30.0)
    if not isinstance(budget_s_per, int | float):
        raise ValueError("'budget_s_per' must be a number")
    budget_s_per = float(budget_s_per)
    if budget_s_per <= 0:
        raise ValueError("'budget_s_per' must be positive")

    # Validate and extract limit (optional, default: 50)
    limit = args.get("limit", 50)
    if not isinstance(limit, int):
        raise ValueError("'limit' must be an integer")
    if limit <= 0:
        raise ValueError("'limit' must be positive")

    # Validate and extract ordering (optional, default: "file_order")
    ordering = args.get("ordering", "file_order")
    if not isinstance(ordering, str):
        raise ValueError("'ordering' must be a string")
    if ordering not in ("file_order", "rank_targets"):
        raise ValueError("'ordering' must be 'file_order' or 'rank_targets'")

    # Build and return command (validation happens in __post_init__)
    return ProbeFileCommand(
        file_path=file.strip(),
        mode=mode,
        budget_s_per=budget_s_per,
        limit=limit,
        ordering=ordering,
    )


def _create_handler(file_path: str) -> tuple[ProbeFileCommandHandler, "HarnessConstructor"]:
    """
    Create ProbeFileCommandHandler with real adapters (composition root).

    This function wires together all dependencies following hexagonal architecture:
    - Single LeanInteractServerManager instance (shared across all theorems)
    - LeanInteractQuerier for querying Lean files
    - LeanInteractProofValidator for proof validation
    - Single ImportBasedHarnessConstructor with caching (shared across all theorems)
    - GitWorktreeProvider or TempCopyProvider for workspace isolation
    - HeuristicClassifier for outcome classification

    Args:
        file_path: Path to the file being probed (used to detect project root)

    Returns:
        Tuple of (Configured ProbeFileCommandHandler, HarnessConstructor for cache clearing)

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.3
    """
    # Detect project root from file path
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

    # 3. Create single ImportBasedHarnessConstructor with caching (shared across all theorems)
    from ..core.harness_construction import (
        ImportBasedHarnessConstructor,
        LeanInteractTheoremTypeExtractor,
        StandardImportPathConverter,
    )

    type_extractor = LeanInteractTheoremTypeExtractor(querier)
    path_converter = StandardImportPathConverter()
    constructor = ImportBasedHarnessConstructor(type_extractor, path_converter)

    # 4. Create LeanInteractProofValidator with ServerManager and HarnessConstructor
    from ..lean.validator import LeanInteractProofValidator
    validator = LeanInteractProofValidator(server_manager=server_manager, harness_constructor=constructor)

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

    # 9. Create ProbeCommandHandler with all dependencies
    probe_handler = ProbeCommandHandler(
        validator=validator,
        querier=querier,
        workspace_provider=workspace_provider,
        classifier=classifier,
        harness_constructor=constructor,
        artifact_store=artifact_store,
        metadata_collector=metadata_collector,
    )

    # 10. Wire dependencies into ProbeFileCommandHandler
    handler = ProbeFileCommandHandler(
        probe_handler=probe_handler,
        scan_file_fn=scan_file,
        rank_targets_fn=rank_targets,
    )

    # Return both handler and constructor (for cache clearing)
    return handler, constructor


def _build_error_response(
    file: str,
    error_message: str,
    error_code: str,
) -> dict[str, Any]:
    """
    Build error response with consistent structure.

    This function ensures all errors return valid JSON with the correct schema,
    including error metadata with error codes.

    Args:
        file: File path from request
        error_message: Human-readable error message
        error_code: Machine-readable error code

    Returns:
        Error response dict conforming to probe_file output schema

    Requirements: 10.4, 10.5
    """
    # Ensure file is a string for schema compliance
    file_str = str(file) if file is not None else "<invalid>"
    # Ensure file is non-empty for schema compliance
    if not file_str or not file_str.strip():
        file_str = "<invalid>"

    return {
        "api_version": API_VERSION,
        "status": "error",
        "file": file_str,
        "summary": {
            "total": 0,
            "closed": 0,
            "promising": 0,
            "failed": 0,
            "timed_out": 0,
        },
        "results": [],
        "metadata": {
            "error_code": error_code,
            "error": error_message,
            "elapsed_ms": 0.0,
        },
    }
