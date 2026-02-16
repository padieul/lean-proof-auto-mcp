# Design Document

## Overview

This design refactors all MCP tool composition roots to eliminate dependency injection violations, add performance optimizations through caching, and establish proper architectural boundaries following hexagonal architecture principles. The refactoring addresses five critical issues identified in the code review:

1. **FIX #3**: Nested ServerManager creation in probe tool
2. **FIX #4**: Server reuse issues in probe_file tool
3. **FIX #5**: Missing caching in ImportBasedHarnessConstructor
4. **FIX #7**: try_automated_proof not following Command/Handler pattern
5. **FIX #8**: SearchOrchestrator using wrong abstraction (LeanRunner instead of ProofValidator)

The design follows the code conventions established in the codebase, applying hexagonal architecture, dependency injection, Command/Handler pattern, and Result/Either pattern throughout.

## Architecture

### Current Architecture Problems

The current implementation violates dependency injection principles in several ways:

1. **probe.py**: ProbeCommandHandler creates its own ServerManager and HarnessConstructor internally, bypassing the composition root
2. **probe_file.py**: Creates N ServerManager instances for N theorems, causing massive performance degradation
3. **try_automated_proof.py**: Uses procedural style instead of Command/Handler pattern, performs monkey-patching
4. **search_orchestrator.py**: Depends on LeanRunner (wrong abstraction) instead of ProofValidator port

### Target Architecture

The refactored architecture establishes clean boundaries:

```
┌─────────────────────────────────────────────────────────────┐
│                    Tool Layer (tools/)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Composition Roots (ONE per tool)                     │  │
│  │  - Create ALL dependencies                            │  │
│  │  - Wire dependencies together                         │  │
│  │  - Pass to handlers                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Domain Layer (core/)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Command Handlers                                     │  │
│  │  - Receive dependencies via constructor               │  │
│  │  - Orchestrate operations                             │  │
│  │  - NO infrastructure creation                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Adapter Layer (lean/)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Port Implementations                                 │  │
│  │  - LeanInteractServerManager                          │  │
│  │  - LeanInteractQuerier                                │  │
│  │  - LeanInteractProofValidator                         │  │
│  │  - LeanInteractProofStateInspector                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Dependency Flow

All dependencies flow from composition roots to handlers:

```
Composition Root (tools/probe.py)
  ├─ LeanInteractServerManager (ONE instance)
  ├─ LeanInteractQuerier (uses same ServerManager)
  ├─ LeanInteractProofValidator (uses same ServerManager)
  ├─ ImportBasedHarnessConstructor (with caching)
  ├─ HeuristicClassifier
  ├─ SubprocessMetadataCollector
  └─ ProbeCommandHandler (receives ALL above)
```

## Components and Interfaces

### Modified Components

#### 1. ProbeCommandHandler (core/probe_domain.py)

**Current Issues**:
- Creates ServerManager internally in `_construct_harness()`
- Creates Querier internally
- Creates HarnessConstructor internally
- Violates dependency injection

**Refactored Design**:
```python
class ProbeCommandHandler:
    def __init__(
        self,
        validator: ProofValidator,  # Changed from lean_runner
        querier: Querier,  # NEW: injected
        workspace_provider: WorkspaceProvider,
        classifier: AutomationClassifier,
        harness_constructor: HarnessConstructor,  # Changed from Optional
        artifact_store: ArtifactStore | None = None,
        metadata_collector: MetadataCollector | None = None,
    ):
        self.validator = validator
        self.querier = querier
        self.workspace_provider = workspace_provider
        self.classifier = classifier
        self.harness_constructor = harness_constructor
        self.artifact_store = artifact_store
        self.metadata_collector = metadata_collector
```

**Key Changes**:
- `lean_runner` → `validator` (uses ProofValidator port)
- `querier` parameter added (no longer created internally)
- `harness_constructor` is required (not Optional)
- Remove `_construct_harness()` method (uses injected constructor)

#### 2. ImportBasedHarnessConstructor (core/harness_construction.py)

**Current Issues**:
- No caching of file content
- No caching of declaration extraction
- Redundant file reads and parsing for batch operations

**Refactored Design**:
```python
class ImportBasedHarnessConstructor:
    def __init__(
        self,
        type_extractor: TheoremTypeExtractor,
        path_converter: ImportPathConverter,
    ) -> None:
        self.type_extractor = type_extractor
        self.path_converter = path_converter

        # NEW: Caching infrastructure
        self._file_cache: dict[str, str] = {}
        self._decl_cache: dict[str, list[Declaration]] = {}
        self._theorem_verified: dict[str, bool] = {}

    def construct(self, config: HarnessConfig) -> HarnessResult:
        # Check caches before reading/parsing
        if config.file_path in self._file_cache:
            file_content = self._file_cache[config.file_path]
        else:
            file_content = self._read_file(config.file_path)
            self._file_cache[config.file_path] = file_content

        if config.file_path in self._decl_cache:
            declarations = self._decl_cache[config.file_path]
        else:
            declarations = self._extract_declarations(config.file_path)
            self._decl_cache[config.file_path] = declarations

        # ... rest of construction logic

    def clear_cache(self) -> None:
        """Clear all caches after batch operation."""
        self._file_cache.clear()
        self._decl_cache.clear()
        self._theorem_verified.clear()
```

**Cache Strategy**:
- File content cache: Avoid redundant disk I/O
- Declaration cache: Avoid redundant parsing
- Theorem verification cache: Avoid redundant lookups
- Manual cache clearing after batch operations

#### 3. ValidateProofCommand and Handler (NEW: core/validate_proof_domain.py)

**Purpose**: Establish Command/Handler pattern for try_automated_proof

**Design**:
```python
@dataclass(frozen=True)
class ValidateProofCommand:
    """Immutable command for proof validation."""
    file_path: str
    theorem_id: str
    proof_attempt: str
    timeout_s: float = 10.0
    return_proof_state: bool = True

class ValidateProofCommandHandler:
    """Handler for proof validation operations."""

    def __init__(
        self,
        querier: Querier,
        validator: ProofValidator,
        constructor: HarnessConstructor,
        proof_state_inspector: ProofStateInspector | None = None,
        metadata_collector: MetadataCollector | None = None,
    ):
        self.querier = querier
        self.validator = validator
        self.constructor = constructor
        self.proof_state_inspector = proof_state_inspector
        self.metadata_collector = metadata_collector

    def handle(self, cmd: ValidateProofCommand) -> ValidationResult:
        # 1. Extract theorem using querier
        declarations = self.querier.extract_declarations(cmd.file_path)
        theorem = self._find_theorem(declarations, cmd.theorem_id)

        # 2. Construct harness with proof attempt
        harness_config = HarnessConfig(
            theorem_id=cmd.theorem_id,
            file_path=cmd.file_path,
            proof_attempt=cmd.proof_attempt,
        )
        harness_result = self.constructor.construct(harness_config)

        # 3. Validate via ProofValidator port
        result = self.validator.validate_proof(
            theorem_statement=theorem.type,
            proof_attempt=harness_result.code,
            timeout_s=cmd.timeout_s,
            file_path=cmd.file_path,
            theorem_id=cmd.theorem_id,
        )

        # 4. Enrich with proof state if incomplete
        if result.status == "incomplete" and cmd.return_proof_state:
            if self.proof_state_inspector:
                proof_state = self.proof_state_inspector.get_initial_proof_state(theorem)
                result = self._enrich_with_proof_state(result, proof_state)

        return result
```

#### 4. SearchOrchestrator (core/search_orchestrator.py)

**Current Issues**:
- Depends on LeanRunner (wrong abstraction)
- `probe_fn` returns False without actually running Lean
- No integration with ProofValidator

**Refactored Design**:
```python
class SearchOrchestrator:
    def __init__(
        self,
        candidate_gen: CandidateGenerator,
        feedback_builder: FeedbackBuilder,
        validator: ProofValidator,  # Changed from lean_runner
        constructor: HarnessConstructor,  # Required, not Optional
        proof_state_inspector: ProofStateInspector | None = None,
        metadata_collector: MetadataCollector | None = None,
    ):
        self.candidate_gen = candidate_gen
        self.feedback_builder = feedback_builder
        self.validator = validator
        self.constructor = constructor
        self.proof_state_inspector = proof_state_inspector
        self.metadata_collector = metadata_collector

    def _test_hint_combination(
        self,
        file_path: str,
        theorem_id: str,
        hints: list[Candidate],
        config: SearchConfig,
    ) -> bool:
        # Build proof attempt with hints
        proof_attempt = self._build_proof_with_hints(hints, config)

        # Construct harness (uses cache)
        harness_config = HarnessConfig(
            theorem_id=theorem_id,
            file_path=file_path,
            proof_attempt=proof_attempt,
        )
        harness_result = self.constructor.construct(harness_config)

        if isinstance(harness_result, HarnessError):
            return False

        # Validate proof using ProofValidator port
        result = self.validator.validate_proof(
            theorem_statement=harness_result.theorem_statement,
            proof_attempt=harness_result.code,
            timeout_s=config.search_budget_s / config.max_search_steps,
            file_path=file_path,
            theorem_id=theorem_id,
        )

        return result.status == "success"
```

### Composition Root Patterns

#### Pattern 1: Single Tool Invocation (probe.py, verify.py)

```python
def _create_handler(file_path: str) -> ProbeCommandHandler:
    # 1. Detect project root
    project_root = _find_lean_project_root(Path(file_path))

    # 2. Create ServerManager (ONE instance)
    server_manager = LeanInteractServerManager(workspace_path=project_root)

    # 3. Create adapters (all use same ServerManager)
    querier = LeanInteractQuerier(server_manager)
    validator = LeanInteractProofValidator(server_manager)

    # 4. Create harness constructor (with caching)
    type_extractor = LeanInteractTheoremTypeExtractor(querier)
    path_converter = StandardImportPathConverter()
    constructor = ImportBasedHarnessConstructor(type_extractor, path_converter)

    # 5. Create other dependencies
    workspace_provider = create_workspace_provider(...)
    classifier = HeuristicClassifier()
    artifact_store = FilesystemArtifactStore(ARTIFACTS_DIR)
    metadata_collector = SubprocessMetadataCollector()

    # 6. Wire into handler
    return ProbeCommandHandler(
        validator=validator,
        querier=querier,
        workspace_provider=workspace_provider,
        classifier=classifier,
        harness_constructor=constructor,
        artifact_store=artifact_store,
        metadata_collector=metadata_collector,
    )
```

#### Pattern 2: Batch Operations (probe_file.py)

```python
def _create_handler(file_path: str) -> ProbeFileCommandHandler:
    # 1. Create shared infrastructure (ONE instance for ALL theorems)
    project_root = _find_lean_project_root(Path(file_path))
    server_manager = LeanInteractServerManager(workspace_path=project_root)

    # 2. Create shared adapters
    querier = LeanInteractQuerier(server_manager)
    validator = LeanInteractProofValidator(server_manager)

    # 3. Create harness constructor WITH CACHING
    type_extractor = LeanInteractTheoremTypeExtractor(querier)
    path_converter = StandardImportPathConverter()
    constructor = ImportBasedHarnessConstructor(type_extractor, path_converter)

    # 4. Create other dependencies
    workspace_provider = create_workspace_provider(...)
    classifier = HeuristicClassifier()
    artifact_store = FilesystemArtifactStore(ARTIFACTS_DIR)
    metadata_collector = SubprocessMetadataCollector()

    # 5. Create ProbeCommandHandler
    probe_handler = ProbeCommandHandler(
        validator=validator,
        querier=querier,
        workspace_provider=workspace_provider,
        classifier=classifier,
        harness_constructor=constructor,
        artifact_store=artifact_store,
        metadata_collector=metadata_collector,
    )

    # 6. Wire into ProbeFileCommandHandler
    return ProbeFileCommandHandler(
        probe_handler=probe_handler,
        scan_file_fn=scan_file,
        rank_targets_fn=rank_targets,
    )

# After batch completes:
constructor.clear_cache()
```

#### Pattern 3: Command/Handler (try_automated_proof.py)

```python
def try_automated_proof(args: dict[str, Any]) -> dict[str, Any]:
    # 1. Build command from args
    try:
        command = _build_command(args)
    except ValueError as e:
        return _build_error_response(...)

    # 2. Create handler at composition root
    try:
        handler = _create_handler(command.file_path)

        # 3. Execute command
        result = handler.handle(command)

        # 4. Format response
        return _format_response(result)
    except Exception as e:
        return _build_error_response(...)

def _build_command(args: dict[str, Any]) -> ValidateProofCommand:
    # Validate and extract arguments
    return ValidateProofCommand(
        file_path=args["file"],
        theorem_id=args["theorem_id"],
        proof_attempt=args["proof_attempt"],
        timeout_s=args.get("timeout_s", 10.0),
        return_proof_state=args.get("return_proof_state", True),
    )

def _create_handler(file_path: str) -> ValidateProofCommandHandler:
    # Create all dependencies
    project_root = _find_lean_project_root(Path(file_path))
    server_manager = LeanInteractServerManager(workspace_path=project_root)
    querier = LeanInteractQuerier(server_manager)
    validator = LeanInteractProofValidator(server_manager)
    proof_state_inspector = LeanInteractProofStateInspector(server_manager)

    type_extractor = LeanInteractTheoremTypeExtractor(querier)
    path_converter = StandardImportPathConverter()
    constructor = ImportBasedHarnessConstructor(type_extractor, path_converter)

    metadata_collector = SubprocessMetadataCollector()

    # Wire into handler
    return ValidateProofCommandHandler(
        querier=querier,
        validator=validator,
        constructor=constructor,
        proof_state_inspector=proof_state_inspector,
        metadata_collector=metadata_collector,
    )
```

## Data Models

### ValidateProofCommand

```python
@dataclass(frozen=True)
class ValidateProofCommand:
    """
    Immutable command for proof validation.

    Attributes:
        file_path: Path to Lean file containing theorem
        theorem_id: Identifier of theorem to validate
        proof_attempt: Proof code to validate
        timeout_s: Timeout in seconds (default: 10.0)
        return_proof_state: Whether to return proof state for incomplete proofs
    """
    file_path: str
    theorem_id: str
    proof_attempt: str
    timeout_s: float = 10.0
    return_proof_state: bool = True

    def __post_init__(self) -> None:
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")
        if not self.proof_attempt:
            raise ValueError("proof_attempt must be non-empty")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
```

### Cache Data Structures

```python
# In ImportBasedHarnessConstructor
_file_cache: dict[str, str]  # file_path -> file_content
_decl_cache: dict[str, list[Declaration]]  # file_path -> declarations
_theorem_verified: dict[str, bool]  # theorem_id -> exists
```

## Correctness Properties


*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Dependency Injection Properties

Property 1: Single ServerManager per tool invocation
*For any* tool invocation, exactly one ServerManager instance should be created at the composition root, and this same instance should be reused for all operations within that invocation
**Validates: Requirements 1.1, 1.2**

Property 2: No infrastructure creation in handlers
*For any* command handler class (ProbeCommandHandler, ValidateProofCommandHandler, SearchOrchestrator), the handler code should not contain instantiation of ServerManager, Querier, or HarnessConstructor
**Validates: Requirements 1.3, 2.2, 2.3, 9.1, 9.2, 9.3**

Property 3: Constructor injection for all dependencies
*For any* command handler, all dependencies (ServerManager, Querier, ProofValidator, HarnessConstructor) should be received as constructor parameters, not created internally
**Validates: Requirements 2.1, 9.6**

Property 4: Injected constructor usage
*For any* harness construction operation in ProbeCommandHandler, the injected HarnessConstructor instance should be used, not a newly created one
**Validates: Requirements 2.4**

### Caching Properties

Property 5: File content caching
*For any* file path, when HarnessConstructor.construct() is called multiple times with the same file_path, the file should be read from disk exactly once, with subsequent calls using cached content
**Validates: Requirements 3.1, 3.4**

Property 6: Declaration extraction caching
*For any* file path, when HarnessConstructor.construct() is called multiple times with the same file_path, declaration extraction should occur exactly once, with subsequent calls using cached results
**Validates: Requirements 3.2, 3.4**

Property 7: Theorem verification caching
*For any* theorem_id, when HarnessConstructor checks theorem existence multiple times, the verification should occur exactly once, with subsequent checks using cached results
**Validates: Requirements 3.3, 3.4**

Property 8: Batch operation caching
*For any* batch operation processing N theorems from the same file, file reading should occur exactly once, and declaration extraction should occur exactly once
**Validates: Requirements 6.4, 8.1, 8.2**

Property 9: Cache clearing
*For any* HarnessConstructor instance, calling clear_cache() should empty all cache dictionaries (_file_cache, _decl_cache, _theorem_verified)
**Validates: Requirements 3.5, 6.5**

### Command/Handler Pattern Properties

Property 10: ValidateProofCommand immutability
*For any* ValidateProofCommand instance, attempting to modify any field after construction should raise an error (frozen dataclass)
**Validates: Requirements 4.1**

Property 11: try_automated_proof workflow
*For any* valid arguments to try_automated_proof, the function should build a ValidateProofCommand, create a ValidateProofCommandHandler, and call handler.handle(command)
**Validates: Requirements 4.3, 4.4, 4.5**

Property 12: No monkey-patching
*For any* code in the refactored modules, there should be no attribute assignment to server objects (pattern: server.attribute = value)
**Validates: Requirements 4.7, 9.4**

### ProofValidator Integration Properties

Property 13: SearchOrchestrator uses ProofValidator
*For any* SearchOrchestrator instance, the validator attribute should be of type ProofValidator, and there should be no references to LeanInteractRunner in the class
**Validates: Requirements 5.1, 5.2**

Property 14: probe_fn uses validator
*For any* hint combination tested by SearchOrchestrator._test_hint_combination(), the method should call validator.validate_proof() to test the proof
**Validates: Requirements 5.3**

Property 15: probe_fn uses injected constructor
*For any* hint combination tested by SearchOrchestrator._test_hint_combination(), the method should call the injected constructor.construct() to build the harness
**Validates: Requirements 5.4**

Property 16: probe_fn result mapping
*For any* ValidationResult returned by validator.validate_proof(), the status should be correctly mapped: "success" → True, "incomplete" → False, "error" → False, "timeout" → False
**Validates: Requirements 5.6**

### Shared Dependencies Properties

Property 17: Single ServerManager in batch operations
*For any* probe_file invocation processing N theorems, exactly one ServerManager instance should be created, and the same instance should be used for all N theorem validations
**Validates: Requirements 6.1, 6.3, 8.3**

Property 18: Single HarnessConstructor in batch operations
*For any* probe_file invocation processing N theorems, exactly one HarnessConstructor instance should be created, and the same instance should be used for all N harness constructions
**Validates: Requirements 6.2**

### Adapter Layer Properties

Property 19: Correct adapter types
*For any* composition root, ServerManager instances should be LeanInteractServerManager, Querier instances should be LeanInteractQuerier, ProofValidator instances should be LeanInteractProofValidator, and ProofStateInspector instances should be LeanInteractProofStateInspector
**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

Property 20: No deprecated adapter references
*For any* tool composition root, there should be no references to LeanInteractRunner or ServerManagerImpl
**Validates: Requirements 7.5, 7.6**

### Architectural Boundary Properties

Property 21: Domain components receive ports only
*For any* domain component (command handler), constructor parameters should be port types (Protocol), not concrete adapter implementations
**Validates: Requirements 9.5**

Property 22: API compatibility
*For any* MCP tool function (probe, probe_file, try_automated_proof, verify, search_automated_proof), the function signature should remain unchanged from the previous implementation
**Validates: Requirements 10.4**

## Error Handling

### Error Categories

1. **Validation Errors**: Invalid command parameters
   - Return error response with validation_error code
   - Do not proceed with execution

2. **Infrastructure Errors**: ServerManager creation failures
   - Return error response with infrastructure_error code
   - Log detailed error information

3. **Construction Errors**: HarnessConstructor failures
   - Return HarnessError result
   - Include error type and message

4. **Execution Errors**: Lean verification failures
   - Return error response with execution_error code
   - Include diagnostics and suggestions

### Error Handling Strategy

All composition roots follow the same error handling pattern:

```python
def tool_function(args: dict[str, Any]) -> dict[str, Any]:
    # 1. Validate and build command
    try:
        command = _build_command(args)
    except ValueError as e:
        return _build_error_response(
            error_message=str(e),
            error_code="validation_error",
        )

    # 2. Create handler and execute
    try:
        handler = _create_handler(command.file_path)
        result = handler.handle(command)
        return _format_response(result)
    except Exception as e:
        logger.exception(f"Tool execution failed")
        return _build_error_response(
            error_message=str(e),
            error_code="execution_error",
        )
```

### Resource Cleanup

All tools ensure proper resource cleanup:

1. **ServerManager**: Automatically managed by LRU cache with MAX_SERVERS limit
2. **Workspace**: Cleaned up in finally block
3. **Harness files**: Deleted after verification
4. **Caches**: Cleared after batch operations

## Testing Strategy

### Unit Testing

Unit tests focus on specific components and edge cases:

1. **Command Validation**:
   - Test ValidateProofCommand with invalid parameters
   - Test ProbeCommand with missing fields
   - Test boundary values (timeout_s = 0, negative values)

2. **Cache Behavior**:
   - Test cache hit/miss scenarios
   - Test cache clearing
   - Test cache isolation between instances

3. **Error Handling**:
   - Test validation errors
   - Test infrastructure errors
   - Test construction errors

4. **Composition Roots**:
   - Test _create_handler() creates correct types
   - Test _build_command() validates inputs
   - Test error response formatting

### Property-Based Testing

Property tests verify universal correctness properties across all inputs:

1. **Dependency Injection Properties** (Properties 1-4):
   - Generate random tool invocations
   - Verify single ServerManager creation
   - Verify no infrastructure in handlers
   - Verify constructor injection

2. **Caching Properties** (Properties 5-9):
   - Generate random file paths and theorem IDs
   - Verify file reads happen exactly once
   - Verify declaration extraction happens exactly once
   - Verify cache clearing empties all caches

3. **Command/Handler Properties** (Properties 10-12):
   - Generate random command parameters
   - Verify immutability
   - Verify workflow execution
   - Verify no monkey-patching

4. **ProofValidator Properties** (Properties 13-16):
   - Generate random hint combinations
   - Verify validator usage
   - Verify constructor usage
   - Verify result mapping

5. **Shared Dependencies Properties** (Properties 17-18):
   - Generate random theorem lists
   - Verify single instance creation
   - Verify instance reuse

6. **Adapter Layer Properties** (Properties 19-20):
   - Verify correct adapter types
   - Verify no deprecated references

7. **Architectural Properties** (Properties 21-22):
   - Verify port types in constructors
   - Verify API compatibility

### Property Test Configuration

Each property test should:
- Run minimum 100 iterations
- Use fast-check (TypeScript) or Hypothesis (Python) for generation
- Tag with feature name and property number
- Reference design document property

Example tag format:
```python
# Feature: tool-composition-roots, Property 1: Single ServerManager per tool invocation
```

### Integration Testing

Integration tests verify end-to-end workflows:

1. **Single Tool Invocation**:
   - Call probe with valid arguments
   - Verify result structure
   - Verify no resource leaks

2. **Batch Operations**:
   - Call probe_file with multiple theorems
   - Verify performance improvement
   - Verify cache usage

3. **Command/Handler Workflow**:
   - Call try_automated_proof with valid proof
   - Verify ValidationResult structure
   - Verify metadata collection

4. **Search Orchestration**:
   - Call search_automated_proof with candidates
   - Verify hint testing
   - Verify feedback generation

### Test Coverage Goals

- Unit tests: 90% line coverage for modified files
- Property tests: All 22 properties implemented
- Integration tests: All 4 workflows covered
- Backward compatibility: All existing tests pass
