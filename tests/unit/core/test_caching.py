"""
Unit tests for caching infrastructure in ImportBasedHarnessConstructor.

Tests verify:
- File content caching
- Declaration extraction caching
- Theorem verification caching
- Cache clearing
"""

from unittest.mock import Mock, call

import pytest

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessConfig,
    HarnessSuccess,
    ImportBasedHarnessConstructor,
    TheoremType,
)


class TestImportBasedHarnessConstructorCaching:
    """Test caching infrastructure in ImportBasedHarnessConstructor."""

    def test_declaration_cache_hit(self, tmp_path):
        """Test that declaration extraction is cached."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem test : True := by trivial
""", encoding="utf-8")

        # Setup mocks
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager

        mock_decl = Mock()
        mock_decl.name = "test"
        mock_decl.full_name = "test"
        mock_querier.extract_declarations.return_value = [mock_decl]

        type_extractor = Mock()
        type_extractor.querier = mock_querier
        type_extractor.extract_type.return_value = TheoremType(
            type_expr="FULL_FILE:test", source="test"
        )

        path_converter = Mock()

        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor, path_converter=path_converter
        )

        # First call - should call extract_type
        config1 = HarnessConfig(
            theorem_id="test", file_path="test.lean", proof_attempt="trivial"
        )
        result1 = constructor.construct(config1)
        assert isinstance(result1, HarnessSuccess)
        assert type_extractor.extract_type.call_count == 1

        # Second call with same file and theorem - should use cache
        config2 = HarnessConfig(
            theorem_id="test", file_path="test.lean", proof_attempt="aesop"
        )
        result2 = constructor.construct(config2)
        assert isinstance(result2, HarnessSuccess)
        # Should still be 1 - cache hit
        assert type_extractor.extract_type.call_count == 1

    def test_file_cache_hit(self, tmp_path):
        """Test that file content is cached."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem test1 : True := by trivial

theorem test2 : True := by trivial
""", encoding="utf-8")

        # Setup mocks
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager

        type_extractor = Mock()
        type_extractor.querier = mock_querier

        # Return different theorem types for different theorems
        def extract_type_side_effect(file_path, theorem_id):
            return TheoremType(type_expr=f"FULL_FILE:{theorem_id}", source="test")

        type_extractor.extract_type.side_effect = extract_type_side_effect

        path_converter = Mock()

        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor, path_converter=path_converter
        )

        # First call - should read file
        config1 = HarnessConfig(
            theorem_id="test1", file_path="test.lean", proof_attempt="trivial"
        )
        result1 = constructor.construct(config1)
        assert isinstance(result1, HarnessSuccess)

        # Check that file was read (cache populated)
        file_path_str = str(tmp_path / "test.lean")
        assert file_path_str in constructor._file_cache

        # Second call with different theorem but same file - should use cached file
        config2 = HarnessConfig(
            theorem_id="test2", file_path="test.lean", proof_attempt="aesop"
        )
        result2 = constructor.construct(config2)
        assert isinstance(result2, HarnessSuccess)

        # Verify cache was used (same file content)
        assert constructor._file_cache[file_path_str] == test_file.read_text(encoding="utf-8")

    def test_theorem_verified_cache(self, tmp_path):
        """Test that theorem verification is cached."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem test : True := by trivial
""", encoding="utf-8")

        # Setup mocks
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager

        type_extractor = Mock()
        type_extractor.querier = mock_querier
        type_extractor.extract_type.return_value = TheoremType(
            type_expr="FULL_FILE:test", source="test"
        )

        path_converter = Mock()

        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor, path_converter=path_converter
        )

        # First call
        config = HarnessConfig(
            theorem_id="test", file_path="test.lean", proof_attempt="trivial"
        )
        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)

        # Verify theorem verification was cached
        cache_key = "test.lean::test"
        assert cache_key in constructor._theorem_verified
        assert constructor._theorem_verified[cache_key] is True

    def test_clear_cache(self, tmp_path):
        """Test that clear_cache empties all caches."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem test : True := by trivial
""", encoding="utf-8")

        # Setup mocks
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager

        type_extractor = Mock()
        type_extractor.querier = mock_querier
        type_extractor.extract_type.return_value = TheoremType(
            type_expr="FULL_FILE:test", source="test"
        )

        path_converter = Mock()

        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor, path_converter=path_converter
        )

        # Populate caches
        config = HarnessConfig(
            theorem_id="test", file_path="test.lean", proof_attempt="trivial"
        )
        result = constructor.construct(config)
        assert isinstance(result, HarnessSuccess)

        # Verify caches are populated
        assert len(constructor._file_cache) > 0
        assert len(constructor._decl_cache) > 0
        assert len(constructor._theorem_verified) > 0

        # Clear caches
        constructor.clear_cache()

        # Verify all caches are empty
        assert len(constructor._file_cache) == 0
        assert len(constructor._decl_cache) == 0
        assert len(constructor._theorem_verified) == 0

    def test_cache_isolation_different_files(self, tmp_path):
        """Test that caches are isolated for different files."""
        # Create two test files
        test_file1 = tmp_path / "test1.lean"
        test_file1.write_text("""import Mathlib

theorem test : True := by trivial
""", encoding="utf-8")

        test_file2 = tmp_path / "test2.lean"
        test_file2.write_text("""import Mathlib

theorem test : False ∨ True := by right; trivial
""", encoding="utf-8")

        # Setup mocks
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager

        type_extractor = Mock()
        type_extractor.querier = mock_querier

        def extract_type_side_effect(file_path, theorem_id):
            return TheoremType(type_expr=f"FULL_FILE:{theorem_id}", source=file_path)

        type_extractor.extract_type.side_effect = extract_type_side_effect

        path_converter = Mock()

        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor, path_converter=path_converter
        )

        # Construct from first file
        config1 = HarnessConfig(
            theorem_id="test", file_path="test1.lean", proof_attempt="trivial"
        )
        result1 = constructor.construct(config1)
        assert isinstance(result1, HarnessSuccess)

        # Construct from second file
        config2 = HarnessConfig(
            theorem_id="test", file_path="test2.lean", proof_attempt="aesop"
        )
        result2 = constructor.construct(config2)
        assert isinstance(result2, HarnessSuccess)

        # Verify both files are cached separately
        file1_path = str(tmp_path / "test1.lean")
        file2_path = str(tmp_path / "test2.lean")
        assert file1_path in constructor._file_cache
        assert file2_path in constructor._file_cache
        assert constructor._file_cache[file1_path] != constructor._file_cache[file2_path]

        # Verify both theorems are cached separately
        assert "test1.lean::test" in constructor._decl_cache
        assert "test2.lean::test" in constructor._decl_cache
