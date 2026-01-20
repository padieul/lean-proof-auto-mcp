"""Unit tests for core.format module."""

import pytest
from src.lean_proof_auto_mcp.core.format import (
    stable_sort_theorems,
    normalize_notes,
    ensure_deterministic,
)


class TestStableSortTheorems:
    """Test cases for stable_sort_theorems function."""
    
    def test_sort_empty_list(self):
        """Test sorting empty theorem list."""
        result = stable_sort_theorems([])
        assert result == []
    
    def test_sort_single_theorem(self):
        """Test sorting single theorem."""
        theorems = [{"theorem_id": "Nat.add_comm", "name": "add_comm"}]
        result = stable_sort_theorems(theorems)
        assert result == theorems
    
    def test_sort_multiple_theorems(self):
        """Test sorting multiple theorems by theorem_id."""
        theorems = [
            {"theorem_id": "Nat.mul_comm", "name": "mul_comm"},
            {"theorem_id": "Nat.add_comm", "name": "add_comm"},
            {"theorem_id": "Nat.zero_add", "name": "zero_add"},
        ]
        result = stable_sort_theorems(theorems)
        expected = [
            {"theorem_id": "Nat.add_comm", "name": "add_comm"},
            {"theorem_id": "Nat.mul_comm", "name": "mul_comm"},
            {"theorem_id": "Nat.zero_add", "name": "zero_add"},
        ]
        assert result == expected
    
    def test_sort_missing_theorem_id(self):
        """Test sorting theorems with missing theorem_id."""
        theorems = [
            {"theorem_id": "Nat.add_comm", "name": "add_comm"},
            {"name": "no_id"},  # missing theorem_id
            {"theorem_id": "Nat.zero_add", "name": "zero_add"},
        ]
        result = stable_sort_theorems(theorems)
        # Missing theorem_id should sort first (empty string)
        assert result[0]["name"] == "no_id"
        assert result[1]["theorem_id"] == "Nat.add_comm"
        assert result[2]["theorem_id"] == "Nat.zero_add"
    
    def test_sort_preserves_original(self):
        """Test that original list is not modified."""
        original = [
            {"theorem_id": "Nat.mul_comm", "name": "mul_comm"},
            {"theorem_id": "Nat.add_comm", "name": "add_comm"},
        ]
        original_copy = original.copy()
        result = stable_sort_theorems(original)
        
        # Original should be unchanged
        assert original == original_copy
        # Result should be sorted
        assert result[0]["theorem_id"] == "Nat.add_comm"
        assert result[1]["theorem_id"] == "Nat.mul_comm"


class TestNormalizeNotes:
    """Test cases for normalize_notes function."""
    
    def test_normalize_empty_notes(self):
        """Test normalizing empty notes list."""
        result = normalize_notes([])
        assert result == []
    
    def test_normalize_short_notes(self):
        """Test normalizing notes within length limit."""
        notes = ["short note", "another note"]
        result = normalize_notes(notes)
        assert result == notes
    
    def test_normalize_long_note(self):
        """Test trimming long notes."""
        long_note = "a" * 250  # 250 characters
        notes = [long_note]
        result = normalize_notes(notes, max_length=200)
        
        assert len(result) == 1
        assert len(result[0]) == 200
        assert result[0].endswith("...")
        assert result[0].startswith("a" * 197)  # 200 - 3 for "..."
    
    def test_normalize_many_notes(self):
        """Test capping notes count at 10."""
        notes = [f"note {i}" for i in range(15)]  # 15 notes
        result = normalize_notes(notes)
        
        assert len(result) == 10
        assert result == [f"note {i}" for i in range(10)]
    
    def test_normalize_custom_max_length(self):
        """Test custom max_length parameter."""
        long_note = "a" * 100
        notes = [long_note]
        result = normalize_notes(notes, max_length=50)
        
        assert len(result[0]) == 50
        assert result[0] == "a" * 47 + "..."
    
    def test_normalize_exact_length(self):
        """Test note exactly at max_length."""
        note = "a" * 200
        notes = [note]
        result = normalize_notes(notes, max_length=200)
        
        assert result == [note]  # Should not be trimmed


class TestEnsureDeterministic:
    """Test cases for ensure_deterministic function."""
    
    def test_ensure_deterministic_empty_dict(self):
        """Test with empty dictionary."""
        result = ensure_deterministic({})
        assert result == {}
    
    def test_round_floats(self):
        """Test rounding floats to 2 decimal places."""
        data = {
            "score": 0.123456,
            "value": 1.999,
            "exact": 2.0,
        }
        result = ensure_deterministic(data)
        expected = {
            "score": 0.12,
            "value": 2.0,
            "exact": 2.0,
        }
        assert result == expected
    
    def test_round_nested_floats(self):
        """Test rounding floats in nested structures."""
        data = {
            "automation": {
                "whole_goal_potential": {"aesop": 0.123456, "grind": 0.789012},
                "annotation_value": 0.555555,
            }
        }
        result = ensure_deterministic(data)
        expected = {
            "automation": {
                "whole_goal_potential": {"aesop": 0.12, "grind": 0.79},
                "annotation_value": 0.56,
            }
        }
        assert result == expected
    
    def test_process_lists(self):
        """Test processing lists with floats."""
        data = {
            "scores": [0.123456, 0.789012, 1.0],
            "skeleton": ["intro", "cases", "apply"],
        }
        result = ensure_deterministic(data)
        expected = {
            "scores": [0.12, 0.79, 1.0],
            "skeleton": ["intro", "cases", "apply"],  # preserved order
        }
        assert result == expected
    
    def test_sort_notes(self):
        """Test sorting notes arrays."""
        data = {
            "notes": ["zebra", "apple", "banana"],
            "skeleton": ["intro", "cases"],  # should preserve order
        }
        result = ensure_deterministic(data)
        expected = {
            "notes": ["apple", "banana", "zebra"],  # sorted
            "skeleton": ["intro", "cases"],  # preserved
        }
        assert result == expected
    
    def test_nested_dictionaries(self):
        """Test processing nested dictionaries."""
        data = {
            "theorem": {
                "automation": {
                    "scores": [0.123, 0.789],
                },
                "notes": ["long proof", "complex"],
            }
        }
        result = ensure_deterministic(data)
        expected = {
            "theorem": {
                "automation": {
                    "scores": [0.12, 0.79],
                },
                "notes": ["complex", "long proof"],  # sorted
            }
        }
        assert result == expected
    
    def test_preserve_non_float_types(self):
        """Test that non-float types are preserved."""
        data = {
            "name": "test_theorem",
            "count": 42,
            "active": True,
            "items": ["a", "b", "c"],
        }
        result = ensure_deterministic(data)
        assert result == data
    
    def test_mixed_list_types(self):
        """Test lists with mixed types."""
        data = {
            "mixed": [0.123, "string", 42, True],
        }
        result = ensure_deterministic(data)
        expected = {
            "mixed": [0.12, "string", 42, True],
        }
        assert result == expected