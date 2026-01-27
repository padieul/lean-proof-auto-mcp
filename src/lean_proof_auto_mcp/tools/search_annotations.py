"""
MCP tool entry point for the search-annotations tool.

This module provides the MCP tool interface for searching and minimizing
local proof hints, implementing argument validation, composition root,
error handling, and response formatting.

Requirements: 1.1, 1.2, 1.3, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8
"""

import hashlib
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..adapters.artifact_store import FilesystemArtifactStore
from ..adapters.lean_interact_runner import LeanInteractRunner
from ..adapters.workspace_provider import create_workspace_provider
from ..core.candidate_generator import CandidateGenerator
from ..core.minimizer import Minimizer
from ..core.probe_classifier import HeuristicClassifier
from ..core.probe_domain import ProbeCommandHandler
from ..core.proof_patch_builder import ProofPatchBuilder
from ..core.search_annotations_domain import (
    AutomationConfig,
    BudgetConfig,
    CandidateConfig,
    CandidateSource,
    SearchAnnotationsCommand,
    SearchAnnotationsCommandHandler,
    SearchConfig,
    SkeletonConfig,
    StyleConfig,
    WorkspaceConfig,
)
from ..core.search_strategy import BeamSearch, GreedySearch

logger = logging.getLogger(__name__)

API_VERSION = "0.1.0"


def search_annotations(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search for minimal local proof hints to make a theorem provable by automation.

    This is the main MCP tool entry point that:
    1. Validates and coerces arguments
    2. Builds SearchAnnotationsCommand from args
    3. Creates handler with real adapters (composition root)
    4. Calls handler.handle(command)
    5. Returns SearchAnnotationsResult as dict
    6. Handles all errors gracefully

    Args:
        args: Dictionary with search parameters:
            - file: Path to Lean file (required)
            - theorem_id: Theorem identifier (required)
            - mode: Operation mode - "local_only" or "suggest_global" (default: "local_only")
            - automation: Automation configuration dict (optional)
            - budgets: Budget configuration dict (optional)
            - search: Search configuration dict (optional)
            - candidates: Candidate configuration dict (optional)
            - skeleton: Skeleton configuration dict (optional)
            - style: Style configuration dict (optional)
            - workspace: Workspace configuration dict (optional)
            - allow_global_edits: Allow global edits (default: False)

    Returns:
        Dictionary conforming to search-annotations output schema with fields:
        - api_version, status, run_id, file, theorem_id
        - viability, baseline, search_result, minimized_hint_set
        - proof_patch, global_suggestions, timing, artifacts, metadata

    Requirements: 1.1, 1.2, 1.3, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8
    """
    # Validate and coerce arguments
    try:
        command = _build_command(args)
    except ValueError as e:
        # Return error response for invalid inputs
        return _build_error_response(
            file=args.get("file", "<invalid>"),
            theorem_id=args.get("theorem_id", "<invalid>"),
            error_message=str(e),
            error_code="input_validation_error",
        )

    # Execute search with error handling wrapper
    try:
        # Create handler with real adapters (composition root)
        handler = _create_handler(command.file)

        # Execute search
        result = handler.handle(command)

        # Convert result to dict
        return asdict(result)

    except Exception as e:
        # Catch all exceptions and return error response
        logger.exception(f"Search failed for {command.file}:{command.theorem_id}")
        return _build_error_response(
            file=command.file,
            theorem_id=command.theorem_id,
            error_message=f"Search error: {str(e)}",
            error_code="internal_error",
        )


def _build_command(args: dict[str, Any]) -> SearchAnnotationsCommand:
    """
    Build SearchAnnotationsCommand from args dict with validation and coercion.

    This function:
    - Validates file is non-empty string
    - Validates theorem_id is non-empty string
    - Validates mode is "local_only" or "suggest_global"
    - Validates and builds configuration objects
    - Provides defaults for optional parameters
    - Raises ValueError for invalid inputs

    Args:
        args: Raw arguments dict

    Returns:
        Validated SearchAnnotationsCommand

    Raises:
        ValueError: If any argument is invalid

    Requirements: 1.1, 1.3, 11.1, 11.2
    """
    # Validate and extract file (required)
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("'file' must be a non-empty string")

    # Validate and extract theorem_id (required)
    theorem_id = args.get("theorem_id")
    if not isinstance(theorem_id, str) or not theorem_id.strip():
        raise ValueError("'theorem_id' must be a non-empty string")

    # Validate and extract mode (optional, default: "local_only")
    mode = args.get("mode", "local_only")
    if not isinstance(mode, str):
        raise ValueError("'mode' must be a string")
    if mode not in ("local_only", "suggest_global"):
        raise ValueError("'mode' must be 'local_only' or 'suggest_global'")

    # Build automation config
    automation_dict = args.get("automation", {})
    if not isinstance(automation_dict, dict):
        raise ValueError("'automation' must be a dict")
    
    automation = AutomationConfig(
        primary=automation_dict.get("primary", "aesop"),
        secondary=automation_dict.get("secondary"),
        aesop_rules=automation_dict.get("aesop_rules")
    )

    # Build budget config
    budgets_dict = args.get("budgets", {})
    if not isinstance(budgets_dict, dict):
        raise ValueError("'budgets' must be a dict")
    
    budgets = BudgetConfig(
        viability_check_s=budgets_dict.get("viability_check_s", 5.0),
        baseline_probe_s=budgets_dict.get("baseline_probe_s", 10.0),
        search_total_s=budgets_dict.get("search_total_s", 300.0),
        candidate_trial_s=budgets_dict.get("candidate_trial_s", 5.0),
        minimize_total_s=budgets_dict.get("minimize_total_s", 60.0),
        final_verify_s=budgets_dict.get("final_verify_s", 10.0)
    )

    # Build search config
    search_dict = args.get("search", {})
    if not isinstance(search_dict, dict):
        raise ValueError("'search' must be a dict")
    
    # Validate strategy if provided
    strategy = search_dict.get("strategy", "greedy")
    if strategy not in ("beam", "greedy"):
        raise ValueError("'search.strategy' must be 'beam' or 'greedy'")
    
    search = SearchConfig(
        strategy=strategy,
        beam_width=search_dict.get("beam_width", 3),
        max_steps=search_dict.get("max_steps", 100),
        max_hints=search_dict.get("max_hints", 10),
        stop_on_first_close=search_dict.get("stop_on_first_close", True)
    )

    # Build candidate config
    candidates_dict = args.get("candidates", {})
    if not isinstance(candidates_dict, dict):
        raise ValueError("'candidates' must be a dict")
    
    # Parse sources list
    sources_raw = candidates_dict.get("sources", ["goal_symbols", "local_context", "same_namespace"])
    if not isinstance(sources_raw, list):
        raise ValueError("'candidates.sources' must be a list")
    
    sources = []
    for source_str in sources_raw:
        if not isinstance(source_str, str):
            raise ValueError(f"'candidates.sources' must contain strings, got {type(source_str)}")
        try:
            sources.append(CandidateSource(source_str))
        except ValueError:
            raise ValueError(f"Invalid candidate source: {source_str}")
    
    candidates = CandidateConfig(
        sources=sources,
        max_candidates_per_source=candidates_dict.get("max_candidates_per_source", 20),
        allow_simp_hints=candidates_dict.get("allow_simp_hints", True),
        allow_unfold_hints=candidates_dict.get("allow_unfold_hints", True)
    )

    # Build skeleton config
    skeleton_dict = args.get("skeleton", {})
    if not isinstance(skeleton_dict, dict):
        raise ValueError("'skeleton' must be a dict")
    
    skeleton = SkeletonConfig(
        enabled=skeleton_dict.get("enabled", False),
        max_depth=skeleton_dict.get("max_depth", 3),
        moves=skeleton_dict.get("moves")
    )

    # Build style config
    style_dict = args.get("style", {})
    if not isinstance(style_dict, dict):
        raise ValueError("'style' must be a dict")
    
    style = StyleConfig(
        prefer_simp_over_aesop=style_dict.get("prefer_simp_over_aesop", True),
        emit_compact=style_dict.get("emit_compact", False),
        simp_only_list=style_dict.get("simp_only_list", False)
    )

    # Build workspace config
    workspace_dict = args.get("workspace", {})
    if not isinstance(workspace_dict, dict):
        raise ValueError("'workspace' must be a dict")
    
    workspace = WorkspaceConfig(
        mode=workspace_dict.get("mode", "git_worktree"),
        keep_artifacts=workspace_dict.get("keep_artifacts", False)
    )

    # Extract allow_global_edits (optional, default: False)
    allow_global_edits = args.get("allow_global_edits", False)
    if not isinstance(allow_global_edits, bool):
        raise ValueError("'allow_global_edits' must be a boolean")

    # Generate run_id
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_hash = hashlib.md5(file.strip().encode()).hexdigest()[:8]
    random_suffix = uuid.uuid4().hex[:6]
    run_id = f"search-{timestamp}-{file_hash}-{random_suffix}"

    # Build and return command (validation happens in __post_init__)
    return SearchAnnotationsCommand(
        file=file.strip(),
        theorem_id=theorem_id.strip(),
        mode=mode,
        automation=automation,
        budgets=budgets,
        search=search,
        candidates=candidates,
        skeleton=skeleton,
        style=style,
        workspace=workspace,
        allow_global_edits=allow_global_edits,
        run_id=run_id
    )


def _create_handler(file_path: str) -> SearchAnnotationsCommandHandler:
    """
    Create SearchAnnotationsCommandHandler with real adapters (composition root).

    This function wires together all dependencies:
    - LeanInteractRunner for Lean execution
    - GitWorktreeProvider or TempCopyProvider for workspace isolation
    - HeuristicClassifier for outcome classification
    - FilesystemArtifactStore for artifact storage
    - CandidateGenerator for hint extraction
    - SearchStrategy (Beam or Greedy) for hint search
    - Minimizer for hint set minimization
    - ProofPatchBuilder for proof generation

    Args:
        file_path: Path to the file being searched (used to detect project root)

    Returns:
        Configured SearchAnnotationsCommandHandler

    Raises:
        FileNotFoundError: If the file does not exist
        
    Requirements: 11.3, 11.4, 11.5, 11.6, 11.7, 11.8
    """
    # Detect project root from file path
    # Look for lakefile.toml or lakefile.lean in parent directories
    file_path_obj = Path(file_path).resolve()
    
    # Check if file exists
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
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

    # Create classifier
    classifier = HeuristicClassifier()

    # Create artifact store
    import os
    artifacts_dir = Path(os.getenv("LPAM_ARTIFACTS_DIR", ".artifacts"))
    artifact_store = FilesystemArtifactStore(artifacts_dir)

    # Create probe handler (reuse existing)
    probe_handler = ProbeCommandHandler(
        lean_runner=lean_runner,
        workspace_provider=workspace_provider,
        classifier=classifier,
    )

    # Create search-specific components
    # Read source for candidate generation
    from ..core.indexer import build_index
    from ..core.source import SourceText
    
    source_text = file_path_obj.read_text(encoding="utf-8")
    source = SourceText(path=file_path, text=source_text)
    index = build_index(source)
    
    candidate_generator = CandidateGenerator(source, index)
    
    # Use greedy search by default (can be configured via command)
    search_strategy = GreedySearch()
    
    minimizer = Minimizer()
    
    proof_patch_builder = ProofPatchBuilder()

    # Wire into handler
    return SearchAnnotationsCommandHandler(
        probe_handler=probe_handler,
        candidate_generator=candidate_generator,
        search_strategy=search_strategy,
        minimizer=minimizer,
        proof_patch_builder=proof_patch_builder,
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
    theorem_id: str,
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
        error_message: Human-readable error message
        error_code: Machine-readable error code

    Returns:
        Error response dict conforming to search-annotations output schema

    Requirements: 1.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.8
    """
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
    run_id = f"search-{timestamp}-{file_hash}-{random_suffix}"

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
        "viability": {
            "status": "not_started",
            "error": error_message
        },
        "baseline": {
            "status": "not_started"
        },
        "search_result": None,
        "minimized_hint_set": None,
        "proof_patch": None,
        "global_suggestions": None,
        "timing": {
            "total_s": 0.0
        },
        "artifacts": {},
        "metadata": {
            "error_code": error_code,
            "error_message": error_message
        }
    }
