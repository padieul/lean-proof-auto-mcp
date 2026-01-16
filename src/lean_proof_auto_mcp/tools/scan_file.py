from __future__ import annotations

from dataclasses import dataclass
from typing import Any

API_VERSION = "0.1"


@dataclass(frozen=True)
class ScanFileArgs:
    file: str


def _coerce_args(args: dict[str, Any]) -> ScanFileArgs:
    file = args.get("file")
    if not isinstance(file, str) or not file.strip():
        raise ValueError("scan_file: 'file' must be a non-empty string")
    return ScanFileArgs(file=file)


def scan_file(args: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic stub implementation.

    Contract guarantees:
    - always returns valid JSON object
    - includes api_version, status, run_id
    - conforms to docs/mcp/schemas/scan_file.json
    """
    try:
        parsed = _coerce_args(args)
    except ValueError as e:
        # Schema requires file to be non-empty, so use placeholder for invalid input
        file_value = args.get("file", "") if isinstance(args, dict) else ""
        if not file_value or not file_value.strip():
            file_value = "<invalid>"

        return {
            "api_version": API_VERSION,
            "status": "fail",
            "run_id": "scan-file-invalid-args",
            "tool": "scan_file",
            "file": file_value,
            "summary": {"theorem_count": 0, "notes": []},
            "diagnostics": [{"severity": "error", "message": str(e)}],
        }

    # deterministic run_id for stub phase; later this becomes a real unique id
    run_id = "scan-file-stub-001"

    return {
        "api_version": API_VERSION,
        "status": "success",
        "run_id": run_id,
        "tool": "scan_file",
        "file": parsed.file,
        "summary": {
            "theorem_count": 0,
            "notes": [
                "stub: no parsing performed",
                "stub: returns deterministic shape for contract testing",
            ],
        },
        "theorems": [],
        "diagnostics": [],
    }
