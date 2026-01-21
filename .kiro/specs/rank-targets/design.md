# Design: rank_targets MCP Tool

## Overview

The `rank_targets` tool implements deterministic, objective-driven ranking of theorem declarations using static analysis signals. It operates as a pure function: given a file and objective, it produces a stable ranking with interpretable scores.

## Architecture

### Component Structure

```
rank_targets (tool entry point)
    ↓
ArgumentParser (validate & coerce inputs)
    ↓
DataLoader (fetch scan_file results, optionally scan_theorem)
    ↓
ScoreComputer (compute component scores per theorem)
    ↓
ObjectiveRanker (apply objective weights, sort)
    ↓
ResponseFormatter (build JSON response)
```

### Design Patterns

- **Strategy Pattern**: Different objectives implemented as scoring strategies
- **Builder Pattern**: Response construction with validation
- **Dependency Injection**: All components receive dependencies via constructor
- **Result/Either Pattern**: Explicit error handling with structured failures

## API Contract

### Input Schema

```json
{
  "api_version": "0.1",
  "file": "path/to/File.lean",
  "objective": "maximize_success",
  "limit": 30,
  "include_components": true,
  "include_reasons": true,
  "use_deep_structure": false,
  "min_confidence": 0.0
}
```

**Required Fields:**
- `file` (string, non-empty): Path to Lean file to analyze

**Optional Fields:**
- `api_version` (string, default="0.1"): API version for compatibility
- `objective` (enum, default="balanced"): Ranking objective
  - Values: "maximize_success", "maximize_impact", "maximize_subgoal_automation", "balanced"
- `limit` (integer, default=30, min=1, max=500): Maximum theorems to return
- `include_components` (boolean, default=true): Include component score breakdown
- `include_reasons` (boolean, default=true): Include human-readable reasons
- `use_deep_structure` (boolean, default=false): Use scan_theorem for enhanced scoring
- `min_confidence` (number, default=0.0, range=[0.0, 1.0]): Minimum confidence threshold

### Output Schema

```json
{
  "api_version": "0.1",
  "status": "success",
  "run_id": "rank-abc12345",
  "tool": "rank_targets",
  "file": "path/to/File.lean",
  "objective": "maximize_success",
  "ranking": [
    {
      "theorem_id": "File.theorem_name",
      "range": {
        "start_line": 10,
        "end_line": 25
      },
      "score": 0.85,
      "components": {
        "success_likelihood": 0.75,
        "impact": 0.60,
        "annotation_value": 0.70,
        "subgoal_potential": 0.65,
        "risk": 0.20
      },
      "reasons": [
        "high confidence proof",
        "good aesop candidate",
        "moderate proof length"
      ],
      "signals": {
        "whole_goal_potential": {"aesop": 0.75, "grind": 0.45},
        "subgoal_potential": {"aesop": 0.65, "grind": 0.50},
        "annotation_value": 0.70,
        "proof_lines": 15,
        "confidence": 0.85
      }
    }
  ],
  "summary": {
    "total": 50,
    "returned": 30,
    "skipped_low_confidence": 5
  },
  "diagnostics": [],
  "metadata": {
    "scan_file_run_id": "scan-file-xyz789",
    "deep_structure_used": false,
    "computation_time_ms": 42
  }
}
```

**Status Values:**
- `success`: Ranking completed successfully
- `fail`: Tool failed (invalid input, file not found, etc.)
- `error`: Unexpected error during processing

## Scoring Model

### Component Definitions

#### 1. Success Likelihood (0.0-1.0)
Estimates probability that automation will successfully solve the theorem.

**Computation:**
```python
success_likelihood = (
    0.6 * max(whole_goal_potential.aesop, whole_goal_potential.grind)
    + 0.3 * confidence
    - 0.1 * complexity_penalty
)
```

**Complexity Penalty:**
- Has induction/cases: +0.2
- Proof lines > 30: +0.1
- Many local lemmas (>3): +0.1
- Capped at 0.5

**Rationale:** Prioritizes theorems with high automation potential and clear proof structure.

#### 2. Impact (0.0-1.0)
Estimates value of automating this theorem (time saved, reusability).

**Computation:**
```python
impact = (
    0.5 * proof_length_score
    + 0.3 * annotation_value
    + 0.2 * reusability_score
)
```

**Proof Length Score (saturating):**
- 0-5 lines: 0.2
- 6-10 lines: 0.4
- 11-20 lines: 0.6
- 21-40 lines: 0.8
- 40+ lines: 1.0

**Reusability Score:**
- Based on theorem kind (theorem > lemma > example)
- Presence of local lemmas (indicates complexity worth reusing)

**Rationale:** Longer, more complex proofs provide more value when automated.

#### 3. Annotation Value (0.0-1.0)
ROI estimate for adding automation annotations (from scan_file).

**Computation:**
- Directly use `annotation_value` from scan_file automation profile
- Already accounts for proof length, patterns, local lemmas, confidence

**Rationale:** Reuse existing scoring logic from core.scoring module.

#### 4. Subgoal Potential (0.0-1.0)
Estimates value of automating individual subgoals vs. whole goal.

**Computation:**
```python
subgoal_potential = (
    0.5 * max(subgoal_potential.aesop, subgoal_potential.grind)
    + 0.3 * structure_bonus
    + 0.2 * confidence
)
```

**Structure Bonus (requires use_deep_structure=true):**
- Has cases: +0.2
- Has rewrite_simp blocks: +0.15
- Multiple blocks: +0.1

**Rationale:** Theorems with clear subgoal structure benefit from targeted automation.

#### 5. Risk (0.0-1.0)
Heuristic penalty for likely global changes or non-local side effects.

**Computation:**
```python
risk = (
    0.3 * global_change_risk
    + 0.3 * simp_risk
    + 0.2 * local_lemma_risk
    + 0.2 * low_confidence_risk
)
```

**Global Change Risk:**
- Many rewrites (>5): 0.6
- Heavy simp usage (>3): 0.4
- "simp?" in notes: 0.8

**Simp Risk:**
- simp_count > 3: 0.6
- simp_count > 1: 0.3

**Local Lemma Risk:**
- local_lemmas_count > 3: 0.5
- local_lemmas_count > 1: 0.2

**Low Confidence Risk:**
- confidence < 0.4: 0.7
- confidence < 0.6: 0.4

**Rationale:** Conservative penalty for proofs that might have unexpected side effects.

### Objective Weightings

#### maximize_success
Focus on theorems most likely to be automated successfully.

```python
weights = {
    "success_likelihood": 0.50,
    "impact": 0.10,
    "annotation_value": 0.10,
    "subgoal_potential": 0.10,
    "risk": -0.20  # Strong penalty
}
```

**Use Case:** First-time automation, building confidence, demos.

#### maximize_impact
Focus on theorems that provide most value when automated.

```python
weights = {
    "success_likelihood": 0.20,
    "impact": 0.40,
    "annotation_value": 0.30,
    "subgoal_potential": 0.05,
    "risk": -0.05  # Weak penalty
}
```

**Use Case:** Mature projects, optimizing developer time, refactoring.

#### maximize_subgoal_automation
Focus on theorems where subgoal automation is most valuable.

```python
weights = {
    "success_likelihood": 0.15,
    "impact": 0.15,
    "annotation_value": 0.20,
    "subgoal_potential": 0.40,
    "risk": -0.10  # Moderate penalty
}
```

**Use Case:** Incremental automation, complex proofs, case analysis.

#### balanced
Balanced weighting across all components.

```python
weights = {
    "success_likelihood": 0.25,
    "impact": 0.25,
    "annotation_value": 0.20,
    "subgoal_potential": 0.20,
    "risk": -0.10  # Moderate penalty
}
```

**Use Case:** General-purpose ranking, exploratory analysis.

### Final Score Computation

```python
final_score = sum(weight * component for weight, component in zip(weights.values(), components.values()))
final_score = max(0.0, min(1.0, final_score))  # Clamp to [0.0, 1.0]
final_score = round(final_score, 2)  # Deterministic rounding
```

### Tie-Breaking Rules

When two theorems have identical scores:
1. **Primary**: Compare theorem_id lexicographically
2. **Secondary**: Compare start_line numerically (earlier first)

This ensures stable, deterministic ordering.

## Data Flow

### 1. Argument Parsing
```python
def _coerce_args(args: dict[str, Any]) -> RankTargetsArgs:
    # Validate required fields
    # Apply defaults for optional fields
    # Validate enums and ranges
    # Return immutable dataclass
```

### 2. Data Loading
```python
def _load_theorem_data(file: str, use_deep_structure: bool) -> list[TheoremData]:
    # Call scan_file to get base data
    # If use_deep_structure, call scan_theorem for each theorem
    # Merge data into unified TheoremData objects
    # Handle missing fields with defaults
```

### 3. Score Computation
```python
def _compute_components(theorem_data: TheoremData) -> ComponentScores:
    # Compute each component score
    # Apply normalization
    # Return immutable ComponentScores
```

### 4. Objective Ranking
```python
def _rank_by_objective(
    theorems: list[TheoremData],
    objective: Objective,
    min_confidence: float
) -> list[RankedTheorem]:
    # Filter by min_confidence
    # Compute final scores using objective weights
    # Sort by score (desc), then theorem_id, then start_line
    # Return ranked list
```

### 5. Response Formatting
```python
def _format_response(
    ranked: list[RankedTheorem],
    args: RankTargetsArgs,
    metadata: dict
) -> dict[str, Any]:
    # Build ranking array
    # Optionally include components/reasons
    # Add summary statistics
    # Ensure deterministic JSON
```

## Error Handling

### Input Validation Errors
- Invalid file path → status="fail", diagnostic with error severity
- Invalid objective → status="fail", diagnostic with valid options
- Invalid limit/confidence → status="fail", diagnostic with valid range

### Runtime Errors
- scan_file fails → status="fail", propagate scan_file diagnostics
- scan_theorem fails (when use_deep_structure=true) → warning diagnostic, continue without deep structure
- Missing required fields → status="fail", diagnostic listing missing fields
- Missing optional fields → info diagnostic, use defaults

### Partial Results
- Some theorems filtered by confidence → success, report in summary.skipped_low_confidence
- Some scan_theorem calls fail → success, warning diagnostics, use scan_file data only

## Performance Considerations

### Target Metrics
- 200 theorems, no deep structure: < 50ms
- 200 theorems, with deep structure: < 200ms

### Optimization Strategies
1. **Lazy Deep Structure**: Only call scan_theorem when use_deep_structure=true
2. **Batch Processing**: Process all theorems in single pass
3. **Minimal Allocations**: Use immutable dataclasses, avoid unnecessary copies
4. **Efficient Sorting**: Single sort with compound key
5. **Conditional Formatting**: Skip component/reason formatting when not requested

### Performance Monitoring
- Include computation_time_ms in metadata
- Log warning if exceeds target (for future optimization)

## Testing Strategy

### Unit Tests
- Component score computation (each component independently)
- Objective weight application
- Tie-breaking logic
- Input validation
- Error handling

### Property-Based Tests

**Property 1: Determinism**
```python
@given(file=valid_lean_files(), objective=objectives())
def test_determinism(file, objective):
    result1 = rank_targets({"file": file, "objective": objective})
    result2 = rank_targets({"file": file, "objective": objective})
    assert result1 == result2
```
**Validates: Requirements 1.3, NFR-1**

**Property 2: Stable Sorting**
```python
@given(file=valid_lean_files(), objective=objectives())
def test_stable_sorting(file, objective):
    result = rank_targets({"file": file, "objective": objective})
    scores = [t["score"] for t in result["ranking"]]
    assert scores == sorted(scores, reverse=True)
    # Check tie-breaking
    for i in range(len(scores) - 1):
        if scores[i] == scores[i+1]:
            assert result["ranking"][i]["theorem_id"] <= result["ranking"][i+1]["theorem_id"]
```
**Validates: Requirements 1.3, NFR-1**

**Property 3: Objective Consistency**
```python
@given(file=valid_lean_files())
def test_objective_consistency(file):
    success_result = rank_targets({"file": file, "objective": "maximize_success"})
    impact_result = rank_targets({"file": file, "objective": "maximize_impact"})
    # Rankings should differ (unless file has < 2 theorems)
    if len(success_result["ranking"]) >= 2:
        assert success_result["ranking"] != impact_result["ranking"]
```
**Validates: Requirements 2.3**

**Property 4: Confidence Filtering**
```python
@given(file=valid_lean_files(), min_conf=st.floats(0.0, 1.0))
def test_confidence_filtering(file, min_conf):
    result = rank_targets({"file": file, "min_confidence": min_conf})
    for theorem in result["ranking"]:
        assert theorem["signals"]["confidence"] >= min_conf
```
**Validates: Requirements 3.1, 3.2**

**Property 5: Score Bounds**
```python
@given(file=valid_lean_files(), objective=objectives())
def test_score_bounds(file, objective):
    result = rank_targets({"file": file, "objective": objective})
    for theorem in result["ranking"]:
        assert 0.0 <= theorem["score"] <= 1.0
        if "components" in theorem:
            for component_score in theorem["components"].values():
                assert 0.0 <= component_score <= 1.0
```
**Validates: Requirements 4.3**

### Contract Tests
- Input schema validation (JSON Schema)
- Output schema validation (JSON Schema)
- API version compatibility
- Required field presence
- Enum value validation

### Integration Tests
- End-to-end with real Lean files
- Performance benchmarks (200 theorems)
- Error scenarios (missing file, invalid input)
- Partial failure scenarios (scan_theorem fails)

## Correctness Properties

### P1: Deterministic Output
**Property:** For any valid input, multiple invocations produce identical JSON output (byte-for-byte).

**Validation:** Property-based test with random inputs, compare serialized JSON.

### P2: Monotonic Scoring
**Property:** Within a ranking, score[i] >= score[i+1] for all i.

**Validation:** Property-based test checking sorted order.

### P3: Tie-Breaking Stability
**Property:** When score[i] == score[i+1], theorem_id[i] <= theorem_id[i+1] lexicographically.

**Validation:** Property-based test checking tie-breaker application.

### P4: Confidence Threshold Enforcement
**Property:** All returned theorems have confidence >= min_confidence.

**Validation:** Property-based test with varying min_confidence values.

### P5: Component Score Bounds
**Property:** All component scores and final scores are in [0.0, 1.0].

**Validation:** Property-based test checking all score fields.

### P6: Objective Weight Consistency
**Property:** Changing objective changes ranking (for files with sufficient theorems).

**Validation:** Property-based test comparing rankings across objectives.

## Implementation Notes

### Module Structure
```
src/lean_proof_auto_mcp/tools/rank_targets.py  # Main tool entry point
src/lean_proof_auto_mcp/core/ranking.py        # Scoring and ranking logic
```

### Key Classes
```python
@dataclass(frozen=True)
class RankTargetsArgs:
    file: str
    objective: str
    limit: int
    include_components: bool
    include_reasons: bool
    use_deep_structure: bool
    min_confidence: float

@dataclass(frozen=True)
class ComponentScores:
    success_likelihood: float
    impact: float
    annotation_value: float
    subgoal_potential: float
    risk: float

@dataclass(frozen=True)
class RankedTheorem:
    theorem_id: str
    range: dict[str, int]
    score: float
    components: ComponentScores | None
    reasons: list[str] | None
    signals: dict[str, Any] | None
```

### Determinism Guarantees
1. Use stable sorting with explicit tie-breakers
2. Round all floats to 2 decimal places
3. Use deterministic run_id generation (hash-based)
4. Sort JSON object keys alphabetically
5. Use consistent random seed for any randomness (none expected)

## Future Enhancements

### Phase 2 (Out of Scope for Initial Implementation)
- Custom objective definitions via JSON config
- Caching of scan_file results across invocations
- Parallel scan_theorem calls for deep structure
- Machine learning-based component weights
- Historical success rate tracking

### Extensibility Points
- New objectives: Add to Objective enum and weights dict
- New components: Add to ComponentScores and computation logic
- New data sources: Extend TheoremData with additional fields
