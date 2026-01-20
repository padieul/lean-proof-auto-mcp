# Design: Static Analysis Tools (scan_file & scan_theorem)

## Architecture Overview

This design follows hexagonal architecture with a shared core for static analysis and thin tool wrappers. The implementation is phased: schemas → stubs → tests → core → integration.

### Design Principles
1. **Separation of Concerns**: Core logic (parsing, analysis) separate from I/O (file reading, JSON formatting)
2. **Pure Functions**: Core modules are pure, deterministic, testable without I/O
3. **Shared Foundation**: Both tools reuse the same indexing and feature extraction
4. **Contract-First**: JSON schemas define the contract before implementation
5. **Incremental Delivery**: Each phase is independently deployable

### High-Level Data Flow
```
Input (file path)
  → Tool Wrapper (I/O boundary)
    → Core Indexer (find theorems)
      → Core Features (extract signals)
        → Core Scoring (compute automation potential)
          → Core Format (normalize output)
  → Tool Wrapper (JSON response)
→ Output (schema-compliant JSON)
```

## Phase 0: JSON Schemas

### Deliverables
1. Create `docs/mcp/schemas/scan_theorem.json`
2. Update `docs/mcp/schemas/scan_file.json` to include theorems array

### Schema Design Decisions

**Shared Structures** (defined once, used by both):
- `automation` object: per-tactic floats + annotation_value
- `location` object: decl_start, decl_end, proof_start, proof_end
- `diagnostics` array: from common.json

**scan_file Additions**:
- `theorems` array (optional): list of theorem objects with automation signals
- Each theorem has `theorem_id` (stable identifier for scan_theorem)

**scan_theorem Specifics**:
- `target` object: supports theorem_id OR range (two input modes)
- `structure` object: skeleton, blocks, cases (proof segmentation)
- `theorem` object: full analysis including structure


## Phase 1: Stubs

### Goal
Provide schema-compliant responses with placeholder data. Stubs enable contract testing before implementation.

### scan_file Stub Behavior
- Accept `file` argument, validate non-empty string
- Return deterministic run_id (e.g., "scan-file-stub-001")
- Return empty `theorems` array
- Return `summary` with theorem_count=0 and stub notes
- Handle invalid input with fail status

### scan_theorem Stub Behavior
- Accept `file` and `target` arguments
- Validate target has either theorem_id or range
- Return deterministic run_id (e.g., "scan-theorem-stub-001")
- Return minimal theorem object:
  - name: echo theorem_id or "theorem_at_line_X"
  - kind: "theorem"
  - location: echo input range or placeholder
  - structure: empty skeleton, empty blocks
  - automation: all zeros
- Handle invalid input with fail status

### Implementation Notes
- Stubs are in `tools/scan_file.py` and `tools/scan_theorem.py`
- No core modules needed yet
- Focus: valid JSON, correct schema compliance
- Deterministic for testing (no UUIDs yet)


## Phase 2: Contract Tests

### Goal
Validate tool responses against JSON schemas. Tests run without Lean, use inline snippets.

### Test Structure
```
tests/
  mcp_contract/
    test_scan_file_contract.py
    test_scan_theorem_contract.py
  fixtures/
    lean_snippets.py  # inline Lean code strings
```

### scan_file Contract Tests
1. **Schema Compliance**: Validate response against scan_file.json schema
2. **Required Fields**: api_version, status, run_id, tool, file, summary present
3. **Field Types**: theorem_count is int, notes is array of strings
4. **Determinism**: Same input produces same output
5. **Error Handling**: Invalid file path returns fail status
6. **Theorems Array**: When present, each theorem has required fields

### scan_theorem Contract Tests
1. **Schema Compliance**: Validate response against scan_theorem.json schema
2. **Required Fields**: All top-level and nested fields present
3. **Input Modes**: Both theorem_id and range modes work
4. **Structure Validation**: skeleton is array, blocks have required fields
5. **Automation Ranges**: All floats are 0.0-1.0
6. **Determinism**: Same input produces same output
7. **Error Handling**: Missing theorem returns fail status

### Test Implementation
- Use `jsonschema` library for validation
- Use `hypothesis` for property-based determinism tests
- Inline Lean snippets as strings (no file I/O)
- Fast: all tests <1 second


## Phase 3: Core Modules

### Module 1: core/source.py

**Responsibility**: Represent source text and locations

**Data Classes**:
```python
@dataclass(frozen=True)
class Span:
    start_line: int
    start_col: int  # optional in v0.1, can default to 0
    end_line: int
    end_col: int    # optional in v0.1, can default to 0

@dataclass(frozen=True)
class SourceText:
    path: str
    text: str

    def get_lines(self, start: int, end: int) -> list[str]:
        """Extract lines [start, end] (1-indexed)"""

    def get_span_text(self, span: Span) -> str:
        """Extract text within span"""
```

**Functions**:
- `get_lines(source, start, end)`: safe line slicing with bounds checking
- `get_span_text(source, span)`: extract text from span
- `line_count(source)`: total lines

**Tests**: Inline text strings, test boundary conditions


### Module 2: core/lean_syntax.py

**Responsibility**: Lightweight Lean tokenization utilities

**Functions**:
```python
def strip_comments(text: str) -> str:
    """Remove -- and /- -/ comments (imperfect is OK for v0.1)"""

def detect_string_literals(text: str) -> list[Span]:
    """Find string literal spans to avoid false positives"""

def normalize_whitespace(text: str) -> str:
    """Normalize indentation for consistent parsing"""

def get_indentation_level(line: str) -> int:
    """Count leading spaces/tabs"""
```

**Implementation Notes**:
- Use regex for comment detection
- Handle nested /- -/ comments (simple stack-based)
- String literals: match "..." patterns
- Imperfect is acceptable: focus on common cases

**Tests**: Inline Lean snippets with comments, strings, mixed indentation


### Module 3: core/indexer.py

**Responsibility**: Build file index of theorem declarations

**Data Classes**:
```python
@dataclass(frozen=True)
class TheoremDecl:
    theorem_id: str  # stable identifier (e.g., "Nat.mul_comm")
    name: str        # short name (e.g., "mul_comm")
    kind: str        # "theorem" | "lemma" | "example" | "instance"
    decl_span: Span  # where declaration starts
    proof_span: Span | None  # where proof lives (if found)
    attributes: list[str]  # @[...] annotations (optional v0.1)

@dataclass(frozen=True)
class FileIndex:
    file: str
    decls: list[TheoremDecl]
```

**Functions**:
```python
def build_index(source: SourceText) -> FileIndex:
    """Find all theorem-like declarations in file"""

def find_by_id(index: FileIndex, theorem_id: str) -> TheoremDecl | None:
    """Lookup theorem by stable ID"""

def find_by_range(index: FileIndex, start: int, end: int) -> TheoremDecl | None:
    """Lookup theorem by line range"""
```

**Detection Strategy**:
1. Regex for `theorem|lemma|example|instance` keywords
2. Find declaration span (keyword to `:=` or `by`)
3. Find proof span (`by` to end of proof block)
4. Extract name from declaration
5. Generate stable theorem_id (namespace + name)

**Tests**: Inline Lean with various theorem styles


### Module 4: core/features.py

**Responsibility**: Extract per-theorem features from text

**Data Classes**:
```python
@dataclass(frozen=True)
class TheoremFeatures:
    proof_lines: int
    tactic_kinds: set[str]  # detected tactics
    has_induction: bool
    has_cases: bool
    rewrite_count: int
    simp_count: int
    local_lemmas_count: int  # have, suffices, let
    confidence: float  # how sure we found the proof (0.0-1.0)
```

**Functions**:
```python
def extract_features(source: SourceText, decl: TheoremDecl) -> TheoremFeatures:
    """Compute features from theorem proof span"""

def detect_tactics(proof_text: str) -> set[str]:
    """Find tactic keywords in proof"""

def count_rewrites(proof_text: str) -> int:
    """Count rw, rewrite occurrences"""

def count_local_lemmas(proof_text: str) -> int:
    """Count have, suffices, let"""
```

**Tactic Detection**:
- Regex for common tactics: intro, induction, cases, rw, simp, apply, exact, etc.
- Avoid false positives in comments/strings (use lean_syntax utilities)
- Count occurrences for density metrics

**Tests**: Inline proofs with various tactic patterns


### Module 5: core/segmenter.py

**Responsibility**: Segment proof into coarse blocks

**Data Classes**:
```python
@dataclass(frozen=True)
class ProofBlock:
    kind: str  # "skeleton" | "rewrite_simp" | "closing" | "unknown"
    span: Span

@dataclass(frozen=True)
class CaseBlock:
    label: str  # "zero", "succ", etc.
    span: Span

@dataclass(frozen=True)
class ProofStructure:
    skeleton: list[str]  # ordered key tactics
    blocks: list[ProofBlock]
    cases: list[CaseBlock]
```

**Functions**:
```python
def segment_proof(source: SourceText, decl: TheoremDecl) -> ProofStructure:
    """Segment proof into skeleton + blocks"""

def extract_skeleton(proof_text: str) -> list[str]:
    """Find top-level structural tactics"""

def identify_blocks(proof_lines: list[str]) -> list[ProofBlock]:
    """Classify contiguous regions by dominant tactic type"""

def extract_cases(proof_text: str) -> list[CaseBlock]:
    """Find case/induction branches (shallow only)"""
```

**Segmentation Strategy**:
1. Extract skeleton: intro, induction, cases, apply (top-level only)
2. Identify blocks by dominant pattern:
   - rewrite_simp: high density of rw/simp
   - closing: exact, rfl, trivial, done
   - skeleton: structural tactics
   - unknown: mixed or unclear
3. Extract case labels from `case` or `·` patterns

**Tests**: Inline proofs with clear structure


### Module 6: core/scoring.py

**Responsibility**: Compute automation potential scores

**Data Classes**:
```python
@dataclass(frozen=True)
class AutomationProfile:
    whole_goal_potential: dict[str, float]  # {"aesop": 0.8, "grind": 0.3}
    subgoal_potential: dict[str, float]
    annotation_value: float
    notes: list[str]
```

**Functions**:
```python
def compute_profile(
    features: TheoremFeatures,
    structure: ProofStructure | None = None
) -> AutomationProfile:
    """Compute automation scores from features"""

def score_aesop_potential(features: TheoremFeatures) -> float:
    """Heuristic: aesop works well on structural proofs"""

def score_grind_potential(features: TheoremFeatures) -> float:
    """Heuristic: grind works well on rewrite-heavy proofs"""

def score_annotation_value(features: TheoremFeatures) -> float:
    """ROI estimate: long proof + patterns + local lemmas"""
```

**Scoring Heuristics** (v0.1 simple rules):
- **aesop whole_goal**: high if short proof, structural tactics, no rewrites
- **grind whole_goal**: high if rewrite-heavy, no induction/cases
- **aesop subgoal**: high if has induction/cases (can automate branches)
- **grind subgoal**: high if has rewrite blocks
- **annotation_value**: high if long proof (>20 lines) + repeated patterns

**Tests**: Feature objects with known patterns, verify score ranges


### Module 7: core/format.py

**Responsibility**: Normalize JSON output for determinism

**Functions**:
```python
def stable_sort_theorems(theorems: list[dict]) -> list[dict]:
    """Sort by theorem_id for deterministic output"""

def normalize_notes(notes: list[str], max_length: int = 200) -> list[str]:
    """Trim note length, cap count"""

def ensure_deterministic(data: dict) -> dict:
    """Ensure all lists are sorted, floats rounded consistently"""
```

**Normalization Rules**:
- Sort theorems by theorem_id (lexicographic)
- Sort skeleton tactics (preserve order, but stable)
- Round floats to 2 decimal places
- Cap notes array at 10 items
- Trim individual notes to 200 chars

**Tests**: Verify sorting, rounding, capping


## Phase 4: Tool Integration

### scan_file Integration

**Updated Implementation**:
```python
def scan_file(args: dict[str, Any]) -> dict[str, Any]:
    # 1. Coerce args
    parsed = _coerce_args(args)

    # 2. Read file (I/O boundary)
    try:
        with open(parsed.file) as f:
            text = f.read()
    except FileNotFoundError:
        return error_response(...)

    # 3. Build source
    source = SourceText(path=parsed.file, text=text)

    # 4. Index file
    index = build_index(source)

    # 5. Extract features for each theorem
    theorems = []
    for decl in index.decls:
        features = extract_features(source, decl)
        profile = compute_profile(features, structure=None)
        theorems.append({
            "theorem_id": decl.theorem_id,
            "name": decl.name,
            "kind": decl.kind,
            "location": {...},
            "automation": {...},
            "notes": profile.notes
        })

    # 6. Format response
    theorems = stable_sort_theorems(theorems)
    return {
        "api_version": API_VERSION,
        "status": "success",
        "run_id": generate_run_id(),
        "tool": "scan_file",
        "file": parsed.file,
        "summary": {
            "theorem_count": len(theorems),
            "notes": [...]
        },
        "theorems": theorems,
        "diagnostics": []
    }
```

**Key Changes from Stub**:
- Read actual file
- Call core modules
- Return real theorem data
- Generate unique run_id (UUID)


### scan_theorem Integration

**Implementation**:
```python
def scan_theorem(args: dict[str, Any]) -> dict[str, Any]:
    # 1. Coerce args
    parsed = _coerce_args(args)

    # 2. Read file
    try:
        with open(parsed.file) as f:
            text = f.read()
    except FileNotFoundError:
        return error_response(...)

    # 3. Build source and index
    source = SourceText(path=parsed.file, text=text)
    index = build_index(source)

    # 4. Find target theorem
    if parsed.target.theorem_id:
        decl = find_by_id(index, parsed.target.theorem_id)
    else:
        decl = find_by_range(index, parsed.target.range.start_line,
                             parsed.target.range.end_line)

    if not decl:
        return fail_response("theorem not found")

    # 5. Extract features and structure
    features = extract_features(source, decl)
    structure = segment_proof(source, decl)
    profile = compute_profile(features, structure)

    # 6. Format response
    return {
        "api_version": API_VERSION,
        "status": "success",
        "run_id": generate_run_id(),
        "tool": "scan_theorem",
        "file": parsed.file,
        "target": {...},
        "theorem": {
            "name": decl.name,
            "kind": decl.kind,
            "location": {...},
            "structure": {
                "skeleton": structure.skeleton,
                "blocks": [...],
                "cases": [...]
            },
            "automation": {...},
            "notes": profile.notes
        },
        "diagnostics": []
    }
```

**Key Differences from scan_file**:
- Finds single theorem (by ID or range)
- Calls segmenter for deep structure
- Returns full structure object


## Error Handling Strategy

### Error Categories
1. **Invalid Input**: Missing/wrong args → fail status
2. **File Not Found**: File doesn't exist → fail status
3. **Parse Errors**: Can't parse Lean → partial results + diagnostics
4. **Theorem Not Found**: scan_theorem can't find target → fail status

### Diagnostic Messages
- Use `diagnostics` array for warnings and errors
- Include location when possible (line, col)
- Severity levels: info, warning, error

### Graceful Degradation
- If indexer finds some theorems but fails on others: return partial results
- If feature extraction fails: return theorem with zero scores + diagnostic
- If segmentation fails: return empty structure + diagnostic

### Example Error Response
```json
{
  "api_version": "0.1",
  "status": "fail",
  "run_id": "...",
  "tool": "scan_theorem",
  "file": "test.lean",
  "target": {"theorem_id": "missing"},
  "theorem": null,
  "diagnostics": [
    {
      "severity": "error",
      "message": "theorem 'missing' not found in file"
    }
  ]
}
```


## Testing Strategy

### Unit Tests (Core Modules)
**Location**: `tests/unit/core/`

**Coverage**:
- `test_source.py`: SourceText, Span, line slicing
- `test_lean_syntax.py`: comment stripping, string detection
- `test_indexer.py`: theorem detection, ID generation
- `test_features.py`: tactic detection, counting
- `test_segmenter.py`: block classification, case extraction
- `test_scoring.py`: score computation, heuristics
- `test_format.py`: sorting, normalization

**Approach**:
- Inline Lean snippets as strings
- Test boundary conditions
- Test error cases
- Fast: <5 seconds total

### Contract Tests (Tools)
**Location**: `tests/mcp_contract/`

**Coverage**:
- `test_scan_file_contract.py`: schema compliance, determinism
- `test_scan_theorem_contract.py`: schema compliance, both input modes

**Approach**:
- Use `jsonschema` for validation
- Test with stub responses first
- Test with real implementation after Phase 4
- Verify determinism with repeated calls

### Property-Based Tests
**Location**: `tests/property/`

**Coverage**:
- Determinism: same input → same output
- Idempotence: repeated calls → same result
- Monotonicity: more proof lines → higher annotation_value
- Bounds: all scores in [0.0, 1.0]

**Approach**:
- Use `hypothesis` library
- Generate random Lean-like text
- Verify invariants hold


## Implementation Order

### Phase 0: Schemas (Day 1)
1. Create `scan_theorem.json` schema
2. Update `scan_file.json` schema with theorems array
3. Validate schemas with online validator

### Phase 1: Stubs (Day 1)
1. Update `scan_file.py` stub to include empty theorems array
2. Create `scan_theorem.py` stub with minimal theorem object
3. Manual test: call stubs, inspect JSON

### Phase 2: Contract Tests (Day 2)
1. Set up test infrastructure (jsonschema, hypothesis)
2. Write `test_scan_file_contract.py`
3. Write `test_scan_theorem_contract.py`
4. Verify stubs pass all contract tests

### Phase 3: Core Modules (Days 3-5)
**Day 3**: Foundation
1. Implement `core/source.py`
2. Implement `core/lean_syntax.py`
3. Write unit tests for both

**Day 4**: Indexing and Features
1. Implement `core/indexer.py`
2. Implement `core/features.py`
3. Write unit tests for both

**Day 5**: Analysis and Formatting
1. Implement `core/segmenter.py`
2. Implement `core/scoring.py`
3. Implement `core/format.py`
4. Write unit tests for all three

### Phase 4: Integration (Day 6)
1. Update `scan_file.py` to use core modules
2. Implement `scan_theorem.py` using core modules
3. Run all contract tests
4. Fix any failures
5. Run property-based tests
6. Final validation


## Correctness Properties

These properties must hold for the implementation to be correct. They will be validated using property-based testing.

### Property 1: Determinism
**Validates: Requirements 1.10, 2.9**

For any valid input, calling the tool multiple times produces identical output.

```python
@given(file_path=valid_lean_files())
def test_scan_file_deterministic(file_path):
    result1 = scan_file({"file": file_path})
    result2 = scan_file({"file": file_path})
    assert result1 == result2
```

### Property 2: Schema Compliance
**Validates: Requirements 1.2, 2.2**

All tool responses conform to their JSON schemas.

```python
@given(file_path=valid_lean_files())
def test_scan_file_schema_compliance(file_path):
    result = scan_file({"file": file_path})
    validate(instance=result, schema=scan_file_schema)
```

### Property 3: Score Bounds
**Validates: Requirements 1.7, 2.7**

All automation scores are in the range [0.0, 1.0].

```python
@given(file_path=valid_lean_files())
def test_automation_scores_bounded(file_path):
    result = scan_file({"file": file_path})
    for theorem in result.get("theorems", []):
        auto = theorem["automation"]
        assert 0.0 <= auto["whole_goal_potential"]["aesop"] <= 1.0
        assert 0.0 <= auto["whole_goal_potential"]["grind"] <= 1.0
        assert 0.0 <= auto["subgoal_potential"]["aesop"] <= 1.0
        assert 0.0 <= auto["subgoal_potential"]["grind"] <= 1.0
        assert 0.0 <= auto["annotation_value"] <= 1.0
```

### Property 4: Stable Ordering
**Validates: Requirements 1.11**

Theorems are always returned in the same order (sorted by theorem_id).

```python
@given(file_path=valid_lean_files())
def test_theorems_stable_order(file_path):
    result = scan_file({"file": file_path})
    theorems = result.get("theorems", [])
    theorem_ids = [t["theorem_id"] for t in theorems]
    assert theorem_ids == sorted(theorem_ids)
```

### Property 5: Theorem Count Consistency
**Validates: Requirements 1.4**

The summary theorem_count matches the length of the theorems array.

```python
@given(file_path=valid_lean_files())
def test_theorem_count_consistent(file_path):
    result = scan_file({"file": file_path})
    summary_count = result["summary"]["theorem_count"]
    actual_count = len(result.get("theorems", []))
    assert summary_count == actual_count
```

### Property 6: Location Validity
**Validates: Requirements 2.5**

All location line numbers are positive and decl_start <= decl_end.

```python
@given(file_path=valid_lean_files())
def test_location_validity(file_path):
    result = scan_file({"file": file_path})
    for theorem in result.get("theorems", []):
        loc = theorem["location"]
        assert loc["decl_start"] >= 1
        assert loc["decl_end"] >= loc["decl_start"]
        if "proof_start" in loc:
            assert loc["proof_start"] >= loc["decl_start"]
            assert loc["proof_end"] >= loc["proof_start"]
```

### Property 7: Target Echo
**Validates: Requirements 2.3**

scan_theorem echoes the input target in the response.

```python
@given(file_path=valid_lean_files(), theorem_id=valid_theorem_ids())
def test_target_echo(file_path, theorem_id):
    result = scan_theorem({
        "file": file_path,
        "target": {"theorem_id": theorem_id}
    })
    if result["status"] == "success":
        assert result["target"]["theorem_id"] == theorem_id
```


## Risk Mitigation

### Risk 1: Imperfect Lean Parsing
**Impact**: May miss theorems or misidentify proof boundaries

**Mitigation**:
- Use confidence scores in features
- Include diagnostics for uncertain cases
- Test with diverse Lean styles
- Accept imperfection in v0.1, iterate based on real usage

### Risk 2: Performance on Large Files
**Impact**: May exceed 100ms target on very large files

**Mitigation**:
- Profile with realistic files
- Optimize hot paths (regex, line iteration)
- Consider early exit for scan_file if >1000 theorems
- Document performance characteristics

### Risk 3: Schema Evolution
**Impact**: Future changes may break clients

**Mitigation**:
- Design schemas to be forward-extensible
- Use optional fields for new features
- Version API (bump minor for compatible changes)
- Document breaking changes clearly

### Risk 4: Test Coverage Gaps
**Impact**: Bugs in edge cases not caught by tests

**Mitigation**:
- Use property-based testing for invariants
- Test with real Lean files from Mathlib
- Collect failure cases and add regression tests
- Aim for >90% code coverage


## Phase 5: Critical Architectural Fixes for Mathlib Files

### Overview
Testing with real Mathlib files revealed three critical architectural issues that require immediate fixes to the core modules. These fixes address fundamental problems with name collisions, proof detection accuracy, and automation scoring coverage.

### Issue 1: Theorem Name Collisions (CRITICAL)

**Problem**: Current implementation generates duplicate theorem_id values when multiple theorems have the same name (e.g., 47+ "eval" theorems in Defs.lean).

**Root Cause**: The `build_index()` function in `core/indexer.py` uses only the theorem name for `theorem_id` generation, ignoring namespace context and position-based disambiguation.

**Architectural Solution**:

**Enhanced theorem_id Generation Strategy**:
```python
def _generate_unique_theorem_id(full_name: str, kind: str, start_line: int,
                               existing_ids: Set[str]) -> str:
    """Generate unique theorem_id with collision resolution.

    Strategy:
    1. Use full namespace path if available (e.g., "Polynomial.eval")
    2. For unnamed theorems, use kind + line number (e.g., "example_42")
    3. For collisions, append line number (e.g., "eval_123")
    4. Ensure uniqueness within file scope
    """
```

**Core Module Changes**:
- **core/indexer.py**: Update `build_index()` to track existing theorem_id values and resolve collisions
- **core/indexer.py**: Enhance namespace extraction from full theorem names
- **core/indexer.py**: Add position-based disambiguation for anonymous theorems
- **core/format.py**: Update sorting to handle new theorem_id format

**Backward Compatibility**: Existing tests continue to work as theorem_id format is enhanced, not changed fundamentally.

### Issue 2: Proof Boundary Detection Failures (CRITICAL)

**Problem**: Current implementation fails to detect proofs in ~30% of valid theorems, particularly with multi-line declarations and complex proof structures.

**Root Cause**: The `_find_declaration_spans()` function in `core/indexer.py` uses overly restrictive regex patterns and insufficient lookahead for proof markers.

**Architectural Solution**:

**Enhanced Proof Detection Strategy**:
```python
def _find_declaration_spans_enhanced(lines: List[str], start_line: int,
                                   start_col: int) -> tuple[Optional[Span], Optional[Span]]:
    """Improved declaration and proof span detection.

    Enhancements:
    1. Multi-line declaration support (theorem name on different line than colon)
    2. Better := vs by detection with context awareness
    3. Improved indentation-based proof end detection
    4. Handling of nested proof structures (have, suffices blocks)
    5. Better term-mode vs tactic-mode distinction
    """
```

**Core Module Changes**:
- **core/indexer.py**: Replace `_find_declaration_spans()` with enhanced multi-line aware version
- **core/indexer.py**: Improve `_find_proof_end()` with better indentation analysis
- **core/indexer.py**: Add `_find_term_proof_end()` enhancements for complex expressions
- **core/indexer.py**: Better handling of proof keywords (`by`, `:=`, `where`) in various contexts

**Detection Improvements**:
- Support theorem declarations spanning multiple lines
- Better recognition of proof start markers in various syntactic contexts
- Enhanced indentation-based proof boundary detection
- Improved handling of nested proof constructs

### Issue 3: Automation Scoring False Negatives (CRITICAL)

**Problem**: Many theorems with valid detected proofs receive 0.0 automation scores due to tactic detection failures and poor confidence scoring.

**Root Cause**: The `detect_tactics()` function in `core/features.py` misses tactics due to context issues, and `_calculate_confidence()` is overly conservative.

**Architectural Solution**:

**Enhanced Tactic Detection Strategy**:
```python
def detect_tactics_enhanced(proof_text: str, source_context: SourceText,
                          proof_span: Span) -> Set[str]:
    """Improved tactic detection with context awareness.

    Enhancements:
    1. Better handling of tactic variants and aliases
    2. Context-aware detection (avoid false positives in strings/comments)
    3. Multi-line tactic recognition (tactics split across lines)
    4. Detection of tactic combinators (;, <;>, try, repeat)
    5. Recognition of custom tactics and macros
    """
```

**Enhanced Confidence Scoring**:
```python
def _calculate_confidence_enhanced(proof_text: str, proof_span: Span,
                                 tactic_kinds: Set[str], decl: TheoremDecl) -> float:
    """Improved confidence calculation with multiple signals.

    Signals:
    1. Proof structure quality (proper indentation, clear boundaries)
    2. Tactic diversity and appropriateness
    3. Proof length relative to declaration complexity
    4. Presence of proof keywords and markers
    5. Absence of suspicious patterns (incomplete proofs, errors)
    """
```

**Core Module Changes**:
- **core/features.py**: Replace `detect_tactics()` with enhanced context-aware version
- **core/features.py**: Update `_calculate_confidence()` with multi-signal approach
- **core/features.py**: Add tactic variant recognition (e.g., `simp_all`, `rw_mod_cast`)
- **core/features.py**: Improve proof text extraction quality assessment
- **core/scoring.py**: Update scoring heuristics to use enhanced confidence signals

### Implementation Strategy

**Phase 5.1: Unique Theorem ID Generation**
1. Update `core/indexer.py` with collision-aware theorem_id generation
2. Add namespace context extraction from full theorem names
3. Implement position-based disambiguation for anonymous theorems
4. Update tests to verify zero collisions on Mathlib files

**Phase 5.2: Enhanced Proof Detection**
1. Replace proof boundary detection with multi-line aware implementation
2. Improve indentation-based proof end detection
3. Add better support for complex proof structures
4. Test detection accuracy on real Mathlib files (target: <5% failures)

**Phase 5.3: Improved Automation Scoring**
1. Enhance tactic detection with context awareness and variant recognition
2. Update confidence scoring with multi-signal approach
3. Improve proof quality assessment
4. Test scoring coverage on real Mathlib files (target: >90% non-zero scores)

**Phase 5.4: Integration and Validation**
1. Run full test suite to ensure no regressions
2. Validate fixes against all three Mathlib test files
3. Measure improvement in success metrics
4. Document architectural changes and remaining limitations

### Backward Compatibility Strategy

**API Compatibility**: All JSON schemas remain unchanged - fixes are internal to core modules.

**Test Compatibility**: Existing unit tests and contract tests continue to pass with enhanced implementations.

**Behavioral Compatibility**: Tools produce the same output format with improved accuracy and coverage.

### Success Metrics for Phase 5

**Name Collision Resolution**:
- Before: 47+ duplicate "eval" theorem_id values in Defs.lean
- After: 0 duplicate theorem_id values in any file

**Proof Detection Accuracy**:
- Before: ~30% "no proof found" cases on valid theorems
- After: <5% "no proof found" cases on well-formed Lean files

**Automation Scoring Coverage**:
- Before: Many theorems with valid proofs get 0.0 scores
- After: >90% of theorems with detected proofs get non-zero automation scores

### Risk Mitigation

**Regression Risk**: Comprehensive test suite ensures existing functionality remains intact while fixes are applied.

**Performance Risk**: Enhanced algorithms maintain O(n) complexity for file processing, with minimal performance impact.

**Compatibility Risk**: Internal implementation changes do not affect external APIs or JSON schemas.

## Future Extensions (Post v0.1)

### Enhanced Parsing
- Better comment handling (nested /- -/)
- Attribute parsing (@[simp], @[aesop])
- Namespace tracking for better theorem_id
- Tactic macro expansion

### Richer Features
- Proof complexity metrics
- Dependency analysis (imports, uses)
- Similarity detection (repeated patterns)
- Proof style classification

### Advanced Segmentation
- Nested case analysis
- Tactic sequence patterns
- Control flow detection (if/then/else)
- Proof term vs tactic mode detection

### Smarter Scoring
- Context-aware scoring (file type, imports)

### Performance Optimizations
- Caching file indexes
- Incremental updates
- Parallel processing for large files
- Lazy evaluation for scan_file

### Additional Tools
- `rank_targets`: consume scan results, produce ranked list
- `probe`: test automation on specific goals
- `search_annotations`: find annotation opportunities
- `check_patch`: validate proposed changes
