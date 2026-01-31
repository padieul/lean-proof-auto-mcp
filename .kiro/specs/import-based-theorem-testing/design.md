# Import-Based Theorem Testing - Design Document

## Overview

This design document specifies the architecture for fixing the critical code generation bugs that cause 100% failure rate in proof-modifying MCP tools. The solution uses Lean's import system and LeanInteract querier to preserve ALL theorem context automatically.

## Code to be OBLITERATED

Before implementing the new architecture, the following broken code must be **completely removed** from the codebase:

### 1. Manual Parsing Code in probe_domain.py
**Location:** `src/lean_proof_auto_mcp/core/probe_domain.py` (approximately lines 681-830)

**Functions to DELETE:**
- `_extract_theorem_signature()` - Manual signature parsing (BROKEN)
- `_parse_theorem_type()` - Manual type extraction (BROKEN)
- `_extract_theorem_context()` - Manual context extraction (BROKEN)
- `_reconstruct_theorem()` - Manual theorem reconstruction (BROKEN)
- Any helper functions used by the above

**Why:** These functions use fragile text parsing that:
- Splits on first `:` (corrupts parameters like `{p : G × N}`)
- Loses type class instances
- Loses variable declarations
- Corrupts Unicode characters
- Causes 100% failure rate

### 2. Search Annotations Tool
**Location:** TBD (needs to be identified in codebase)

**What to DELETE:**
- Search annotations tool implementation (all files)
- MCP tool registration for search_annotations
- All tests for search_annotations
- All documentation for search_annotations
- ALL references to "search_annotations" or "SearchAnnotations"

**Why:** This tool is not mentioned in requirements and should not exist.

### 3. Any Legacy Harness Constructor
**Location:** TBD (if exists)

**What to DELETE:**
- Any class named `LegacyHarnessConstructor` or similar
- Any harness construction code that manually reconstructs signatures
- ALL references to legacy constructors

**Why:** Only ImportBasedHarnessConstructor should exist.

### Verification Steps
After removal, verify:
1. `grep -r "_extract_theorem_signature" src/` returns nothing
2. `grep -r "_parse_theorem_type" src/` returns nothing
3. `grep -r "search_annotations" .` returns nothing (except in this spec)
4. `grep -r "LegacyHarness" src/` returns nothing
5. All tests pass (or fail only due to missing implementations, not broken imports)

## Architecture

### Core Design Principle: Import-Based Harness Construction

**Pattern:** Instead of reconstructing theorem signatures manually, import the original file and reference the theorem type.

```lean
-- CORRECT APPROACH (Import-Based):
import OriginalFile.Path
import Aesop  -- if needed for automation

-- Test using the imported theorem's type
example : <theorem_type_from_querier> := by
  <test_tactic>
```

**Benefits:**
- Lean's import system handles ALL context (namespaces, variables, instances, notation)
- No manual parsing required
- Works for ALL theorem signatures regardless of complexity
- Simple, maintainable, and reliable

### Hexagonal Architecture Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                        │
│  (probe, try_automated_proof, search_automated_proof)   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Core Domain Layer                           │
│  - HarnessConstructor (Strategy Pattern)                │
│  - TheoremTypeExtractor (uses LeanInteract)             │
│  - ImportPathConverter                                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                        │
│  - LeanInteractQuerier (external dependency)            │
│  - ServerManager (Lean process management)              │
│  - FileSystem (read/write harness files)                │
└─────────────────────────────────────────────────────────┘
```

## Component Design

### 1. HarnessConstructor (Strategy Pattern)

**Purpose:** Construct test harnesses using different strategies based on context.

**Interface:**
```python
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for harness construction."""
    theorem_id: str
    file_path: str
    proof_attempt: str
    additional_imports: list[str] = field(default_factory=list)

class HarnessConstructor(Protocol):
    """Strategy for constructing test harnesses."""
    
    def construct(self, config: HarnessConfig) -> str:
        """
        Construct a test harness.
        
        Returns: Valid Lean code as string
        Raises: HarnessConstructionError if construction fails
        """
        ...
```

**Implementation:**

**ImportBasedHarnessConstructor** (ONLY implementation)
   - Uses import + example pattern
   - Extracts theorem type via LeanInteractQuerier
   - Guarantees valid Lean code
   - Replaces ALL legacy manual parsing code

### 2. TheoremTypeExtractor (Dependency Injection)

**Purpose:** Extract theorem types using LeanInteract, not manual parsing.

**Interface:**
```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class TheoremType:
    """Extracted theorem type information."""
    type_expr: str  # The type expression
    source: str     # Where it came from (for debugging)

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
```

**Implementation:**
```python
from lean_proof_auto_mcp.lean.lean_interact_querier import LeanInteractQuerier

class LeanInteractTheoremTypeExtractor:
    """Extract theorem types using LeanInteract."""
    
    def __init__(self, querier: LeanInteractQuerier):
        self.querier = querier
    
    def extract_type(self, file_path: str, theorem_id: str) -> TheoremType:
        """Extract type using LeanInteract's Declaration objects."""
        declarations = self.querier.extract_declarations(file_path)
        
        # Find the theorem
        for decl in declarations:
            if decl.name == theorem_id:
                return TheoremType(
                    type_expr=decl.type,
                    source=f"LeanInteract:{file_path}"
                )
        
        raise TheoremNotFoundError(
            f"Theorem {theorem_id} not found in {file_path}"
        )
```

### 3. ImportPathConverter (Builder Pattern)

**Purpose:** Convert file paths to Lean import paths correctly.

**Interface:**
```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class ImportPath:
    """A Lean import path."""
    path: str  # e.g., "Fixtures.Algebra.Group"
    
    def to_import_statement(self) -> str:
        """Convert to import statement."""
        return f"import {self.path}"

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
```

**Implementation:**
```python
import os
from pathlib import Path

class StandardImportPathConverter:
    """Convert file paths to Lean import paths."""
    
    def convert(self, file_path: str) -> ImportPath:
        """
        Convert file path to import path.
        
        Examples:
            "Fixtures/Algebra/Group.lean" -> "Fixtures.Algebra.Group"
            "fixtures/mathlib/Fixtures/Algebra/Group.lean" -> "Fixtures.Algebra.Group"
        """
        # Normalize path
        path = Path(file_path)
        
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
```

### 4. ImportBasedHarnessConstructor (Complete Implementation)

**Purpose:** Construct harnesses using the import-based approach.

```python
from dataclasses import dataclass
from typing import Protocol

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
    
    def construct(self, config: HarnessConfig) -> str:
        """
        Construct import-based test harness.
        
        Returns: Valid Lean code with:
            - Line 1: import statements
            - Line N: example : <type> := by <proof>
        """
        # Step 1: Extract theorem type
        theorem_type = self.type_extractor.extract_type(
            config.file_path,
            config.theorem_id
        )
        
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
        
        return harness
    
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
```

## Error Handling (Result Pattern)

**Design Principle:** Use Result/Either pattern for explicit error handling.

```python
from dataclasses import dataclass
from typing import Union

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

HarnessResult = Union[HarnessSuccess, HarnessError]

class ImportBasedHarnessConstructor:
    """Updated with Result pattern."""
    
    def construct(self, config: HarnessConfig) -> HarnessResult:
        """
        Construct harness, returning Result.
        
        Returns: HarnessSuccess or HarnessError
        """
        try:
            # Extract type
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
        
        try:
            # Convert path
            import_path = self.path_converter.convert(config.file_path)
            
            # Build harness
            harness = self._build_harness(
                theorem_type,
                import_path,
                config
            )
            
            # Validate
            self._validate_harness(harness)
            
            return HarnessSuccess(
                code=harness,
                theorem_id=config.theorem_id,
                file_path=config.file_path
            )
            
        except Exception as e:
            return HarnessError(
                error_type="construction_failed",
                message=str(e),
                theorem_id=config.theorem_id,
                file_path=config.file_path,
                generated_code=harness if 'harness' in locals() else None
            )
```

## Integration with Existing Tools

### 1. Probe Tool Integration

**Current Code (probe_domain.py lines 681-830):**
- Uses manual signature parsing (BROKEN)
- Needs to be replaced with ImportBasedHarnessConstructor

**Updated Design:**
```python
class ProbeOrchestrator:
    """Orchestrate theorem probing."""
    
    def __init__(
        self,
        harness_constructor: HarnessConstructor,
        server_manager: ServerManager
    ):
        self.harness_constructor = harness_constructor
        self.server_manager = server_manager
    
    def probe_theorem(
        self,
        theorem_id: str,
        file_path: str,
        mode: str
    ) -> ProbeResult:
        """
        Probe a theorem with automation.
        
        Args:
            theorem_id: Fully qualified theorem name
            file_path: Path to Lean file
            mode: Automation mode (aesop, grind, etc.)
        """
        # Build harness config
        config = HarnessConfig(
            theorem_id=theorem_id,
            file_path=file_path,
            proof_attempt=self._mode_to_tactic(mode),
            additional_imports=self._mode_to_imports(mode)
        )
        
        # Construct harness
        result = self.harness_constructor.construct(config)
        
        # Handle errors
        if isinstance(result, HarnessError):
            return ProbeResult(
                status="error",
                error_type=result.error_type,
                message=result.message,
                generated_code=result.generated_code
            )
        
        # Run Lean on harness
        lean_result = self.server_manager.check_file(result.code)
        
        return self._interpret_lean_result(lean_result)
```

### 2. Validator Integration

**Current Status:** Already fixed (uses import-based approach)

**No changes needed** - validator.py already implements the correct pattern.

### 3. Search Orchestrator Integration

**Current Status:** Not yet implemented

**Design:**
```python
class SearchOrchestrator:
    """Orchestrate proof search with hints."""
    
    def __init__(
        self,
        harness_constructor: HarnessConstructor,
        server_manager: ServerManager
    ):
        self.harness_constructor = harness_constructor
        self.server_manager = server_manager
    
    def search_with_hints(
        self,
        theorem_id: str,
        file_path: str,
        candidate_hints: list[str]
    ) -> SearchResult:
        """
        Search for proof using candidate hints.
        
        For each hint combination:
        1. Construct harness with hints
        2. Test if automation succeeds
        3. Track which hints work
        """
        results = []
        
        for hints in self._generate_hint_combinations(candidate_hints):
            # Build proof attempt with hints
            proof = self._build_proof_with_hints(hints)
            
            # Construct harness
            config = HarnessConfig(
                theorem_id=theorem_id,
                file_path=file_path,
                proof_attempt=proof,
                additional_imports=["import Aesop"]
            )
            
            result = self.harness_constructor.construct(config)
            
            if isinstance(result, HarnessError):
                continue  # Skip this combination
            
            # Test harness
            lean_result = self.server_manager.check_file(result.code)
            
            if lean_result.success:
                results.append(SearchAttempt(
                    hints=hints,
                    success=True,
                    proof=proof
                ))
        
        return SearchResult(attempts=results)
```

## Dependency Injection Wiring

**Composition Root:**
```python
def build_probe_orchestrator(
    server_manager: ServerManager
) -> ProbeOrchestrator:
    """
    Build ProbeOrchestrator with all dependencies.
    
    This is the composition root - all wiring happens here.
    """
    # Build querier
    querier = LeanInteractQuerier(server_manager)
    
    # Build type extractor
    type_extractor = LeanInteractTheoremTypeExtractor(querier)
    
    # Build path converter
    path_converter = StandardImportPathConverter()
    
    # Build harness constructor
    harness_constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor,
        path_converter=path_converter
    )
    
    # Build orchestrator
    return ProbeOrchestrator(
        harness_constructor=harness_constructor,
        server_manager=server_manager
    )
```

## Testing Strategy

### Unit Tests

**Test 1: ImportPathConverter**
```python
def test_import_path_conversion():
    converter = StandardImportPathConverter()
    
    # Test basic conversion
    result = converter.convert("Fixtures/Algebra/Group.lean")
    assert result.path == "Fixtures.Algebra.Group"
    
    # Test with extra prefix
    result = converter.convert("fixtures/mathlib/Fixtures/Algebra/Group.lean")
    assert result.path == "Fixtures.Algebra.Group"
    
    # Test nested directories
    result = converter.convert("Mathlib/Data/List/Basic.lean")
    assert result.path == "Mathlib.Data.List.Basic"
```

**Test 2: TheoremTypeExtractor**
```python
def test_theorem_type_extraction(mock_querier):
    extractor = LeanInteractTheoremTypeExtractor(mock_querier)
    
    # Mock querier returns Declaration
    mock_querier.extract_declarations.return_value = [
        Declaration(name="Subgroup.mem_prod", type="p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K")
    ]
    
    result = extractor.extract_type("test.lean", "Subgroup.mem_prod")
    
    assert result.type_expr == "p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K"
    assert "LeanInteract" in result.source
```

**Test 3: HarnessConstructor**
```python
def test_harness_construction():
    # Setup mocks
    type_extractor = Mock()
    type_extractor.extract_type.return_value = TheoremType(
        type_expr="p ∈ H.prod K ↔ p.1 ∈ H ∧ p.2 ∈ K",
        source="test"
    )
    
    path_converter = Mock()
    path_converter.convert.return_value = ImportPath(
        path="Fixtures.Algebra.Group"
    )
    
    constructor = ImportBasedHarnessConstructor(
        type_extractor=type_extractor,
        path_converter=path_converter
    )
    
    # Construct harness
    config = HarnessConfig(
        theorem_id="Subgroup.mem_prod",
        file_path="Fixtures/Algebra/Group.lean",
        proof_attempt="aesop"
    )
    
    result = constructor.construct(config)
    
    # Verify structure
    assert isinstance(result, HarnessSuccess)
    lines = result.code.split('\n')
    assert lines[0].startswith("import")
    assert "example :" in result.code
    assert "aesop" in result.code
```

### Integration Tests

**Test 4: End-to-End Probe**
```python
def test_probe_with_real_lean_file():
    """Test probe with actual Lean file."""
    # Use real ServerManager
    server_manager = ServerManager()
    
    # Build orchestrator
    orchestrator = build_probe_orchestrator(server_manager)
    
    # Probe a simple theorem
    result = orchestrator.probe_theorem(
        theorem_id="Subgroup.mem_prod",
        file_path="fixtures/mathlib/Fixtures/Algebra/Group/Subgroup/Basic.lean",
        mode="aesop"
    )
    
    # Should not have syntax errors
    assert result.status != "error" or "syntax" not in result.message.lower()
    
    # Should have attempted proof (may succeed or fail)
    assert result.status in ["success", "not_closed", "timeout"]
```

## Correctness Properties

### Property 1: Import-First Invariant
**Property:** ALL generated harnesses have imports on line 1

**Test:**
```python
@given(st.text(), st.text(), st.text())
def test_imports_always_first(theorem_id, file_path, proof):
    """Property: Imports are always on line 1."""
    config = HarnessConfig(
        theorem_id=theorem_id,
        file_path=file_path,
        proof_attempt=proof
    )
    
    result = constructor.construct(config)
    
    if isinstance(result, HarnessSuccess):
        lines = result.code.split('\n')
        first_line = next((line for line in lines if line.strip()), "")
        assert first_line.startswith("import")
```

### Property 2: No Signature Reconstruction
**Property:** Generated code NEVER manually reconstructs theorem signatures

**Test:**
```python
def test_no_manual_signature_reconstruction():
    """Property: No manual signature reconstruction."""
    result = constructor.construct(config)
    
    if isinstance(result, HarnessSuccess):
        # Should use "example :", not "theorem <name>"
        assert "example :" in result.code
        assert f"theorem {config.theorem_id}" not in result.code
```

### Property 3: Type Preservation
**Property:** Theorem type in harness matches type from LeanInteract

**Test:**
```python
def test_type_preservation():
    """Property: Type is preserved exactly."""
    # Extract type via LeanInteract
    original_type = querier.extract_declarations(file_path)[0].type
    
    # Construct harness
    result = constructor.construct(config)
    
    # Type should appear in harness
    assert original_type in result.code
```

## Migration Plan

### Phase 1: Complete Removal of Legacy Code (CRITICAL)
1. **OBLITERATE** all manual parsing code from probe_domain.py
2. **OBLITERATE** search annotations tool completely
3. **OBLITERATE** any legacy harness construction code
4. Remove ALL references to removed code

### Phase 2: Implement New Architecture (CRITICAL)
1. Implement ImportBasedHarnessConstructor
2. Update ProbeOrchestrator to use new constructor
3. Validate with 14 theorems from bug report

### Phase 3: Implement Search Orchestrator (HIGH)
1. Implement SearchOrchestrator with ImportBasedHarnessConstructor
2. Add tests
3. Validate hint discovery works

### Phase 4: Documentation
1. Update all documentation
2. Remove references to removed tools
3. Document new architecture

## Success Metrics

- **Harness compilation rate:** 100% (currently 0%)
- **Syntax error rate:** 0% (currently 100%)
- **Test coverage:** >90% for new components
- **Property test coverage:** All 3 correctness properties

---

**Status:** DRAFT  
**Created:** 2026-01-31  
**Dependencies:** LeanInteract, ServerManager  
**Blocks:** All proof automation features
