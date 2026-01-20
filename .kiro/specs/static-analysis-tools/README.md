# Static Analysis Tools Spec

This spec defines the implementation of `scan_file` and `scan_theorem` tools for static analysis of Lean proof files.

## Documents

- **requirements.md**: User stories and acceptance criteria
- **design.md**: Architecture, data structures, and implementation details
- **tasks.md**: Phased implementation plan with concrete tasks

## Implementation Approach

**Phased Delivery**: schemas → stubs → tests → core → integration

### Phase 0: JSON Schemas
Create crisp contracts for both tools before any implementation.

### Phase 1: Stubs
Implement minimal valid responses for contract testing.

### Phase 2: Contract Tests
Validate tool responses against schemas, test determinism and error handling.

### Phase 3: Core Modules
Build shared analysis foundation:
- source.py: Text and location representation
- lean_syntax.py: Comment stripping, tokenization
- indexer.py: Find theorem declarations
- features.py: Extract proof characteristics
- segmenter.py: Segment proofs into blocks
- scoring.py: Compute automation potential
- format.py: Normalize output

### Phase 4: Tool Integration
Wire tools to core modules, pass all tests.

## Key Design Decisions

1. **Hexagonal Architecture**: Core logic separate from I/O
2. **Shared Foundation**: Both tools reuse same indexing/features
3. **Contract-First**: Schemas define behavior before implementation
4. **Pure Functions**: Core modules are deterministic and testable
5. **Graceful Degradation**: Partial results on parse errors

## Testing Strategy

- **Unit Tests**: Each core module with inline Lean snippets
- **Contract Tests**: Schema compliance and determinism
- **Property Tests**: Invariants using Hypothesis

No Lean installation required. Fast CI (<10 seconds).

## Success Criteria

- All tests pass
- >90% code coverage
- Valid JSON for all inputs
- Performance: scan_file <100ms, scan_theorem <50ms
- Zero external dependencies (no Lean runtime)
