# Requirements: scan-rank-shared-semantics

## Problem Statement

The `scan_file`, `scan_theorem`, and `rank_targets` tools share common semantic concepts (confidence, automation potential, already-automated detection) but currently have inconsistent implementations and missing functionality. This spec addresses critical gaps:

1. **Confidence is broken**: Calculated internally but always returns 0.0 in tool outputs
2. **No skip-already-automated**: Tools recommend theorems that already use aesop/grind
3. **Poor objective UX**: Clients must guess valid objective names through trial-and-error
4. **Pessimistic scoring**: Top scores (~0.34-0.38) feel mediocre, lacking human-friendly tiers

This spec defines shared semantics and fixes to make these tools production-ready.

## User Stories

### US-1: Confidence Values Are Exposed and Usable
**As a** user filtering theorems by confidence  
**I want to** see actual confidence values (not 0.0) in tool outputs  
**So that** I can filter unreliable analyses and trust min_confidence filtering

**Acceptance Criteria:**
- 1.1: `scan_file` includes numeric confidence in notes (e.g., "confidence: 0.85")
- 1.2: `scan_theorem` includes numeric confidence in notes
- 1.3: `rank_targets` correctly extracts confidence from notes into signals
- 1.4: Confidence values reflect actual calculation from `_calculate_confidence()`
- 1.5: When min_confidence > 0, theorems are actually filtered (not all skipped)
- 1.6: Summary reports accurate skipped_low_confidence counts

**Current Bug:**
```python
# scoring.py _generate_notes() - WRONG
if features.confidence >= 0.8:
    notes.append("high confidence proof")  # ❌ No numeric value

# Should be:
notes.append(f"confidence: {features.confidence:.2f}")  # ✓
```

### US-2: Skip Already-Automated Theorems
**As a** user prioritizing annotation work  
**I want to** exclude theorems that already use automation tactics  
**So that** I don't waste time "improving" proofs that are already automated

**Acceptance Criteria:**
- 2.1: `rank_targets` accepts `skip_already_automated` boolean parameter (default: false)
- 2.2: When enabled, filters theorems containing aesop/grind/simp tactics in proof
- 2.3: When enabled, filters theorems with @[aesop], @[simp] attributes
- 2.4: Summary reports `skipped_already_automated` count
- 2.5: Detection works for both tactic-mode and term-mode proofs
- 2.6: Detection is conservative (false negatives OK, false positives not OK)

**Detection Rules:**
- Proof contains: `by aesop`, `by grind`, `by simp`, `aesop`, `grind`, `simp`
- Declaration has: `@[aesop]`, `@[simp]`, `@[aesop safe]`, etc.
- Proof is trivial: `:= by rfl`, `:= rfl`, `:= trivial`

### US-3: Objective Discovery and Validation
**As a** client using rank_targets  
**I want to** discover valid objectives without trial-and-error  
**So that** I don't get schema errors when exploring ranking strategies

**Acceptance Criteria:**
- 3.1: `rank_targets` response includes `available_objectives` array
- 3.2: Each objective includes: name, description, use_case
- 3.3: Invalid objective errors include list of valid objectives
- 3.4: Documentation clearly explains each objective's weighting strategy
- 3.5: Clients can query objectives without running full analysis

**Response Format:**
```json
{
  "available_objectives": [
    {
      "name": "maximize_success",
      "description": "Prioritize theorems most likely to be automated successfully",
      "use_case": "When you want quick wins and high success rate",
      "weights": {
        "success_likelihood": 0.50,
        "impact": 0.10,
        "risk": -0.20
      }
    },
    // ... other objectives
  ]
}
```

### US-4: Human-Friendly Score Tiers
**As a** user reviewing ranked theorems  
**I want to** see intuitive quality tiers (S/A/B/C/D)  
**So that** I can quickly identify excellent vs mediocre candidates

**Acceptance Criteria:**
- 4.1: Each ranked theorem includes `tier` field (S/A/B/C/D)
- 4.2: Tier is computed from percentile rank within the file
- 4.3: Tier thresholds: S (top 10%), A (10-25%), B (25-50%), C (50-75%), D (75-100%)
- 4.4: Tier is independent of absolute score (relative to file)
- 4.5: Summary includes tier distribution counts
- 4.6: Raw score remains available for programmatic use

**Tier Semantics:**
- **S-tier**: Exceptional candidates, highest priority
- **A-tier**: Strong candidates, high priority
- **B-tier**: Good candidates, medium priority
- **C-tier**: Acceptable candidates, lower priority
- **D-tier**: Weak candidates, consider skipping

### US-5: Already-Automated Penalty Component
**As a** user who wants nuanced control  
**I want to** down-rank (not skip) already-automated theorems  
**So that** I can still see them but prioritize unannotated work

**Acceptance Criteria:**
- 5.1: Component scores include `already_automated_penalty` (0.0-1.0)
- 5.2: Penalty is 0.0 for unannotated theorems
- 5.3: Penalty is 0.3 for theorems using automation tactics
- 5.4: Penalty is 0.5 for theorems with automation attributes
- 5.5: Penalty is 0.8 for trivial proofs (rfl, trivial)
- 5.6: Penalty reduces final score proportionally
- 5.7: Penalty is visible in component breakdown

**Integration with skip_already_automated:**
- When `skip_already_automated=false`: penalty applied, theorems ranked lower
- When `skip_already_automated=true`: theorems filtered out entirely

### US-6: Confidence Default is Safe
**As a** new user trying rank_targets  
**I want to** see results on first try (not empty list)  
**So that** I can evaluate the tool before tuning parameters

**Acceptance Criteria:**
- 6.1: Default `min_confidence` is 0.0 (no filtering)
- 6.2: Documentation warns that confidence may be unreliable
- 6.3: Tool suggests trying min_confidence=0.0 if results are empty
- 6.4: Error message when all theorems filtered includes diagnostic hint

**Error Message Example:**
```json
{
  "status": "success",
  "ranking": [],
  "summary": {
    "total": 141,
    "returned": 0,
    "skipped_low_confidence": 141
  },
  "diagnostics": [{
    "severity": "warning",
    "message": "All theorems filtered by min_confidence=0.5. Try min_confidence=0.0 to see all results."
  }]
}
```

### US-7: Configurable Heuristic Parameters
**As a** researcher or power user tuning automation scoring  
**I want to** adjust heuristic thresholds and weights without modifying code  
**So that** I can experiment with scoring strategies and adapt to different codebases

**Acceptance Criteria:**
- 7.1: All hardcoded heuristic values are externalized to configuration
- 7.2: Configuration is loaded from external file with validation
- 7.3: Default configuration ships with the package and works out of box
- 7.4: Users can override defaults by providing custom config file
- 7.5: Configuration is versioned for compatibility tracking
- 7.6: Invalid configuration fails fast with helpful diagnostics
- 7.7: Configuration changes don't require code recompilation

**Categories of Configurable Parameters:**
- Confidence calculation thresholds and bonuses
- Aesop scoring heuristics (base scores, bonuses, penalties, thresholds)
- Grind scoring heuristics (base scores, bonuses, penalties, thresholds)
- Annotation value scoring heuristics
- Subgoal potential scoring heuristics
- Risk scoring thresholds and weights
- Impact scoring thresholds and weights
- Success likelihood scoring weights
- Objective weight configurations (all 4 objectives)
- Already-automated detection patterns and penalties
- Tier percentile thresholds (S/A/B/C/D)

**Note:** Specific parameter values and configuration file format will be defined in design.md

## Non-Functional Requirements

### NFR-1: Backward Compatibility
- Existing `rank_targets` calls continue to work unchanged
- New parameters are optional with safe defaults
- Response schema is extended (not changed)
- API version bumped to indicate new features

### NFR-2: Performance
- Already-automated detection adds < 5ms overhead
- Tier computation adds < 2ms overhead
- Confidence extraction adds < 1ms overhead
- Total overhead < 10ms for 200 theorems

### NFR-3: Determinism
- Already-automated detection is deterministic
- Tier assignments are stable for same input
- Confidence values are deterministic
- All new features maintain deterministic output

### NFR-4: Conservative Detection
- Already-automated detection prefers false negatives over false positives
- Better to recommend an automated theorem than skip a manual one
- Detection uses explicit pattern matching (no heuristics)

### NFR-5: Documentation
- All new parameters documented in tool contract
- Objective descriptions are clear and actionable
- Tier semantics are well-defined
- Migration guide for existing users

### NFR-6: Configuration Flexibility
- Configuration is optional (defaults work out of box)
- Configuration is validated on load with clear errors
- Invalid configuration fails fast before any analysis
- Configuration changes don't require code recompilation
- Configuration is versioned for compatibility tracking

## Technical Design Constraints

### Confidence Fix Location
- Modify `core/scoring.py` in `_generate_notes()` function
- Add numeric confidence value to notes list

### Already-Automated Detection
- Create new module for detection logic
- Detection must be conservative (prefer false negatives)
- Use explicit pattern matching (no heuristics)

### Configuration System
- Configuration must be optional (defaults work out of box)
- Configuration must be immutable once loaded
- Configuration must follow hexagonal architecture (port/adapter pattern)
- Scoring functions receive configuration via dependency injection

### API Changes
- All new parameters are optional with backward-compatible defaults
- Response schema is extended (not changed)
- API version must be bumped to indicate new features

## Dependencies

### Modified Modules
- `core/scoring.py`: Fix confidence note generation
- `core/ranking.py`: Add tier computation, objective metadata, already-automated penalty
- `tools/rank_targets.py`: Add skip_already_automated parameter, available_objectives response

### New Modules
- `core/automation_detection.py`: Already-automated detection logic
- `core/config.py`: Configuration loading and validation
- Default configuration file (format TBD in design.md)

### Unchanged Modules
- `core/features.py`: Confidence calculation already works
- `core/indexer.py`: No changes needed
- `tools/scan_file.py`: Inherits fix from scoring.py
- `tools/scan_theorem.py`: Inherits fix from scoring.py

## Success Metrics

### Confidence Fix
- ✅ min_confidence=0.5 returns non-empty results for typical files
- ✅ Confidence values in [0.0, 1.0] range, not all 0.0
- ✅ Confidence correlates with proof detection quality

### Skip Already-Automated
- ✅ Filters out theorems with `by aesop`, `by grind`, `by simp`
- ✅ Filters out theorems with @[aesop], @[simp] attributes
- ✅ No false positives (manual proofs not filtered)

### Objective UX
- ✅ Clients can discover objectives without errors
- ✅ Invalid objective errors are helpful
- ✅ Objective descriptions are clear

### Score Tiers
- ✅ S-tier theorems are genuinely excellent candidates
- ✅ Tier distribution is reasonable (not all D-tier)
- ✅ Users prefer tier over raw score for quick scanning

### Configuration System
- ✅ Users can tune heuristics without code changes
- ✅ Default config works well for typical Lean codebases
- ✅ Invalid config fails fast with helpful errors
- ✅ Configuration changes are reproducible and shareable
- ✅ Researchers can experiment with scoring strategies

## Out of Scope

- Modifying confidence calculation algorithm (already works)
- Adding new objectives beyond the existing 4 (users can define custom via config)
- Detecting automation in dependencies (only current theorem)
- Machine learning or heuristic-based detection
- Caching or cross-file analysis
- GUI for configuration editing (YAML editing is sufficient)

## Migration Guide

### For Existing Users
1. **No breaking changes**: All existing calls work unchanged
2. **Confidence now works**: If you were using min_confidence, it now actually filters
3. **New parameters are optional**: skip_already_automated defaults to false
4. **Response includes new fields**: tier, available_objectives, already_automated_penalty

### For New Users
1. Start with `min_confidence=0.0` (default)
2. Use `skip_already_automated=true` to focus on unannotated work
3. Look at `tier` field for quick quality assessment
4. Check `available_objectives` to understand ranking strategies
5. Use default `heuristics.yaml` initially, tune later if needed
6. Share custom configs with team for consistent scoring
