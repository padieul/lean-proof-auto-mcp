# Requirements Document

## Introduction

This feature refactors all MCP tool composition roots to use the unified adapter layer, fixing dependency injection violations, adding performance optimizations through caching, and establishing proper architectural boundaries. The refactoring addresses critical issues where tools create duplicate server instances, bypass dependency injection, and perform redundant file operations, leading to poor performance and architectural violations.

This feature depends on the adapter-layer-refactor feature (Branch 1) being completed first, as it relies on the renamed adapter classes from that branch.

## Glossary

- **Composition_Root**: The single location in an application where all dependencies are wired together and injected into command handlers
- **ServerManager**: Component responsible for managing Lean server lifecycle and providing server instances
- **ProofValidator**: Port (interface) for validating proof attempts against theorem statements
- **HarnessConstructor**: Component that builds test harnesses by extracting theorem context and constructing executable Lean code
- **Querier**: Port (interface) for querying Lean files to extract declarations and type information
- **ProofStateInspector**: Port (interface) for inspecting proof state during interactive theorem proving
- **Command**: Immutable data structure representing a request to perform an operation
- **Handler**: Component that orchestrates the execution of a command by coordinating multiple dependencies
- **SearchOrchestrator**: Component that coordinates automated proof search by testing hint combinations
- **probe_fn**: Callback function used by search strategies to test whether a hint combination produces a valid proof

## Requirements

### Requirement 1: Single ServerManager Per Tool

**User Story:** As a system architect, I want each tool to create exactly one ServerManager instance at its composition root, so that server resources are properly managed and not duplicated.

#### Acceptance Criteria

1. WHEN a tool initializes, THE System SHALL create exactly one ServerManager instance at the composition root
2. WHEN multiple operations are performed within a tool invocation, THE System SHALL reuse the same ServerManager instance
3. THE System SHALL NOT create ServerManager instances inside command handlers or domain logic
4. WHEN a tool completes execution, THE System SHALL properly dispose of the ServerManager instance

### Requirement 2: Dependency Injection for HarnessConstructor

**User Story:** As a developer, I want HarnessConstructor to be injected at composition roots, so that handlers don't create their own dependencies and violate architectural boundaries.

#### Acceptance Criteria

1. WHEN ProbeCommandHandler is initialized, THE System SHALL receive HarnessConstructor as a constructor parameter
2. THE ProbeCommandHandler SHALL NOT create ServerManager instances internally
3. THE ProbeCommandHandler SHALL NOT create Querier instances internally
4. WHEN constructing a harness, THE ProbeCommandHandler SHALL use the injected HarnessConstructor

### Requirement 3: Caching in HarnessConstructor

**User Story:** As a performance engineer, I want HarnessConstructor to cache file content and declaration extraction results, so that batch operations don't redundantly parse the same files.

#### Acceptance Criteria

1. WHEN HarnessConstructor reads a file for the first time, THE System SHALL cache the file content
2. WHEN HarnessConstructor extracts declarations for the first time, THE System SHALL cache the extraction results
3. WHEN HarnessConstructor checks theorem existence for the first time, THE System SHALL cache the verification result
4. WHEN HarnessConstructor is called with a previously processed file, THE System SHALL return cached results without re-reading or re-parsing
5. WHEN a batch operation completes, THE System SHALL provide a method to clear all caches
6. THE HarnessConstructor SHALL maintain separate caches for file content, declarations, and theorem verification

### Requirement 4: Command/Handler Pattern for try_automated_proof

**User Story:** As a system architect, I want try_automated_proof to follow the Command/Handler pattern, so that it has clean entry points and proper dependency injection like other tools.

#### Acceptance Criteria

1. THE System SHALL define a ValidateProofCommand as an immutable data structure containing file_path, theorem_id, proof_attempt, timeout_s, and return_proof_state
2. THE System SHALL define a ValidateProofCommandHandler that receives Querier, ProofValidator, HarnessConstructor, and ProofStateInspector as constructor parameters
3. WHEN try_automated_proof is invoked, THE System SHALL build a ValidateProofCommand from the arguments
4. WHEN try_automated_proof is invoked, THE System SHALL create a ValidateProofCommandHandler at the composition root
5. WHEN try_automated_proof is invoked, THE System SHALL call handler.handle(command) to execute the operation
6. THE ValidateProofCommandHandler SHALL NOT create any dependencies internally
7. THE System SHALL NOT perform monkey-patching of server objects

### Requirement 5: ProofValidator Port in SearchOrchestrator

**User Story:** As a system architect, I want SearchOrchestrator to use the ProofValidator port instead of LeanInteractRunner, so that it follows proper architectural boundaries and uses the correct abstraction.

#### Acceptance Criteria

1. WHEN SearchOrchestrator is initialized, THE System SHALL receive ProofValidator as a constructor parameter
2. THE SearchOrchestrator SHALL NOT receive or reference LeanInteractRunner
3. WHEN SearchOrchestrator creates a probe_fn callback, THE probe_fn SHALL use validator.validate_proof() to test hint combinations
4. WHEN probe_fn validates a proof, THE System SHALL construct a harness using the injected HarnessConstructor
5. WHEN probe_fn validates a proof, THE System SHALL use cached file content and declarations from HarnessConstructor
6. WHEN probe_fn receives a validation result, THE System SHALL map the result status to ProbeOutcome (success → SUCCESS, incomplete → PARTIAL, otherwise → FAILED)

### Requirement 6: Shared Dependencies in probe_file

**User Story:** As a performance engineer, I want probe_file to share ServerManager and HarnessConstructor across all theorems in a batch, so that we don't create N servers and parse files N times.

#### Acceptance Criteria

1. WHEN probe_file processes multiple theorems, THE System SHALL create ServerManager exactly once at the composition root
2. WHEN probe_file processes multiple theorems, THE System SHALL create HarnessConstructor exactly once at the composition root
3. WHEN probe_file processes multiple theorems, THE System SHALL reuse the same ServerManager for all theorem validations
4. WHEN probe_file processes multiple theorems, THE System SHALL reuse cached file content and declarations from HarnessConstructor
5. WHEN probe_file completes processing all theorems, THE System SHALL call constructor.clear_cache() to release cached data

### Requirement 7: Adapter Layer Integration

**User Story:** As a system architect, I want all tools to use the renamed adapter classes from the adapter-layer-refactor feature, so that the codebase has consistent naming and proper architectural layers.

#### Acceptance Criteria

1. WHEN tools create a ServerManager, THE System SHALL use LeanInteractServerManager
2. WHEN tools create a Querier, THE System SHALL use LeanInteractQuerier
3. WHEN tools create a ProofValidator, THE System SHALL use LeanInteractProofValidator
4. WHEN tools create a ProofStateInspector, THE System SHALL use LeanInteractProofStateInspector
5. THE System SHALL NOT reference LeanInteractRunner in any tool composition root
6. THE System SHALL NOT reference ServerManagerImpl directly in tool code

### Requirement 8: Performance Improvement in probe_file

**User Story:** As a user, I want probe_file to execute significantly faster when processing multiple theorems, so that batch operations complete in reasonable time.

#### Acceptance Criteria

1. WHEN probe_file processes N theorems from the same file, THE System SHALL perform file reading exactly once
2. WHEN probe_file processes N theorems from the same file, THE System SHALL perform declaration extraction exactly once
3. WHEN probe_file processes N theorems, THE System SHALL maintain a single Lean server instance throughout the batch
4. WHEN probe_file completes, THE System SHALL demonstrate measurable performance improvement compared to the previous implementation (target: ~60% speedup for multi-theorem files)

### Requirement 9: Elimination of Architectural Violations

**User Story:** As a system architect, I want all architectural violations identified in the code review to be eliminated, so that the codebase follows hexagonal architecture and dependency injection principles.

#### Acceptance Criteria

1. THE System SHALL NOT create ServerManager instances inside command handlers
2. THE System SHALL NOT create Querier instances inside command handlers
3. THE System SHALL NOT create HarnessConstructor instances inside command handlers
4. THE System SHALL NOT perform monkey-patching of server objects
5. THE System SHALL NOT pass raw server instances to domain components
6. WHEN a handler needs a dependency, THE System SHALL receive it through constructor injection at the composition root

### Requirement 10: Backward Compatibility

**User Story:** As a developer, I want all existing tests to continue passing after the refactoring, so that we maintain system correctness while improving architecture.

#### Acceptance Criteria

1. WHEN the refactoring is complete, THE System SHALL pass all existing unit tests
2. WHEN the refactoring is complete, THE System SHALL pass all existing integration tests
3. WHEN the refactoring is complete, THE System SHALL pass all existing property tests
4. THE System SHALL maintain the same external API for all MCP tools
5. THE System SHALL produce equivalent results for all tool operations compared to the previous implementation
