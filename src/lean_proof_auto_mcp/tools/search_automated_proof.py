"""
MCP tool entry point for the search_automated_proof tool.

This module provides the enhanced MCP tool interface for searching automated
proofs with LLM-controlled parameters, rich feedback mechanisms, and metadata
collection. It replaces the search_annotations tool with improved capabilities.

Requirements: 4.1, 4.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 29.5, 29.6
"""

import hashlib
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

from ..core.candidate_generator import CandidateGenerator
from ..core.context_extractor import ContextExtractor
from ..core.feedback_builder import FeedbackBuilder
from ..core.search_automated_proof_domain import CandidateSource
from ..core.search_orchestrator import SearchConfig, SearchOrchestrator
from ..lean.ports import ProofValidator
from ..lean.proof_state import ProofStateInspectorImpl
from ..lean.querier import LeanInteractQuerierImpl
from ..lean.validator import ProofValidatorImpl
from ..observability import SubprocessMetadataCollector

logger = logging.getLogger(__name__)

API_VERSION = "0.2.0"


def search_automated_proof(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search for automated proof with rich feedback and LLM-controlled parameters.

    This is the enhanced MCP tool that replaces search_annotations with:
    - LLM-controlled search depth presets (quick, normal, deep, exhaustive)
    - Rich feedback mechanisms (proof states, partial progress, tactical suggestions)
    - Support for all four candidate sources including original_proof_refs
    - Metadata collection for debugging and reproducibility
    - Configurable return options for different use cases

    Args:
        args: Dictionary with search parameters:
            - file: Path to Lean file (required)
            - theorem_id: Theorem identifier (required)
            - search_depth: Search depth preset - "quick", "normal", "deep", "exhaustive" (default: "normal")
            - search_budget_s: Override search budget in seconds (optional)
            - max_candidates: Override max candidates (optional)
            - candidate_sources: List of candidate sources to use (optional)
            - max_candidates_per_source: Max candidates per source (optional)
            - automation_mode: Automation mode - "aesop", "simp", "omega", "grind" (default: "aesop")
            - automation_secondary: Secondary automation for fallback (optional)
            - search_strategy: Search strategy - "greedy", "beam", "exhaustive" (default: "greedy")
            - beam_width: Beam width for beam search (default: 3)
            - max_search_steps: Maximum search steps (optional)
            - max_hints_in_set: Maximum hints in a set (default: 10)
            - allow_simp_hints: Allow simp hints (default: True)
            - allow_unfold_hints: Allow unfold hints (default: True)
            - allow_unsafe_hints: Allow unsafe hints (default: False)
            - minimize_hints: Minimize hint set after finding solution (default: True)
            - minimize_budget_s: Override minimization budget (optional)
            - return_proof_states: Return initial and final proof states (default: True)
            - return_partial_progress: Return partial progress information (default: True)
            - return_context: Return theorem context (default: False)
            - return_similar_proofs: Return similar proofs (default: False)
            - return_search_trace: Return detailed search trace (default: False)

    Returns:
        Dictionary with fields:
        - api_version: API version string
        - status: "success", "partial", or "error"
        - run_id: Unique run identifier
        - file: File path
        - theorem_id: Theorem identifier
        - outcome: Search outcome - "closed", "partial", "failed"
        - best_hint_set: Best hint set found (if any)
        - attempts: Number of combinations tried
        - explored_sets: Number of unique hint sets explored
        - feedback: Rich feedback with proof states, progress, suggestions
        - metadata: Environment metadata (git commit, lean version, lake version)
        - search_trace: Detailed search trace (if requested)
        - timing: Timing information for all phases

    Requirements: 4.1, 4.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 29.5, 29.6
    """
    # Validate and coerce arguments
    try:
        config, file_path, theorem_id, run_id = _build_search_config(args)
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
        orchestrator = _create_orchestrator(file_path)

        # Execute search
        result = orchestrator.search(file_path, theorem_id, config)

        # Convert result to dict
        return _format_response(result, file_path, theorem_id, run_id)

    except Exception as e:
        # Catch all exceptions and return error response
        logger.exception(f"Search failed for {file_path}:{theorem_id}")
        return _build_error_response(
            file=file_path,
            theorem_id=theorem_id,
            error_message=f"Search error: {str(e)}",
            error_code="internal_error",
        )


def _build_search_config(
    args: dict[str, Any]
) -> tuple[SearchConfig, str, str, str]:
    """
    Build SearchConfig from args dict with validation and coercion.

    This function:
    - Validates file is non-empty string
    - Validates theorem_id is non-empty string
    - Validates search_depth is valid preset
    - Builds SearchConfig with presets and overrides
    - Provides defaults for optional parameters
    - Raises ValueError for invalid inputs

    Args:
        args: Raw arguments dict

    Returns:
        Tuple of (SearchConfig, file_path, theorem_id, run_id)

    Raises:
        ValueError: If any argument is invalid

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
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

    # Validate and extract search_depth (optional, default: "normal")
    search_depth = args.get("search_depth", "normal")
    if not isinstance(search_depth, str):
        raise ValueError("'search_depth' must be a string")
    if search_depth not in ("quick", "normal", "deep", "exhaustive"):
        raise ValueError("'search_depth' must be 'quick', 'normal', 'deep', or 'exhaustive'")

    # Start with preset configuration
    config = SearchConfig.from_depth(search_depth)

    # Apply overrides if provided
    overrides = {}

    # Search budget override
    if "search_budget_s" in args:
        budget = args["search_budget_s"]
        if not isinstance(budget, (int, float)) or budget <= 0:
            raise ValueError("'search_budget_s' must be a positive number")
        overrides["search_budget_s"] = float(budget)

    # Max candidates override
    if "max_candidates" in args:
        max_cand = args["max_candidates"]
        if not isinstance(max_cand, int) or max_cand <= 0:
            raise ValueError("'max_candidates' must be a positive integer")
        overrides["max_candidates"] = max_cand

    # Candidate sources override
    if "candidate_sources" in args:
        sources_raw = args["candidate_sources"]
        if not isinstance(sources_raw, list):
            raise ValueError("'candidate_sources' must be a list")
        sources = []
        for source_str in sources_raw:
            if not isinstance(source_str, str):
                raise ValueError(f"'candidate_sources' must contain strings, got {type(source_str)}")
            try:
                sources.append(CandidateSource(source_str))
            except ValueError as e:
                raise ValueError(f"Invalid candidate source: {source_str}") from e
        overrides["candidate_sources"] = sources

    # Max candidates per source override
    if "max_candidates_per_source" in args:
        max_per = args["max_candidates_per_source"]
        if not isinstance(max_per, int) or max_per <= 0:
            raise ValueError("'max_candidates_per_source' must be a positive integer")
        overrides["max_candidates_per_source"] = max_per

    # Automation mode override
    if "automation_mode" in args:
        mode = args["automation_mode"]
        if not isinstance(mode, str):
            raise ValueError("'automation_mode' must be a string")
        if mode not in ("aesop", "simp", "omega", "grind"):
            raise ValueError("'automation_mode' must be 'aesop', 'simp', 'omega', or 'grind'")
        overrides["automation_mode"] = mode

    # Automation secondary override
    if "automation_secondary" in args:
        secondary = args["automation_secondary"]
        if secondary is not None:
            if not isinstance(secondary, str):
                raise ValueError("'automation_secondary' must be a string or None")
            if secondary not in ("aesop", "simp", "omega", "grind"):
                raise ValueError("'automation_secondary' must be 'aesop', 'simp', 'omega', 'grind', or None")
        overrides["automation_secondary"] = secondary

    # Search strategy override
    if "search_strategy" in args:
        strategy = args["search_strategy"]
        if not isinstance(strategy, str):
            raise ValueError("'search_strategy' must be a string")
        if strategy not in ("greedy", "beam", "exhaustive"):
            raise ValueError("'search_strategy' must be 'greedy', 'beam', or 'exhaustive'")
        overrides["search_strategy"] = strategy

    # Beam width override
    if "beam_width" in args:
        width = args["beam_width"]
        if not isinstance(width, int) or width <= 0:
            raise ValueError("'beam_width' must be a positive integer")
        overrides["beam_width"] = width

    # Max search steps override
    if "max_search_steps" in args:
        steps = args["max_search_steps"]
        if not isinstance(steps, int) or steps <= 0:
            raise ValueError("'max_search_steps' must be a positive integer")
        overrides["max_search_steps"] = steps

    # Max hints in set override
    if "max_hints_in_set" in args:
        max_hints = args["max_hints_in_set"]
        if not isinstance(max_hints, int) or max_hints <= 0:
            raise ValueError("'max_hints_in_set' must be a positive integer")
        overrides["max_hints_in_set"] = max_hints

    # Boolean overrides
    for key in ["allow_simp_hints", "allow_unfold_hints", "allow_unsafe_hints", "minimize_hints"]:
        if key in args:
            value = args[key]
            if not isinstance(value, bool):
                raise ValueError(f"'{key}' must be a boolean")
            overrides[key] = value

    # Minimize budget override
    if "minimize_budget_s" in args:
        min_budget = args["minimize_budget_s"]
        if not isinstance(min_budget, (int, float)) or min_budget <= 0:
            raise ValueError("'minimize_budget_s' must be a positive number")
        overrides["minimize_budget_s"] = float(min_budget)

    # Return options overrides
    for key in [
        "return_proof_states",
        "return_partial_progress",
        "return_context",
        "return_similar_proofs",
        "return_search_trace",
    ]:
        if key in args:
            value = args[key]
            if not isinstance(value, bool):
                raise ValueError(f"'{key}' must be a boolean")
            overrides[key] = value

    # Apply overrides to config
    if overrides:
        # Create new config with overrides
        config_dict = asdict(config)
        config_dict.update(overrides)
        config = SearchConfig(**config_dict)

    # Generate run_id
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
    random_suffix = uuid.uuid4().hex[:6]
    run_id = f"search-auto-{timestamp}-{file_hash}-{random_suffix}"

    return config, file_path, theorem_id, run_id


def _create_orchestrator(file_path: str) -> SearchOrchestrator:
    """
    Create SearchOrchestrator with real adapters (composition root).

    This function wires together all dependencies:
    - LeanInteractQuerier for declaration extraction
    - ProofStateInspector for proof state inspection
    - ProofValidator for proof validation
    - CandidateGenerator for hint extraction
    - FeedbackBuilder for feedback generation
    - SubprocessMetadataCollector for metadata collection

    Args:
        file_path: Path to the file being searched (used to detect project root)

    Returns:
        Configured SearchOrchestrator

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
    from ..lean.server_manager import ServerManagerImpl
    server_manager = ServerManagerImpl(workspace_path=project_root)

    # Create LeanInteractQuerier with ServerManager
    querier = LeanInteractQuerierImpl(server_manager=server_manager)

    # Get server instance from ServerManager for proof state inspection
    server = server_manager.get_server(file_path)

    # Create ProofStateInspector with server
    proof_state_inspector = ProofStateInspectorImpl(server=server)

    # Create ProofValidator with server (doesn't need workspace_path)
    validator = ProofValidatorImpl(server=server)

    # Create CandidateGenerator
    # Read source for candidate generation
    from ..core.indexer import build_index
    from ..core.source import SourceText

    source_text = file_path_obj.read_text(encoding="utf-8")
    source = SourceText(path=file_path, text=source_text)
    index = build_index(source)

    candidate_generator = CandidateGenerator(source, index, querier, proof_state_inspector)

    # Create FeedbackBuilder
    feedback_builder = FeedbackBuilder()

    # Create SubprocessMetadataCollector at composition root
    metadata_collector = SubprocessMetadataCollector()

    # Create HarnessConstructor for building test harnesses
    from ..core.harness_construction import (
        ImportBasedHarnessConstructor,
        LeanInteractTheoremTypeExtractor,
        StandardImportPathConverter,
    )
    from ..adapters.lean_interact_runner import LeanInteractRunner
    
    type_extractor = LeanInteractTheoremTypeExtractor(querier)
    path_converter = StandardImportPathConverter()
    harness_constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor,
        path_converter=path_converter
    )
    
    # Create LeanRunner for executing harnesses
    lean_runner = LeanInteractRunner(
        server_manager=server_manager,
        timeout_buffer_ms=100
    )

    # Wire into SearchOrchestrator
    return SearchOrchestrator(
        candidate_gen=candidate_generator,
        feedback_builder=feedback_builder,
        validator=validator,
        harness_constructor=harness_constructor,
        lean_runner=lean_runner,
        proof_state_inspector=proof_state_inspector,
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


def _format_response(
    result: Any,  # SearchResultEnhanced
    file_path: str,
    theorem_id: str,
    run_id: str,
) -> dict[str, Any]:
    """
    Format SearchResultEnhanced as JSON response.

    Args:
        result: SearchResultEnhanced from orchestrator
        file_path: File path
        theorem_id: Theorem identifier
        run_id: Run identifier

    Returns:
        JSON response dict

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 29.6
    """
    # Determine status from outcome
    status_map = {
        "closed": "success",
        "partial": "partial",
        "failed": "fail",  # Failed search is "fail" not "error"
    }
    status = status_map.get(result.outcome, "error")

    # Format best hint set
    best_hints = None
    if result.best_hint_set:
        best_hints = [
            {
                "name": candidate.hint.name,
                "hint_type": candidate.hint.type.value,
                "source": candidate.hint.source.value,
                "rank": candidate.rank,
            }
            for candidate in result.best_hint_set
        ]

    # Format feedback
    feedback_dict = asdict(result.feedback)

    return {
        "api_version": API_VERSION,
        "status": status,
        "run_id": run_id,
        "file": file_path,
        "theorem_id": theorem_id,
        "outcome": result.outcome,
        "best_hint_set": best_hints,
        "attempts": result.attempts,
        "explored_sets": result.explored_sets,
        "feedback": feedback_dict,
        "metadata": result.metadata,
        "search_trace": result.search_trace,
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

    Requirements: 4.8, 6.6
    """
    # Generate run_id for error response
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_str = str(file) if file is not None else "<invalid>"
    if not file_str or not file_str.strip():
        file_str = "<invalid>"
    file_hash = hashlib.md5(file_str.encode()).hexdigest()[:8]
    random_suffix = uuid.uuid4().hex[:6]
    run_id = f"search-auto-{timestamp}-{file_hash}-{random_suffix}"

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
        "outcome": "failed",
        "best_hint_set": None,
        "attempts": 0,
        "explored_sets": 0,
        "feedback": {
            "status": "error",
            "hints_found": [],
            "partial_progress": None,
            "current_goal": None,
            "suggestions": [],
        },
        "metadata": {"error_code": error_code, "error_message": error_message},
        "search_trace": None,
        "timing": {"total_s": 0.0},
    }
