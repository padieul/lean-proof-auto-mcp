"""
Format module for normalizing JSON output to ensure deterministic responses.

This module provides functions to:
- Sort theorems by theorem_id for stable ordering
- Normalize notes arrays (trim length, cap count)
- Ensure all output is deterministic (sorted lists, rounded floats)
"""

from typing import Any


def stable_sort_theorems(theorems: list[dict]) -> list[dict]:
    """
    Sort theorems by theorem_id for deterministic output.

    Args:
        theorems: List of theorem dictionaries with theorem_id field

    Returns:
        New list sorted by theorem_id (lexicographic order)
    """
    return sorted(theorems, key=lambda t: t.get("theorem_id", ""))


def normalize_notes(notes: list[str], max_length: int = 200) -> list[str]:
    """
    Trim note length and cap count for consistent output.

    Args:
        notes: List of note strings
        max_length: Maximum length per note (default 200)

    Returns:
        Normalized notes list (max 10 items, each trimmed to max_length)
    """
    # Cap at 10 items
    capped_notes = notes[:10]

    # Trim each note to max_length
    trimmed_notes = []
    for note in capped_notes:
        trimmed_note = note[: max_length - 3] + "..." if len(note) > max_length else note
        trimmed_notes.append(trimmed_note)

    return trimmed_notes


def ensure_deterministic(data: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure all lists are sorted and floats rounded consistently.

    Args:
        data: Dictionary that may contain lists and floats

    Returns:
        New dictionary with normalized values for deterministic output
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        if isinstance(value, dict):
            # Recursively process nested dictionaries
            result[key] = ensure_deterministic(value)
        elif isinstance(value, list):
            # Process lists
            normalized_list: list[Any] = []
            for item in value:
                if isinstance(item, dict):
                    normalized_list.append(ensure_deterministic(item))
                elif isinstance(item, float):
                    normalized_list.append(round(item, 2))
                else:
                    normalized_list.append(item)

            # Sort if all items are strings (like skeleton tactics)
            # But preserve order for mixed types or complex structures
            if all(isinstance(item, str) for item in normalized_list):
                # Special case: preserve order for skeleton (ordered tactics)
                # Only sort if key suggests it should be sorted
                if key in ["notes"] or "sorted" in key.lower():
                    result[key] = sorted(normalized_list)
                else:
                    result[key] = normalized_list
            else:
                result[key] = normalized_list
        elif isinstance(value, float):
            # Round floats to 2 decimal places
            result[key] = round(value, 2)
        else:
            # Keep other types as-is
            result[key] = value

    return result


def _round_automation_scores(automation: dict[str, Any]) -> dict[str, Any]:
    """
    Helper function to round automation scores to 2 decimal places.

    Args:
        automation: Automation dictionary with score fields

    Returns:
        Automation dict with rounded scores
    """
    result: dict[str, Any] = {}

    for key, value in automation.items():
        if isinstance(value, dict):
            # Handle nested score dictionaries like whole_goal_potential
            result[key] = {k: round(v, 2) if isinstance(v, float) else v for k, v in value.items()}
        elif isinstance(value, float):
            result[key] = round(value, 2)
        else:
            result[key] = value

    return result
