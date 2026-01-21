# MCP tool contract

## Versioning
- All tools include `api_version`.
- All responses include `status` and `run_id`.

## Common response fields
- `status`: `success` | `fail` | `timeout` | `error` | other terminal states
- `run_id`: unique identifier for artifact lookup
- `diagnostics`: structured list when applicable

## Tool list (v0)
- scan_file
- scan_theorem
- rank_targets
- probe
- probe_file
- search_annotations
- check_patch
- verify
- apply_patch (optional)
- get_artifacts

---

## rank_targets

**Purpose:** Provides deterministic, objective-driven ranking of theorem declarations within a Lean file to support proof automation decision-making.

**API Version:** 0.1

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

#### Required Parameters

- **file** (string): Path to Lean file to analyze. Must be non-empty.

#### Optional Parameters

- **api_version** (string, default="0.1"): API version for compatibility tracking
- **objective** (enum, default="balanced"): Ranking objective that determines component weightings
  - `"maximize_success"`: Prioritize theorems most likely to be automated successfully
  - `"maximize_impact"`: Prioritize theorems that provide most value when automated
  - `"maximize_subgoal_automation"`: Prioritize theorems where subgoal automation is most valuable
  - `"balanced"`: Balanced weighting across all components
- **limit** (integer, default=30, min=1, max=500): Maximum number of theorems to return
- **include_components** (boolean, default=true): Include component score breakdown in response
- **include_reasons** (boolean, default=true): Include human-readable reasons in response
- **use_deep_structure** (boolean, default=false): Use scan_theorem for enhanced scoring with deep structure analysis
- **min_confidence** (number, default=0.0, range=[0.0, 1.0]): Minimum confidence threshold for including theorems

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

#### Response Fields

- **api_version** (string): API version used for this response
- **status** (string): Response status - `"success"`, `"fail"`, or `"error"`
- **run_id** (string): Unique identifier for this ranking operation
- **tool** (string): Always `"rank_targets"`
- **file** (string): Path to the analyzed file
- **objective** (string): Objective used for ranking
- **ranking** (array): Ordered list of ranked theorems (highest score first)
  - **theorem_id** (string): Fully qualified theorem identifier
  - **range** (object): Source location
    - **start_line** (integer): Starting line number
    - **end_line** (integer): Ending line number
  - **score** (number): Final ranking score in [0.0, 1.0]
  - **components** (object, optional): Component score breakdown (if include_components=true)
    - **success_likelihood** (number): Probability automation will succeed [0.0, 1.0]
    - **impact** (number): Value of automating this theorem [0.0, 1.0]
    - **annotation_value** (number): ROI of adding annotations [0.0, 1.0]
    - **subgoal_potential** (number): Value of subgoal automation [0.0, 1.0]
    - **risk** (number): Heuristic penalty for side effects [0.0, 1.0]
  - **reasons** (array, optional): Human-readable explanations (if include_reasons=true)
  - **signals** (object, optional): Raw automation signals from scan_file
- **summary** (object): Ranking statistics
  - **total** (integer): Total theorems found in file
  - **returned** (integer): Number of theorems in ranking
  - **skipped_low_confidence** (integer): Theorems filtered by min_confidence
- **diagnostics** (array): Structured diagnostic messages
- **metadata** (object): Additional execution metadata
  - **scan_file_run_id** (string): Run ID from underlying scan_file call
  - **deep_structure_used** (boolean): Whether scan_theorem was used
  - **computation_time_ms** (integer): Ranking computation time

### Objectives and Scoring

#### Component Scores

All component scores are normalized to [0.0, 1.0]:

1. **success_likelihood**: Estimates probability that automation will successfully solve the theorem
   - Based on whole_goal_potential, confidence, and complexity penalty
   - Higher for simple proofs with high automation potential

2. **impact**: Estimates value of automating this theorem (time saved, reusability)
   - Based on proof length, annotation value, and reusability
   - Higher for longer, more complex proofs

3. **annotation_value**: ROI estimate for adding automation annotations
   - Directly from scan_file automation profile
   - Accounts for proof patterns and structure

4. **subgoal_potential**: Value of automating individual subgoals vs. whole goal
   - Based on subgoal_potential signals and proof structure
   - Enhanced when use_deep_structure=true

5. **risk**: Heuristic penalty for likely global changes or side effects
   - Based on rewrite/simp usage, local lemmas, and confidence
   - Higher risk means more caution needed

#### Objective Weightings

**maximize_success** - Focus on theorems most likely to be automated successfully
```
success_likelihood: 0.50
impact: 0.10
annotation_value: 0.10
subgoal_potential: 0.10
risk: -0.20 (strong penalty)
```
Use case: First-time automation, building confidence, demos

**maximize_impact** - Focus on theorems that provide most value when automated
```
success_likelihood: 0.20
impact: 0.40
annotation_value: 0.30
subgoal_potential: 0.05
risk: -0.05 (weak penalty)
```
Use case: Mature projects, optimizing developer time, refactoring

**maximize_subgoal_automation** - Focus on theorems where subgoal automation is most valuable
```
success_likelihood: 0.15
impact: 0.15
annotation_value: 0.20
subgoal_potential: 0.40
risk: -0.10 (moderate penalty)
```
Use case: Incremental automation, complex proofs, case analysis

**balanced** - Balanced weighting across all components
```
success_likelihood: 0.25
impact: 0.25
annotation_value: 0.20
subgoal_potential: 0.20
risk: -0.10 (moderate penalty)
```
Use case: General-purpose ranking, exploratory analysis

### Examples

#### Example 1: Basic Usage (maximize_success)

**Request:**
```json
{
  "file": "Mathlib/Data/List/Basic.lean",
  "objective": "maximize_success"
}
```

**Response:**
```json
{
  "api_version": "0.1",
  "status": "success",
  "run_id": "rank-a1b2c3d4",
  "tool": "rank_targets",
  "file": "Mathlib/Data/List/Basic.lean",
  "objective": "maximize_success",
  "ranking": [
    {
      "theorem_id": "List.append_nil",
      "range": {"start_line": 45, "end_line": 48},
      "score": 0.92,
      "components": {
        "success_likelihood": 0.95,
        "impact": 0.45,
        "annotation_value": 0.80,
        "subgoal_potential": 0.60,
        "risk": 0.10
      },
      "reasons": [
        "very high confidence proof (0.95)",
        "excellent aesop candidate (0.90)",
        "short proof (3 lines)",
        "low complexity"
      ],
      "signals": {
        "whole_goal_potential": {"aesop": 0.90, "grind": 0.75},
        "confidence": 0.95,
        "proof_lines": 3
      }
    }
  ],
  "summary": {
    "total": 150,
    "returned": 30,
    "skipped_low_confidence": 0
  },
  "diagnostics": [],
  "metadata": {
    "scan_file_run_id": "scan-file-xyz789",
    "deep_structure_used": false,
    "computation_time_ms": 38
  }
}
```

#### Example 2: Impact-Focused with Confidence Filtering

**Request:**
```json
{
  "file": "Mathlib/Algebra/Ring/Basic.lean",
  "objective": "maximize_impact",
  "limit": 10,
  "min_confidence": 0.7,
  "include_components": false,
  "include_reasons": false
}
```

**Response:**
```json
{
  "api_version": "0.1",
  "status": "success",
  "run_id": "rank-e5f6g7h8",
  "tool": "rank_targets",
  "file": "Mathlib/Algebra/Ring/Basic.lean",
  "objective": "maximize_impact",
  "ranking": [
    {
      "theorem_id": "Ring.mul_comm_proof",
      "range": {"start_line": 120, "end_line": 165},
      "score": 0.88,
      "signals": {
        "proof_lines": 45,
        "confidence": 0.85,
        "annotation_value": 0.75
      }
    }
  ],
  "summary": {
    "total": 80,
    "returned": 10,
    "skipped_low_confidence": 15
  },
  "diagnostics": [
    {
      "severity": "info",
      "message": "Filtered 15 theorems below min_confidence threshold of 0.7"
    }
  ],
  "metadata": {
    "scan_file_run_id": "scan-file-abc123",
    "deep_structure_used": false,
    "computation_time_ms": 42
  }
}
```

#### Example 3: Subgoal Automation with Deep Structure

**Request:**
```json
{
  "file": "Mathlib/Logic/Basic.lean",
  "objective": "maximize_subgoal_automation",
  "use_deep_structure": true,
  "limit": 5
}
```

**Response:**
```json
{
  "api_version": "0.1",
  "status": "success",
  "run_id": "rank-i9j0k1l2",
  "tool": "rank_targets",
  "file": "Mathlib/Logic/Basic.lean",
  "objective": "maximize_subgoal_automation",
  "ranking": [
    {
      "theorem_id": "Logic.cases_theorem",
      "range": {"start_line": 200, "end_line": 235},
      "score": 0.85,
      "components": {
        "success_likelihood": 0.70,
        "impact": 0.65,
        "annotation_value": 0.75,
        "subgoal_potential": 0.90,
        "risk": 0.15
      },
      "reasons": [
        "high subgoal automation potential (0.90)",
        "has case analysis structure",
        "multiple distinct subgoals",
        "good aesop subgoal candidate"
      ],
      "signals": {
        "subgoal_potential": {"aesop": 0.85, "grind": 0.70},
        "proof_lines": 35,
        "confidence": 0.80
      }
    }
  ],
  "summary": {
    "total": 45,
    "returned": 5,
    "skipped_low_confidence": 0
  },
  "diagnostics": [],
  "metadata": {
    "scan_file_run_id": "scan-file-def456",
    "deep_structure_used": true,
    "computation_time_ms": 185
  }
}
```

#### Example 4: Error Response

**Request:**
```json
{
  "file": "NonExistent.lean",
  "objective": "maximize_success"
}
```

**Response:**
```json
{
  "api_version": "0.1",
  "status": "fail",
  "run_id": "rank-m3n4o5p6",
  "tool": "rank_targets",
  "file": "NonExistent.lean",
  "diagnostics": [
    {
      "severity": "error",
      "message": "File not found: NonExistent.lean"
    }
  ]
}
```

### Performance Characteristics

- **Without deep structure** (use_deep_structure=false): < 50ms for 200 theorems
- **With deep structure** (use_deep_structure=true): < 200ms for 200 theorems
- **Deterministic**: Same inputs always produce identical outputs
- **Stateless**: No caching between invocations

### Error Handling

All errors return structured JSON with `status="fail"` and diagnostics:

- **Invalid file path**: Error diagnostic with file path
- **Invalid objective**: Error diagnostic listing valid objectives
- **Invalid parameters**: Error diagnostic with valid ranges
- **scan_file failure**: Propagates scan_file diagnostics
- **scan_theorem failure** (when use_deep_structure=true): Warning diagnostic, continues with scan_file data only

Partial results are returned when possible (e.g., some scan_theorem calls fail).
