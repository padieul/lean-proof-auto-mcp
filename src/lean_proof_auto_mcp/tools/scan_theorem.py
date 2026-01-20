from __future__ import annotations

from dataclasses import dataclass
from typing import Any

API_VERSION = "0.1"


@dataclass(frozen=True)
class TheoremTarget:
    theorem_id: str | None
    range: tuple[int, int] | None  # (start_line, end_line)


@dataclass(frozen=True)
class ScanTheoremArgs:
    file: str
    target: TheoremTarget


def _coerce_args(args: dict[str, Any]) -> ScanTheoremArgs:
    """Parse and validate scan_theorem arguments."""
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("scan_theorem: 'file' must be a non-empty string")

    target = args.get("target")
    if not isinstance(target, dict):
        raise ValueError("scan_theorem: 'target' must be an object")

    # Parse target: either theorem_id or range
    theorem_id = target.get("theorem_id")
    range_obj = target.get("range")

    if theorem_id is not None and range_obj is not None:
        raise ValueError("scan_theorem: 'target' must have either 'theorem_id' or 'range', not both")

    if theorem_id is None and range_obj is None:
        raise ValueError("scan_theorem: 'target' must have either 'theorem_id' or 'range'")

    parsed_theorem_id = None
    parsed_range = None

    if theorem_id is not None:
        if not isinstance(theorem_id, str) or not theorem_id.strip():
            raise ValueError("scan_theorem: 'theorem_id' must be a non-empty string")
        parsed_theorem_id = theorem_id

    if range_obj is not None:
        if not isinstance(range_obj, dict):
            raise ValueError("scan_theorem: 'range' must be an object")
        start_line = range_obj.get("start_line")
        end_line = range_obj.get("end_line")
        if not isinstance(start_line, int) or start_line < 1:
            raise ValueError("scan_theorem: 'start_line' must be an integer >= 1")
        if not isinstance(end_line, int) or end_line < 1:
            raise ValueError("scan_theorem: 'end_line' must be an integer >= 1")
        parsed_range = (start_line, end_line)

    return ScanTheoremArgs(
        file=file,
        target=TheoremTarget(theorem_id=parsed_theorem_id, range=parsed_range)
    )


def scan_theorem(args: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic stub implementation.

    Contract guarantees:
    - always returns valid JSON object
    - includes api_version, status, run_id
    - conforms to docs/mcp/schemas/scan_theorem.json
    - returns minimal theorem object with empty skeleton, empty blocks, zero scores
    """
    try:
        parsed = _coerce_args(args)
    except ValueError as e:
        # Build error response with whatever we can extract
        file_value = args.get("file", "") if isinstance(args, dict) else ""
        if not isinstance(file_value, str) or not file_value.strip():
            file_value = "<invalid>"

        target_value = args.get("target", {}) if isinstance(args, dict) else {}
        if not isinstance(target_value, dict):
            target_value = {"theorem_id": "<invalid>"}
        elif not target_value:
            target_value = {"theorem_id": "<invalid>"}

        return {
            "api_version": API_VERSION,
            "status": "fail",
            "run_id": "scan-theorem-invalid-args",
            "tool": "scan_theorem",
            "file": file_value,
            "target": target_value,
            "theorem": None,
            "diagnostics": [{"severity": "error", "message": str(e)}],
        }

    # deterministic run_id for stub phase; later this becomes a real unique id
    run_id = "scan-theorem-stub-001"

    # Build target object for response (echo input)
    target_response: dict[str, Any] = {}
    if parsed.target.theorem_id is not None:
        target_response["theorem_id"] = parsed.target.theorem_id
        theorem_name = parsed.target.theorem_id.split(".")[-1]  # Extract short name
    else:
        assert parsed.target.range is not None
        start_line, end_line = parsed.target.range
        target_response["range"] = {
            "start_line": start_line,
            "end_line": end_line
        }
        theorem_name = f"theorem_at_line_{start_line}"

    # Minimal theorem object with placeholder data
    theorem_obj = {
        "name": theorem_name,
        "kind": "theorem",
        "location": {
            "decl_start": parsed.target.range[0] if parsed.target.range else 1,
            "decl_end": parsed.target.range[1] if parsed.target.range else 1,
        },
        "structure": {
            "skeleton": [],  # Empty skeleton (stub)
            "blocks": [],    # Empty blocks (stub)
        },
        "automation": {
            "whole_goal_potential": {
                "aesop": 0.0,  # Zero scores (stub)
                "grind": 0.0
            },
            "subgoal_potential": {
                "aesop": 0.0,
                "grind": 0.0
            },
            "annotation_value": 0.0
        },
        "notes": [
            "stub: no parsing performed",
            "stub: returns minimal structure for contract testing"
        ]
    }

    return {
        "api_version": API_VERSION,
        "status": "success",
        "run_id": run_id,
        "tool": "scan_theorem",
        "file": parsed.file,
        "target": target_response,
        "theorem": theorem_obj,
        "diagnostics": [],
    }
