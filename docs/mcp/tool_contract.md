# MCP tool contract

## Versioning
- All tools include `api_version`.
- All responses include `status` and `run_id`.

## Common response fields
- `status`: `success` | `fail` | `timeout` | `error` | other terminal states
- `run_id`: unique identifier for artifact lookup
- `diagnostics`: structured list when applicable

## Tool list (v1)
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

## Migration Guide: API 0.1 → 1.0

### Breaking Changes Summary

**API Version 1.0** introduces several breaking changes to improve production readiness:

1. **New Required Parameter**: `skip_already_automated` is now required for `rank_targets`
2. **Response Structure Changes**: All tools now include additional fields
3. **Confidence Values Fixed**: Numeric confidence now appears in notes
4. **Tier System Added**: Rankings include S/A/B/C/D tier classifications
5. **Configuration System**: All heuristics are now configurable via external YAML files

### Migration Steps

#### For rank_targets Users

**Before (API 0.1):**
```json
{
  "file": "MyFile.lean",
  "objective": "maximize_success"
}
```

**After (API 1.0):**
```json
{
  "file": "MyFile.lean",
  "objective": "maximize_success",
  "skip_already_automated": false
}
```

**Response Changes:**
- New field: `tier` (S/A/B/C/D) in each ranking entry
- New field: `available_objectives` in response root
- New field: `already_automated_penalty` in components
- New field: `tier_distribution` in summary
- New field: `skipped_already_automated` in summary
- New field: `config_source` in metadata

#### For scan_file and scan_theorem Users

**Response Changes:**
- Numeric confidence now appears in notes: `"confidence: 0.85"`
- API version bumped to "1.0"
- Optional `config_path` parameter for custom heuristics

#### Configuration System

All tools now support custom heuristic configuration:

```json
{
  "file": "MyFile.lean",
  "config_path": "custom_heuristics.yaml"
}
```

Or via environment variable:
```bash
export LEAN_PROOF_AUTO_MCP_CONFIG=/path/to/heuristics.yaml
```

### Backward Compatibility

**API 1.0 is NOT backward compatible with 0.1.** Clients must:
1. Add `skip_already_automated` parameter to all `rank_targets` calls
2. Update response parsing to handle new fields
3. Update API version checks from "0.1" to "1.0"

---

## rank_targets

**Purpose:** Provides deterministic, objective-driven ranking of theorem declarations within a Lean file to support proof automation decision-making.

**API Version:** 1.0

### Input Schema

```json
{
  "api_version": "1.0",
  "file": "path/to/File.lean",
  "objective": "maximize_success",
  "limit": 30,
  "include_components": true,
  "include_reasons": true,
  "use_deep_structure": false,
  "min_confidence": 0.0,
  "skip_already_automated": false,
  "config_path": null
}
```

#### Required Parameters

- **file** (string): Path to Lean file to analyze. Must be non-empty.
- **skip_already_automated** (boolean): Whether to filter out theorems that already use automation tactics or attributes. **NEW in API 1.0 - REQUIRED**

#### Optional Parameters

- **api_version** (string, default="1.0"): API version for compatibility tracking
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
- **config_path** (string | null, default=null): Path to custom heuristics configuration file. If null, uses environment variable `LEAN_PROOF_AUTO_MCP_CONFIG` or package default. **NEW in API 1.0**

### Output Schema

```json
{
  "api_version": "1.0",
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
      "tier": "A",
      "components": {
        "success_likelihood": 0.75,
        "impact": 0.60,
        "annotation_value": 0.70,
        "subgoal_potential": 0.65,
        "risk": 0.20,
        "already_automated_penalty": 0.0
      },
      "reasons": [
        "confidence: 0.85",
        "high confidence proof",
        "good aesop candidate",
        "moderate proof length"
      ],
      "signals": {
        "whole_goal_potential": {"aesop": 0.75, "grind": 0.45},
        "subgoal_potential": {"aesop": 0.65, "grind": 0.50},
        "annotation_value": 0.70,
        "proof_lines": 15,
        "confidence": 0.85,
        "already_automated": false,
        "automation_penalty": 0.0,
        "automation_type": "none"
      }
    }
  ],
  "summary": {
    "total": 50,
    "returned": 30,
    "skipped_low_confidence": 5,
    "skipped_already_automated": 0,
    "tier_distribution": {
      "S": 3,
      "A": 7,
      "B": 10,
      "C": 7,
      "D": 3
    }
  },
  "diagnostics": [],
  "metadata": {
    "scan_file_run_id": "scan-file-xyz789",
    "deep_structure_used": false,
    "computation_time_ms": 42,
    "config_source": "default"
  },
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate",
      "weights": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "annotation_value": 0.10,
        "subgoal_potential": 0.10,
        "risk": -0.20
      }
    }
  ]
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
  - **tier** (string): Quality tier - "S" (top 10%), "A" (10-25%), "B" (25-50%), "C" (50-75%), "D" (75-100%). **NEW in API 1.0**
  - **components** (object, optional): Component score breakdown (if include_components=true)
    - **success_likelihood** (number): Probability automation will succeed [0.0, 1.0]
    - **impact** (number): Value of automating this theorem [0.0, 1.0]
    - **annotation_value** (number): ROI of adding annotations [0.0, 1.0]
    - **subgoal_potential** (number): Value of subgoal automation [0.0, 1.0]
    - **risk** (number): Heuristic penalty for side effects [0.0, 1.0]
    - **already_automated_penalty** (number): Penalty for already-automated theorems [0.0, 1.0]. **NEW in API 1.0**
  - **reasons** (array, optional): Human-readable explanations (if include_reasons=true). **Now includes numeric confidence as first item**
  - **signals** (object, optional): Raw automation signals from scan_file
    - **already_automated** (boolean): Whether theorem uses automation tactics/attributes. **NEW in API 1.0**
    - **automation_penalty** (number): Penalty value for automation detection. **NEW in API 1.0**
    - **automation_type** (string): Type of automation detected - "tactic", "attribute", "trivial", "none". **NEW in API 1.0**
- **summary** (object): Ranking statistics
  - **total** (integer): Total theorems found in file
  - **returned** (integer): Number of theorems in ranking
  - **skipped_low_confidence** (integer): Theorems filtered by min_confidence
  - **skipped_already_automated** (integer): Theorems filtered by skip_already_automated. **NEW in API 1.0**
  - **tier_distribution** (object): Count of theorems in each tier (S/A/B/C/D). **NEW in API 1.0**
- **diagnostics** (array): Structured diagnostic messages
- **metadata** (object): Additional execution metadata
  - **scan_file_run_id** (string): Run ID from underlying scan_file call
  - **deep_structure_used** (boolean): Whether scan_theorem was used
  - **computation_time_ms** (integer): Ranking computation time
  - **config_source** (string): Configuration source - "path", "environment", or "default". **NEW in API 1.0**
- **available_objectives** (array): List of available ranking objectives with metadata. **NEW in API 1.0**
  - **name** (string): Objective identifier
  - **description** (string): What this objective optimizes for
  - **use_case** (string): When to use this objective
  - **weights** (object): Component weight configuration

### Already-Automated Detection

**NEW in API 1.0**: The `skip_already_automated` parameter enables filtering of theorems that already use automation tactics or attributes.

#### Detection Rules

The system uses conservative pattern matching to detect automation:

1. **Tactic Detection** (penalty: 0.3)
   - Proof contains: `by aesop`, `by grind`, `by simp`, `aesop`, `grind`, `simp`
   - Detected tactic kinds include: aesop, grind, simp, simp_all, omega, decide, tauto

2. **Attribute Detection** (penalty: 0.5)
   - Declaration has: `@[aesop]`, `@[simp]`, `@[aesop safe]`, etc.

3. **Trivial Proof Detection** (penalty: 0.8)
   - Proof is: `:= by rfl`, `:= rfl`, `:= trivial`

#### Behavior

- **When `skip_already_automated=true`**: Theorems with detected automation are filtered out entirely
- **When `skip_already_automated=false`**: Theorems are ranked but receive penalty via `already_automated_penalty` component
- Detection is **conservative**: Prefers false negatives over false positives (better to recommend an automated theorem than skip a manual one)

#### Example

```json
{
  "file": "MyFile.lean",
  "skip_already_automated": true
}
```

Response will exclude theorems like:
```lean
@[aesop safe]
theorem my_theorem : P := by
  aesop
```

### Tier System

**NEW in API 1.0**: Each ranked theorem includes a tier classification (S/A/B/C/D) based on percentile rank within the file.

#### Tier Definitions

- **S-tier** (top 10%): Exceptional candidates, highest priority
- **A-tier** (10-25%): Strong candidates, high priority
- **B-tier** (25-50%): Good candidates, medium priority
- **C-tier** (50-75%): Acceptable candidates, lower priority
- **D-tier** (75-100%): Weak candidates, consider skipping

#### Characteristics

- Tiers are **relative to the file**, not absolute scores
- Same theorem may have different tiers in different files
- Tier thresholds are configurable via `heuristics.yaml`
- Raw score remains available for programmatic use

#### Example

A theorem with score 0.65 might be:
- **S-tier** in a file with generally low scores
- **C-tier** in a file with generally high scores

### Configuration System

**NEW in API 1.0**: All heuristic parameters are externalized to configuration files.

#### Configuration Sources (Priority Order)

1. **Explicit parameter**: `config_path` in request
2. **Environment variable**: `LEAN_PROOF_AUTO_MCP_CONFIG`
3. **Package default**: Built-in `heuristics.yaml`

#### Configuration File Format

See `docs/configuration.md` for complete documentation.

Example custom configuration:
```yaml
version: "1.0"

confidence:
  base_score: 0.3
  proof_structure_bonus: 0.2
  # ... more parameters

aesop_scoring:
  base_score: 0.4
  # ... more parameters

tiers:
  s_tier_percentile: 5.0  # Top 5% instead of 10%
  a_tier_percentile: 20.0
  # ... more thresholds
```

#### Usage

```json
{
  "file": "MyFile.lean",
  "config_path": "/path/to/custom_heuristics.yaml"
}
```

Or via environment:
```bash
export LEAN_PROOF_AUTO_MCP_CONFIG=/path/to/custom_heuristics.yaml
```

The response includes `config_source` in metadata to indicate which configuration was used.

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

6. **already_automated_penalty**: Penalty for theorems already using automation. **NEW in API 1.0**
   - 0.0 for unannotated theorems
   - 0.3 for theorems using automation tactics
   - 0.5 for theorems with automation attributes
   - 0.8 for trivial proofs
   - Applied as: `final_score -= 0.15 * already_automated_penalty`

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
  "objective": "maximize_success",
  "skip_already_automated": false
}
```

**Response:**
```json
{
  "api_version": "1.0",
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
      "tier": "S",
      "components": {
        "success_likelihood": 0.95,
        "impact": 0.45,
        "annotation_value": 0.80,
        "subgoal_potential": 0.60,
        "risk": 0.10,
        "already_automated_penalty": 0.0
      },
      "reasons": [
        "confidence: 0.95",
        "very high confidence proof",
        "excellent aesop candidate (0.90)",
        "short proof (3 lines)",
        "low complexity"
      ],
      "signals": {
        "whole_goal_potential": {"aesop": 0.90, "grind": 0.75},
        "confidence": 0.95,
        "proof_lines": 3,
        "already_automated": false,
        "automation_penalty": 0.0,
        "automation_type": "none"
      }
    }
  ],
  "summary": {
    "total": 150,
    "returned": 30,
    "skipped_low_confidence": 0,
    "skipped_already_automated": 0,
    "tier_distribution": {
      "S": 15,
      "A": 22,
      "B": 38,
      "C": 37,
      "D": 38
    }
  },
  "diagnostics": [],
  "metadata": {
    "scan_file_run_id": "scan-file-xyz789",
    "deep_structure_used": false,
    "computation_time_ms": 38,
    "config_source": "default"
  },
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate",
      "weights": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "annotation_value": 0.10,
        "subgoal_potential": 0.10,
        "risk": -0.20
      }
    },
    {
      "name": "maximize_impact",
      "description": "Prioritize theorems that save the most time when automated",
      "use_case": "When you want maximum ROI on automation effort",
      "weights": {
        "success_likelihood": 0.20,
        "impact": 0.40,
        "annotation_value": 0.30,
        "subgoal_potential": 0.05,
        "risk": -0.05
      }
    },
    {
      "name": "maximize_subgoal_automation",
      "description": "Prioritize theorems with good partial automation opportunities",
      "use_case": "When you want to automate proof steps rather than whole goals",
      "weights": {
        "success_likelihood": 0.15,
        "impact": 0.15,
        "annotation_value": 0.20,
        "subgoal_potential": 0.40,
        "risk": -0.10
      }
    },
    {
      "name": "balanced",
      "description": "Balanced weighting across all factors",
      "use_case": "When you want a general-purpose ranking",
      "weights": {
        "success_likelihood": 0.25,
        "impact": 0.25,
        "annotation_value": 0.20,
        "subgoal_potential": 0.20,
        "risk": -0.10
      }
    }
  ]
}
```

#### Example 2: Skip Already-Automated with Custom Config

**Request:**
```json
{
  "file": "Mathlib/Algebra/Ring/Basic.lean",
  "objective": "maximize_impact",
  "limit": 10,
  "min_confidence": 0.7,
  "skip_already_automated": true,
  "config_path": "/path/to/custom_heuristics.yaml",
  "include_components": false,
  "include_reasons": false
}
```

**Response:**
```json
{
  "api_version": "1.0",
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
      "tier": "A",
      "signals": {
        "proof_lines": 45,
        "confidence": 0.85,
        "annotation_value": 0.75,
        "already_automated": false,
        "automation_penalty": 0.0,
        "automation_type": "none"
      }
    }
  ],
  "summary": {
    "total": 80,
    "returned": 10,
    "skipped_low_confidence": 15,
    "skipped_already_automated": 22,
    "tier_distribution": {
      "S": 1,
      "A": 3,
      "B": 3,
      "C": 2,
      "D": 1
    }
  },
  "diagnostics": [
    {
      "severity": "info",
      "message": "Filtered 15 theorems below min_confidence threshold of 0.7"
    },
    {
      "severity": "info",
      "message": "Filtered 22 theorems with already-automated detection"
    }
  ],
  "metadata": {
    "scan_file_run_id": "scan-file-abc123",
    "deep_structure_used": false,
    "computation_time_ms": 42,
    "config_source": "path"
  },
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate",
      "weights": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "annotation_value": 0.10,
        "subgoal_potential": 0.10,
        "risk": -0.20
      }
    }
  ]
}
```

#### Example 3: Subgoal Automation with Deep Structure

**Request:**
```json
{
  "file": "Mathlib/Logic/Basic.lean",
  "objective": "maximize_subgoal_automation",
  "use_deep_structure": true,
  "skip_already_automated": false,
  "limit": 5
}
```

**Response:**
```json
{
  "api_version": "1.0",
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
      "tier": "S",
      "components": {
        "success_likelihood": 0.70,
        "impact": 0.65,
        "annotation_value": 0.75,
        "subgoal_potential": 0.90,
        "risk": 0.15,
        "already_automated_penalty": 0.0
      },
      "reasons": [
        "confidence: 0.80",
        "high subgoal automation potential (0.90)",
        "has case analysis structure",
        "multiple distinct subgoals",
        "good aesop subgoal candidate"
      ],
      "signals": {
        "subgoal_potential": {"aesop": 0.85, "grind": 0.70},
        "proof_lines": 35,
        "confidence": 0.80,
        "already_automated": false,
        "automation_penalty": 0.0,
        "automation_type": "none"
      }
    }
  ],
  "summary": {
    "total": 45,
    "returned": 5,
    "skipped_low_confidence": 0,
    "skipped_already_automated": 0,
    "tier_distribution": {
      "S": 4,
      "A": 7,
      "B": 11,
      "C": 11,
      "D": 12
    }
  },
  "diagnostics": [],
  "metadata": {
    "scan_file_run_id": "scan-file-def456",
    "deep_structure_used": true,
    "computation_time_ms": 185,
    "config_source": "default"
  },
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate",
      "weights": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "annotation_value": 0.10,
        "subgoal_potential": 0.10,
        "risk": -0.20
      }
    }
  ]
}
```

#### Example 4: Error Response - Missing Required Parameter

**Request:**
```json
{
  "file": "MyFile.lean",
  "objective": "maximize_success"
}
```

**Response:**
```json
{
  "api_version": "1.0",
  "status": "fail",
  "run_id": "rank-m3n4o5p6",
  "tool": "rank_targets",
  "file": "MyFile.lean",
  "diagnostics": [
    {
      "severity": "error",
      "message": "rank_targets: 'skip_already_automated' parameter is required in API 1.0"
    }
  ]
}
```

#### Example 5: Error Response - Invalid Objective

**Request:**
```json
{
  "file": "MyFile.lean",
  "objective": "invalid_objective",
  "skip_already_automated": false
}
```

**Response:**
```json
{
  "api_version": "1.0",
  "status": "fail",
  "run_id": "rank-q7r8s9t0",
  "tool": "rank_targets",
  "file": "MyFile.lean",
  "diagnostics": [
    {
      "severity": "error",
      "message": "rank_targets: invalid objective 'invalid_objective'\nAvailable objectives:\n  - maximize_success: Prioritize theorems most likely to be automated successfully\n  - maximize_impact: Prioritize theorems that save the most time when automated\n  - maximize_subgoal_automation: Prioritize theorems with good partial automation opportunities\n  - balanced: Balanced weighting across all factors"
    }
  ]
}
```

### Performance Characteristics

- **Without deep structure** (use_deep_structure=false): < 50ms for 200 theorems
- **With deep structure** (use_deep_structure=true): < 200ms for 200 theorems
- **Configuration loading**: ~5ms (cached after first load)
- **Already-automated detection**: < 5ms overhead for 200 theorems
- **Tier computation**: < 2ms overhead for 200 theorems
- **Deterministic**: Same inputs always produce identical outputs
- **Stateless**: No caching between invocations

### Error Handling

All errors return structured JSON with `status="fail"` and diagnostics:

- **Missing required parameter**: Error diagnostic indicating which parameter is missing
- **Invalid file path**: Error diagnostic with file path
- **Invalid objective**: Error diagnostic listing valid objectives with descriptions
- **Invalid parameters**: Error diagnostic with valid ranges
- **Invalid configuration**: Error diagnostic with validation details
- **scan_file failure**: Propagates scan_file diagnostics
- **scan_theorem failure** (when use_deep_structure=true): Warning diagnostic, continues with scan_file data only

Partial results are returned when possible (e.g., some scan_theorem calls fail).

---

## scan_file

**Purpose:** Analyzes a Lean file to extract automation profiles for all theorem declarations.

**API Version:** 1.0

### Changes in API 1.0

- **Confidence values fixed**: Numeric confidence now appears in notes (e.g., `"confidence: 0.85"`)
- **Configuration support**: Optional `config_path` parameter for custom heuristics
- **API version bumped**: From "0.1" to "1.0"

### Input Schema

```json
{
  "api_version": "1.0",
  "file": "path/to/File.lean",
  "config_path": null
}
```

#### Required Parameters

- **file** (string): Path to Lean file to analyze

#### Optional Parameters

- **api_version** (string, default="1.0"): API version for compatibility tracking
- **config_path** (string | null, default=null): Path to custom heuristics configuration file. **NEW in API 1.0**

### Output Schema

Response structure remains the same as API 0.1, with these changes:

- **api_version**: Now "1.0"
- **notes**: Now includes numeric confidence as first item (e.g., `"confidence: 0.85"`)
- **metadata.config_source**: New field indicating configuration source. **NEW in API 1.0**

### Example

**Request:**
```json
{
  "file": "MyFile.lean",
  "config_path": "/path/to/custom_heuristics.yaml"
}
```

**Response:**
```json
{
  "api_version": "1.0",
  "status": "success",
  "run_id": "scan-file-abc123",
  "tool": "scan_file",
  "file": "MyFile.lean",
  "theorems": [
    {
      "theorem_id": "MyFile.my_theorem",
      "range": {"start_line": 10, "end_line": 20},
      "automation_profile": {
        "whole_goal_potential": {"aesop": 0.75, "grind": 0.45},
        "subgoal_potential": {"aesop": 0.65, "grind": 0.50},
        "annotation_value": 0.70
      },
      "notes": [
        "confidence: 0.85",
        "high confidence proof",
        "good aesop candidate"
      ]
    }
  ],
  "summary": {
    "total_theorems": 1,
    "computation_time_ms": 25
  },
  "diagnostics": [],
  "metadata": {
    "config_source": "path"
  }
}
```

---

## scan_theorem

**Purpose:** Performs deep structural analysis of a single theorem for enhanced automation scoring.

**API Version:** 1.0

### Changes in API 1.0

- **Confidence values fixed**: Numeric confidence now appears in notes (e.g., `"confidence: 0.85"`)
- **Configuration support**: Optional `config_path` parameter for custom heuristics
- **API version bumped**: From "0.1" to "1.0"

### Input Schema

```json
{
  "api_version": "1.0",
  "file": "path/to/File.lean",
  "theorem_id": "File.theorem_name",
  "config_path": null
}
```

#### Required Parameters

- **file** (string): Path to Lean file containing the theorem
- **theorem_id** (string): Fully qualified theorem identifier

#### Optional Parameters

- **api_version** (string, default="1.0"): API version for compatibility tracking
- **config_path** (string | null, default=null): Path to custom heuristics configuration file. **NEW in API 1.0**

### Output Schema

Response structure remains the same as API 0.1, with these changes:

- **api_version**: Now "1.0"
- **notes**: Now includes numeric confidence as first item (e.g., `"confidence: 0.85"`)
- **metadata.config_source**: New field indicating configuration source. **NEW in API 1.0**

### Example

**Request:**
```json
{
  "file": "MyFile.lean",
  "theorem_id": "MyFile.my_theorem",
  "config_path": "/path/to/custom_heuristics.yaml"
}
```

**Response:**
```json
{
  "api_version": "1.0",
  "status": "success",
  "run_id": "scan-theorem-xyz789",
  "tool": "scan_theorem",
  "file": "MyFile.lean",
  "theorem_id": "MyFile.my_theorem",
  "automation_profile": {
    "whole_goal_potential": {"aesop": 0.75, "grind": 0.45},
    "subgoal_potential": {"aesop": 0.85, "grind": 0.70},
    "annotation_value": 0.80
  },
  "notes": [
    "confidence: 0.90",
    "very high confidence proof",
    "excellent aesop subgoal candidate",
    "has case analysis structure"
  ],
  "diagnostics": [],
  "metadata": {
    "computation_time_ms": 45,
    "config_source": "path"
  }
}
```
