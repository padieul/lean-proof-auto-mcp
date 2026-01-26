# Requirements: rank_targets MCP Tool

## Problem Statement

The `rank_targets` tool provides deterministic, interpretable ranking of theorem-like declarations within a Lean file to support proof automation decision-making. It consumes static analysis signals from `scan_file` (and optionally `scan_theorem`) to rank theorems according to explicit objectives, enabling both interactive users and automated agents to prioritize automation efforts effectively.

## User Stories

### US-1: Interactive Proof Automation Prioritization
**As a** Lean developer working on a file with many theorems
**I want to** see which theorems are most likely to benefit from automation
**So that** I can focus my manual annotation efforts on high-value targets

**Acceptance Criteria:**
- 1.1: Tool accepts a file path and returns ranked list of theorems
- 1.2: Each ranked theorem includes score, components, and human-readable reasons
- 1.3: Rankings are stable and deterministic across multiple invocations
- 1.4: Tool completes in < 50ms for files with up to 200 theorems
- 1.5: Tool provides clear diagnostics for any issues encountered

### US-2: Objective-Driven Ranking
**As a** user with specific automation goals
**I want to** rank theorems according to different objectives
**So that** I can optimize for success rate, impact, or other criteria

**Acceptance Criteria:**
- 2.1: Tool supports at least 4 objectives: maximize_success, maximize_impact, maximize_subgoal_automation, balanced
- 2.2: Each objective uses different component weightings that reflect its goal
- 2.3: Same file with different objectives produces different rankings
- 2.4: Objective weightings are documented and interpretable
- 2.5: Rankings for each objective are deterministic

### US-3: Confidence-Based Filtering
**As a** user working with uncertain proof boundaries
**I want to** filter out low-confidence theorem detections
**So that** I only see theorems where the analysis is reliable

**Acceptance Criteria:**
- 3.1: Tool accepts min_confidence parameter (0.0-1.0)
- 3.2: Theorems below threshold are excluded from ranking
- 3.3: Summary reports how many theorems were skipped due to confidence
- 3.4: Default min_confidence is 0.0 (no filtering)

### US-4: Transparent Scoring
**As a** user evaluating automation recommendations
**I want to** understand why each theorem received its score
**So that** I can validate the ranking logic and make informed decisions

**Acceptance Criteria:**
- 4.1: Each ranked theorem includes component scores (success_likelihood, impact, etc.)
- 4.2: Each ranked theorem includes human-readable reasons
- 4.3: Component scores are normalized to [0.0, 1.0] range
- 4.4: Reasons reference specific features from scan_file analysis
- 4.5: Users can disable component/reason output for performance

### US-5: Batch Processing for Agents
**As an** automated agent processing multiple files
**I want to** rank theorems efficiently without deep structure analysis
**So that** I can make quick decisions at scale

**Acceptance Criteria:**
- 5.1: Tool operates purely on scan_file output by default
- 5.2: Tool provides use_deep_structure flag for optional scan_theorem integration
- 5.3: Tool completes in < 50ms for 200 theorems without deep structure
- 5.4: Tool provides run_id for artifact correlation
- 5.5: Tool returns structured JSON conforming to schema

### US-6: Resilient to Missing Data
**As a** user working with incomplete or evolving scan_file output
**I want to** get rankings even when some fields are missing
**So that** the tool remains useful as the codebase evolves

**Acceptance Criteria:**
- 6.1: Tool handles missing optional fields gracefully with defaults
- 6.2: Tool provides diagnostics when using fallback values
- 6.3: Tool never fails due to missing optional scan_file fields
- 6.4: Tool validates required fields and fails fast with clear errors

## Non-Functional Requirements

### NFR-1: Determinism
- All rankings must be deterministic: same inputs produce identical outputs
- Tie-breaking must use stable, explicit rules (theorem_id, then source order)
- Floating-point operations must use consistent rounding
- JSON output must have stable key ordering

### NFR-2: Performance
- Target: < 50ms for 200 theorems without deep structure analysis
- Target: < 200ms for 200 theorems with deep structure analysis
- No Lean execution or compilation
- No LLM calls or network requests

### NFR-3: Transparency
- All scoring components must be interpretable
- Component weightings must be documented
- Reasons must reference observable features
- No "black box" scoring

### NFR-4: API Stability
- Tool contract versioned with api_version field
- Schema changes require version bump
- Backward compatibility maintained within major version

### NFR-5: Error Handling
- All errors return structured JSON with status="fail"
- Diagnostics include severity levels (error, warning, info)
- Tool never crashes or returns invalid JSON
- Partial results returned when possible

## Dependencies

### Existing Tools (Do Not Modify)
- **scan_file**: Provides per-theorem features and automation signals
  - Returns: theorem_id, location, automation scores, notes
  - Used as primary data source for ranking
- **scan_theorem**: Provides deep structure analysis
  - Returns: skeleton, blocks, cases
  - Used only when use_deep_structure=true

### Core Modules (Read-Only)
- **core.features**: TheoremFeatures extraction
- **core.scoring**: AutomationProfile computation
- **core.format**: Deterministic output formatting
- **core.indexer**: Theorem indexing

## Out of Scope

- Modifying scan_file or scan_theorem implementations
- Running Lean compiler or type checker
- Making LLM calls or policy decisions
- Modifying source files or applying patches
- Caching across invocations (each call is stateless)
