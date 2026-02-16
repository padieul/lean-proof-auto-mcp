"""
Unit tests for harness construction components.

Tests cover:
- ImportPath dataclass
- HarnessConfig dataclass
- StandardImportPathConverter
"""

import pytest

from lean_proof_auto_mcp.core.harness_construction import (
    HarnessConfig,
    ImportPath,
    StandardImportPathConverter,
)

# ============================================================================
# Tests for ImportPath
# ============================================================================


class TestImportPath:
    """Test ImportPath dataclass."""

    def test_import_path_creation(self):
        """Test creating an ImportPath."""
        path = ImportPath(path="Fixtures.Algebra.Group")
        assert path.path == "Fixtures.Algebra.Group"

    def test_to_import_statement(self):
        """Test converting to import statement."""
        path = ImportPath(path="Fixtures.Algebra.Group")
        assert path.to_import_statement() == "import Fixtures.Algebra.Group"

    def test_import_path_immutable(self):
        """Test that ImportPath is immutable."""
        path = ImportPath(path="Test.Module")
        with pytest.raises(AttributeError):
            path.path = "NewPath"  # type: ignore


# ============================================================================
# Tests for HarnessConfig
# ============================================================================


class TestHarnessConfig:
    """Test HarnessConfig dataclass."""

    def test_harness_config_creation(self):
        """Test creating a HarnessConfig."""
        config = HarnessConfig(
            theorem_id="Subgroup.mem_prod",
            file_path="Fixtures/Algebra/Group.lean",
            proof_attempt="aesop",
        )
        assert config.theorem_id == "Subgroup.mem_prod"
        assert config.file_path == "Fixtures/Algebra/Group.lean"
        assert config.proof_attempt == "aesop"
        assert config.additional_imports == []

    def test_harness_config_with_imports(self):
        """Test HarnessConfig with additional imports."""
        config = HarnessConfig(
            theorem_id="test",
            file_path="test.lean",
            proof_attempt="aesop",
            additional_imports=["import Aesop", "import Mathlib"],
        )
        assert len(config.additional_imports) == 2


# ============================================================================
# Tests for StandardImportPathConverter
# ============================================================================


class TestStandardImportPathConverter:
    """Test StandardImportPathConverter."""

    def test_basic_conversion(self):
        """Test basic file path to import path conversion."""
        converter = StandardImportPathConverter()
        result = converter.convert("Fixtures/Algebra/Group.lean")
        assert result.path == "Fixtures.Algebra.Group"

    def test_conversion_with_extra_prefix(self):
        """Test conversion with extra prefix directories."""
        converter = StandardImportPathConverter()
        result = converter.convert("fixtures/mathlib/Fixtures/Algebra/Group.lean")
        assert result.path == "Fixtures.Algebra.Group"

    def test_nested_directories(self):
        """Test conversion with nested directories."""
        converter = StandardImportPathConverter()
        result = converter.convert("Mathlib/Data/List/Basic.lean")
        assert result.path == "Mathlib.Data.List.Basic"

    def test_without_lean_extension(self):
        """Test conversion without .lean extension."""
        converter = StandardImportPathConverter()
        result = converter.convert("Fixtures/Algebra/Group")
        assert result.path == "Fixtures.Algebra.Group"

    def test_single_directory(self):
        """Test conversion with single directory."""
        converter = StandardImportPathConverter()
        result = converter.convert("Test.lean")
        assert result.path == "Test"

    def test_windows_path_separators(self):
        """Test conversion with Windows path separators."""
        converter = StandardImportPathConverter()
        result = converter.convert("Fixtures\\Algebra\\Group.lean")
        assert result.path == "Fixtures.Algebra.Group"
