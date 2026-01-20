# Requirements: Static Analysis Tools (scan_file & scan_theorem)

## Overview
Implement static analysis tools for Lean proof files using a phased approach: stubs → tests → implementation. The tools share a common core for parsing, indexing, and feature extraction, with thin wrappers for tool-specific logic.

**CRITICAL FIXES NEEDED**: Testing with real Mathlib files revealed major issues that must be addressed:
- **Name Collision Crisis**: 47+ theorems named "eval" in a single file
- **Proof Detection Failures**: ~30% "no proof found" for theorems that clearly have proofs  
- **Zero Automation Scores**: Many theorems with valid proofs get 0.0 scores

## User Stories

### 0. As a developer, I want crisp JSON schemas for both tools
**Acceptance Criteria:**
- 0.1 Create `docs/mcp/schemas/scan_theorem.json` with complete schema
- 0.2 Update `docs/mcp/schemas/scan_file.json` to include theorems array
- 0.3 Both schemas share common automation signal structure
- 0.4 Both schemas use common.json definitions for shared fields
- 0.5 Schemas are forward-extensible (can add fields without breaking clients)
- 0.6 scan_theorem supports two input modes: theorem_id or range

### 1. As a developer, I want scan_file to analyze a Lean file and return theorem metadata
**Acceptance Criteria:**
- 1.1 Tool accepts a file path as input
- 1.2 Tool returns valid JSON conforming to `docs/mcp/schemas/scan_file.json`
- 1.3 Response includes: api_version, status, run_id, tool, file, summary, diagnostics
- 1.4 Summary contains theorem_count and notes array
- 1.5 Tool emits stable theorem_id for each theorem (used by scan_theorem) **CRITICAL: Must be unique per file - zero name collisions**
- 1.6 Tool computes lightweight per-theorem features (proof length, tactic keywords)
- 1.7 Tool includes automation signals matching scan_theorem format:
  - whole_goal_potential: {aesop: float, grind: float}
  - subgoal_potential: {aesop: float, grind: float}
  - annotation_value: single float
- 1.8 Tool handles invalid input gracefully with fail status
- 1.9 Tool operates on static text analysis (no Lean execution)
- 1.10 Tool is deterministic (same input → same output)
- 1.11 Tool output has stable ordering (by theorem name + span)

### 2. As a developer, I want scan_theorem to deeply analyze a single theorem
**Acceptance Criteria:**
- 2.1 Tool accepts two input modes:
  - Mode A: theorem_id (string) + file (string) - preferred, uses stable ID from scan_file
  - Mode B: file (string) + range (start_line, end_line) - fallback for ambiguous names
- 2.2 Tool returns valid JSON conforming to `docs/mcp/schemas/scan_theorem.json`
- 2.3 Response includes: api_version, status, run_id, tool, file, target, theorem, diagnostics
- 2.4 Theorem object contains: name, kind (theorem|lemma|example|instance), location, structure, automation
- 2.5 Location includes: decl_start, decl_end, proof_start (optional), proof_end (optional)
- 2.6 Structure includes:
  - skeleton: ordered list of key tactics (e.g., ["intro", "induction", "cases"])
  - blocks: coarse segments with kind (skeleton|rewrite_simp|closing|unknown) and line spans
  - cases: optional shallow nesting with labels and line spans
- 2.7 Automation signals use per-tactic floats (0.0-1.0):
  - whole_goal_potential: {aesop: float, grind: float}
  - subgoal_potential: {aesop: float, grind: float}
  - annotation_value: single float
- 2.8 Tool handles missing theorems gracefully with fail status
- 2.9 Tool reuses file indexing logic from shared core
- 2.10 Tool does NOT attempt full tactic AST (shallow heuristics only)

### 3. As a developer, I want a shared core module for static analysis
**Acceptance Criteria:**
- 3.1 Core modules are independent of tool wrappers
- 3.2 Core modules handle source text representation and locations
- 3.3 Core modules provide Lean syntax utilities (comment stripping, tokenization)
- 3.4 Core modules build file indexes of theorem declarations
- 3.5 Core modules extract per-theorem features
- 3.6 Core modules segment proofs into blocks
- 3.7 Core modules compute automation scores
- 3.8 All core functions are pure (no I/O in core)

### 4. As a developer, I want contract tests to validate tool responses
**Acceptance Criteria:**
- 4.1 Tests validate JSON schema compliance
- 4.2 Tests verify required fields are present
- 4.3 Tests check field types and constraints
- 4.4 Tests validate deterministic behavior
- 4.5 Tests run without Lean installation
- 4.6 Tests use inline Lean snippets (no external files)

### 5. As a developer, I want phased implementation (stubs → tests → implementation)
**Acceptance Criteria:**
- 5.1 Phase 0: Create JSON schemas for both tools
- 5.2 Phase 1: Stubs return valid schema-compliant responses with placeholder data
  - scan_file stub returns empty theorems array
  - scan_theorem stub returns minimal theorem object with zero scores
- 5.3 Phase 2: Contract tests validate stub responses against schemas
  - Test JSON schema compliance
  - Test deterministic behavior
  - Test error handling
- 5.4 Phase 3: Core modules implement actual parsing and analysis
  - Implement in order: source → lean_syntax → indexer → features → segmenter → scoring
  - Each module has unit tests with inline Lean snippets
- 5.5 Phase 4: Tools integrate core modules and pass all tests
  - Update scan_file to use core modules
  - Implement scan_theorem using shared core
  - All contract tests pass
- 5.6 Each phase is independently testable and deployable

### 6. As a developer, I want the tools to work correctly on real Mathlib files
**Acceptance Criteria:**
- 6.1 **CRITICAL FIX**: Zero duplicate theorem_id values within any single file
- 6.2 **CRITICAL FIX**: <5% "no proof found" cases on well-formed Lean files (currently ~30%)
- 6.3 **CRITICAL FIX**: >90% of theorems with detected proofs get non-zero automation scores
- 6.4 Theorem names include sufficient context to distinguish overloads (e.g., "Polynomial.eval" vs "List.eval")
- 6.5 Anonymous theorems get deterministic unique identifiers (e.g., "example_42", "instance_15")
- 6.6 Improved proof boundary detection for both `:=` and `by` patterns
- 6.7 Better handling of multi-line declarations and complex proof structures
- 6.8 Enhanced tactic detection to avoid false negatives in scoring

## Schema Specifications

### scan_file Response Schema
```json
{
  "api_version": "0.1",
  "status": "success",
  "run_id": "unique-id",
  "tool": "scan_file",
  "file": "path/to/file.lean",
  "summary": {
    "theorem_count": 5,
    "notes": ["info messages"]
  },
  "theorems": [
    {
      "theorem_id": "Nat.mul_comm",
      "name": "mul_comm",
      "kind": "theorem",
      "location": {
        "decl_start": 10,
        "decl_end": 25,
        "proof_start": 12,
        "proof_end": 24
      },
      "automation": {
        "whole_goal_potential": {"aesop": 0.8, "grind": 0.3},
        "subgoal_potential": {"aesop": 0.6, "grind": 0.7},
        "annotation_value": 0.75
      },
      "notes": ["long proof", "uses induction"]
    }
  ],
  "diagnostics": []
}
```

### scan_theorem Response Schema
```json
{
  "api_version": "0.1",
  "status": "success",
  "run_id": "unique-id",
  "tool": "scan_theorem",
  "file": "path/to/file.lean",
  "target": {
    "theorem_id": "Nat.mul_comm"
    // OR: "range": {"start_line": 10, "end_line": 25}
  },
  "theorem": {
    "name": "mul_comm",
    "kind": "theorem",
    "location": {
      "decl_start": 10,
      "decl_end": 25,
      "proof_start": 12,
      "proof_end": 24
    },
    "structure": {
      "skeleton": ["intro", "induction", "cases"],
      "blocks": [
        {"kind": "skeleton", "start_line": 12, "end_line": 15},
        {"kind": "rewrite_simp", "start_line": 16, "end_line": 20},
        {"kind": "closing", "start_line": 21, "end_line": 24}
      ],
      "cases": [
        {"label": "zero", "start_line": 13, "end_line": 15},
        {"label": "succ", "start_line": 16, "end_line": 24}
      ]
    },
    "automation": {
      "whole_goal_potential": {"aesop": 0.8, "grind": 0.3},
      "subgoal_potential": {"aesop": 0.6, "grind": 0.7},
      "annotation_value": 0.75
    },
    "notes": ["long proof", "uses induction", "rewrite-heavy middle section"]
  },
  "diagnostics": []
}
```

### Input Schemas

**scan_file input:**
```json
{
  "file": "path/to/file.lean"
}
```

**scan_theorem input (Mode A - preferred):**
```json
{
  "file": "path/to/file.lean",
  "target": {
    "theorem_id": "Nat.mul_comm"
  }
}
```

**scan_theorem input (Mode B - fallback):**
```json
{
  "file": "path/to/file.lean",
  "target": {
    "range": {
      "start_line": 10,
      "end_line": 25
    }
  }
}
```

## Technical Constraints

### Contract Coherence
- Both tools share identical automation signal structure
- Both tools share identical diagnostics array structure
- Both tools use stable theorem_id concept
- Both tools produce deterministic, stably-ordered output
- This makes rank_targets trivial: consumes same signals from both tools

### Architecture
- Follow hexagonal architecture: core logic separate from I/O
- Use dependency injection for all external dependencies
- Tools are thin wrappers over shared core
- Core modules expose pure functions

### Data Flow
```
File → Tool Wrapper → Core Indexer → Core Features → Core Scoring → JSON Response
```

### Module Structure
```
src/lean_proof_auto_mcp/
  core/
    source.py       # SourceText, Span
    lean_syntax.py  # Comment stripping, tokenization
    indexer.py      # FileIndex, TheoremDecl
    features.py     # TheoremFeatures extraction
    segmenter.py    # ProofStructure segmentation
    scoring.py      # AutomationProfile computation
    format.py       # JSON normalization
  tools/
    scan_file.py    # File-level analysis wrapper
    scan_theorem.py # Theorem-level analysis wrapper
```

### Schema Compliance
- All responses must conform to JSON schemas in `docs/mcp/schemas/`
- Use common.json definitions for shared fields
- Validate against schemas in contract tests

### Testing Strategy
- Unit tests for each core module with inline Lean snippets
- Contract tests for tool JSON responses (validate against schemas)
- Property-based tests for determinism and invariants using Hypothesis
- No Lean installation required for tests
- Fast CI: all tests run in <10 seconds

## Non-Functional Requirements

### Performance
- scan_file should analyze typical files (<1000 lines) in <100ms
- scan_theorem should analyze typical theorems in <50ms
- No external process calls (Lean, lake, etc.)

### Reliability
- Deterministic: same input always produces same output
- Graceful degradation: partial results on parse errors
- Clear error messages in diagnostics array

### Maintainability
- Pure functions for core logic
- Clear separation between parsing and scoring
- Extensible for future tactics and patterns

## Out of Scope (v0.1)
- Perfect Lean parsing (heuristic regex is acceptable)
- Tactic execution or proof checking
- File watching or incremental updates
- Caching or persistence
- Multi-file analysis or dependency tracking

## Dependencies
- Python 3.11+
- No Lean runtime required
- jsonschema library for schema validation in tests
- hypothesis library for property-based testing

## Success Metrics
- All contract tests pass
- Core modules have >90% test coverage
- Tools return valid JSON for all test cases
- Zero external process dependencies
- **CRITICAL SUCCESS METRICS**:
  - **Name Collision Resolution**: 0 duplicate theorem_id values per file (was 47+ "eval" theorems)
  - **Proof Detection Accuracy**: <5% "no proof found" cases (was ~30%)
  - **Automation Scoring Coverage**: >90% of detected proofs get meaningful scores (was many zeros)
