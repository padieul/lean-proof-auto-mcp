"""Unit tests for search_annotations deprecation.

This tool has been deprecated and replaced by search_automated_proof.

Requirements: 4.8, 26.5
"""

from lean_proof_auto_mcp.tools.search_annotations import search_annotations


class TestSearchAnnotationsDeprecation:
    """Test that search_annotations returns deprecation error.

    Requirements: 4.8, 26.5
    """

    def test_returns_deprecation_error(self):
        """Test that search_annotations returns deprecation error."""
        result = search_annotations({})

        assert result["status"] == "error"
        assert result["error_code"] == "tool_deprecated"

    def test_error_message_is_clear(self):
        """Test that error message clearly explains deprecation."""
        result = search_annotations({})

        error_message = result["error_message"]
        assert "search_annotations" in error_message
        assert "search_automated_proof" in error_message
        assert "removed" in error_message or "replaced" in error_message

    def test_provides_migration_guide(self):
        """Test that response includes migration guide."""
        result = search_annotations({})

        assert "migration_guide" in result
        migration_guide = result["migration_guide"]
        assert "old_tool" in migration_guide
        assert "new_tool" in migration_guide
        assert migration_guide["old_tool"] == "search_annotations"
        assert migration_guide["new_tool"] == "search_automated_proof"

    def test_migration_guide_has_key_differences(self):
        """Test that migration guide explains key differences."""
        result = search_annotations({})

        migration_guide = result["migration_guide"]
        assert "key_differences" in migration_guide
        assert isinstance(migration_guide["key_differences"], list)
        assert len(migration_guide["key_differences"]) > 0

    def test_migration_guide_has_example_usage(self):
        """Test that migration guide includes example usage."""
        result = search_annotations({})

        migration_guide = result["migration_guide"]
        assert "example_usage" in migration_guide
        example = migration_guide["example_usage"]
        assert "tool" in example
        assert example["tool"] == "search_automated_proof"
        assert "parameters" in example
        assert "file" in example["parameters"]
        assert "theorem_id" in example["parameters"]

    def test_deprecation_with_any_arguments(self):
        """Test that deprecation error is returned regardless of arguments."""
        # Test with various argument combinations
        test_cases = [
            {},
            {"file": "test.lean"},
            {"file": "test.lean", "theorem_id": "MyTheorem"},
            {
                "file": "test.lean",
                "theorem_id": "MyTheorem",
                "mode": "local_only",
                "budgets": {"search_total_s": 300.0},
            },
        ]

        for args in test_cases:
            result = search_annotations(args)
            assert result["status"] == "error"
            assert result["error_code"] == "tool_deprecated"
            assert "search_automated_proof" in result["error_message"]

    def test_no_exceptions_raised(self):
        """Test that no exceptions are raised, only error response returned."""
        # Should not raise any exceptions
        result = search_annotations({"invalid": "args"})
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert result["error_code"] == "tool_deprecated"
