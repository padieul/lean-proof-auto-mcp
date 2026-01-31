"""
Import-based harness construction for theorem testing.

This module provides components for constructing test harnesses that preserve
ALL context from the original file by using Lean's import system instead of
manual signature reconstruction.
"""

from dataclasses import dataclass, field
from typing import Protocol, Union


# ============================================================================
# Core Data Types
# ============================================================================

@dataclass(frozen=True)
class ImportPath:
    """A Lean import path."""
    
    path: str  # e.g., "Fixtures.Algebra.Group"
    
    def to_import_statement(self) -> str:
        """Convert to import statement."""
        return f"import {self.path}"


@dataclass(frozen=True)
class TheoremType:
    """Extracted theorem type information."""
    
    type_expr: str  # The type expression
    source: str     # Where it came from (for debugging)


@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for harness construction."""
    
    theorem_id: str
    file_path: str
    proof_attempt: str
    additional_imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HarnessSuccess:
    """Successful harness construction."""
    
    code: str
    theorem_id: str
    file_path: str


@dataclass(frozen=True)
class HarnessError:
    """Failed harness construction."""
    
    error_type: str  # "theorem_not_found", "invalid_path", "construction_failed"
    message: str
    theorem_id: str
    file_path: str
    generated_code: str | None = None  # For debugging


# Result type for harness construction
HarnessResult = Union[HarnessSuccess, HarnessError]


# ============================================================================
# Exceptions
# ============================================================================

class HarnessConstructionError(Exception):
    """Base exception for harness construction errors."""
    
    def __init__(self, message: str, generated_code: str | None = None):
        super().__init__(message)
        self.generated_code = generated_code


class TheoremNotFoundError(HarnessConstructionError):
    """Raised when a theorem cannot be found."""
    pass


# ============================================================================
# Protocols (Ports)
# ============================================================================

class ImportPathConverter(Protocol):
    """Convert file paths to import paths."""
    
    def convert(self, file_path: str) -> ImportPath:
        """
        Convert file path to import path.
        
        Args:
            file_path: e.g., "Fixtures/Algebra/Group.lean"
            
        Returns: ImportPath e.g., "Fixtures.Algebra.Group"
        """
        ...


class TheoremTypeExtractor(Protocol):
    """Extract theorem types from Lean files."""
    
    def extract_type(self, file_path: str, theorem_id: str) -> TheoremType:
        """
        Extract the type of a theorem.
        
        Args:
            file_path: Path to Lean file
            theorem_id: Fully qualified theorem name
            
        Returns: TheoremType with type expression
        Raises: TheoremNotFoundError if theorem doesn't exist
        """
        ...


class HarnessConstructor(Protocol):
    """Strategy for constructing test harnesses."""
    
    def construct(self, config: HarnessConfig) -> HarnessResult:
        """
        Construct a test harness.
        
        Returns: HarnessSuccess or HarnessError
        """
        ...



# ============================================================================
# Implementations
# ============================================================================

class StandardImportPathConverter:
    """Convert file paths to Lean import paths."""
    
    def convert(self, file_path: str) -> ImportPath:
        """
        Convert file path to import path.
        
        Examples:
            "Fixtures/Algebra/Group.lean" -> "Fixtures.Algebra.Group"
            "fixtures/mathlib/Fixtures/Algebra/Group.lean" -> "Fixtures.Algebra.Group"
        
        Args:
            file_path: Path to Lean file
            
        Returns: ImportPath with dotted notation
        """
        from pathlib import Path
        
        # Normalize path separators (handle both Unix and Windows)
        normalized_path = file_path.replace("\\", "/")
        
        # Normalize path
        path = Path(normalized_path)
        
        # Remove .lean extension
        if path.suffix == ".lean":
            path = path.with_suffix("")
        
        # Convert to parts
        parts = list(path.parts)
        
        # Find the Lean project root (heuristic: first capitalized directory)
        start_idx = 0
        for i, part in enumerate(parts):
            if part and part[0].isupper():
                start_idx = i
                break
        
        # Take from project root onwards
        import_parts = parts[start_idx:]
        
        # Join with dots
        import_path = ".".join(import_parts)
        
        return ImportPath(path=import_path)



class LeanInteractTheoremTypeExtractor:
    """Extract theorem types using LeanInteract."""
    
    def __init__(self, querier: "LeanInteractQuerier"):
        """
        Initialize with LeanInteract querier.
        
        Args:
            querier: LeanInteractQuerier instance for extracting declarations
        """
        from lean_proof_auto_mcp.lean.ports import LeanInteractQuerier
        
        self.querier: LeanInteractQuerier = querier
    
    def extract_type(self, file_path: str, theorem_id: str) -> TheoremType:
        """
        Extract type using LeanInteract's Declaration objects.
        
        Args:
            file_path: Path to Lean file
            theorem_id: Fully qualified theorem name
            
        Returns: TheoremType with type expression
        Raises: TheoremNotFoundError if theorem doesn't exist
        """
        declarations = self.querier.extract_declarations(file_path)
        
        # Find the theorem
        for decl in declarations:
            if decl.name == theorem_id or decl.full_name == theorem_id:
                return TheoremType(
                    type_expr=decl.type,
                    source=f"LeanInteract:{file_path}"
                )
        
        raise TheoremNotFoundError(
            f"Theorem {theorem_id} not found in {file_path}"
        )



class ImportBasedHarnessConstructor:
    """Construct test harnesses using import-based approach."""
    
    def __init__(
        self,
        type_extractor: TheoremTypeExtractor,
        path_converter: ImportPathConverter
    ):
        """
        Initialize with dependencies.
        
        Args:
            type_extractor: Extracts theorem types
            path_converter: Converts file paths to import paths
        """
        self.type_extractor = type_extractor
        self.path_converter = path_converter
    
    def construct(self, config: HarnessConfig) -> HarnessResult:
        """
        Construct import-based test harness.
        
        Returns: HarnessSuccess or HarnessError with:
            - Line 1: import statements
            - Line N: example : <type> := by <proof>
        """
        try:
            # Step 1: Extract theorem type
            theorem_type = self.type_extractor.extract_type(
                config.file_path,
                config.theorem_id
            )
        except TheoremNotFoundError as e:
            return HarnessError(
                error_type="theorem_not_found",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path
            )
        except Exception as e:
            return HarnessError(
                error_type="type_extraction_failed",
                message=f"Failed to extract theorem type: {e}",
                theorem_id=config.theorem_id,
                file_path=config.file_path
            )
        
        try:
            # Step 2: Convert file path to import path
            import_path = self.path_converter.convert(config.file_path)
            
            # Step 3: Build import statements (MUST be line 1)
            imports = [import_path.to_import_statement()]
            imports.extend(config.additional_imports)
            import_block = "\n".join(imports)
            
            # Step 4: Build example statement
            example_block = f"""
-- Test harness for {config.theorem_id}
example : {theorem_type.type_expr} := by
  {config.proof_attempt}
"""
            
            # Step 5: Combine (imports FIRST)
            harness = f"{import_block}\n{example_block}"
            
            # Step 6: Validate before returning
            self._validate_harness(harness)
            
            return HarnessSuccess(
                code=harness,
                theorem_id=config.theorem_id,
                file_path=config.file_path
            )
            
        except HarnessConstructionError as e:
            return HarnessError(
                error_type="construction_failed",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
                generated_code=e.generated_code
            )
        except Exception as e:
            return HarnessError(
                error_type="construction_failed",
                message=f"Unexpected error during construction: {e}",
                theorem_id=config.theorem_id,
                file_path=config.file_path,
                generated_code=harness if 'harness' in locals() else None
            )
    
    def _validate_harness(self, harness: str) -> None:
        """
        Validate generated harness structure.
        
        Raises: HarnessConstructionError if invalid
        """
        lines = harness.split('\n')
        
        # Check 1: First non-empty line must be import
        first_line = next((line for line in lines if line.strip()), "")
        if not first_line.startswith("import"):
            raise HarnessConstructionError(
                "First line must be import statement",
                generated_code=harness
            )
        
        # Check 2: No imports after line 1 (except consecutive imports)
        found_non_import = False
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith("import"):
                found_non_import = True
            elif found_non_import and line.strip().startswith("import"):
                raise HarnessConstructionError(
                    f"Import statement at line {i+1} must be at beginning",
                    generated_code=harness
                )
        
        # Check 3: Must contain "example :"
        if "example :" not in harness:
            raise HarnessConstructionError(
                "Harness must contain 'example :' statement",
                generated_code=harness
            )
