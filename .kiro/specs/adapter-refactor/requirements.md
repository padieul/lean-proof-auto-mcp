# Requirements Document

## Introduction

This document specifies requirements for refactoring the adapter layer in the lean_proof_auto_mcp codebase. The refactor aims to establish a unified architecture with consistent naming conventions, efficient server lifecycle management with LRU eviction, consolidated functionality by absorbing LeanInteractRunner into ProofValidator, and elimination of thread-unsafe `os.chdir()` calls. The refactor maintains hexagonal architecture principles where core domain logic depends on technology-agnostic protocols, and adapter implementations provide concrete LeanInteract-based implementations.

## Glossary

- **Protocol**: Abstract interface (Python Protocol) defining a port in hexagonal architecture
- **Adapter**: Concrete implementation of a protocol that depends on external technology (LeanInteract)
- **ServerManager**: Component responsible for managing LeanInteract server lifecycle
- **LRU_Eviction**: Least Recently Used eviction policy for cache management
- **Querier**: Protocol for extracting declarations and references from Lean files
- **ProofStateInspector**: Protocol for inspecting proof states and applying tactics
- **ProofValidator**: Protocol for validating proof attempts
- **LeanInteract**: External library for interacting with Lean proof assistant
- **LeanServer**: Server instance from LeanInteract library for processing Lean commands

## Requirements

### Requirement 1: Technology-Agnostic Protocol Naming

**User Story:** As a developer, I want protocol names to be technology-agnostic, so that the core domain layer remains independent of specific adapter implementations.

#### Acceptance Criteria

1. THE Protocol_Naming_System SHALL use names that describe capabilities without referencing specific technologies
2. WHEN a protocol is defined in ports.py, THE Protocol_Naming_System SHALL NOT include "LeanInteract" prefix in the protocol name
3. THE Querier protocol SHALL be named "Querier" without "LeanInteract" prefix
4. THE ProofStateInspector protocol SHALL remain named "ProofStateInspector"
5. THE ProofValidator protocol SHALL remain named "ProofValidator"
6. THE ServerManager protocol SHALL remain named "ServerManager"

### Requirement 2: Consistent Adapter Implementation Naming

**User Story:** As a developer, I want adapter implementations to follow a consistent naming convention, so that I can easily distinguish protocols from implementations.

#### Acceptance Criteria

1. WHEN an adapter implements a protocol, THE Adapter_Naming_System SHALL prefix the implementation name with "LeanInteract"
2. WHEN an adapter implements a protocol, THE Adapter_Naming_System SHALL NOT suffix the implementation name with "Impl"
3. THE LeanInteractQuerierImpl class SHALL be renamed to "LeanInteractQuerier"
4. THE ProofStateInspectorImpl class SHALL be renamed to "LeanInteractProofStateInspector"
5. THE ProofValidatorImpl class SHALL be renamed to "LeanInteractProofValidator"
6. THE ServerManagerImpl class SHALL be renamed to "LeanInteractServerManager"

### Requirement 3: LRU Server Cache Management

**User Story:** As a system operator, I want the ServerManager to limit the number of concurrent servers using LRU eviction, so that memory usage remains bounded during long-running operations.

#### Acceptance Criteria

1. THE LeanInteractServerManager SHALL use OrderedDict instead of plain dict for server cache storage
2. THE LeanInteractServerManager SHALL define a MAX_SERVERS constant with default value of 3
3. WHERE the LEAN_MAX_SERVERS environment variable is set, THE LeanInteractServerManager SHALL use that value for MAX_SERVERS
4. WHEN get_server() is called and the cache is at MAX_SERVERS capacity, THE LeanInteractServerManager SHALL evict the least recently used server before adding a new server
5. WHEN get_server() is called for an existing server, THE LeanInteractServerManager SHALL move that server to the end of the OrderedDict to mark it as most recently used
6. WHEN evicting a server, THE LeanInteractServerManager SHALL call the graceful shutdown method before removal

### Requirement 4: Server Health Monitoring

**User Story:** As a system operator, I want the ServerManager to check server health before reuse, so that crashed servers are detected and replaced automatically.

#### Acceptance Criteria

1. THE LeanInteractServerManager SHALL implement a _is_server_alive() method that checks server health
2. WHEN get_server() retrieves a cached server, THE LeanInteractServerManager SHALL verify the server is alive using _is_server_alive()
3. IF a cached server is not alive, THEN THE LeanInteractServerManager SHALL remove it from cache and create a new server
4. THE _is_server_alive() method SHALL return True if the server has required methods and is responsive
5. THE _is_server_alive() method SHALL return False if the server is unresponsive or missing required methods

### Requirement 5: Graceful Server Shutdown

**User Story:** As a system operator, I want servers to be shut down gracefully, so that resources are properly released and no processes are left orphaned.

#### Acceptance Criteria

1. THE LeanInteractServerManager SHALL implement a _shutdown_server() method for graceful shutdown
2. WHEN _shutdown_server() is called, THE LeanInteractServerManager SHALL invoke the server's kill() method if available
3. WHEN _shutdown_server() encounters an error, THE LeanInteractServerManager SHALL log the error and continue without raising an exception
4. WHEN shutdown_all() is called, THE LeanInteractServerManager SHALL call _shutdown_server() for each cached server
5. WHEN evicting a server for LRU replacement, THE LeanInteractServerManager SHALL call _shutdown_server() before removal

### Requirement 6: ProofValidator File Verification

**User Story:** As a developer, I want ProofValidator to support file-level verification, so that I can verify entire Lean files without needing a separate Runner component.

#### Acceptance Criteria

1. THE ProofValidator protocol SHALL include a verify_file() method signature
2. THE verify_file() method SHALL accept workspace_path, file_path, theorem_id, and budget_s parameters
3. THE verify_file() method SHALL return a LeanRunResult with status, diagnostics, logs, and timing information
4. WHEN verify_file() is called with theorem_id as None, THE ProofValidator SHALL perform file-level verification
5. WHEN verify_file() is called with a theorem_id value, THE ProofValidator SHALL perform theorem-level verification

### Requirement 7: Absorb LeanInteractRunner Functionality

**User Story:** As a developer, I want LeanInteractRunner functionality consolidated into ProofValidator, so that there is a single adapter for all verification operations.

#### Acceptance Criteria

1. THE LeanInteractProofValidator class SHALL implement the verify_file() method from ProofValidator protocol
2. THE verify_file() implementation SHALL contain all logic currently in LeanInteractRunner.verify_file()
3. THE LeanInteractProofValidator SHALL receive ServerManager via constructor injection
4. THE LeanInteractProofValidator SHALL use the injected ServerManager to obtain server instances for verification
5. THE adapters/lean_interact_runner.py file SHALL be deleted from the codebase

### Requirement 8: Dependency Injection for Adapters

**User Story:** As a developer, I want all adapter implementations to receive ServerManager via constructor injection, so that dependencies are explicit and testable.

#### Acceptance Criteria

1. THE LeanInteractQuerier constructor SHALL accept ServerManager as a required parameter
2. THE LeanInteractProofStateInspector constructor SHALL accept ServerManager as a required parameter
3. THE LeanInteractProofValidator constructor SHALL accept ServerManager as a required parameter
4. WHEN an adapter needs a server instance, THE Adapter SHALL obtain it through the injected ServerManager
5. THE Adapter implementations SHALL NOT create ServerManager instances internally

### Requirement 9: Eliminate os.chdir() Hazard

**User Story:** As a developer, I want to eliminate all os.chdir() calls, so that the codebase is thread-safe and avoids race conditions in concurrent environments.

#### Acceptance Criteria

1. THE Codebase SHALL NOT contain any os.chdir() function calls
2. THE Codebase SHALL NOT contain any _working_directory() context manager implementations
3. WHEN creating a LocalProject instance, THE Code SHALL pass workspace path explicitly via the path parameter
4. IF os.chdir() is required for elan toolchain resolution, THEN THE Code SHALL use threading.Lock to serialize access
5. IF threading.Lock is used for os.chdir(), THEN THE Code SHALL document the reason and lock usage in comments

### Requirement 10: Module Export Updates

**User Story:** As a developer, I want module exports to reflect the new class names, so that imports work correctly throughout the codebase.

#### Acceptance Criteria

1. THE lean/__init__.py file SHALL export "LeanInteractQuerier" instead of "LeanInteractQuerierImpl"
2. THE lean/__init__.py file SHALL export "LeanInteractProofStateInspector" instead of "ProofStateInspectorImpl"
3. THE lean/__init__.py file SHALL export "LeanInteractProofValidator" instead of "ProofValidatorImpl"
4. THE lean/__init__.py file SHALL export "LeanInteractServerManager" instead of "ServerManagerImpl"
5. THE lean/__init__.py file SHALL continue exporting all protocol types unchanged

### Requirement 11: Test File Cleanup

**User Story:** As a developer, I want obsolete test files removed, so that the test suite only contains relevant tests for the current architecture.

#### Acceptance Criteria

1. THE tests/unit/adapters/test_lean_interact_runner.py file SHALL be deleted
2. THE tests/unit/test_server_manager_refactoring.py file SHALL be deleted
3. THE tests/unit/test_lean_version_detection.py file SHALL be deleted
4. WHEN tests reference old class names, THE Test_Code SHALL be updated to use new class names
5. WHEN tests import from deleted modules, THE Test_Code SHALL be updated to import from correct modules

### Requirement 12: Import Statement Updates

**User Story:** As a developer, I want all import statements updated to use new class names, so that the codebase compiles and runs without errors.

#### Acceptance Criteria

1. WHEN code imports LeanInteractQuerierImpl, THE Import_Statement SHALL be updated to import LeanInteractQuerier
2. WHEN code imports ProofStateInspectorImpl, THE Import_Statement SHALL be updated to import LeanInteractProofStateInspector
3. WHEN code imports ProofValidatorImpl, THE Import_Statement SHALL be updated to import LeanInteractProofValidator
4. WHEN code imports ServerManagerImpl, THE Import_Statement SHALL be updated to import LeanInteractServerManager
5. WHEN code references LeanInteractRunner, THE Code SHALL be updated to use LeanInteractProofValidator with verify_file() method

### Requirement 13: Backward Compatibility Validation

**User Story:** As a developer, I want all existing tests to pass after the refactor, so that I can verify the refactor maintains existing functionality.

#### Acceptance Criteria

1. WHEN the refactor is complete, THE Test_Suite SHALL execute all remaining tests
2. WHEN tests are executed, THE Test_Suite SHALL report zero failures for tests that passed before the refactor
3. IF a test fails after refactor, THEN THE Test_Failure SHALL be due to intentional behavior changes documented in requirements
4. THE Refactored_Code SHALL maintain the same external API for all public methods
5. THE Refactored_Code SHALL maintain the same behavior for all existing use cases
