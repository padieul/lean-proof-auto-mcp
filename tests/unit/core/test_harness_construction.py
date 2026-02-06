"""
Unit tests for import-based harness construction components.

Tests cover:
- ImportPath dataclass
- TheoremType dataclass
- HarnessConfig dataclass
- StandardImportPathConverter
- LeanInteractTheoremTypeExtractor
- ImportBasedHarnessConstructor
"""

import pytest
from unittest.mock import Mock, MagicMock

from lean_proof_auto_mcp.core.harness_construction import (
    ImportPath,
    TheoremType,
    HarnessConfig,
    HarnessSuccess,
    HarnessError,
    StandardImportPathConverter,
    LeanInteractTheoremTypeExtractor,
    ImportBasedHarnessConstructor,
    TheoremNotFoundError,
    HarnessConstructionError,
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
# Tests for TheoremType
# ============================================================================

class TestTheoremType:
    """Test TheoremType dataclass."""
    
    def test_theorem_type_creation(self):
        """Test creating a TheoremType."""
        theorem_type = TheoremType(
            type_expr="p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K",
            source="LeanInteract:test.lean"
        )
        assert theorem_type.type_expr == "p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K"
        assert theorem_type.source == "LeanInteract:test.lean"
    
    def test_theorem_type_immutable(self):
        """Test that TheoremType is immutable."""
        theorem_type = TheoremType(type_expr="test", source="test")
        with pytest.raises(AttributeError):
            theorem_type.type_expr = "new"  # type: ignore


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
            proof_attempt="aesop"
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
            additional_imports=["import Aesop", "import Mathlib"]
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


# ============================================================================
# Tests for LeanInteractTheoremTypeExtractor
# ============================================================================

class TestLeanInteractTheoremTypeExtractor:
    """Test LeanInteractTheoremTypeExtractor."""
    
    def test_extract_type_success(self, tmp_path):
        """Test successful type extraction."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

variable {G : Type*} [Group G]

theorem Subgroup.mem_prod : p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K := by
  sorry
""")
        
        # Mock querier with proper server_manager
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager
        
        mock_decl = Mock()
        mock_decl.name = "Subgroup.mem_prod"
        mock_decl.full_name = "Subgroup.mem_prod"
        mock_decl.type = "p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K"
        mock_querier.extract_declarations.return_value = [mock_decl]
        
        extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        result = extractor.extract_type("test.lean", "Subgroup.mem_prod")
        
        # New implementation returns FULL_FILE marker
        assert result.type_expr == "FULL_FILE:Subgroup.mem_prod"
        assert "FullFile" in result.source
        mock_querier.extract_declarations.assert_called_once_with("test.lean")
    
    def test_extract_type_by_full_name(self, tmp_path):
        """Test type extraction using full name."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem mem_prod : test_type := by
  sorry
""")
        
        # Mock querier with proper server_manager
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager
        
        mock_decl = Mock()
        mock_decl.name = "mem_prod"
        mock_decl.full_name = "Subgroup.mem_prod"
        mock_decl.type = "test_type"
        mock_querier.extract_declarations.return_value = [mock_decl]
        
        extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        result = extractor.extract_type("test.lean", "Subgroup.mem_prod")
        
        # New implementation returns FULL_FILE marker
        assert result.type_expr == "FULL_FILE:Subgroup.mem_prod"
    
    def test_extract_type_theorem_not_found(self):
        """Test type extraction when theorem not found."""
        mock_querier = Mock()
        mock_querier.extract_declarations.return_value = []
        
        extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        
        with pytest.raises(TheoremNotFoundError) as exc_info:
            extractor.extract_type("test.lean", "NonExistent")
        
        assert "NonExistent" in str(exc_info.value)
        assert "test.lean" in str(exc_info.value)
    
    def test_extract_type_multiple_declarations(self, tmp_path):
        """Test type extraction with multiple declarations."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem theorem1 : type1 := by sorry

theorem theorem2 : type2 := by sorry
""")
        
        # Mock querier with proper server_manager
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager
        
        mock_decl1 = Mock()
        mock_decl1.name = "theorem1"
        mock_decl1.full_name = "theorem1"
        mock_decl1.type = "type1"
        
        mock_decl2 = Mock()
        mock_decl2.name = "theorem2"
        mock_decl2.full_name = "theorem2"
        mock_decl2.type = "type2"
        
        mock_querier.extract_declarations.return_value = [mock_decl1, mock_decl2]
        
        extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        result = extractor.extract_type("test.lean", "theorem2")
        
        # New implementation returns FULL_FILE marker
        assert result.type_expr == "FULL_FILE:theorem2"


# ============================================================================
# Tests for ImportBasedHarnessConstructor
# ============================================================================

class TestImportBasedHarnessConstructor:
    """Test ImportBasedHarnessConstructor."""
    
    def test_construct_success(self, tmp_path):
        """Test successful harness construction with full file approach."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

variable {G : Type*} [Group G]

theorem test_theorem : True := by
  trivial

theorem other_theorem : False ∨ True := by
  right
  trivial
""")
        
        # Setup mocks
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager
        
        mock_decl = Mock()
        mock_decl.name = "test_theorem"
        mock_decl.full_name = "test_theorem"
        mock_querier.extract_declarations.return_value = [mock_decl]
        
        type_extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        path_converter = StandardImportPathConverter()
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        # Construct harness
        config = HarnessConfig(
            theorem_id="test_theorem",
            file_path="test.lean",
            proof_attempt="aesop"
        )
        
        result = constructor.construct(config)
        
        # Verify success
        assert isinstance(result, HarnessSuccess)
        assert result.theorem_id == "test_theorem"
        assert result.file_path == "test.lean"
        
        # Verify structure - should preserve everything
        assert "import Mathlib" in result.code
        assert "variable {G : Type*} [Group G]" in result.code
        assert "theorem test_theorem" in result.code
        assert "aesop" in result.code
        assert "theorem other_theorem" in result.code
        assert "sorry" in result.code  # Other theorems use sorry
    
    def test_construct_with_additional_imports(self, tmp_path):
        """Test harness construction with additional imports."""
        # Create a test file
        test_file = tmp_path / "test.lean"
        test_file.write_text("""import Mathlib

theorem test : True := by trivial
""")
        
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager
        
        mock_decl = Mock()
        mock_decl.name = "test"
        mock_decl.full_name = "test"
        mock_querier.extract_declarations.return_value = [mock_decl]
        
        type_extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        path_converter = StandardImportPathConverter()
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        config = HarnessConfig(
            theorem_id="test",
            file_path="test.lean",
            proof_attempt="aesop",
            additional_imports=["Aesop", "Std"]
        )
        
        result = constructor.construct(config)
        
        assert isinstance(result, HarnessSuccess)
        assert "import Mathlib" in result.code
        assert "import Aesop" in result.code
        assert "import Std" in result.code
    
    def test_construct_theorem_not_found(self):
        """Test harness construction when theorem not found."""
        type_extractor = Mock()
        type_extractor.extract_type.side_effect = TheoremNotFoundError(
            "Theorem not found"
        )
        
        path_converter = Mock()
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        config = HarnessConfig(
            theorem_id="NonExistent",
            file_path="test.lean",
            proof_attempt="aesop"
        )
        
        result = constructor.construct(config)
        
        assert isinstance(result, HarnessError)
        assert result.error_type == "theorem_not_found"
        assert "NonExistent" in result.theorem_id
    
    def test_construct_type_extraction_failed(self):
        """Test harness construction when type extraction fails."""
        type_extractor = Mock()
        type_extractor.extract_type.side_effect = RuntimeError("Extraction failed")
        
        path_converter = Mock()
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        config = HarnessConfig(
            theorem_id="test",
            file_path="test.lean",
            proof_attempt="aesop"
        )
        
        result = constructor.construct(config)
        
        assert isinstance(result, HarnessError)
        assert result.error_type == "type_extraction_failed"
    
    def test_validate_harness_requires_import(self):
        """Test validation requires at least one import."""
        type_extractor = Mock()
        path_converter = Mock()
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        # Invalid harness (no import)
        invalid_harness = "theorem test : True := by trivial"
        with pytest.raises(HarnessConstructionError) as exc_info:
            constructor._validate_harness(invalid_harness)
        assert "import" in str(exc_info.value).lower()
    
    def test_validate_harness_requires_theorem(self):
        """Test validation requires at least one theorem."""
        type_extractor = Mock()
        path_converter = Mock()
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        # Invalid harness (no theorem)
        invalid_harness = "import Test\n\nvariable (x : Nat)"
        with pytest.raises(HarnessConstructionError) as exc_info:
            constructor._validate_harness(invalid_harness)
        assert "theorem" in str(exc_info.value).lower() or "lemma" in str(exc_info.value).lower()
    
    def test_construct_preserves_unicode(self):
        """Test that harness construction preserves Unicode characters."""
        type_extractor = Mock()
        type_extractor.extract_type.return_value = TheoremType(
            type_expr="∀ x : ℕ, x ≤ x",
            source="test"
        )
        
        path_converter = Mock()
        path_converter.convert.return_value = ImportPath(path="Test")
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        config = HarnessConfig(
            theorem_id="test",
            file_path="test.lean",
            proof_attempt="rfl"
        )
        
        result = constructor.construct(config)
        
        assert isinstance(result, HarnessSuccess)
        assert "∀ x : ℕ, x ≤ x" in result.code
    
    def test_construct_handles_complex_types(self):
        """Test harness construction with complex theorem types."""
        type_extractor = Mock()
        type_extractor.extract_type.return_value = TheoremType(
            type_expr="{p : G × N} → p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K",
            source="test"
        )
        
        path_converter = Mock()
        path_converter.convert.return_value = ImportPath(path="Test")
        
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        config = HarnessConfig(
            theorem_id="test",
            file_path="test.lean",
            proof_attempt="aesop"
        )
        
        result = constructor.construct(config)
        
        assert isinstance(result, HarnessSuccess)
        assert "{p : G × N}" in result.code
        assert "↔" in result.code


# ============================================================================
# Integration Tests
# ============================================================================

class TestHarnessConstructionIntegration:
    """Integration tests for harness construction components."""
    
    def test_full_pipeline(self, tmp_path):
        """Test full harness construction pipeline."""
        # Create a test file
        test_file = tmp_path / "Test" / "Module.lean"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("""import Mathlib

theorem test_theorem : True := by
  trivial
""")
        
        # Create real components
        path_converter = StandardImportPathConverter()
        
        # Mock querier with proper server_manager
        mock_querier = Mock()
        mock_server_manager = Mock()
        mock_server_manager.workspace_path = tmp_path
        mock_querier.server_manager = mock_server_manager
        
        mock_decl = Mock()
        mock_decl.name = "test_theorem"
        mock_decl.full_name = "Test.test_theorem"
        mock_decl.type = "True"
        mock_querier.extract_declarations.return_value = [mock_decl]
        
        type_extractor = LeanInteractTheoremTypeExtractor(mock_querier)
        
        # Create constructor
        constructor = ImportBasedHarnessConstructor(
            type_extractor=type_extractor,
            path_converter=path_converter
        )
        
        # Construct harness
        config = HarnessConfig(
            theorem_id="test_theorem",
            file_path="Test/Module.lean",
            proof_attempt="trivial"
        )
        
        result = constructor.construct(config)
        
        # Verify
        assert isinstance(result, HarnessSuccess)
        # New implementation copies imports and theorem from source file
        assert "import Mathlib" in result.code
        assert "theorem test_theorem" in result.code
        assert "trivial" in result.code
