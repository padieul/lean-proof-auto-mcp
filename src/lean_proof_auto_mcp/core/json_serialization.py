"""
JSON serialization utilities for search-annotations domain objects.

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


def result_to_dict(result: Any) -> dict[str, Any]:
    """
    Convert a SearchAnnotationsResult to a JSON-serializable dict.
    
    This function ensures:
    - All enums are converted to values
    - All frozensets are converted to sorted lists
    - All nested dataclasses are converted to dicts
    - Output is deterministic and JSON-serializable
    
    Args:
        result: SearchAnnotationsResult instance
        
    Returns:
        JSON-serializable dictionary
        
    Requirements: 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5
    """
    # Convert dataclass to dict
    result_dict = asdict(result)
    
    # Recursively convert to JSON-serializable form
    return to_json_serializable(result_dict)


def command_to_dict(command: Any) -> dict[str, Any]:
    """
    Convert a SearchAnnotationsCommand to a JSON-serializable dict.
    
    This function ensures:
    - All enums are converted to values
    - All nested dataclasses are converted to dicts
    - Output is deterministic and JSON-serializable
    
    Args:
        command: SearchAnnotationsCommand instance
        
    Returns:
        JSON-serializable dictionary
        
    Requirements: 13.1, 13.2
    """
    # Convert dataclass to dict
    command_dict = asdict(command)
    
    # Recursively convert to JSON-serializable form
    return to_json_serializable(command_dict)


def dumps_deterministic(obj: Any, **kwargs: Any) -> str:
    """
    Serialize object to JSON string with deterministic formatting.
    
    This function ensures:
    - Keys are sorted alphabetically
    - Formatting is consistent
    - Output is deterministic across runs
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments for json.dumps
        
    Returns:
        JSON string
        
    Requirements: 13.1, 13.5
    """
    # Convert to JSON-serializable form
    serializable = to_json_serializable(obj)
    
    # Serialize with sorted keys and consistent formatting
    return json.dumps(serializable, sort_keys=True, indent=2, **kwargs)
