"""
JSON serialization utilities for domain objects.

This module provides custom JSON serialization for domain objects that contain
enums, frozensets, and other non-JSON-serializable types.

Requirements: 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5
"""

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def to_json_serializable(obj: Any) -> Any:
    """
    Convert an object to a JSON-serializable form.

    This function recursively converts:
    - Enums to their values
    - Frozensets to sorted lists
    - Dataclasses to dicts
    - Other objects remain unchanged

    Args:
        obj: Object to convert

    Returns:
        JSON-serializable version of the object

    Requirements: 10.9, 10.10, 13.1, 13.2
    """
    # Handle None
    if obj is None:
        return None

    # Handle enums
    if isinstance(obj, Enum):
        return obj.value

    # Handle frozensets - convert to sorted list for determinism
    if isinstance(obj, frozenset):
        # Convert frozenset elements recursively
        items = [to_json_serializable(item) for item in obj]
        # Sort by JSON representation for determinism
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))

    # Handle sets - convert to sorted list for determinism
    if isinstance(obj, set):
        items = [to_json_serializable(item) for item in obj]
        return sorted(items, key=lambda x: json.dumps(x, sort_keys=True))

    # Handle lists
    if isinstance(obj, list):
        return [to_json_serializable(item) for item in obj]

    # Handle tuples
    if isinstance(obj, tuple):
        return [to_json_serializable(item) for item in obj]

    # Handle dicts
    if isinstance(obj, dict):
        return {key: to_json_serializable(value) for key, value in obj.items()}

    # Handle dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        # Convert to dict first, then recursively process
        obj_dict = asdict(obj)
        return to_json_serializable(obj_dict)

    # Handle basic types (str, int, float, bool)
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # For other types, try to convert to string
    return str(obj)

