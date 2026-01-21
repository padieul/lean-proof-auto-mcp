"""rank_targets MCP tool for ranking theorem automation targets.

This tool provides deterministic, objective-driven ranking of theorem
declarations using static analysis signals from scan_file and optionally
scan_theorem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.format import ensure_deterministic
from ..core.ranking import (
    OBJECTIVE_WEIGHTS,
    TheoremData,
    generate_reasons,
    rank_theorems,
)
from .scan_file import scan_file
from .scan_theorem import scan_theorem

API_VERSION = "0.1"


@dataclass(frozen=True)
class RankTargetsArgs:
    """Arguments for rank_targets tool.

    Attributes:
        file: Path to Lean file to analyze
        objective: Ranking objective (maximize_success, maximize_impact, etc.)
        limit: Maximum number of theorems to return
        include_components: Include component score breakdown
        include_reasons: Include human-readable reasons
        use_deep_structure: Use scan_theorem for enhanced scoring
        min_confidence: Minimum confidence threshold for filtering
    """

    file: str
    objective: str
    limit: int
    include_components: bool
    include_reasons: bool
    use_deep_structure: bool
    min_confidence: float

    def __post_init__(self) -> None:
        """Validate argument invariants."""
        if not self.file or not self.file.strip():
            raise ValueError("file must be a non-empty string")

        if self.objective not in OBJECTIVE_WEIGHTS:
            valid_objectives = ", ".join(OBJECTIVE_WEIGHTS.keys())
            raise ValueError(
                f"objective must be one of: {valid_objectives}, got '{self.objective}'"
            )

        if not (1 <= self.limit <= 500):
            raise ValueError(f"limit must be in [1, 500], got {self.limit}")

        if not (0.0 <= self.min_confidence <= 1.0):
            raise ValueError(f"min_confidence must be in [0.0, 1.0], got {self.min_confidence}")


def _coerce_args(args: dict[str, Any]) -> RankTargetsArgs:
    """Parse and validate rank_targets arguments.

    Args:
        args: Raw arguments dictionary

    Returns:
        Validated RankTargetsArgs instance

    Raises:
        ValueError: If arguments are invalid
    """
    # Required field
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("rank_targets: 'file' must be a non-empty string")

    # Optional fields with defaults
    objective = args.get("objective", "balanced")
    if not isinstance(objective, str):
        raise ValueError("rank_targets: 'objective' must be a string")

    limit = args.get("limit", 30)
    if not isinstance(limit, int):
        raise ValueError("rank_targets: 'limit' must be an integer")

    include_components = args.get("include_components", True)
    if not isinstance(include_components, bool):
        raise ValueError("rank_targets: 'include_components' must be a boolean")

    include_reasons = args.get("include_reasons", True)
    if not isinstance(include_reasons, bool):
        raise ValueError("rank_targets: 'include_reasons' must be a boolean")

    use_deep_structure = args.get("use_deep_structure", False)
    if not isinstance(use_deep_structure, bool):
        raise ValueError("rank_targets: 'use_deep_structure' must be a boolean")

    min_confidence = args.get("min_confidence", 0.0)
    if not isinstance(min_confidence, (int, float)):
        raise ValueError("rank_targets: 'min_confidence' must be a number")

    # Create and validate args (validation happens in __post_init__)
    return RankTargetsArgs(
        file=file,
        objective=objective,
        limit=limit,
        include_components=include_components,
        include_reasons=include_reasons,
        use_deep_structure=use_deep_structure,
        min_confidence=float(min_confidence),
    )


def _load_theorem_data(
    file: str, use_deep_structure: bool
) -> tuple[list[TheoremData], list[dict[str, Any]], str | None]:
    """Load theorem data from scan_file and optionally scan_theorem.

    Args:
        file: Path to Lean file
        use_deep_structure: Whether to call scan_theorem for deep structure

    Returns:
        Tuple of (theorem_data_list, diagnostics, scan_file_run_id)
        - theorem_data_list: List of TheoremData objects
        - diagnostics: List of diagnostic messages
        - scan_file_run_id: Run ID from scan_file for correlation

    Raises:
        Exception: If scan_file fails or returns error status
    """
    diagnostics = []

    # Call scan_file to get base data
    scan_file_result = scan_file({"file": file})

    # Check if scan_file succeeded
    if scan_file_result.get("status") != "success":
        # Propagate scan_file diagnostics
        scan_file_diagnostics = scan_file_result.get("diagnostics", [])
        diagnostics.extend(scan_file_diagnostics)
        raise Exception(f"scan_file failed: {scan_file_diagnostics}")

    scan_file_run_id = scan_file_result.get("run_id")
    theorems = scan_file_result.get("theorems", [])

    # Propagate scan_file diagnostics
    scan_file_diagnostics = scan_file_result.get("diagnostics", [])
    diagnostics.extend(scan_file_diagnostics)

    # Build TheoremData objects
    theorem_data_list = []

    for theorem in theorems:
        theorem_id = theorem.get("theorem_id", "")
        location = theorem.get("location", {})
        automation = theorem.get("automation", {})
        notes = theorem.get("notes", [])

        # Extract location with defaults
        decl_start = location.get("decl_start", 0)
        decl_end = location.get("decl_end", 0)
        proof_start = location.get("proof_start", decl_start)
        proof_end = location.get("proof_end", decl_end)

        # Build range (use proof range if available, otherwise decl range)
        range_dict = {"start_line": proof_start, "end_line": proof_end}

        # Extract automation signals with defaults
        whole_goal_potential = automation.get("whole_goal_potential", {})
        subgoal_potential = automation.get("subgoal_potential", {})
        annotation_value = automation.get("annotation_value", 0.0)

        # Build signals dictionary
        signals = {
            "whole_goal_potential": whole_goal_potential,
            "subgoal_potential": subgoal_potential,
            "annotation_value": annotation_value,
            "notes": notes,
            "confidence": 0.0,  # Default, will be extracted from notes if available
            "proof_lines": max(0, proof_end - proof_start + 1) if proof_start > 0 else 0,
            "rewrite_count": 0,
            "simp_count": 0,
            "local_lemmas_count": 0,
            "has_induction": False,
            "has_cases": False,
        }

        # Extract additional signals from notes
        for note in notes:
            note_lower = note.lower()
            if "confidence" in note_lower:
                # Try to extract confidence value from note
                # Format: "confidence: 0.85" or similar
                try:
                    parts = note.split(":")
                    if len(parts) >= 2:
                        conf_str = parts[1].strip()
                        signals["confidence"] = float(conf_str)
                except (ValueError, IndexError):
                    pass

            if "rewrite" in note_lower:
                signals["rewrite_count"] += 1
            if "simp" in note_lower:
                signals["simp_count"] += 1
            if "local lemma" in note_lower:
                signals["local_lemmas_count"] += 1
            if "induction" in note_lower:
                signals["has_induction"] = True
            if "cases" in note_lower or "case" in note_lower:
                signals["has_cases"] = True

        # Handle missing optional fields with diagnostics
        if not whole_goal_potential:
            diagnostics.append(
                {
                    "severity": "info",
                    "message": f"Theorem {theorem_id}: using default whole_goal_potential",
                }
            )

        if not subgoal_potential:
            diagnostics.append(
                {
                    "severity": "info",
                    "message": f"Theorem {theorem_id}: using default subgoal_potential",
                }
            )

        # Optionally load deep structure
        structure = None
        if use_deep_structure:
            try:
                scan_theorem_result = scan_theorem(
                    {"file": file, "target": {"theorem_id": theorem_id}}
                )

                if scan_theorem_result.get("status") == "success":
                    theorem_obj = scan_theorem_result.get("theorem")
                    if theorem_obj:
                        structure = theorem_obj.get("structure")
                else:
                    # scan_theorem failed, add warning but continue
                    diagnostics.append(
                        {
                            "severity": "warning",
                            "message": f"scan_theorem failed for {theorem_id}, "
                            "using scan_file data only",
                        }
                    )
            except Exception as e:
                # scan_theorem error, add warning but continue
                diagnostics.append(
                    {
                        "severity": "warning",
                        "message": f"Error calling scan_theorem for {theorem_id}: {str(e)}",
                    }
                )

        # Create TheoremData
        try:
            theorem_data = TheoremData(
                theorem_id=theorem_id,
                range=range_dict,
                signals=signals,
                structure=structure,
            )
            theorem_data_list.append(theorem_data)
        except ValueError as e:
            # Invalid theorem data, add diagnostic and skip
            diagnostics.append(
                {
                    "severity": "warning",
                    "message": f"Skipping invalid theorem {theorem_id}: {str(e)}",
                }
            )

    return theorem_data_list, diagnostics, scan_file_run_id


def _generate_run_id(file_path: str, prefix: str) -> str:
    """Generate a deterministic run_id for testing compatibility.

    Args:
        file_path: Path to the file being analyzed
        prefix: Prefix for the run_id

    Returns:
        Deterministic run_id string
    """
    import hashlib

    content = f"{prefix}-{file_path}"
    hash_obj = hashlib.md5(content.encode())
    return f"{prefix}-{hash_obj.hexdigest()[:8]}"


def _format_response(
    ranked_theorems: list[Any],
    args: RankTargetsArgs,
    total_theorems: int,
    skipped_low_confidence: int,
    diagnostics: list[dict[str, Any]],
    scan_file_run_id: str | None,
    computation_time_ms: float,
) -> dict[str, Any]:
    """Format the response JSON for rank_targets.

    Args:
        ranked_theorems: List of RankedTheorem objects
        args: Parsed arguments
        total_theorems: Total number of theorems before filtering
        skipped_low_confidence: Number of theorems filtered by confidence
        diagnostics: List of diagnostic messages
        scan_file_run_id: Run ID from scan_file
        computation_time_ms: Computation time in milliseconds

    Returns:
        Response dictionary conforming to schema
    """
    # Generate run_id
    run_id = _generate_run_id(args.file, "rank")

    # Build ranking array
    ranking = []
    for ranked in ranked_theorems[: args.limit]:
        theorem_data = ranked.theorem_data
        components = ranked.components

        # Build theorem object
        theorem_obj: dict[str, Any] = {
            "theorem_id": theorem_data.theorem_id,
            "range": {
                "start_line": theorem_data.range["start_line"],
                "end_line": theorem_data.range["end_line"],
            },
            "score": ranked.score,
        }

        # Optionally include components
        if args.include_components:
            theorem_obj["components"] = {
                "success_likelihood": components.success_likelihood,
                "impact": components.impact,
                "annotation_value": components.annotation_value,
                "subgoal_potential": components.subgoal_potential,
                "risk": components.risk,
            }

        # Optionally include reasons
        if args.include_reasons:
            reasons = generate_reasons(theorem_data.signals, components, theorem_data.structure)
            theorem_obj["reasons"] = reasons

        # Include signals for transparency
        theorem_obj["signals"] = {
            "whole_goal_potential": theorem_data.signals.get("whole_goal_potential", {}),
            "subgoal_potential": theorem_data.signals.get("subgoal_potential", {}),
            "annotation_value": theorem_data.signals.get("annotation_value", 0.0),
            "proof_lines": theorem_data.signals.get("proof_lines", 0),
            "confidence": theorem_data.signals.get("confidence", 0.0),
        }

        ranking.append(theorem_obj)

    # Build summary
    summary = {
        "total": total_theorems,
        "returned": len(ranking),
        "skipped_low_confidence": skipped_low_confidence,
    }

    # Build metadata
    metadata: dict[str, Any] = {
        "deep_structure_used": args.use_deep_structure,
        "computation_time_ms": round(computation_time_ms, 2),
    }
    if scan_file_run_id:
        metadata["scan_file_run_id"] = scan_file_run_id

    # Build response
    response = {
        "api_version": API_VERSION,
        "status": "success",
        "run_id": run_id,
        "tool": "rank_targets",
        "file": args.file,
        "objective": args.objective,
        "ranking": ranking,
        "summary": summary,
        "diagnostics": diagnostics,
        "metadata": metadata,
    }

    # Ensure deterministic output
    return ensure_deterministic(response)


def rank_targets(args: dict[str, Any]) -> dict[str, Any]:
    """Rank theorem automation targets in a Lean file.

    This tool provides deterministic, objective-driven ranking of theorem
    declarations using static analysis signals from scan_file and optionally
    scan_theorem.

    Args:
        args: Dictionary with rank_targets parameters

    Returns:
        Dictionary conforming to docs/mcp/schemas/rank_targets.json
    """
    import time

    start_time = time.time()

    # Parse and validate arguments
    try:
        parsed = _coerce_args(args)
    except ValueError as e:
        # Build error response with whatever we can extract
        file_value = args.get("file", "") if isinstance(args, dict) else ""
        if not isinstance(file_value, str) or not file_value.strip():
            file_value = "<invalid>"

        objective_value = args.get("objective", "balanced")
        if not isinstance(objective_value, str):
            objective_value = "balanced"

        return {
            "api_version": API_VERSION,
            "status": "fail",
            "run_id": _generate_run_id(file_value, "rank-invalid"),
            "tool": "rank_targets",
            "file": file_value,
            "objective": objective_value,
            "ranking": [],
            "summary": {"total": 0, "returned": 0, "skipped_low_confidence": 0},
            "diagnostics": [{"severity": "error", "message": str(e)}],
            "metadata": {"deep_structure_used": False, "computation_time_ms": 0.0},
        }

    # Generate run_id
    run_id = _generate_run_id(parsed.file, "rank")

    try:
        # Load theorem data
        theorem_data_list, diagnostics, scan_file_run_id = _load_theorem_data(
            parsed.file, parsed.use_deep_structure
        )

        total_theorems = len(theorem_data_list)

        # Rank theorems with confidence filtering
        ranked_theorems = rank_theorems(theorem_data_list, parsed.objective, parsed.min_confidence)

        # Calculate how many were skipped due to confidence
        skipped_low_confidence = total_theorems - len(ranked_theorems)

        # Calculate computation time
        end_time = time.time()
        computation_time_ms = (end_time - start_time) * 1000

        # Format response
        return _format_response(
            ranked_theorems=ranked_theorems,
            args=parsed,
            total_theorems=total_theorems,
            skipped_low_confidence=skipped_low_confidence,
            diagnostics=diagnostics,
            scan_file_run_id=scan_file_run_id,
            computation_time_ms=computation_time_ms,
        )

    except Exception as e:
        # Calculate computation time even for errors
        end_time = time.time()
        computation_time_ms = (end_time - start_time) * 1000

        # Build error response
        return {
            "api_version": API_VERSION,
            "status": "fail",
            "run_id": run_id,
            "tool": "rank_targets",
            "file": parsed.file,
            "objective": parsed.objective,
            "ranking": [],
            "summary": {"total": 0, "returned": 0, "skipped_low_confidence": 0},
            "diagnostics": [{"severity": "error", "message": f"Analysis error: {str(e)}"}],
            "metadata": {
                "deep_structure_used": parsed.use_deep_structure,
                "computation_time_ms": round(computation_time_ms, 2),
            },
        }
