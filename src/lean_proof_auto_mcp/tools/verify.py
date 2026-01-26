"""
MCP tool entry point for the verify tool.

This module provides the MCP tool interface for Lean verification, implementing
argument validation, composition root, error handling, and response formatting.

Requirements: 1.1, 8.3
"""

import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..adapters.artifact_store import FilesystemArtifactStore
from ..adapters.lean_interact_runner import LeanInteractRunner
from ..adapters.workspace_provider import create_workspace_provider
from ..core.verify_domain import VerifyCommand, VerifyCommandHandler

logger = logging.getLogger(__name__)

API_VERSION = "0.2.0"


def verify(args: dict[str, Any]) -> dict[str, Any]:
    """
    Verify a Lean file or theorem with deterministic, sandboxed execution.

    This is the main MCP tool entry point that:
    1. Validates and coerces arguments
    2. Builds VerifyCommand from args
    3. Creates handler with real adapters (composition root)
    4. Calls handler.handle(command)
    5. Returns VerifyResult as dict
    6. Handles all errors gracefully

    Args:
        args: Dictionary with verification parameters:
            - file: Path to Lean file (required)
            - theorem_id: Optional theorem identifier
            - budget_s: Time budget in seconds (default: 30.0)
            - max_log_excerpt_chars: Max chars for log excerpts (default: 2000)
            - store_full_logs: Whether to store full logs (default: True)
            - workspace_mode: Workspace mode ("worktree", "temp", or None for auto)

    Returns:
        Dictionary conforming to verify output schema with fields:
        - api_version, status, run_id, file, theorem_id
        - verification_scope_used, diagnostics, diagnostic_summary
        - evidence, metadata, timing

    Requirements: 1.1, 8.3
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

    # Execute verification with error handling wrapper
    try:
        # Create handler with real adapters (composition root)
        handler = _create_handler(command.file_path)

        # Execute verification
        result = handler.handle(command)

        # Convert result to dict
        return asdict(result)

    except Exception as e:
        # Catch all exceptions and return error response
        logger.exception(f"Verification failed for {command.file_path}")
        return _build_error_response(
            file=command.file_path,
            error_message=f"Verification error: {str(e)}",
            error_code="internal_error",
            theorem_id=command.theorem_id,
        )


def _build_command(args: dict[str, Any]) -> VerifyCommand:
    """
    Build VerifyCommand from args dict with validation and coercion.

    This function:
    - Validates file is non-empty string
    - Validates budget_s is positive number
    - Validates max_log_excerpt_chars is positive integer
    - Provides defaults for optional parameters
    - Raises ValueError for invalid inputs

    Args:
        args: Raw arguments dict

    Returns:
        Validated VerifyCommand

    Raises:
        ValueError: If any argument is invalid

    Requirements: 1.1
    """
    # Validate and extract file (required)
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("'file' must be a non-empty string")

    # Extract theorem_id (optional)
    theorem_id = args.get("theorem_id")
    if theorem_id is not None and not isinstance(theorem_id, str):
        raise ValueError("'theorem_id' must be a string or null")

    # Validate and extract budget_s (optional, default: 30.0)
    budget_s = args.get("budget_s", 30.0)
    if not isinstance(budget_s, int | float):
        raise ValueError("'budget_s' must be a number")
    budget_s = float(budget_s)
    if budget_s <= 0:
        raise ValueError("'budget_s' must be positive")

    # Validate and extract max_log_excerpt_chars (optional, default: 2000)
    max_log_excerpt_chars = args.get("max_log_excerpt_chars", 2000)
    if not isinstance(max_log_excerpt_chars, int):
        raise ValueError("'max_log_excerpt_chars' must be an integer")
    if max_log_excerpt_chars <= 0:
        raise ValueError("'max_log_excerpt_chars' must be positive")

    # Extract store_full_logs (optional, default: True)
    store_full_logs = args.get("store_full_logs", True)
    if not isinstance(store_full_logs, bool):
        raise ValueError("'store_full_logs' must be a boolean")

    # Extract workspace_mode (optional, default: None for auto-detect)
    workspace_mode = args.get("workspace_mode")
    if workspace_mode is not None and not isinstance(workspace_mode, str):
        raise ValueError("'workspace_mode' must be a string or null")
    if workspace_mode is not None and workspace_mode not in ("worktree", "temp"):
        raise ValueError("'workspace_mode' must be 'worktree', 'temp', or null")

    # Build and return command (validation happens in __post_init__)
    return VerifyCommand(
        file_path=file.strip(),
        theorem_id=theorem_id,
        budget_s=budget_s,
        max_log_excerpt_chars=max_log_excerpt_chars,
        store_full_logs=store_full_logs,
        workspace_mode=workspace_mode,
    )


def _create_handler(file_path: str) -> VerifyCommandHandler:
    """
    Create VerifyCommandHandler with real adapters (composition root).

    This function wires together all dependencies:
    - LeanInteractRunner for Lean execution
    - GitWorktreeProvider or TempCopyProvider for workspace isolation
    - FilesystemArtifactStore for artifact storage

    Args:
        file_path: Path to the file being verified (used to detect project root)

    Returns:
        Configured VerifyCommandHandler

    Requirements: 1.1
    """
    # Detect project root from file path
    # Look for lakefile.toml or lakefile.lean in parent directories
    file_path_obj = Path(file_path).resolve()
    project_root = _find_lean_project_root(file_path_obj)

    # If no Lean project found, use the file's directory
    if project_root is None:
        project_root = file_path_obj.parent

    # Create LeanInteractRunner
    lean_runner = LeanInteractRunner(timeout_buffer_ms=100)

    # Create workspace provider (auto-detect mode)
    workspace_provider = create_workspace_provider(
        workspace_mode=None,  # Auto-detect
        project_root=project_root,
        worktree_dir=project_root / ".worktrees",
    )

    # Create artifact store
    artifacts_dir = Path(os.getenv("LPAM_ARTIFACTS_DIR", ".artifacts"))
    artifact_store = FilesystemArtifactStore(artifacts_dir)

    # Wire dependencies into handler
    return VerifyCommandHandler(
        lean_runner=lean_runner,
        workspace_provider=workspace_provider,
        artifact_store=artifact_store,
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
    error_message: str,
    error_code: str,
    theorem_id: str | None = None,
) -> dict[str, Any]:
    """
    Build error response with consistent structure.

    This function ensures all errors return valid JSON with the correct schema,
    including error diagnostics and notes with error codes.

    Args:
        file: File path from request
        error_message: Human-readable error message
        error_code: Machine-readable error code
        theorem_id: Optional theorem_id from request

    Returns:
        Error response dict conforming to verify output schema

    Requirements: 1.1
    """
    import hashlib
    import uuid
    from datetime import datetime, timezone

    # Generate run_id for error response
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Ensure file is a string for hashing
    file_str = str(file) if file is not None else "<invalid>"
    # Ensure file is non-empty for schema compliance (minLength: 1)
    if not file_str or not file_str.strip():
        file_str = "<invalid>"
    file_hash = hashlib.md5(file_str.encode()).hexdigest()[:8]
    # Add random suffix for uniqueness (same format as success responses)
    random_suffix = uuid.uuid4().hex[:6]
    run_id = f"verify-{timestamp}-{file_hash}-{random_suffix}"

    return {
        "api_version": API_VERSION,
        "status": "error",
        "run_id": run_id,
        "file": file_str,
        "theorem_id": theorem_id,
        "verification_scope_used": "none",
        "diagnostics": [
            {
                "severity": "error",
                "message": error_message,
                "location": None,
            }
        ],
        "diagnostic_summary": {
            "error_count": 1,
            "warning_count": 0,
            "info_count": 0,
        },
        "evidence": {
            "stdout_excerpt": "",
            "stderr_excerpt": "",
            "notes": [f"error_code: {error_code}"],
        },
        "metadata": {},
        "timing": {},
    }
