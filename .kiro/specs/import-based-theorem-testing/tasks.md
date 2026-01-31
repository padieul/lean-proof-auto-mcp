# Import-Based Theorem Testing - Tasks

## Phase 0: OBLITERATE Legacy Code (BLOCKING)

- [x] 0. Complete removal of all broken legacy code
  - [x] 0.1 Identify all code to remove (run grep commands from REMOVAL_CHECKLIST.md)
  - [x] 0.2 Delete manual parsing functions from probe_domain.py (lines ~681-830)
  - [x] 0.3 Delete search_annotations tool completely (all files, tests, docs, references)
  - [x] 0.4 Delete any legacy harness constructor code
  - [x] 0.5 Verify removal (grep commands return nothing, code compiles)

## Phase 1: Core Infrastructure

- [x] 1. Implement core components for import-based harness construction
  - [x] 1.1 Create dataclasses (ImportPath, TheoremType, HarnessConfig, HarnessSuccess, HarnessError)
  - [x] 1.2 Implement ImportPathConverter (Protocol + StandardImportPathConverter)
  - [x] 1.3 Implement TheoremTypeExtractor (Protocol + LeanInteractTheoremTypeExtractor)
  - [x] 1.4 Implement ImportBasedHarnessConstructor with validation
  - [x] 1.5 Write unit tests for all components (>90% coverage)

## Phase 2: Probe Tool Integration

- [x] 2. Integrate new harness constructor with probe tool
  - [x] 2.1 Update ProbeOrchestrator to use HarnessConstructor via dependency injection
  - [x] 2.2 Create composition root (build_probe_orchestrator function)
  - [x] 2.3 Update MCP tool entry points
  - [x] 2.4 Run integration tests with 14 bug report theorems
  - [x] 2.5 Verify 100% harness compilation rate (currently 0%)

## Phase 3: Property-Based Testing

- [x] 3. Implement correctness properties with property-based tests
  - [x] 3.1 Write property test: Import-First Invariant (imports always line 1)
  - [x] 3.2 Write property test: No Signature Reconstruction (uses example, not theorem)
  - [x] 3.3 Write property test: Type Preservation (type matches LeanInteract)
  - [x] 3.4 Run all property tests with 100+ examples each

## Phase 4: Search Orchestrator

- [ ] 4. Implement search orchestrator with hint discovery
  - [ ] 4.1 Implement SearchOrchestrator with HarnessConstructor
  - [ ] 4.2 Implement hint combination generation
  - [ ] 4.3 Write unit tests for SearchOrchestrator
  - [ ] 4.4 Run integration tests (verify attempts > 0)

## Phase 5: Documentation

- [ ] 5. Update documentation and verify performance
  - [ ] 5.1 Update README with new architecture
  - [ ] 5.2 Remove references to deleted tools from all docs
  - [ ] 5.3 Add architecture diagram and examples
  - [ ] 5.4 Benchmark performance (<100ms per harness)
