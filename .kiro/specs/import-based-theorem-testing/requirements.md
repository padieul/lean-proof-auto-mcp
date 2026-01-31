# Import-Based Theorem Testing - Requirements

## Overview

When testing theorems with automation or validating proof attempts, we need to create test harnesses that preserve ALL context from the original file. The current approach of manually reconstructing theorem signatures is fundamentally broken and causes 100% failure rate.

## Problem Statement

### Current Broken Approach
Tools currently try to:
1. Parse theorem signatures from source text
2. Extract the type by finding `:` and `:=` markers
3. Reconstruct a standalone theorem in a new file

**This fails because:**
- Parsing is fragile (splits on first `:` which might be in parameters like `{p : G × N}`)
- Loses type class instances like `[Group G]`
- Loses variable declarations
- Loses namespace context
- Loses notation imports
- Corrupts Unicode characters
- Results in syntax errors like "unexpected token '('" at line 4, col 18

### Evidence from Bug Report
- **probe tool:** "invalid 'import' command" at line 3 (imports not at top)
- **try_automated_proof:** "unexpected token '('" at line 4, col 18 (corrupted signature)
- **search_automated_proof:** 0 attempts (fails before starting)
- **100% failure rate** across 14 theorems and 26+ tool invocations

## User Stories

### US-1: Test Theorem with Automation
**As a** proof engineer  
**I want to** test if a theorem can be proved by automation (aesop, grind, etc.)  
**So that** I can identify which theorems are amenable to automated proving

**Acceptance Criteria:**
1. Given a theorem in a Lean file
2. When I run automation on it
3. Then the test harness preserves all context from the original file
4. And the harness compiles without syntax errors
5. And automation can attempt the proof (may succeed or fail, but no syntax errors)

### US-2: Validate Proof Attempt
**As a** proof engineer  
**I want to** validate an LLM-generated proof attempt  
**So that** I can verify if the proposed proof is correct

**Acceptance Criteria:**
1. Given a theorem and a proof attempt
2. When I validate the proof
3. Then the validation harness preserves all context
4. And Lean can check the proof without "unknown identifier" errors
5. And I get meaningful feedback (success, incomplete, or specific error)

### US-3: Search for Proof Hints
**As a** proof engineer  
**I want to** search for lemmas that enable automation  
**So that** I can discover which hints make a proof automatable

**Acceptance Criteria:**
1. Given a theorem and candidate hints
2. When I test hint combinations
3. Then each test harness preserves all context
4. And I can try multiple hint combinations without syntax errors
5. And I get results showing which hints work

## Functional Requirements

### FR-1: Import-Based Harness Construction
**Priority:** CRITICAL  
**Requirement:** All test harnesses MUST use import-based approach

**Specification:**
```lean
-- CORRECT APPROACH:
import OriginalFile.Path
import Aesop  -- if needed

-- Test the theorem
example : <theorem_type> := by
  <test_tactic>
```

**NOT:**
```lean
-- WRONG APPROACH (current broken implementation):
namespace SomeNamespace
variable {G : Type*} [Group G]  -- manually reconstructed

theorem test_theorem {p : G × N} : p ∈ H.prod K ↔ ... := by
  <test_tactic>
```

**Rationale:**
- Lean's import system handles ALL context automatically
- No manual parsing required
- Works for ALL theorems regardless of complexity
- Simple and maintainable

### FR-2: Theorem Type Extraction
**Priority:** CRITICAL  
**Requirement:** Theorem types MUST be extracted using LeanInteract, not manual parsing

**Specification:**
- Use `LeanInteractQuerier.extract_declarations()` to get `Declaration` objects
- Use `Declaration.type` field for the theorem type
- NEVER manually parse source text to extract types

**Rationale:**
- LeanInteract provides accurate, parsed type information
- Avoids all parsing bugs (wrong `:` detection, binder corruption, etc.)
- Reliable across all theorem signatures

### FR-3: Import Path Conversion
**Priority:** HIGH  
**Requirement:** File paths MUST be correctly converted to Lean import paths

**Specification:**
- Convert file path to import path: `"Fixtures/Algebra/Group.lean"` → `"Fixtures.Algebra.Group"`
- Handle nested directories correctly
- Strip `.lean` extension
- Replace `/` and `\` with `.`

**Edge Cases:**
- User provides path with extra prefix: `"fixtures/mathlib/Fixtures/..."` → extract just `"Fixtures..."`
- Relative vs absolute paths
- Windows vs Unix path separators

### FR-4: Example vs Theorem
**Priority:** HIGH  
**Requirement:** Test harnesses MUST use `example` not `theorem`

**Specification:**
```lean
-- CORRECT:
example : <type> := by <proof>

-- WRONG:
theorem test_name : <type> := by <proof>  -- Error: "already declared"
```

**Rationale:**
- Original theorem is already declared in imported file
- Using `theorem` causes "already declared" error
- `example` tests the same type without declaring a new theorem

### FR-5: Import Order
**Priority:** CRITICAL  
**Requirement:** ALL imports MUST be at line 1 of generated files

**Specification:**
```lean
Line 1: import OriginalFile
Line 2: import Aesop  -- if needed
Line 3: [blank line]
Line 4: -- Comment
Line 5: example : ...
```

**NEVER:**
```lean
Line 1: namespace Something  -- WRONG!
Line 2: [other code]
Line 3: import OriginalFile  -- ERROR: imports must be at top
```

**Rationale:**
- Lean requires ALL imports at the beginning of the file
- Bug report shows "invalid 'import' command" at line 3

## Non-Functional Requirements

### NFR-1: Reliability
- Test harnesses MUST compile without syntax errors
- Success rate MUST be > 95% (currently 0%)
- No "unexpected token" errors
- No "invalid binder annotation" errors

### NFR-2: Maintainability
- Use Lean's import system (infrastructure) not custom parsing (fragile)
- Minimal code complexity
- Easy to debug (generated code is readable)

### NFR-3: Performance
- Harness generation MUST be fast (< 100ms)
- Can cache querier results if needed
- No unnecessary file I/O

### NFR-4: Compatibility
- Works with all Lean 4 theorem signatures
- Handles Unicode correctly
- Supports all parameter types (explicit, implicit, instance, named instance)

## Affected Components

### 1. Probe Tool (`probe_domain.py`)
**Current Status:** BROKEN - uses manual parsing  
**Issue:** Manual parsing code causes 100% failure rate  
**Fix Required:** 
1. **OBLITERATE** all manual parsing functions (lines ~681-830)
2. Replace with ImportBasedHarnessConstructor using LeanInteractQuerier
3. Remove ALL references to removed functions

### 2. Validator (`validator.py`)
**Current Status:** ✅ CORRECT - already uses import-based approach  
**Issue:** None  
**Action:** Keep as-is, use as reference implementation

### 3. Search Orchestrator (`search_orchestrator.py`)
**Current Status:** Not yet implemented  
**Action:** Implement using ImportBasedHarnessConstructor pattern

### 4. Search Annotations Tool
**Current Status:** EXISTS (should not)  
**Issue:** Not in requirements, should not exist  
**Action:** **OBLITERATE COMPLETELY** - remove all files, tests, documentation, references

## Success Criteria

### Phase 0: Complete Code Removal (BLOCKING)
- [ ] All manual parsing functions removed from probe_domain.py
- [ ] search_annotations tool completely removed
- [ ] All legacy harness code removed
- [ ] No grep matches for removed function names
- [ ] Codebase compiles (tests may fail, but no import errors)

### Phase 1: Fix Type Extraction (BLOCKING)
- [ ] Probe tool uses LeanInteractQuerier for type extraction
- [ ] All test harnesses compile without syntax errors
- [ ] No "unexpected token '('" errors
- [ ] No "invalid 'import' command" errors

### Phase 2: Validation (REQUIRED)
- [ ] Test with 14 theorems from bug report
- [ ] 100% of harnesses compile successfully
- [ ] Automation can attempt proofs (may fail to prove, but no syntax errors)
- [ ] All three tools (probe, try_automated_proof, search) work

### Phase 3: Integration (DESIRED)
- [ ] Integration tests with real Lean files
- [ ] Performance benchmarks
- [ ] Documentation updated
- [ ] User guide with examples

## Out of Scope

- Improving automation success rates (that's a separate problem)
- Adding new automation modes
- Optimizing proof search strategies
- UI/UX improvements

## Dependencies

- LeanInteract library (already used)
- ServerManager (already implemented)
- LeanInteractQuerier (already implemented)

## Risks and Mitigations

### Risk 1: Querier Performance
**Risk:** Querier might be slow for large files  
**Mitigation:** Cache querier results, use instance-level caching

### Risk 2: Import Path Detection
**Risk:** User provides path with extra prefix directories  
**Mitigation:** Detect Lean project root, normalize paths

### Risk 3: Backward Compatibility
**Risk:** Changing harness format might break existing tests  
**Mitigation:** Keep fallback behavior, add feature flags if needed

## Timeline

- **Phase 1 (Fix Type Extraction):** 1-2 hours
- **Phase 2 (Validation):** 1 hour
- **Phase 3 (Integration):** 2-3 hours
- **Total:** 4-6 hours

## References

- Bug Report: "MCP Server Critical Bug Report - FINAL ANALYSIS"
- Existing Implementation: `probe_domain.py` lines 681-830
- Fixed Implementation: `validator.py` `_construct_validation_with_import`
- LeanInteract Documentation: https://github.com/lean-dojo/LeanInfer

---

**Status:** DRAFT  
**Created:** 2026-01-31  
**Priority:** P0 - CRITICAL (blocks all proof automation features)
