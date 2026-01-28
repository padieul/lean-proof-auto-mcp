# Design Document: Iterative Orchestration Enhancements

## Overview

This design extends the `search_annotations` MCP tool to provide LLM orchestrators with contextual information needed for effective iterative proof automation. Based on research on Mathlib proof automation, we address five critical issues: subgoal blindness, induction case splitting, hint provenance tracking, cross-file dependency detection, and progress metrics.

The design follows hexagonal architecture principles, keeping core domain logic independent of infrastructure concerns. All enhancements are implemented as optional extensions to existing data structures, maintaining full backward compatibility with API version 0.1.0.

## Architecture

### Hexagonal Architecture Layers>

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                        │
│  (search_annotations.py - argument validation, routing)  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                       │
│  (SearchAnnotationsCommandHandler - orchestration)       │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Domain Layer                          │
│  • SubgoalAnalyzer (new)                                │
│  • CaseDetector (new)                                   │
│  • ProvenanceTracker (new)                              │
│  • DependencyAnalyzer (new)                             │
│  • ProgressCalculator (new)                             │
│  • Enhanced domain models (immutable)                    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                    │
│  • LeanInteractRunner (existing)                        │
│  • WorkspaceProvider (existing)                         │
│  • ArtifactStore (existing)                             │
└─────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Immutability**: All domain models are frozen dataclasses
2. **Dependency Injection**: Services receive dependencies via constructor
3. **Command Pattern**: Each enhancement is triggered by command configuration
4. **Strategy Pattern**: Different analysis strategies can be plugged in
5. **Result Pattern**: All operations return explicit success/failure results
6. **Backward Compatibility**: All new fields are optional, omitted when not populated

## Components and Interfaces

### 1. Enhanced Domain Models

#### SubgoalState

Represents the remaining goal state after partial hint application.

```python
@dataclass(frozen=True)
class SubgoalState:
    """
    Remaining goal state after partial hint application.
    
    Requirements: 1.1, 1.2, 1.3, 1.5
    """
    remaining_goals: list[str]  # List of remaining goal expressions
    applied_hints: list[Hint]  # Hints that were applied to reach this state
    complexity_before: int  # Goal complexity before hints
    complexity_after: int  # Goal complexity after hints
    
    def __post_init__(self) -> None:
        if self.complexity_before < 0:
            raise ValueError("complexity_before must be non-negative")
        if self.complexity_after < 0:
            raise ValueError("complexity_after must be non-negative")
        if self.complexity_after > self.complexity_before:
            raise ValueError("complexity_after cannot exceed complexity_before")
```

#### CaseAnalysis

Represents induction structure and case-specific information.

```python
@dataclass(frozen=True)
class CaseInfo:
    """
    Information about a single case in an inductive proof.
    
    Requirements: 2.3, 2.4, 2.6
    """
    case_label: str  # e.g., "base", "inductive", "zero", "succ"
    goal_expression: str  # The goal for this specific case
    recommended_hints: list[Hint]  # Case-specific hint recommendations
    complexity: int  # Complexity metric for this case
    
    def __post_init__(self) -> None:
        if not self.case_label:
            raise ValueError("case_label must be non-empty")
        if self.complexity < 0:
            raise ValueError("complexity must be non-negative")


@dataclass(frozen=True)
class CaseAnalysis:
    """
    Analysis of induction structure in a theorem.
    
    Requirements: 2.2, 2.3, 2.4, 2.6
    """
    has_induction: bool  # Whether induction structure was detected
    cases: list[CaseInfo]  # List of identified cases
    induction_variable: str | None  # Variable being inducted on
    
    def __post_init__(self) -> None:
        if self.has_induction and not self.cases:
            raise ValueError("has_induction=True requires non-empty cases")
        if not self.has_induction and self.cases:
            raise ValueError("has_induction=False requires empty cases")
```

#### HintProvenance

Represents the source and relevance information for a hint.

```python
@dataclass(frozen=True)
class HintProvenance:
    """
    Provenance information for a hint.
    
    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    source_category: CandidateSource  # Where the hint came from
    source_theorem: str | None  # Source theorem name if applicable
    relevance_score: float  # Relevance score in [0, 1]
    selection_reasoning: str  # Why this hint was selected
    
    def __post_init__(self) -> None:
        if not (0.0 <= self.relevance_score <= 1.0):
            raise ValueError("relevance_score must be in [0, 1]")
        if not self.selection_reasoning:
            raise ValueError("selection_reasoning must be non-empty")
```

#### DependencyAnalysis

Represents cross-file dependency information.

```python
@dataclass(frozen=True)
class DependencyAnalysis:
    """
    Analysis of cross-file dependencies.
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """
    has_missing_dependencies: bool  # Whether missing dependencies were detected
    missing_symbols: list[str]  # List of undefined symbols
    suggested_imports: list[str]  # Suggested import statements
    suggest_global_mode: bool  # Whether to suggest switching to suggest_global
    confidence: float  # Confidence in suggestion, in [0, 1]
    
    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")
        if self.has_missing_dependencies and not self.missing_symbols:
            raise ValueError("has_missing_dependencies=True requires non-empty missing_symbols")
```

#### ProgressMetrics

Represents quantitative progress metrics.

```python
@dataclass(frozen=True)
class ProgressMetrics:
    """
    Quantitative progress metrics for iteration decisions.
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
    """
    complexity_before: int  # Goal complexity before hints
    complexity_after: int  # Goal complexity after hints
    reduction_percentage: float  # (before - after) / before * 100
    blockers: list[str]  # What is blocking progress
    iteration_recommendation: str  # Recommendation for next iteration
    
    def __post_init__(self) -> None:
        if self.complexity_before < 0:
            raise ValueError("complexity_before must be non-negative")
        if self.complexity_after < 0:
            raise ValueError("complexity_after must be non-negative")
        if self.complexity_before > 0:
            expected_reduction = (
                (self.complexity_before - self.complexity_after) 
                / self.complexity_before * 100
            )
            if abs(self.reduction_percentage - expected_reduction) > 0.01:
                raise ValueError("reduction_percentage must match calculated value")
```

#### Enhanced Hint Model

```python
@dataclass(frozen=True)
class Hint:
    """
    Immutable hint for automation (enhanced with provenance).
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    name: str
    type: HintType
    source: CandidateSource
    provenance: HintProvenance | None = None  # Optional provenance info
    
    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")
```

#### Enhanced SearchAnnotationsResult

```python
@dataclass(frozen=True)
class SearchAnnotationsResult:
    """
    Final result from search-annotations execution (enhanced).
    
    Requirements: 6.1, 6.2, 6.4, 6.5, 7.1, 7.2, 7.3
    """
    # Existing fields (unchanged)
    api_version: str
    status: Literal["success", "fail", "timeout", "error"]
    run_id: str
    file: str
    theorem_id: str
    viability: dict[str, Any]
    baseline: dict[str, Any]
    search_result: SearchResult | None
    minimized_hint_set: HintSet | None
    proof_patch: ProofPatch | None
    global_suggestions: list[GlobalSuggestion] | None
    timing: dict[str, float]
    artifacts: dict[str, str]
    metadata: dict[str, Any]
    workflow_recommendation: str | None = None
    
    # New optional fields (omitted from JSON when None)
    subgoal_state: SubgoalState | None = None
    case_analysis: CaseAnalysis | None = None
    dependency_analysis: DependencyAnalysis | None = None
    progress_metrics: ProgressMetrics | None = None
```

### 2. Core Services

#### SubgoalAnalyzer

Analyzes partial outcomes to extract subgoal state.

```python
class SubgoalAnalyzer:
    """
    Analyzes partial outcomes to extract remaining subgoal state.
    
    Requirements: 1.1, 1.2, 1.3, 1.5
    """
    
    def __init__(self, lean_runner: LeanInteractRunner):
        """
        Initialize with Lean execution dependency.
        
        Args:
            lean_runner: Runner for executing Lean commands
        """
        self.lean_runner = lean_runner
    
    def analyze(
        self,
        theorem_id: str,
        applied_hints: list[Hint],
        execution_output: str,
    ) -> SubgoalState:
        """
        Extract subgoal state from partial execution.
        
        Args:
            theorem_id: Theorem being analyzed
            applied_hints: Hints that were applied
            execution_output: Output from Lean execution
            
        Returns:
            SubgoalState with remaining goals and complexity metrics
            
        Requirements: 1.1, 1.2, 1.3, 1.5
        """
        pass  # Implementation details
```

#### CaseDetector

Detects induction structure and identifies cases.

```python
class CaseDetector:
    """
    Detects induction structure in theorems.
    
    Requirements: 2.2, 2.3, 2.4, 2.6
    """
    
    def detect(self, theorem_decl: TheoremDeclaration) -> CaseAnalysis:
        """
        Detect induction structure in a theorem.
        
        Args:
            theorem_decl: Theorem declaration to analyze
            
        Returns:
            CaseAnalysis with detected structure
            
        Requirements: 2.2, 2.3
        """
        pass  # Implementation details
    
    def recommend_hints_for_case(
        self,
        case_info: CaseInfo,
        available_hints: list[Hint],
    ) -> list[Hint]:
        """
        Recommend hints specific to a case.
        
        Args:
            case_info: Case to recommend hints for
            available_hints: Pool of available hints
            
        Returns:
            List of case-specific hint recommendations
            
        Requirements: 2.4
        """
        pass  # Implementation details
```

#### ProvenanceTracker

Tracks hint provenance and relevance.

```python
class ProvenanceTracker:
    """
    Tracks provenance information for hints.
    
    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    
    def __init__(self, index: Index):
        """
        Initialize with theorem index.
        
        Args:
            index: Index of theorems and definitions
        """
        self.index = index
    
    def track(
        self,
        hint: Hint,
        goal_expression: str,
        context: dict[str, Any],
    ) -> HintProvenance:
        """
        Generate provenance information for a hint.
        
        Args:
            hint: Hint to track provenance for
            goal_expression: Current goal expression
            context: Additional context for relevance scoring
            
        Returns:
            HintProvenance with source and relevance information
            
        Requirements: 3.1, 3.2, 3.3, 3.4
        """
        pass  # Implementation details
```

#### DependencyAnalyzer

Analyzes cross-file dependencies.

```python
class DependencyAnalyzer:
    """
    Analyzes cross-file dependencies.
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """
    
    def __init__(self, index: Index):
        """
        Initialize with theorem index.
        
        Args:
            index: Index of theorems and definitions
        """
        self.index = index
    
    def analyze(
        self,
        theorem_decl: TheoremDeclaration,
        current_file: str,
    ) -> DependencyAnalysis:
        """
        Analyze cross-file dependencies for a theorem.
        
        Args:
            theorem_decl: Theorem to analyze
            current_file: Current file path
            
        Returns:
            DependencyAnalysis with missing symbols and suggestions
            
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
        """
        pass  # Implementation details
```

#### ProgressCalculator

Calculates progress metrics.

```python
class ProgressCalculator:
    """
    Calculates progress metrics for iteration decisions.
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
    """
    
    def calculate(
        self,
        complexity_before: int,
        complexity_after: int,
        execution_output: str,
    ) -> ProgressMetrics:
        """
        Calculate progress metrics.
        
        Args:
            complexity_before: Goal complexity before hints
            complexity_after: Goal complexity after hints
            execution_output: Output from Lean execution
            
        Returns:
            ProgressMetrics with reduction and recommendations
            
        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
        """
        pass  # Implementation details
    
    def identify_blockers(self, execution_output: str) -> list[str]:
        """
        Identify what is blocking progress.
        
        Args:
            execution_output: Output from Lean execution
            
        Returns:
            List of identified blockers
            
        Requirements: 5.4
        """
        pass  # Implementation details
```

### 3. Enhanced Command Configuration

```python
@dataclass(frozen=True)
class EnhancementsConfig:
    """
    Configuration for iterative orchestration enhancements.
    
    Requirements: 1.1, 2.1, 3.1, 4.1, 5.1
    """
    enable_subgoal_reporting: bool = False
    enable_case_analysis: bool = False
    enable_provenance_tracking: bool = False
    enable_dependency_detection: bool = False
    enable_progress_metrics: bool = False
    target_case: str | None = None  # For case-specific search


@dataclass(frozen=True)
class SearchAnnotationsCommand:
    """
    Enhanced command with enhancements configuration.
    
    Requirements: 1.1, 2.1, 3.1, 4.1, 5.1
    """
    # Existing fields (unchanged)
    file: str
    theorem_id: str
    mode: Literal["local_only", "suggest_global"]
    automation: AutomationConfig
    budgets: BudgetConfig
    search: SearchConfig
    candidates: CandidateConfig
    skeleton: SkeletonConfig
    style: StyleConfig
    workspace: WorkspaceConfig
    allow_global_edits: bool
    run_id: str
    
    # New optional field
    enhancements: EnhancementsConfig = EnhancementsConfig()
```

## Data Models

### Complexity Calculation

Goal complexity is calculated using a simple heuristic:
- Count of symbols in goal expression
- Nesting depth of expressions
- Number of quantifiers
- Number of function applications

```python
def calculate_complexity(goal_expression: str) -> int:
    """
    Calculate goal complexity metric.
    
    Args:
        goal_expression: Lean goal expression
        
    Returns:
        Complexity score (higher = more complex)
    """
    # Simple heuristic: count symbols, depth, quantifiers
    symbol_count = len(goal_expression.split())
    depth = goal_expression.count('(') + goal_expression.count('[')
    quantifiers = goal_expression.count('∀') + goal_expression.count('∃')
    
    return symbol_count + (depth * 2) + (quantifiers * 3)
```

### Case Detection Heuristics

Induction structure is detected by:
1. Scanning proof for `induction` tactic
2. Extracting case labels from proof structure
3. Identifying the induction variable
4. Parsing case-specific goals

```python
def detect_induction_structure(proof_text: str) -> tuple[bool, list[str], str | None]:
    """
    Detect induction structure in proof.
    
    Args:
        proof_text: Proof text to analyze
        
    Returns:
        Tuple of (has_induction, case_labels, induction_variable)
    """
    # Look for induction tactic
    if 'induction' not in proof_text:
        return (False, [], None)
    
    # Extract case labels (simplified)
    case_labels = []
    for line in proof_text.split('\n'):
        if 'case' in line:
            # Extract case label
            label = line.split('case')[1].strip().split()[0]
            case_labels.append(label)
    
    # Extract induction variable (simplified)
    induction_var = None
    for line in proof_text.split('\n'):
        if 'induction' in line:
            parts = line.split('induction')[1].strip().split()
            if parts:
                induction_var = parts[0]
            break
    
    return (True, case_labels, induction_var)
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Subgoal State Completeness
*For any* search result with `outcome="partial"`, the response should include a non-null `subgoal_state` with all required fields populated (remaining_goals, applied_hints, complexity metrics).

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Complexity Monotonicity
*For any* `SubgoalState` or `ProgressMetrics`, the complexity_after should be less than or equal to complexity_before (hints should not increase complexity).

**Validates: Requirements 1.2, 5.1, 5.2**

### Property 3: Case-Specific Search Correctness
*For any* theorem with induction structure, when searching with a specific `target_case`, all returned hints should be relevant to that case (verified by checking hint provenance and case labels).

**Validates: Requirements 2.1, 2.4**

### Property 4: Induction Detection Accuracy
*For any* theorem containing the `induction` tactic, the `CaseDetector` should correctly identify `has_induction=True` and extract at least one case label.

**Validates: Requirements 2.2, 2.3**

### Property 5: Hint Provenance Completeness
*For any* hint with provenance tracking enabled, the `provenance` field should be non-null and contain valid source_category, relevance_score in [0,1], and non-empty selection_reasoning.

**Validates: Requirements 3.1, 3.3, 3.4**

### Property 6: Dependency Detection Accuracy
*For any* theorem referencing undefined symbols, the `DependencyAnalyzer` should correctly identify `has_missing_dependencies=True` and list those symbols in `missing_symbols`.

**Validates: Requirements 4.1, 4.4**

### Property 7: Progress Reduction Calculation
*For any* `ProgressMetrics`, the `reduction_percentage` should equal `(complexity_before - complexity_after) / complexity_before * 100` (within 0.01% tolerance).

**Validates: Requirements 5.3**

### Property 8: Backward Compatibility - Optional Fields
*For any* `SearchAnnotationsResult`, when enhancement features are disabled, the new optional fields (subgoal_state, case_analysis, dependency_analysis, progress_metrics) should be None and omitted from JSON serialization.

**Validates: Requirements 7.1, 7.2, 7.5**

### Property 9: Backward Compatibility - Existing Fields
*For any* `SearchAnnotationsResult`, all existing fields (api_version, status, run_id, file, theorem_id, etc.) should maintain their original types and names.

**Validates: Requirements 7.3**

### Property 10: Serialization Round-Trip
*For any* valid instance of the new data structures (SubgoalState, CaseAnalysis, HintProvenance, DependencyAnalysis, ProgressMetrics), serializing to JSON then deserializing should produce an equivalent object.

**Validates: Requirements 9.6**

### Property 11: Artifact Logging Completeness
*For any* `SearchAnnotationsResult` with enhancement fields populated, storing via `ArtifactStore` and then loading the result.json file should contain all enhancement data (subgoal_state, case_analysis, dependency_analysis, progress_metrics, hint provenance).

**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**

## Error Handling

### Artifact Logging Integration

The existing `ArtifactStore` interface already handles storing `SearchAnnotationsResult` objects. Since all enhancement fields are part of the `SearchAnnotationsResult` dataclass, they will automatically be included in the stored artifacts when present.

**Key Points:**
1. No changes needed to `ArtifactStore` interface
2. Enhancement fields are serialized via existing `to_json_serializable()` function
3. The `_store_artifacts_and_update_result()` method in `SearchAnnotationsCommandHandler` already handles storing the complete result
4. Artifact structure remains unchanged:
   - `request.json`: Contains the command (including `EnhancementsConfig`)
   - `result.json`: Contains the result (including all enhancement fields when present)
   - `lean_output.log`: Contains execution logs

**Example Artifact Structure with Enhancements:**

```json
{
  "api_version": "0.1.0",
  "status": "success",
  "run_id": "search-20260128-abc123-def456",
  "file": "MyTheorem.lean",
  "theorem_id": "my_theorem",
  "subgoal_state": {
    "remaining_goals": ["∀ n, eval₂_sum n = ..."],
    "applied_hints": [{"name": "R", "type": "add_safe", "source": "goal_symbols"}],
    "complexity_before": 45,
    "complexity_after": 32
  },
  "case_analysis": {
    "has_induction": true,
    "cases": [
      {
        "case_label": "base",
        "goal_expression": "eval₂_sum 0 = ...",
        "recommended_hints": [...],
        "complexity": 15
      },
      {
        "case_label": "succ",
        "goal_expression": "eval₂_sum (n + 1) = ...",
        "recommended_hints": [...],
        "complexity": 30
      }
    ],
    "induction_variable": "n"
  },
  "dependency_analysis": {
    "has_missing_dependencies": false,
    "missing_symbols": [],
    "suggested_imports": [],
    "suggest_global_mode": false,
    "confidence": 0.95
  },
  "progress_metrics": {
    "complexity_before": 45,
    "complexity_after": 32,
    "reduction_percentage": 28.89,
    "blockers": [],
    "iteration_recommendation": "Good progress. Try adding 'sum' hint based on domain knowledge."
  },
  "minimized_hint_set": {
    "hints": [
      {
        "name": "R",
        "type": "add_safe",
        "source": "goal_symbols",
        "provenance": {
          "source_category": "goal_symbols",
          "source_theorem": null,
          "relevance_score": 0.85,
          "selection_reasoning": "Symbol 'R' appears in goal expression"
        }
      }
    ]
  },
  ...
}
```

### Error Categories

1. **Analysis Errors**: Failures in subgoal/case/dependency analysis
   - Log warning and continue without enhancement data
   - Return partial result with available information

2. **Performance Timeout**: Enhancement computation exceeds budget
   - Log warning and skip remaining enhancements
   - Return result with completed enhancements only

3. **Validation Errors**: Invalid enhancement configuration
   - Return error response with clear message
   - Do not proceed with search

### Error Handling Strategy

```python
def handle_enhancement_error(
    enhancement_name: str,
    error: Exception,
    result: SearchAnnotationsResult,
) -> SearchAnnotationsResult:
    """
    Handle enhancement errors gracefully.
    
    Strategy:
    1. Log warning with error details
    2. Set enhancement field to None
    3. Add error to metadata
    4. Continue with remaining enhancements
    
    Requirements: 12.1, 12.2, 12.3
    """
    logger.warning(f"{enhancement_name} failed: {error}")
    
    # Add error to metadata
    metadata = dict(result.metadata)
    metadata[f"{enhancement_name}_error"] = str(error)
    
    # Return result with updated metadata
    return SearchAnnotationsResult(
        **{**asdict(result), "metadata": metadata}
    )
```

## Testing Strategy

### Unit Tests

Unit tests focus on:
- Individual service behavior (SubgoalAnalyzer, CaseDetector, etc.)
- Data model validation (invalid inputs raise ValueError)
- Error handling paths
- Edge cases (empty hints, no induction, etc.)
- Artifact logging integration (verify enhancement data in artifacts)

### Property-Based Tests

Property tests verify universal properties across randomized inputs:

1. **Complexity Monotonicity** (Property 2)
   - Generate random SubgoalState instances
   - Verify complexity_after <= complexity_before
   - Tag: **Feature: iterative-orchestration-enhancements, Property 2**

2. **Progress Calculation** (Property 7)
   - Generate random complexity values
   - Calculate ProgressMetrics
   - Verify reduction_percentage formula
   - Tag: **Feature: iterative-orchestration-enhancements, Property 7**

3. **Serialization Round-Trip** (Property 10)
   - Generate random instances of all new data structures
   - Serialize to JSON, deserialize, compare
   - Verify equivalence
   - Tag: **Feature: iterative-orchestration-enhancements, Property 10**

4. **Backward Compatibility** (Properties 8, 9)
   - Generate random SearchAnnotationsResult with/without enhancements
   - Verify optional fields omitted when None
   - Verify existing fields unchanged
   - Tag: **Feature: iterative-orchestration-enhancements, Property 8, Property 9**

5. **Artifact Logging Completeness** (Property 11)
   - Generate random SearchAnnotationsResult with enhancements
   - Store via ArtifactStore
   - Load result.json and verify all enhancement fields present
   - Tag: **Feature: iterative-orchestration-enhancements, Property 11**

### Integration Tests

Integration tests verify:
- End-to-end enhancement workflow
- Interaction between services
- Real Lean execution with enhancements
- Artifact storage with enhanced results
- Artifact retrieval and inspection

### Test Configuration

- Minimum 100 iterations per property test
- Use Hypothesis library for property-based testing
- Mock LeanInteractRunner for unit tests
- Use real Lean for integration tests
- Verify artifact files after each integration test

## Implementation Notes

### Phase 1: Core Data Models (Week 1)
- Implement SubgoalState, CaseAnalysis, HintProvenance, DependencyAnalysis, ProgressMetrics
- Add optional fields to SearchAnnotationsResult
- Implement JSON serialization with omit-when-None behavior
- Write property tests for serialization round-trip

### Phase 2: Subgoal Analysis (Week 1-2)
- Implement SubgoalAnalyzer
- Integrate into SearchAnnotationsCommandHandler
- Add enable_subgoal_reporting configuration
- Write unit and property tests

### Phase 3: Provenance Tracking (Week 2)
- Implement ProvenanceTracker
- Enhance Hint model with provenance field
- Integrate into candidate generation
- Write unit and property tests

### Phase 4: Dependency Detection (Week 3)
- Implement DependencyAnalyzer
- Integrate into viability check phase
- Add mode switch suggestions
- Write unit and property tests

### Phase 5: Case Analysis (Month 2)
- Implement CaseDetector
- Add target_case parameter support
- Integrate case-specific search
- Write unit and property tests

### Phase 6: Progress Metrics (Month 2)
- Implement ProgressCalculator
- Integrate into result building
- Add iteration recommendations
- Write unit and property tests

### Backward Compatibility Strategy

1. All new fields are optional (default to None)
2. JSON serialization omits None fields
3. API version remains "0.1.0"
4. Existing clients see no changes
5. New clients opt-in via EnhancementsConfig

### Performance Considerations

- Subgoal analysis: Parse Lean output once, cache results
- Case detection: Scan proof text once during viability check
- Provenance tracking: Compute relevance scores lazily
- Dependency analysis: Reuse existing index, no additional Lean calls
- Progress metrics: Compute from cached complexity values

Target overhead: < 500ms total for all enhancements combined
