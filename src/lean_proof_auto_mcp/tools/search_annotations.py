"""
DEPRECATED: search_annotations tool has been removed.

This tool has been replaced by search_automated_proof which provides
enhanced functionality with LLM-controlled parameters and rich feedback.

Requirements: 4.8, 26.5
"""

from typing import Any


def search_annotations(args: dict[str, Any]) -> dict[str, Any]:
    """
    DEPRECATED: This tool has been removed.

    The search_annotations tool has been replaced by search_automated_proof,
    which provides enhanced functionality including:
    - LLM-controlled search depth (quick, normal, deep, exhaustive)
    - Configurable candidate sources
    - Rich feedback with proof states and partial progress
    - Tactical suggestions for iteration
    - Similar proof discovery

    Please use search_automated_proof instead.

    Args:
        args: Ignored (tool is deprecated)

    Returns:
        Error response directing users to search_automated_proof

    Requirements: 4.8, 26.5
    """
    return {
        "status": "error",
        "error_code": "tool_deprecated",
        "error_message": (
            "The search_annotations tool has been removed and replaced by "
            "search_automated_proof. Please use search_automated_proof instead. "
            "The new tool provides enhanced functionality with LLM-controlled "
            "search parameters, rich feedback mechanisms, and better iteration support."
        ),
        "migration_guide": {
            "old_tool": "search_annotations",
            "new_tool": "search_automated_proof",
            "key_differences": [
                "Use 'search_depth' parameter instead of complex budget configuration",
                "Candidate sources are now explicitly configurable",
                "Rich feedback includes proof states and tactical suggestions",
                "Better support for iterative refinement"
            ],
            "example_usage": {
                "tool": "search_automated_proof",
                "parameters": {
                    "file": "path/to/file.lean",
                    "theorem_id": "MyTheorem",
                    "search_depth": "normal",
                    "return_proof_states": True,
                    "return_partial_progress": True
                }
            }
        }
    }

