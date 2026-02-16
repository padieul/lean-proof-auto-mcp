# Implementation Plan: Adapter Layer Refactor

## Overview

This plan refactors the adapter layer to establish unified architecture with consistent naming, LRU server management, consolidated verification functionality, and thread-safe operation. The refactor follows hexagonal architecture principles with technology-agnostic protocols and LeanInteract-specific adapters.

## Tasks

- [x] 1. Rename protocols to be technology-agnostic
  - Update `lean/ports.py` to rename `LeanInteractQuerier` protocol to `Querier`
  - Update all type hints and docstrings referencing the protocol
  - Verify all other protocols (ProofValidator, ProofStateInspector, ServerManager) are already technology-agnostic
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6_

- [ ]* 1.1 Write unit tests for protocol naming
  - Test that Querier protocol exists in ports.py
  - Test that no protocols in ports.py have "LeanInteract" prefix
  - _Requirements: 1.2, 1.3_

- [x] 2. Rename ServerManagerImpl to LeanInteractServerManager
  - Rename class in `lean/server_manager.py`
  - Update all docstrings and comments
  - Update `lean/__init__.py` exports
  - _Requirements: 2.6, 10.4_

- [x] 3. Implement LRU eviction in LeanInteractServerManager
  - [x] 3.1 Replace plain dict with OrderedDict for _servers
    - Import OrderedDict from collections
    - Change `self._servers: dict[str, object]` to `self._servers: OrderedDict[str, Any]`
    - _Requirements: 3.1_

  - [x] 3.2 Add MAX_SERVERS configuration
    - Add module-level constant: `MAX_SERVERS = int(os.environ.get("LEAN_MAX_SERVERS", "3"))`
    - Document the environment variable in docstring
    - _Requirements: 3.2, 3.3_

  - [x] 3.3 Implement LRU eviction logic in get_server()
    - Before creating new server, check if `len(self._servers) >= MAX_SERVERS`
    - If at capacity, evict oldest: `oldest_file, oldest_server = self._servers.popitem(last=False)`
    - Call `self._shutdown_server(oldest_server)` before eviction
    - Log eviction with file path
    - _Requirements: 3.4, 3.6_

  - [x] 3.4 Implement LRU tracking on access
    - When returning existing server, call `self._servers.move_to_end(file_path)`
    - This marks the server as most recently used
    - _Requirements: 3.5_

  - [ ]* 3.5 Write property test for LRU eviction
    - **Property 1: LRU Eviction Triggers Shutdown**
    - **Validates: Requirements 3.4, 3.6, 5.5**

  - [ ]* 3.6 Write property test for LRU tracking
    - **Property 2: LRU Tracking on Access**
    - **Validates: Requirements 3.5**

- [x] 4. Add server health monitoring to LeanInteractServerManager
  - [x] 4.1 Implement _is_server_alive() method
    - Check if server has `run` and `kill` methods using hasattr()
    - Return True if both methods exist, False otherwise
    - Wrap in try-except to handle any exceptions
    - _Requirements: 4.1, 4.4, 4.5_

  - [x] 4.2 Add health check to get_server()
    - When retrieving cached server, call `self._is_server_alive(server)`
    - If not alive, log warning, call `self._shutdown_server(server)`, delete from cache
    - Create new server if dead server was removed
    - _Requirements: 4.2, 4.3_

  - [ ]* 4.3 Write property test for dead server replacement
    - **Property 3: Dead Server Replacement**
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 4.4 Write property test for health check correctness
    - **Property 4: Health Check Correctness**
    - **Validates: Requirements 4.4, 4.5**

- [x] 5. Add graceful shutdown to LeanInteractServerManager
  - [x] 5.1 Implement _shutdown_server() method
    - Check if server has `kill` method using hasattr()
    - Call `server.kill()` if available
    - Wrap in try-except to catch and log any exceptions
    - Never raise exceptions from this method
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 5.2 Update shutdown_all() to use _shutdown_server()
    - Iterate over all cached servers
    - Call `self._shutdown_server(server)` for each
    - Clear the cache after all shutdowns
    - _Requirements: 5.4_

  - [x] 5.3 Update restart_server() to use _shutdown_server()
    - Call `self._shutdown_server(server)` before deleting from cache
    - _Requirements: 5.5_

  - [ ]* 5.4 Write property test for graceful shutdown
    - **Property 5: Graceful Shutdown Behavior**
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 5.5 Write property test for shutdown_all completeness
    - **Property 6: Shutdown All Completeness**
    - **Validates: Requirements 5.4**

- [x] 6. Eliminate os.chdir() from LeanInteractServerManager
  - Update `_create_server()` to pass workspace path explicitly to LocalProject
  - Change `LocalProject(directory=str(workspace))` to `LocalProject(path=str(workspace))`
  - Remove any `os.chdir()` calls if present
  - Remove `_working_directory()` context manager if present
  - _Requirements: 9.1, 9.2, 9.3_

- [ ]* 6.1 Write property test for LocalProject path injection
  - **Property 9: LocalProject Path Injection**
  - **Validates: Requirements 9.3**

- [x] 7. Update LeanInteractServerManager to accept ServerManager protocol type
  - Update type hints in `get_server()`, `restart_server()`, etc. to use protocol types
  - Ensure the class properly implements the ServerManager protocol
  - _Requirements: 8.1, 8.2, 8.3_

- [x] 8. Rename LeanInteractQuerierImpl to LeanInteractQuerier
  - Rename class in `lean/querier.py`
  - Update constructor to accept `ServerManager` protocol (not concrete ServerManagerImpl)
  - Update all docstrings and comments
  - Update `lean/__init__.py` exports
  - _Requirements: 2.3, 8.1, 10.1_

- [x] 9. Rename ProofStateInspectorImpl to LeanInteractProofStateInspector
  - [x] 9.1 Rename class in `lean/proof_state.py`
    - Update class name
    - Update all docstrings and comments
    - _Requirements: 2.4, 10.2_

  - [x] 9.2 Update constructor to accept ServerManager
    - Change constructor signature: `def __init__(self, server_manager: ServerManager)`
    - Store as `self._server_manager = server_manager`
    - Remove `server` parameter
    - _Requirements: 8.2_

  - [x] 9.3 Update methods to use ServerManager
    - In `get_initial_proof_state()`, get server via `self._server_manager.get_server("default")`
    - In `apply_tactic()`, get server via `self._server_manager.get_server("default")`
    - _Requirements: 8.4_

  - [x] 9.4 Update lean/__init__.py exports
    - Export `LeanInteractProofStateInspector` instead of `ProofStateInspectorImpl`
    - _Requirements: 10.2_

- [x] 10. Rename ProofValidatorImpl to LeanInteractProofValidator and add verify_file()
  - [x] 10.1 Rename class in `lean/validator.py`
    - Update class name
    - Update all docstrings and comments
    - _Requirements: 2.5, 10.3_

  - [x] 10.2 Update constructor to accept ServerManager
    - Change constructor signature: `def __init__(self, server_manager: ServerManager)`
    - Store as `self._server_manager = server_manager`
    - Remove `server` parameter
    - _Requirements: 8.3_

  - [x] 10.3 Update validate_proof() to use ServerManager
    - Get server via `self._server_manager.get_server(file_path or "default")`
    - Update all server access to use ServerManager
    - _Requirements: 8.4_

  - [x] 10.4 Add verify_file() method to ProofValidator protocol
    - Update `lean/ports.py` to add method signature
    - Method signature: `def verify_file(self, workspace_path: Path, file_path: str, theorem_id: str | None, budget_s: float) -> LeanRunResult`
    - Add docstring describing the method
    - _Requirements: 6.1, 6.2_

  - [x] 10.5 Implement verify_file() in LeanInteractProofValidator
    - Copy implementation from `LeanInteractRunner.verify_file()`
    - Use `self._server_manager.get_server(file_path)` to obtain server
    - Implement `_parse_diagnostics()` helper method
    - Implement `_determine_status()` helper method
    - Return LeanRunResult with appropriate status, diagnostics, scope_used, logs, timing
    - _Requirements: 6.3, 6.4, 6.5, 7.1, 7.4_

  - [ ]* 10.6 Write property test for verification scope handling
    - **Property 7: Verification Scope Handling**
    - **Validates: Requirements 6.4, 6.5**

  - [x] 10.7 Update lean/__init__.py exports
    - Export `LeanInteractProofValidator` instead of `ProofValidatorImpl`
    - _Requirements: 10.3_

- [x] 11. Delete LeanInteractRunner and related files
  - Delete `src/lean_proof_auto_mcp/adapters/lean_interact_runner.py`
  - Delete `tests/unit/adapters/test_lean_interact_runner.py`
  - Delete `tests/unit/test_server_manager_refactoring.py`
  - Delete `tests/unit/test_lean_version_detection.py`
  - _Requirements: 7.5, 11.1, 11.2, 11.3_

- [x] 12. Update all imports throughout codebase
  - [x] 12.1 Update tool files to use new class names
    - Update `tools/verify.py`: import and use `LeanInteractServerManager`, `LeanInteractProofValidator`
    - Update `tools/probe.py`: import and use `LeanInteractServerManager`, `LeanInteractProofValidator`
    - Update `tools/probe_file.py`: import and use `LeanInteractServerManager`, `LeanInteractProofValidator`
    - Update `tools/search_automated_proof.py`: import and use `LeanInteractServerManager`, `LeanInteractProofValidator`
    - Replace `LeanInteractRunner` usage with `LeanInteractProofValidator.verify_file()`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 12.2 Update core domain files
    - Update `core/probe_domain.py`: import `LeanInteractServerManager` instead of `ServerManagerImpl`
    - Update any other core files that import adapter classes
    - _Requirements: 12.4_

  - [x] 12.3 Update test files
    - Update `tests/unit/lean/test_error_handling.py`: use new class names
    - Update `tests/property/test_server_manager_properties.py`: use `LeanInteractServerManager`
    - Update `tests/integration/test_adapter_layer_integration.py`: use new class names
    - Update `tests/benchmark/test_declaration_extraction_accuracy.py`: use new class names
    - _Requirements: 11.4, 11.5, 12.1, 12.2, 12.3, 12.4_

  - [ ]* 12.4 Write property test for codebase migration completeness
    - **Property 11: Codebase Migration Completeness**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**

  - [ ]* 12.5 Write property test for test migration completeness
    - **Property 12: Test Migration Completeness**
    - **Validates: Requirements 11.4, 11.5**

- [x] 13. Update composition roots in tools
  - [x] 13.1 Update verify.py composition root
    - Create `server_manager = LeanInteractServerManager(workspace_path=project_root)`
    - Create `validator = LeanInteractProofValidator(server_manager)`
    - Pass validator to command handler
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 13.2 Update probe.py composition root
    - Create `server_manager = LeanInteractServerManager(workspace_path=project_root)`
    - Create `validator = LeanInteractProofValidator(server_manager)`
    - Pass validator to command handler
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 13.3 Update probe_file.py composition root
    - Create `server_manager = LeanInteractServerManager(workspace_path=project_root)`
    - Create `validator = LeanInteractProofValidator(server_manager)`
    - Pass validator to command handler
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 13.4 Update search_automated_proof.py composition root
    - Create `server_manager = LeanInteractServerManager(workspace_path=project_root)`
    - Create `querier = LeanInteractQuerier(server_manager)`
    - Create `validator = LeanInteractProofValidator(server_manager)`
    - Pass to command handler
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 13.5 Update try_automated_proof.py composition root
    - Create `server_manager = LeanInteractServerManager(workspace_path=project_root)`
    - Create `validator = LeanInteractProofValidator(server_manager)`
    - Pass to command handler
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 13.6 Update get_proof_context.py composition root
    - Create `server_manager = LeanInteractServerManager(workspace_path=project_root)`
    - Create `querier = LeanInteractQuerier(server_manager)`
    - Pass to command handler
    - _Requirements: 8.1, 8.2, 8.3_

- [ ]* 14. Write property test for adapter ServerManager usage
  - **Property 8: Adapter ServerManager Usage**
  - **Validates: Requirements 8.4, 8.5**

- [ ]* 15. Write property test for adapter naming convention
  - **Property 10: Adapter Naming Convention**
  - **Validates: Requirements 2.1, 2.2**

- [x] 16. Checkpoint - Ensure all tests pass
  - Run full test suite: `pytest tests/`
  - Verify all unit tests pass
  - Verify all property tests pass
  - Verify all integration tests pass
  - Fix any failures related to refactoring
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 17. Write property test for backward compatibility
  - **Property 13: Backward Compatibility**
  - **Validates: Requirements 13.4, 13.5**

- [x] 18. Final verification and cleanup
  - Verify no references to old class names remain: `grep -r "LeanInteractQuerierImpl\|ProofStateInspectorImpl\|ProofValidatorImpl\|ServerManagerImpl\|LeanInteractRunner" src/ tests/`
  - Verify no os.chdir() calls remain: `grep -r "os\.chdir" src/`
  - Verify deleted files are gone
  - Run full test suite one final time
  - _Requirements: 9.1, 11.1, 11.2, 11.3, 12.1, 12.2, 12.3, 12.4, 12.5_

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis library
- Unit tests validate specific examples and edge cases
- The refactor maintains backward compatibility for all public APIs except constructor signatures (which now accept ServerManager protocol)
