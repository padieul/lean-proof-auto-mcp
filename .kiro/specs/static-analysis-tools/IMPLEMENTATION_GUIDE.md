# Implementation Guide

## Quick Start

This spec implements static analysis tools for Lean proof files using a strict phased approach.

### Phase Sequence

```
Phase 0: Schemas → Phase 1: Stubs → Phase 2: Tests → Phase 3: Core → Phase 4: Integration
```

**DO NOT skip phases or implement ahead of schedule.**

## Phase Boundaries

### Phase 0: JSON Schemas
**What to do**: Create/update JSON schema files in `docs/mcp/schemas/`
**What NOT to do**: Write any Python code

### Phase 1: Stubs
**What to do**:
- Create minimal functions that return valid JSON
- Use placeholder data: empty arrays, zero scores, deterministic IDs
- Validate input arguments only

**What NOT to do**:
- Read actual files
- Parse Lean code
- Detect theorems
- Analyze proofs
- Implement any core logic

**Example stub response**:
```python
return {
    "api_version": "0.1",
    "status": "success",
    "run_id": "scan-file-stub-001",
    "tool": "scan_file",
    "file": parsed.file,
    "summary": {"theorem_count": 0, "notes": ["stub implementation"]},
    "theorems": [],  # EMPTY - no actual detection
    "diagnostics": []
}
```

### Phase 2: Contract Tests
**What to do**:
- Write tests that validate JSON schema compliance
- Test with stub responses (which return placeholder data)
- Verify determinism, error handling, field types

**What NOT to do**:
- Expect real theorem detection (stubs return empty data)
- Test actual parsing logic (doesn't exist yet)

### Phase 3: Core Modules
**What to do**:
- Implement actual parsing, indexing, feature extraction
- Write unit tests with inline Lean snippets
- Build pure functions (no I/O)

**This is where real implementation happens.**

### Phase 4: Tool Integration
**What to do**:
- Replace stub implementations with calls to core modules
- Add file reading logic
- Wire everything together
- Run all tests (should now pass with real data)

## Common Pitfalls

### ❌ Pitfall 1: Implementing too early
**Wrong**: In Phase 1, reading files and parsing Lean code
**Right**: In Phase 1, returning hardcoded placeholder JSON

### ❌ Pitfall 2: Skipping stubs
**Wrong**: Going straight from schemas to full implementation
**Right**: Creating stubs first, then tests, then implementation

### ❌ Pitfall 3: Testing real behavior too early
**Wrong**: In Phase 2, expecting stubs to detect actual theorems
**Right**: In Phase 2, testing that stubs return valid JSON structure

## How to Execute

1. Open `tasks.md`
2. Start with Phase 0, task 0.1
3. Complete ALL tasks in a phase before moving to the next
4. When you see "STUB ONLY" warnings, do NOT implement real logic
5. Real implementation starts in Phase 3

## Success Criteria by Phase

- **Phase 0**: Schema files exist and validate
- **Phase 1**: Tools return valid JSON with placeholder data
- **Phase 2**: All contract tests pass (with stub data)
- **Phase 3**: Core modules work and have unit tests
- **Phase 4**: Tools return real data and all tests pass

## Questions?

- "Should I implement file reading in Phase 1?" → **NO**
- "Should I parse Lean code in Phase 1?" → **NO**
- "Should stubs return empty arrays?" → **YES**
- "When do I implement actual parsing?" → **Phase 3**
- "When do I wire tools to core modules?" → **Phase 4**
