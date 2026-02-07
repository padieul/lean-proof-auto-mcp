# Design Document: Adapter Layer Refactor

## Overview

This design specifies the refactoring of the adapter layer to establish a unified, maintainable architecture following hexagonal architecture principles. The refactor addresses four key areas:

1. **Naming Convention Standardization**: Protocols become technology-agnostic (no `LeanInteract` prefix), while implementations carry `LeanInteract` prefix without `Impl` suffix
2. **LRU Server Management**: ServerManager uses OrderedDict with configurable MAX_SERVERS and LRU eviction to bound memory usage
3. **Functionality Consolidation**: LeanInteractRunner is absorbed into ProofValidator, eliminating redundant verification logic
4. **Thread Safety**: All `os.chdir()` calls are eliminated to prevent race conditions

The refactor maintains backward compatibility for all public APIs while improving internal consistency and testability.

## Architecture

### Hexagonal Architecture Principles

The adapter layer follows hexagonal architecture where:

- **Core Domain Layer** depends on abstract protocols (ports) defined in `lean/ports.py`
- **Adapter Layer** provides concrete implementations that depend inward toward protocols
- **Protocols** are technology-agnostic and describe capabilities, not implementations
- **Adapters** are technology-specific (LeanInteract) and handle external interaction

```
┌─────────────────────────────────────────────────────────┐
│                    Core Domain Layer                     │
│                                                          │
│  Depends on: Querier, ProofValidator,                   │
│              ProofStateInspector, ServerManager          │
└──────────────────────┬──────────────────────────────────┘
                       │ (depends on protocols)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Protocol Layer (Ports)                 │
│                                                          │
│  • Querier                                              │
│  • ProofValidator (with verify_file)                    │
│  • ProofStateInspector                                  │
│  • ServerManager                                        │
└──────────────────────┬──────────────────────────────────┘
                       │ (implemented by adapters)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    Adapter Layer                         │
│                                                          │
│  • LeanInteractQuerier                                  │
│  • LeanInteractProofValidator (with verify_file)        │
│  • LeanInteractProofStateInspector                      │
│  • LeanInteractServerManager (with LRU eviction)        │
└─────────────────────────────────────────────────────────┘
```

### Dependency Injection Pattern

All adapters receive ServerManager via constructor injection:

```python
# Composition root (in tools)
server_manager = LeanInteractServerManager(workspace_path=project_root)
querier = LeanInteractQuerier(server_manager)
validator = LeanInteractProofValidator(server_manager)
inspector = LeanInteractProofStateInspector(server_manager)
```

This makes dependencies explicit, enables testing with mock ServerManager, and prevents hidden coupling.

### Naming Convention

**Protocols (Technology-Agnostic)**:
- `Querier` - extracts declarations and references
- `ProofValidator` - validates proofs and verifies files
- `ProofStateInspector` - inspects proof states and applies tactics
- `ServerManager` - manages server lifecycle

**Adapters (Technology-Specific)**:
- `LeanInteractQuerier` - implements Querier using LeanInteract
- `LeanInteractProofValidator` - implements ProofValidator using LeanInteract
- `LeanInteractProofStateInspector` - implements ProofStateInspector using LeanInteract
- `LeanInteractServerManager` - implements ServerManager using LeanInteract

## Components and Interfaces

### 1. Protocol Layer (lean/ports.py)

#### Querier Protocol

```python
class Querier(Protocol):
    """Port for extracting declarations and references from Lean files."""
    
    @property
    def server_manager(self) -> "ServerManager":
        """Get the server manager instance."""
        ...
    
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        """Extract all declarations from a file."""
        ...
    
    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        """Extract lemma references from a proof."""
        ...
    
    def get_theorem_context(self, file_path: str, theorem_id: str) -> TheoremContext:
        """Get full context for a theorem."""
        ...
```

**Changes**: Renamed from `LeanInteractQuerier` to `Querier`

#### ProofValidator Protocol

```python
class ProofValidator(Protocol):
    """Port for validating proof attempts and verifying files."""
    
    def validate_proof(
        self,
        theorem_statement: str,
        proof_attempt: str,
        timeout_s: float = 10.0,
        file_path: str | None = None,
        theorem_id: str | None = None,
    ) -> ValidationResult:
        """Validate a proof attempt using Command."""
        ...
    
    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """Run Lean verification on file or theorem."""
        ...
```

**Changes**: 
- Renamed from `ProofValidator` (no change needed)
- Added `verify_file()` method signature (absorbed from LeanInteractRunner)

#### ProofStateInspector Protocol

```python
class ProofStateInspector(Protocol):
    """Port for inspecting proof states and applying tactics."""
    
    def get_initial_proof_state(self, theorem: Declaration) -> ProofState:
        """Get initial proof state using Command with sorry."""
        ...
    
    def apply_tactic(self, proof_state_id: int, tactic: str) -> TacticResult:
        """Apply a tactic using ProofStep."""
        ...
```

**Changes**: No changes to protocol (already technology-agnostic)

#### ServerManager Protocol

```python
class ServerManager(Protocol):
    """Port for managing LeanInteract server lifecycle."""
    
    def get_server(self, file_path: str) -> "LeanServer":
        """Get or create server instance for file."""
        ...
    
    def restart_server(self, file_path: str) -> None:
        """Restart crashed server."""
        ...
    
    def shutdown_all(self) -> None:
        """Shutdown all server instances."""
        ...
```

**Changes**: No changes to protocol (already technology-agnostic)

### 2. Adapter Layer

#### LeanInteractQuerier (lean/querier.py)

```python
class LeanInteractQuerier:
    """Concrete implementation of Querier using LeanInteract library."""
    
    def __init__(self, server_manager: ServerManager):
        """Initialize with ServerManager via dependency injection."""
        self._server_manager = server_manager
    
    @property
    def server_manager(self) -> ServerManager:
        """Get the server manager instance."""
        return self._server_manager
    
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        """Extract declarations using FileCommand(declarations=True)."""
        server = self._server_manager.get_server(file_path)
        # ... implementation ...
    
    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        """Extract references using value.constants."""
        # ... implementation ...
    
    def get_theorem_context(self, file_path: str, theorem_id: str) -> TheoremContext:
        """Get theorem context including scope and hypotheses."""
        # ... implementation ...
```

**Changes**:
- Renamed from `LeanInteractQuerierImpl` to `LeanInteractQuerier`
- Constructor accepts `ServerManager` protocol (not concrete `ServerManagerImpl`)
- Property `server_manager` returns protocol type

#### LeanInteractProofValidator (lean/validator.py)

```python
class LeanInteractProofValidator:
    """Concrete implementation of ProofValidator using LeanInteract library."""
    
    def __init__(self, server_manager: ServerManager):
        """Initialize with ServerManager via dependency injection."""
        self._server_manager = server_manager
    
    def validate_proof(
        self,
        theorem_statement: str,
        proof_attempt: str,
        timeout_s: float = 10.0,
        file_path: str | None = None,
        theorem_id: str | None = None,
    ) -> ValidationResult:
        """Validate proof using Command."""
        server = self._server_manager.get_server(file_path or "default")
        # ... implementation ...
    
    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """
        Run Lean verification on file or theorem.
        
        This method absorbs functionality from LeanInteractRunner.verify_file().
        """
        server = self._server_manager.get_server(file_path)
        
        try:
            from lean_interact.interface import FileCommand
            
            command = FileCommand(path=file_path)
            response = server.run(command, timeout=budget_s)
            
            # Parse response into LeanRunResult
            diagnostics = self._parse_diagnostics(response)
            status = self._determine_status(diagnostics)
            
            return LeanRunResult(
                status=status,
                diagnostics=diagnostics,
                scope_used="file" if theorem_id is None else "theorem",
                full_logs="",
                timing={"verification_s": 0.0},
                exit_code=0 if status == "success" else 1,
            )
        except TimeoutError as e:
            raise TimeoutError(f"Verification timed out after {budget_s}s") from e
        except Exception as e:
            raise RuntimeError(f"Lean verification failed: {e}") from e
    
    def _parse_diagnostics(self, response: object) -> list[dict]:
        """Parse diagnostics from LeanInteract response."""
        # ... implementation from LeanInteractRunner ...
    
    def _determine_status(self, diagnostics: list[dict]) -> str:
        """Determine verification status from diagnostics."""
        # ... implementation from LeanInteractRunner ...
```

**Changes**:
- Renamed from `ProofValidatorImpl` to `LeanInteractProofValidator`
- Constructor accepts `ServerManager` protocol instead of raw `LeanServer`
- Added `verify_file()` method with logic from `LeanInteractRunner.verify_file()`
- Added helper methods `_parse_diagnostics()` and `_determine_status()` from LeanInteractRunner

#### LeanInteractProofStateInspector (lean/proof_state.py)

```python
class LeanInteractProofStateInspector:
    """Concrete implementation of ProofStateInspector using LeanInteract library."""
    
    def __init__(self, server_manager: ServerManager):
        """Initialize with ServerManager via dependency injection."""
        self._server_manager = server_manager
    
    def get_initial_proof_state(self, theorem: Declaration) -> ProofState:
        """Get initial proof state using Command with sorry."""
        # Use default server or theorem-specific server
        server = self._server_manager.get_server("default")
        # ... implementation ...
    
    def apply_tactic(self, proof_state_id: int, tactic: str) -> TacticResult:
        """Apply tactic using ProofStep."""
        server = self._server_manager.get_server("default")
        # ... implementation ...
```

**Changes**:
- Renamed from `ProofStateInspectorImpl` to `LeanInteractProofStateInspector`
- Constructor accepts `ServerManager` protocol instead of raw `LeanServer`
- Uses `server_manager.get_server()` to obtain server instances

#### LeanInteractServerManager (lean/server_manager.py)

```python
from collections import OrderedDict
import os
from pathlib import Path
from typing import Any

MAX_SERVERS = int(os.environ.get("LEAN_MAX_SERVERS", "3"))

class LeanInteractServerManager:
    """
    Concrete implementation of ServerManager with LRU eviction.
    
    Maintains up to MAX_SERVERS server instances using LRU eviction policy.
    When cache is full, evicts least recently used server before adding new one.
    """
    
    def __init__(self, workspace_path: Path | None = None):
        """Initialize ServerManager with optional workspace path."""
        self.workspace_path = workspace_path
        self._servers: OrderedDict[str, Any] = OrderedDict()
        self._request_log: list[tuple[str, str, object]] = []
    
    def get_server(self, file_path: str) -> Any:
        """
        Get or create server instance for file with LRU tracking.
        
        If server exists and is alive, moves it to end (most recently used).
        If cache is at MAX_SERVERS capacity, evicts oldest server before adding new one.
        """
        # Check if server exists and is alive
        if file_path in self._servers:
            server = self._servers[file_path]
            if self._is_server_alive(server):
                # Move to end (mark as most recently used)
                self._servers.move_to_end(file_path)
                return server
            else:
                # Server is dead, remove it
                self._shutdown_server(server)
                del self._servers[file_path]
        
        # Check if we need to evict (LRU)
        if len(self._servers) >= MAX_SERVERS:
            # Evict least recently used (first item)
            oldest_file, oldest_server = self._servers.popitem(last=False)
            self._shutdown_server(oldest_server)
            logger.info(f"Evicted LRU server for {oldest_file}")
        
        # Create new server
        server = self._create_server(file_path)
        self._servers[file_path] = server
        return server
    
    def restart_server(self, file_path: str) -> None:
        """Restart crashed server."""
        if file_path in self._servers:
            server = self._servers[file_path]
            self._shutdown_server(server)
            del self._servers[file_path]
        
        server = self._create_server(file_path)
        self._servers[file_path] = server
    
    def shutdown_all(self) -> None:
        """Shutdown all server instances."""
        for _file_path, server in list(self._servers.items()):
            self._shutdown_server(server)
        self._servers.clear()
    
    def _is_server_alive(self, server: Any) -> bool:
        """
        Check if a server is alive.
        
        Returns True if server has required methods and is responsive.
        """
        try:
            return hasattr(server, "run") and hasattr(server, "kill")
        except Exception:
            return False
    
    def _shutdown_server(self, server: Any) -> None:
        """
        Gracefully shutdown a server.
        
        Calls server.kill() if available, logs errors without raising.
        """
        try:
            if hasattr(server, "kill"):
                server.kill()
        except Exception as e:
            logger.warning(f"Failed to kill server: {e}")
    
    def _create_server(self, file_path: str) -> Any:
        """
        Create a new LeanServer for the given file.
        
        Uses workspace_path if provided, passes it explicitly to LocalProject
        via path parameter (no os.chdir()).
        """
        try:
            workspace = self.workspace_path or Path(file_path).parent
            
            # Check for lakefile
            lakefile_path = workspace / "lakefile.toml"
            lakefile_lean_path = workspace / "lakefile.lean"
            
            if lakefile_path.exists() or lakefile_lean_path.exists():
                # Use LocalProject with explicit path (no os.chdir)
                project = LocalProject(path=str(workspace), auto_build=False)
                config = LeanREPLConfig(project=project)
                server = LeanServer(config)
                return server
            
            # Standalone mode
            config = LeanREPLConfig()
            server = LeanServer(config)
            return server
            
        except Exception as e:
            raise RuntimeError(f"Failed to create server for {file_path}: {e}") from e
```

**Changes**:
- Renamed from `ServerManagerImpl` to `LeanInteractServerManager`
- Uses `OrderedDict` instead of plain `dict` for LRU tracking
- Added `MAX_SERVERS` constant (configurable via `LEAN_MAX_SERVERS` env var)
- Implemented LRU eviction in `get_server()`: evicts oldest when at capacity
- Added `_is_server_alive()` health check method
- Added `_shutdown_server()` graceful shutdown method
- `get_server()` moves accessed servers to end (marks as most recently used)
- `_create_server()` passes workspace path explicitly to `LocalProject(path=...)` (no `os.chdir()`)

### 3. Module Exports (lean/__init__.py)

```python
from .ports import (
    Declaration,
    DeclValue,
    Querier,  # Protocol (no LeanInteract prefix)
    ProofState,
    ProofStateInspector,  # Protocol
    ProofValidator,  # Protocol
    Range,
    ServerManager,  # Protocol
    TacticResult,
    TheoremContext,
    ValidationResult,
)
from .proof_state import LeanInteractProofStateInspector  # Adapter
from .querier import LeanInteractQuerier  # Adapter
from .server_manager import LeanInteractServerManager  # Adapter
from .validator import LeanInteractProofValidator  # Adapter

__all__ = [
    # Ports (protocols)
    "Declaration",
    "DeclValue",
    "Querier",
    "ProofState",
    "ProofStateInspector",
    "ProofValidator",
    "Range",
    "ServerManager",
    "TacticResult",
    "TheoremContext",
    "ValidationResult",
    # Implementations (adapters)
    "LeanInteractQuerier",
    "LeanInteractProofStateInspector",
    "LeanInteractProofValidator",
    "LeanInteractServerManager",
]
```

**Changes**:
- Export `Querier` protocol (renamed from `LeanInteractQuerier`)
- Export `LeanInteractQuerier` adapter (renamed from `LeanInteractQuerierImpl`)
- Export `LeanInteractProofStateInspector` (renamed from `ProofStateInspectorImpl`)
- Export `LeanInteractProofValidator` (renamed from `ProofValidatorImpl`)
- Export `LeanInteractServerManager` (renamed from `ServerManagerImpl`)

## Data Models

### LeanRunResult

```python
@dataclass(frozen=True)
class LeanRunResult:
    """Result of running Lean verification."""
    status: str  # "success" | "fail" | "timeout"
    diagnostics: list[dict]  # List of diagnostic messages
    scope_used: str  # "file" | "theorem"
    full_logs: str  # Full output logs
    timing: dict[str, float]  # Timing information
    exit_code: int  # Exit code from Lean process
```

This data model is used by `verify_file()` method (absorbed from LeanInteractRunner).

### Server Cache Entry

The ServerManager maintains an OrderedDict mapping:
- **Key**: `file_path: str` - Path to Lean file
- **Value**: `LeanServer` - Server instance for that file

The OrderedDict maintains insertion order, with most recently used servers at the end.

## Correctness Properties


*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: LRU Eviction Triggers Shutdown

*For any* LeanInteractServerManager at MAX_SERVERS capacity, when get_server() is called for a new file, the least recently used server should be shut down gracefully before eviction.

**Validates: Requirements 3.4, 3.6, 5.5**

### Property 2: LRU Tracking on Access

*For any* existing server in the cache, when get_server() is called for that server's file, the server should be moved to the end of the OrderedDict (marked as most recently used).

**Validates: Requirements 3.5**

### Property 3: Dead Server Replacement

*For any* cached server that is not alive, when get_server() is called for that server's file, the dead server should be removed from cache and a new server should be created.

**Validates: Requirements 4.2, 4.3**

### Property 4: Health Check Correctness

*For any* server object, _is_server_alive() should return True if and only if the server has both run() and kill() methods and is responsive.

**Validates: Requirements 4.4, 4.5**

### Property 5: Graceful Shutdown Behavior

*For any* server object, when _shutdown_server() is called, it should invoke the server's kill() method if available and should not raise exceptions even if kill() fails.

**Validates: Requirements 5.2, 5.3**

### Property 6: Shutdown All Completeness

*For any* LeanInteractServerManager with N cached servers, when shutdown_all() is called, _shutdown_server() should be called exactly N times (once per server).

**Validates: Requirements 5.4**

### Property 7: Verification Scope Handling

*For any* file path and budget, when verify_file() is called, the returned LeanRunResult.scope_used should be "file" if theorem_id is None, and "theorem" if theorem_id is provided.

**Validates: Requirements 6.4, 6.5**

### Property 8: Adapter ServerManager Usage

*For any* adapter (LeanInteractQuerier, LeanInteractProofValidator, LeanInteractProofStateInspector), when the adapter needs a server instance, it should obtain it through the injected ServerManager and should not create ServerManager instances internally.

**Validates: Requirements 8.4, 8.5**

### Property 9: LocalProject Path Injection

*For any* LocalProject instantiation in the codebase, the workspace path should be passed explicitly via the path parameter without using os.chdir().

**Validates: Requirements 9.3**

### Property 10: Adapter Naming Convention

*For all* adapter implementation classes in the lean/ directory, the class name should start with "LeanInteract" and should not end with "Impl".

**Validates: Requirements 2.1, 2.2**

### Property 11: Codebase Migration Completeness

*For all* Python files in the codebase, there should be no imports or references to old class names (LeanInteractQuerierImpl, ProofStateInspectorImpl, ProofValidatorImpl, ServerManagerImpl, LeanInteractRunner).

**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**

### Property 12: Test Migration Completeness

*For all* test files, there should be no imports from deleted modules and no references to old class names.

**Validates: Requirements 11.4, 11.5**

### Property 13: Backward Compatibility

*For all* public methods in the refactored adapters, the method signatures and behavior should match the original implementations (except for constructor changes to accept ServerManager).

**Validates: Requirements 13.4, 13.5**

## Error Handling

### Server Creation Failures

When `_create_server()` fails to create a LeanServer:
- Raise `RuntimeError` with descriptive message
- Include original exception as cause
- Log error with file path context

### Server Health Check Failures

When `_is_server_alive()` detects a dead server:
- Return `False` without raising exceptions
- Log warning about dead server detection
- Allow `get_server()` to handle replacement

### Shutdown Failures

When `_shutdown_server()` encounters errors:
- Log warning with error details
- Continue without raising exceptions
- Ensure cleanup proceeds for other servers

### LRU Eviction Failures

When evicting a server fails during shutdown:
- Log error but continue with eviction
- Remove server from cache regardless
- Proceed with creating new server

### Verification Failures

When `verify_file()` encounters errors:
- Raise `TimeoutError` for timeout conditions
- Raise `RuntimeError` for unexpected failures
- Include original exception as cause
- Return structured `LeanRunResult` with error status

## Testing Strategy

### Unit Testing

Unit tests focus on specific examples, edge cases, and error conditions:

**LeanInteractServerManager Tests**:
- Test MAX_SERVERS default value is 3
- Test MAX_SERVERS reads from LEAN_MAX_SERVERS env var
- Test OrderedDict is used for _servers
- Test _is_server_alive() with servers missing methods
- Test _shutdown_server() with servers that raise exceptions
- Test get_server() with dead servers
- Test restart_server() removes and recreates server
- Test shutdown_all() with empty cache

**LeanInteractProofValidator Tests**:
- Test verify_file() with valid file returns success
- Test verify_file() with invalid file returns error
- Test verify_file() with timeout raises TimeoutError
- Test validate_proof() with valid proof returns success
- Test validate_proof() with invalid proof returns error

**Adapter Constructor Tests**:
- Test LeanInteractQuerier accepts ServerManager
- Test LeanInteractProofStateInspector accepts ServerManager
- Test LeanInteractProofValidator accepts ServerManager

**Migration Tests**:
- Test lean/__init__.py exports correct names
- Test no references to old class names in codebase
- Test deleted files are removed

### Property-Based Testing

Property tests verify universal properties across all inputs (minimum 100 iterations per test):

**Property Test 1: LRU Eviction Triggers Shutdown**
- Generate random sequences of file paths
- Fill cache to MAX_SERVERS capacity
- Request new file and verify oldest server is shut down
- Tag: **Feature: adapter-refactor, Property 1: LRU Eviction Triggers Shutdown**

**Property Test 2: LRU Tracking on Access**
- Generate random sequences of file accesses
- Verify accessed servers move to end of OrderedDict
- Tag: **Feature: adapter-refactor, Property 2: LRU Tracking on Access**

**Property Test 3: Dead Server Replacement**
- Generate random server states (alive/dead)
- Verify dead servers are replaced on access
- Tag: **Feature: adapter-refactor, Property 3: Dead Server Replacement**

**Property Test 4: Health Check Correctness**
- Generate random server objects with/without methods
- Verify _is_server_alive() returns correct boolean
- Tag: **Feature: adapter-refactor, Property 4: Health Check Correctness**

**Property Test 5: Graceful Shutdown Behavior**
- Generate random server objects (some raise on kill())
- Verify _shutdown_server() never raises exceptions
- Tag: **Feature: adapter-refactor, Property 5: Graceful Shutdown Behavior**

**Property Test 6: Shutdown All Completeness**
- Generate random number of cached servers
- Verify shutdown_all() calls _shutdown_server() for each
- Tag: **Feature: adapter-refactor, Property 6: Shutdown All Completeness**

**Property Test 7: Verification Scope Handling**
- Generate random file paths and theorem_ids (some None)
- Verify LeanRunResult.scope_used matches theorem_id presence
- Tag: **Feature: adapter-refactor, Property 7: Verification Scope Handling**

**Property Test 8: Adapter ServerManager Usage**
- Generate random adapter instances
- Verify all use injected ServerManager, none create internally
- Tag: **Feature: adapter-refactor, Property 8: Adapter ServerManager Usage**

**Property Test 9: LocalProject Path Injection**
- Scan all LocalProject instantiations in codebase
- Verify all pass path parameter explicitly
- Tag: **Feature: adapter-refactor, Property 9: LocalProject Path Injection**

**Property Test 10: Adapter Naming Convention**
- Scan all adapter classes in lean/ directory
- Verify all start with "LeanInteract" and don't end with "Impl"
- Tag: **Feature: adapter-refactor, Property 10: Adapter Naming Convention**

**Property Test 11: Codebase Migration Completeness**
- Scan all Python files for old class names
- Verify zero occurrences of old names
- Tag: **Feature: adapter-refactor, Property 11: Codebase Migration Completeness**

**Property Test 12: Test Migration Completeness**
- Scan all test files for old imports and references
- Verify zero occurrences of old names
- Tag: **Feature: adapter-refactor, Property 12: Test Migration Completeness**

**Property Test 13: Backward Compatibility**
- Compare method signatures before and after refactor
- Verify all public methods maintain same signatures (except constructors)
- Tag: **Feature: adapter-refactor, Property 13: Backward Compatibility**

### Testing Library

Use **Hypothesis** for property-based testing in Python:
- Configure each test with `@settings(max_examples=100)`
- Use `@given()` decorator with appropriate strategies
- Generate random file paths, server states, and sequences
- Verify properties hold across all generated inputs

### Integration Testing

Integration tests verify end-to-end workflows:
- Test full verification workflow with LeanInteractProofValidator.verify_file()
- Test declaration extraction with LeanInteractQuerier
- Test proof state inspection with LeanInteractProofStateInspector
- Test server lifecycle across multiple operations
- Verify all existing integration tests pass with new class names
