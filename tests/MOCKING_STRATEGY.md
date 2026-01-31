# Test Mocking Strategy

This document describes the mocking strategy for the lean-proof-auto-mcp test suite after migration to LeanInteract-based architecture.

## Overview

The system follows hexagonal architecture with three layers:
1. **MCP Tool Layer**: LLM-facing interface
2. **Core Domain Layer**: Business logic
3. **LeanInteract Adapter Layer**: All Lean interaction

The mocking strategy respects these boundaries and mocks at the appropriate layer for each test type.

## Mocking Principles

### 1. Mock at the Adapter Layer Interfaces

**Rule**: Tests should mock the LeanInteract Adapter Layer interfaces (ports), NOT the Lean CLI or LeanInteract library directly.

**Rationale**: 
- The Core Domain Layer depends on abstract interfaces (protocols), not concrete implementations
- Mocking at the interface level tests the business logic in isolation
- This approach is independent of the underlying Lean interaction mechanism

**Example**:
```python
from lean_proof_auto_mcp.lean.ports import LeanInteractQuerier, Declaration

class MockLeanInteractQuerier:
    """Mock implementation of LeanInteractQuerier port."""
    
    def __init__(self, declarations: list[Declaration]):
        self.declarations = declarations
    
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        return self.declarations
    
    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        return []
```

### 2. No Direct Lean CLI Mocking

**Rule**: Tests should NOT mock subprocess calls to `lean` or `lake` commands.

**Rationale**:
- The system no longer uses direct Lean CLI calls
- All Lean interaction goes through LeanInteract
- Mocking subprocess calls would test the wrong abstraction

**Before (OLD - DO NOT USE)**:
```python
@patch('subprocess.run')
def test_old_approach(mock_run):
    # DON'T DO THIS - we don't use subprocess for Lean anymore
    mock_run.return_value = MagicMock(stdout="theorem found")
```

**After (NEW - CORRECT)**:
```python
def test_new_approach():
    # Mock the adapter layer interface instead
    mock_querier = MockLeanInteractQuerier(declarations=[...])
    generator = CandidateGenerator(source, index, mock_querier)
```

### 3. Integration Tests Use Real LeanInteract

**Rule**: Integration tests should use real LeanInteract, not mocks.

**Rationale**:
- Integration tests verify the complete workflow including Lean interaction
- Mocking LeanInteract in integration tests defeats their purpose
- Use `@pytest.mark.integration` to mark these tests

**Example**:
```python
@pytest.mark.integration
def test_with_real_leaninteract():
    # No mocks - uses real LeanInteract
    querier = LeanInteractQuerierImpl(server_manager=server_manager)
    result = querier.extract_declarations("test.lean")
    assert len(result) > 0
```

## Mocking Strategy by Test Type

### Unit Tests (Core Domain Layer)

**What to mock**: LeanInteract Adapter Layer interfaces (ports)

**Example**:
```python
# tests/unit/core/test_candidate_generator.py

from lean_proof_auto_mcp.lean.ports import LeanInteractQuerier, Declaration

class MockLeanInteractQuerier:
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        return [
            Declaration(
                name="test_theorem",
                full_name="Test.test_theorem",
                type="True",
                value=None,
                attributes=[],
                range=Range(start_line=1, start_col=0, end_line=1, end_col=0),
                namespace="Test",
            )
        ]

def test_candidate_generation():
    mock_querier = MockLeanInteractQuerier()
    generator = CandidateGenerator(source, index, mock_querier)
    candidates = generator.generate(theorem_decl, sources, config)
    assert len(candidates) > 0
```

### Unit Tests (Adapter Layer)

**What to mock**: LeanInteract library responses

**Example**:
```python
# tests/unit/lean/test_querier.py

from unittest.mock import MagicMock, patch

@patch('lean_proof_auto_mcp.lean.querier.LeanInteractServer')
def test_querier_extract_declarations(mock_server_class):
    mock_server = MagicMock()
    mock_server.run_command.return_value = {
        'declarations': [
            {
                'name': 'test_theorem',
                'type': 'True',
                # ... other fields
            }
        ]
    }
    mock_server_class.return_value = mock_server
    
    querier = LeanInteractQuerierImpl(server_manager=server_manager)
    result = querier.extract_declarations("test.lean")
    assert len(result) == 1
```

### Property-Based Tests

**What to mock**: LeanInteract Adapter Layer interfaces (ports)

**Example**:
```python
# tests/property/test_candidate_source_extraction_properties.py

from hypothesis import given, settings
import hypothesis.strategies as st

@given(config=valid_candidate_config())
@settings(max_examples=100)
def test_property_candidate_extraction(config):
    # Mock the adapter layer
    mock_querier = MockLeanInteractQuerier(
        declarations=[...],
        proof_references={...}
    )
    
    generator = CandidateGenerator(source, index, mock_querier)
    candidates = generator.generate(theorem_decl, config.sources, config)
    
    # Verify property holds
    assert len(candidates) <= config.max_candidates_per_source
```

### Integration Tests

**What to mock**: Nothing (use real implementations)

**Example**:
```python
# tests/integration/test_adapter_layer_integration.py

@pytest.mark.integration
def test_real_leaninteract_extraction():
    # No mocks - uses real LeanInteract
    server_manager = ServerManagerImpl(workspace_path=project_root)
    querier = LeanInteractQuerierImpl(server_manager=server_manager)
    
    result = querier.extract_declarations("test.lean")
    assert len(result) > 0
    assert all(isinstance(d, Declaration) for d in result)
```

### MCP Tool Tests

**What to mock**: SearchOrchestrator and other Core Domain components

**Example**:
```python
# tests/unit/tools/test_search_automated_proof.py

from unittest.mock import MagicMock, patch

@patch('lean_proof_auto_mcp.tools.search_automated_proof._create_orchestrator')
def test_search_automated_proof_tool(mock_create_orchestrator):
    # Mock the orchestrator (Core Domain Layer)
    mock_orchestrator = MagicMock()
    mock_orchestrator.search.return_value = SearchResultEnhanced(...)
    mock_create_orchestrator.return_value = mock_orchestrator
    
    result = search_automated_proof({
        "file": "test.lean",
        "theorem_id": "test_theorem",
    })
    
    assert result["status"] == "success"
```

## Mock Implementation Guidelines

### 1. Use Dataclasses for Mock Data

**Rule**: Use the actual dataclasses from the codebase for mock data.

**Example**:
```python
from lean_proof_auto_mcp.lean.ports import Declaration, Range

mock_declaration = Declaration(
    name="test_theorem",
    full_name="Test.test_theorem",
    type="True",
    value=None,
    attributes=[],
    range=Range(start_line=1, start_col=0, end_line=1, end_col=0),
    namespace="Test",
)
```

### 2. Create Reusable Mock Classes

**Rule**: Create reusable mock classes for common interfaces.

**Example**:
```python
# tests/fixtures/mocks.py

class MockLeanInteractQuerier:
    """Reusable mock for LeanInteractQuerier port."""
    
    def __init__(self, declarations: list[Declaration], proof_references: dict[str, list[str]]):
        self.declarations = declarations
        self.proof_references = proof_references
    
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        return self.declarations
    
    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        return self.proof_references.get(theorem_id, [])
    
    def get_theorem_context(self, file_path: str, theorem_id: str):
        raise NotImplementedError("Not needed for most tests")
```

### 3. Mock Only What You Need

**Rule**: Don't implement methods that aren't used in the test.

**Example**:
```python
class MinimalMockQuerier:
    """Minimal mock that only implements what's needed."""
    
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        return []
    
    # Don't implement get_proof_references if not needed
```

## Migration Checklist

When updating tests to the new mocking strategy:

- [ ] Remove all `@patch('subprocess.run')` decorators
- [ ] Remove all mocks of `lean` or `lake` CLI commands
- [ ] Replace with mocks of LeanInteract Adapter Layer interfaces
- [ ] Use actual dataclasses (Declaration, DeclValue, etc.) for mock data
- [ ] Ensure integration tests use real LeanInteract (no mocks)
- [ ] Update test assertions to match new data structures
- [ ] Verify tests still cover the same functionality

## Common Patterns

### Pattern 1: Mocking CandidateGenerator Dependencies

```python
def test_candidate_generation():
    # Create mock querier
    mock_querier = MockLeanInteractQuerier(
        declarations=[
            Declaration(name="helper", full_name="Test.helper", ...)
        ],
        proof_references={"test_theorem": ["Test.helper"]}
    )
    
    # Create generator with mock
    generator = CandidateGenerator(source, index, mock_querier, proof_state_inspector=None)
    
    # Test
    candidates = generator.generate(theorem_decl, sources, config)
    assert len(candidates) > 0
```

### Pattern 2: Mocking SearchOrchestrator

```python
@patch('module._create_orchestrator')
def test_search_tool(mock_create_orchestrator):
    # Create mock orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator.search.return_value = SearchResultEnhanced(
        outcome="closed",
        best_hint_set=[...],
        ...
    )
    mock_create_orchestrator.return_value = mock_orchestrator
    
    # Test
    result = search_automated_proof({"file": "test.lean", ...})
    assert result["outcome"] == "closed"
```

### Pattern 3: Integration Test (No Mocks)

```python
@pytest.mark.integration
def test_end_to_end_workflow():
    # No mocks - use real implementations
    server_manager = ServerManagerImpl(workspace_path=project_root)
    querier = LeanInteractQuerierImpl(server_manager=server_manager)
    validator = ProofValidatorImpl(server=server_manager.get_server("test.lean"))
    
    # Test complete workflow
    declarations = querier.extract_declarations("test.lean")
    assert len(declarations) > 0
```

## Requirements Validation

This mocking strategy satisfies:

- **Requirement 25.5**: Mock LeanInteract Adapter Layer interfaces instead of Lean CLI
- **Requirement 9.2**: Core Domain Layer depends only on abstractions
- **Requirement 27.1**: Unit tests for all Core Domain Layer components
- **Requirement 27.2**: Integration tests for LeanInteract Adapter Layer components
- **Requirement 28.1**: All Lean interaction through LeanInteract (no CLI mocking)

## References

- Hexagonal Architecture: See `design.md` for layer responsibilities
- Port Interfaces: See `src/lean_proof_auto_mcp/lean/ports.py`
- Mock Examples: See `tests/property/test_candidate_source_extraction_properties.py`
- Integration Tests: See `tests/integration/test_adapter_layer_integration.py`
