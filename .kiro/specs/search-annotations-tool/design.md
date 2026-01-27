# Design Document: Search Annotations Tool

## Overview

The Search Annotations Tool is a sophisticated proof automation enhancement system that discovers minimal sets of local proof hints to make Lean theorems provable by automation. The system follows hexagonal architecture principles, separating core search logic from external concerns (file I/O, Lean execution, Git operations) through explicit ports and adapters.

The tool operates in phases: viability validation, baseline assessment, candidate generation, hint set search, minimization, and result reporting. Each phase has configurable time budgets and produces structured results. The system uses dependency injection throughout, with all external services provided as abstract ports.

## Architecture

### Simplified Hexagonal Architecture

The tool follows hexagonal architecture by **directly reusing existing core services** without additional port wrappers:

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Tool Layer                          │
│  search_annotations() (entry point, parameter validation)   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Application Layer (New)                        │
│  SearchAnnotationsCommand, SearchAnnotationsCommandHandler  │
│  (orchestration, workflow, budget enforcement)              │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Core Domain (New Components)                   │
│  CandidateGenerator, SearchStrategy (Beam/Greedy)          │
│  Minimizer, ProofPatchBuilder                              │
│  HintSet, Candidate, SearchResult                          │
│  (search-specific business logic)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         Existing Core Services (Reused Directly)            │
│  ProbeCommandHandler, VerifyCommandHandler                  │
│  build_index(), find_by_id() from core/indexer             │
│  (no wrappers needed)                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│         Existing Adapters (Reused Directly)                 │
│  LeanInteractRunner, WorkspaceProvider                      │
│  FilesystemArtifactStore, HeuristicClassifier               │
│  (already implement hexagonal architecture)                 │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

1. **No additional port abstractions**: Directly use existing `ProbeCommandHandler`, `VerifyCommandHandler`, etc.
2. **Reuse existing adapters**: `LeanInteractRunner`, `WorkspaceProvider`, `FilesystemArtifactStore`
3. **New components only for search logic**: `CandidateGenerator`, `SearchStrategy`, `Minimizer`
4. **Composition root pattern**: Wire dependencies in `_create_handler()` function (same as probe.py, verify.py)

### Dependency Flow

- MCP Tool → SearchAnnotationsCommandHandler → Search Components → Existing Core Services → Existing Adapters
- All wiring happens in composition root
- No tool-to-tool calls (direct service usage)

## Components and Interfaces

### 1. Command and Handler (Application Layer)

**SearchAnnotationsCommand** (immutable data structure):
```python
@dataclass(frozen=True)
class SearchAnnotationsCommand:
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
```

**SearchAnnotationsCommandHandler**:
```python
class SearchAnnotationsCommandHandler:
    """Orchestrate search workflow using existing services."""
    
    def __init__(
        self,
        probe_handler: ProbeCommandHandler,  # Reuse existing
        candidate_generator: CandidateGenerator,
        search_strategy: SearchStrategy,
        minimizer: Minimizer,
        artifact_store: FilesystemArtifactStore  # Reuse existing
    ):
        self.probe_handler = probe_handler
        self.candidate_generator = candidate_generator
        self.search_strategy = search_strategy
        self.minimizer = minimizer
        self.artifact_store = artifact_store
    
    def handle(self, cmd: SearchAnnotationsCommand) -> SearchAnnotationsResult:
        """Execute complete search workflow."""
        # 1. Viability check (using existing indexer)
        # 2. Baseline probe (using probe_handler)
        # 3. Generate candidates (using candidate_generator)
        # 4. Search for closing hints (using search_strategy)
        # 5. Minimize hint set (using minimizer)
        # 6. Build proof patch
        # 7. Store artifacts (using artifact_store)
        ...
```

### 2. Core Domain Services (New Components)

**CandidateGenerator**:
```python
class CandidateGenerator:
    """Generate candidate hints from theorem and context."""
    
    def __init__(self, source: SourceText, index: TheoremIndex):
        self.source = source
        self.index = index
    
    def generate(
        self,
        theorem_decl: TheoremDecl,
        sources: list[str],
        config: CandidateConfig
    ) -> list[Candidate]:
        """Generate candidates from configured sources."""
        candidates = []
        
        if "goal_symbols" in sources:
            candidates.extend(self._extract_from_goal(theorem_decl))
        if "local_context" in sources:
            candidates.extend(self._extract_from_context(theorem_decl))
        if "same_namespace" in sources:
            candidates.extend(self._extract_from_namespace(theorem_decl))
        if "nearby_decls" in sources:
            candidates.extend(self._extract_nearby(theorem_decl))
        if "original_proof_refs" in sources:
            candidates.extend(self._extract_from_proof(theorem_decl))
        
        return self._rank_and_deduplicate(candidates, config)
```

**SearchStrategy** (Strategy Pattern):
```python
class SearchStrategy(Protocol):
    """Abstract search strategy."""
    def search(
        self,
        candidates: list[Candidate],
        probe_fn: Callable[[HintSet], ProbeResult],
        config: SearchConfig
    ) -> HintSet | None:
        """Search for closing hint set."""
        ...

class BeamSearch:
    """Beam search implementation."""
    def search(
        self,
        candidates: list[Candidate],
        probe_fn: Callable[[HintSet], ProbeResult],
        config: SearchConfig
    ) -> HintSet | None:
        """Maintain beam_width hint sets, expand by adding candidates."""
        ...

class GreedySearch:
    """Greedy search implementation."""
    def search(
        self,
        candidates: list[Candidate],
        probe_fn: Callable[[HintSet], ProbeResult],
        config: SearchConfig
    ) -> HintSet | None:
        """Start empty, add best candidate each step."""
        ...
```

**Minimizer**:
```python
class Minimizer:
    """Delta-debug minimization."""
    
    def minimize(
        self,
        hint_set: HintSet,
        probe_fn: Callable[[HintSet], ProbeResult]
    ) -> HintSet:
        """Remove redundant hints iteratively."""
        current = hint_set
        changed = True
        
        while changed:
            changed = False
            for hint in current.hints:
                candidate = current.remove(hint)
                result = probe_fn(candidate)
                if result.probe_result.outcome == "closed":
                    current = candidate
                    changed = True
                    break
        
        return current
```

**ProofPatchBuilder**:
```python
class ProofPatchBuilder:
    """Generate ready-to-paste Lean proof code."""
    
    def build(
        self,
        hint_set: HintSet,
        automation: str,
        style: StyleConfig
    ) -> ProofPatch:
        """Generate proof patch with style preferences."""
        # Apply style rules:
        # - prefer_simp_over_aesop
        # - emit_compact
        # - simp_only_list
        ...
```

### 3. Existing Services (Reused Directly)

**From `core/indexer.py`**:
```python
def build_index(source: SourceText) -> TheoremIndex:
    """Build theorem index from source."""
    ...

def find_by_id(index: TheoremIndex, theorem_id: str) -> TheoremDecl | None:
    """Locate theorem by ID."""
    ...
```

**From `core/probe_domain.py`**:
```python
class ProbeCommandHandler:
    """Execute automation probes (existing service)."""
    def __init__(
        self,
        lean_runner: LeanRunner,
        workspace_provider: WorkspaceProvider,
        classifier: AutomationClassifier
    ):
        ...
    
    def handle(self, cmd: ProbeCommand) -> ProbeResult:
        """Execute probe workflow."""
        ...
```

**From `core/verify_domain.py`**:
```python
class VerifyCommandHandler:
    """Execute verification (existing service)."""
    def __init__(
        self,
        lean_runner: LeanRunner,
        workspace_provider: WorkspaceProvider,
        artifact_store: ArtifactStore
    ):
        ...
    
    def handle(self, cmd: VerifyCommand) -> VerifyResult:
        """Execute verification workflow."""
        ...
```

**From `adapters/lean_interact_runner.py`**:
```python
class LeanInteractRunner:
    """Execute Lean processes with timeout (existing adapter)."""
    def __init__(self, timeout_buffer_ms: int = 100):
        ...
    
    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float
    ) -> LeanRunResult:
        ...
```

**From `adapters/workspace_provider.py`**:
```python
def create_workspace_provider(
    workspace_mode: str | None,
    project_root: Path,
    worktree_dir: Path
) -> WorkspaceProvider:
    """Create workspace provider (existing factory)."""
    ...
```

**From `adapters/artifact_store.py`**:
```python
class FilesystemArtifactStore:
    """Store artifacts to disk (existing adapter)."""
    def __init__(self, artifacts_dir: Path):
        ...
    
    def store(
        self,
        run_id: str,
        command: Any,
        result: Any,
        full_logs: str
    ) -> None:
        ...
```

## Composition Root

The tool entry point wires dependencies following the same pattern as `probe.py` and `verify.py`:

```python
def search_annotations(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool entry point."""
    try:
        command = _build_command(args)
    except ValueError as e:
        return _build_error_response(str(e), "input_validation_error")
    
    try:
        handler = _create_handler(command.file)
        result = handler.handle(command)
        return asdict(result)
    except Exception as e:
        logger.exception(f"Search failed for {command.file}:{command.theorem_id}")
        return _build_error_response(str(e), "internal_error")


def _create_handler(file_path: str) -> SearchAnnotationsCommandHandler:
    """Create handler with real services (composition root)."""
    # Detect project root
    file_path_obj = Path(file_path).resolve()
    project_root = _find_lean_project_root(file_path_obj)
    if project_root is None:
        project_root = file_path_obj.parent
    
    # Create existing adapters (reuse pattern from probe.py)
    lean_runner = LeanInteractRunner(timeout_buffer_ms=100)
    workspace_provider = create_workspace_provider(
        workspace_mode=None,  # Auto-detect
        project_root=project_root,
        worktree_dir=project_root / ".worktrees"
    )
    classifier = HeuristicClassifier()
    artifact_store = FilesystemArtifactStore(Path(".artifacts"))
    
    # Create probe handler (reuse existing)
    probe_handler = ProbeCommandHandler(
        lean_runner=lean_runner,
        workspace_provider=workspace_provider,
        classifier=classifier
    )
    
    # Create search-specific components
    source = SourceText(path=file_path, text=Path(file_path).read_text())
    index = build_index(source)
    candidate_generator = CandidateGenerator(source, index)
    search_strategy = BeamSearch()  # or GreedySearch based on config
    minimizer = Minimizer()
    
    # Wire into handler
    return SearchAnnotationsCommandHandler(
        probe_handler=probe_handler,
        candidate_generator=candidate_generator,
        search_strategy=search_strategy,
        minimizer=minimizer,
        artifact_store=artifact_store
    )
```

This follows the exact pattern from existing tools - no port wrappers, direct service usage.

### HintSet
```python
@dataclass(frozen=True)
class HintSet:
    hints: frozenset[Hint]
    
    def add(self, hint: Hint) -> HintSet:
        return HintSet(self.hints | {hint})
    
    def remove(self, hint: Hint) -> HintSet:
        return HintSet(self.hints - {hint})
    
    def size(self) -> int:
        return len(self.hints)
```

### Hint
```python
@dataclass(frozen=True)
class Hint:
    name: str
    type: HintType  # AddSafe, AddUnsafe, Unfold, Simp, RuleSet
    source: CandidateSource
    
    def to_lean_syntax(self) -> str:
        ...
```

### Candidate
```python
@dataclass(frozen=True)
class Candidate:
    hint: Hint
    rank: float
    metadata: dict[str, Any]
```

### SearchResult
```python
@dataclass(frozen=True)
class SearchResult:
    outcome: Literal["closed", "partial", "failed"]
    best_hint_set: HintSet | None
    attempts: int
    explored_sets: int
    evidence: ExecutionOutcome | None
```

### ExecutionOutcome
```python
@dataclass(frozen=True)
class ExecutionOutcome:
    status: Literal["success", "failure", "timeout", "error"]
    automation_used: str
    duration_s: float
    output: str
    error: str | None
```

### ProofPatch
```python
@dataclass(frozen=True)
class ProofPatch:
    lean_code: str
    hint_set: HintSet
    automation: str
    style: StyleConfig
```

### GlobalSuggestion
```python
@dataclass(frozen=True)
class GlobalSuggestion:
    hint_name: str
    attribute: str  # "@[aesop]", "@[simp]", etc.
    rationale: str
    confidence: Literal["high", "medium", "low"]
```

### BudgetConfig
```python
@dataclass(frozen=True)
class BudgetConfig:
    viability_check_s: float
    baseline_probe_s: float
    search_total_s: float
    candidate_trial_s: float
    minimize_total_s: float
    final_verify_s: float
```

### SearchConfig
```python
@dataclass(frozen=True)
class SearchConfig:
    strategy: Literal["beam", "greedy"]
    beam_width: int
    max_steps: int
    max_hints: int
    stop_on_first_close: bool
```

### CandidateConfig
```python
@dataclass(frozen=True)
class CandidateConfig:
    sources: list[CandidateSource]
    max_candidates_per_source: int
    allow_simp_hints: bool
    allow_unfold_hints: bool
```

### StyleConfig
```python
@dataclass(frozen=True)
class StyleConfig:
    prefer_simp_over_aesop: bool
    emit_compact: bool
    simp_only_list: bool
```

### WorkspaceConfig
```python
@dataclass(frozen=True)
class WorkspaceConfig:
    mode: Literal["git_worktree"]
    keep_artifacts: bool
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: File Validation Correctness
*For any* file path provided as input, the system should correctly identify whether the file exists and is readable, returning appropriate success or error results.
**Validates: Requirements 1.1**

### Property 2: Error Descriptiveness
*For any* error condition (missing theorem, invalid file, Lean failure), the system should return a structured error with sufficient diagnostic information to understand the failure cause.
**Validates: Requirements 1.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.8**

### Property 3: Budget Enforcement
*For any* phase with a configured time budget, when that budget is exceeded, the system should terminate that phase gracefully and return appropriate timeout status with the best available partial results.
**Validates: Requirements 1.5, 2.5, 4.8, 5.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7**

### Property 4: Viability Check Isolation
*For any* viability check execution, the file system state should remain unchanged (no files modified, created, or deleted).
**Validates: Requirements 1.6**

### Property 5: Automation Configuration Propagation
*For any* automation configuration provided, the system should correctly pass all configuration parameters to the underlying automation tool without loss or modification.
**Validates: Requirements 2.2**

### Property 6: Fallback Automation Attempt
*For any* execution where a secondary automation tool is configured and the primary tool fails, the system should attempt the secondary tool.
**Validates: Requirements 2.3**

### Property 7: Early Termination on Baseline Success
*For any* execution where baseline automation succeeds, the system should return success immediately without performing hint search.
**Validates: Requirements 2.4**

### Property 8: Baseline Attempt Recording
*For any* execution, all baseline automation attempts should be recorded in the final result report with their outcomes.
**Validates: Requirements 2.6**

### Property 9: Candidate Source Extraction Completeness
*For any* set of enabled candidate sources, the system should extract candidates from all enabled sources and include them in the candidate pool.
**Validates: Requirements 3.1**

### Property 10: Conditional Hint Type Inclusion
*For any* hint type flag (allow_simp_hints, allow_unfold_hints), when the flag is true, candidates of that type should be included; when false, they should be excluded.
**Validates: Requirements 3.7, 3.8**

### Property 11: Candidate Limit Enforcement
*For any* candidate source, the number of candidates extracted from that source should not exceed max_candidates_per_source.
**Validates: Requirements 3.9**

### Property 12: Candidate Ranking Priority
*For any* set of candidates, the ranking should prioritize .def lemmas over non-def lemmas, [simp] lemmas over non-simp lemmas, and original proof references over other candidates.
**Validates: Requirements 3.10**

### Property 13: Greedy Search Incremental Growth
*For any* greedy search execution, the search should start with an empty hint set and grow by exactly one hint per step, always adding the best-scoring candidate.
**Validates: Requirements 4.1**

### Property 14: Beam Search Width Invariant
*For any* beam search execution, the number of active hint sets should not exceed beam_width at any point during the search.
**Validates: Requirements 4.2**

### Property 15: Success Recording
*For any* hint set that successfully closes the goal, that hint set should be recorded in the search results as a successful configuration.
**Validates: Requirements 4.4**

### Property 16: Search Termination Control
*For any* search execution, when stop_on_first_close is true and a closing hint set is found, search should terminate immediately; when false, search should continue until max_steps or budget exhaustion.
**Validates: Requirements 4.5, 4.6**

### Property 17: Hint Set Size Limit
*For any* hint set explored during search, the number of hints in that set should not exceed max_hints.
**Validates: Requirements 4.7**

### Property 18: Hint Set Scoring Consistency
*For any* two hint sets with different automation outcomes, the scoring function should assign higher scores to better outcomes (success > partial > failure).
**Validates: Requirements 4.9**

### Property 19: Minimization Preservation
*For any* closing hint set undergoing minimization, the minimization process should iteratively remove hints while ensuring the resulting set still closes the goal.
**Validates: Requirements 5.1, 5.2**

### Property 20: Minimization Restoration
*For any* hint whose removal causes the goal to fail during minimization, that hint should be restored to the hint set.
**Validates: Requirements 5.3**

### Property 21: Minimized Set Closure Guarantee
*For any* minimized hint set returned as a final result, that hint set should successfully close the goal when applied.
**Validates: Requirements 5.5**

### Property 22: Minimized Set Stability
*For any* minimized hint set, multiple verification attempts should all succeed, demonstrating the set is stable and not dependent on non-deterministic behavior.
**Validates: Requirements 5.6**

### Property 23: Proof Patch Syntax Validity
*For any* generated proof patch, the Lean code should parse as syntactically valid Lean syntax.
**Validates: Requirements 6.1**

### Property 24: Automation-Specific Proof Formatting
*For any* proof patch, when the closing automation is simp and prefer_simp_over_aesop is true, the proof should use simp syntax; when the closing automation is aesop, the proof should use aesop syntax with local hints.
**Validates: Requirements 6.2, 6.3**

### Property 25: Proof Formatting Style Control
*For any* proof patch, when emit_compact is true, hints should be formatted on a single line; when false, hints should be formatted with one per line.
**Validates: Requirements 6.4, 6.5**

### Property 26: Simp Variant Selection
*For any* simp-based proof patch, when simp_only_list is true, the proof should use "simp only [...]" syntax; when false, it should use "simp_all [...]" syntax.
**Validates: Requirements 6.6**

### Property 27: Definitional Proof Preservation
*For any* theorem with a definitional proof (rfl, Iff.rfl, trivial), the system should not replace that proof with automation.
**Validates: Requirements 6.7, 15.1, 15.2, 15.3**

### Property 28: Proof Patch Completeness
*For any* proof patch, it should include the automation configuration used and all necessary local hints.
**Validates: Requirements 6.8**

### Property 29: Mode-Conditional Global Suggestions
*For any* execution, when mode is local_only, no global annotation suggestions should be generated; when mode is suggest_global, global suggestions should be analyzed and included.
**Validates: Requirements 7.1, 7.2**

### Property 30: Effective Hint Suggestion Generation
*For any* hint that appears in the minimized set and is determined to be frequently effective, a global annotation suggestion should be generated.
**Validates: Requirements 7.3**

### Property 31: Suggestion Rationale Completeness
*For any* global annotation suggestion, a rationale explaining why the suggestion is made should be included.
**Validates: Requirements 7.4**

### Property 32: Global Edit Safety
*For any* execution, when allow_global_edits is false, no file modifications should occur and only advisory suggestions should be provided; when true, global edits may be applied.
**Validates: Requirements 7.5, 7.6**

### Property 33: Worktree Creation and Isolation
*For any* execution with workspace mode git_worktree, an isolated Git worktree should be created for experiments.
**Validates: Requirements 8.1**

### Property 34: Worktree Cleanup Control
*For any* execution, when keep_artifacts is false, the worktree should be cleaned up after completion; when true, the worktree should be preserved and its location logged.
**Validates: Requirements 8.2, 8.3**

### Property 35: Cleanup Guarantee Under Failure
*For any* execution that crashes or times out, worktree cleanup should still occur, ensuring no resource leaks.
**Validates: Requirements 8.4**

### Property 36: Process Cleanup Guarantee
*For any* execution (successful or failed), no orphan processes should remain after the system completes.
**Validates: Requirements 8.5**

### Property 37: Original Directory Isolation
*For any* search execution, files in the original working directory should remain unmodified.
**Validates: Requirements 8.6**

### Property 38: Timing Completeness
*For any* execution, the result should include time measurements for all phases (viability, baseline, search, minimization, verification).
**Validates: Requirements 9.8**

### Property 39: Result Structure Completeness
*For any* execution, the result should include all required fields: status, viability details, baseline attempts, final hint set (if found), proof patch (if successful), timing breakdown, and artifact paths.
**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8**

### Property 40: Result Determinism
*For any* two executions with identical inputs and configurations, the output JSON should be identical (same field ordering, same hint ordering, same formatting).
**Validates: Requirements 10.9, 10.10, 13.1, 13.2, 13.3, 13.4, 13.5**

### Property 41: Skeleton Mode Conditional Behavior
*For any* execution, when skeleton.enabled is false, standard hint search should be performed; when true, skeleton-based search with tactic moves should be explored.
**Validates: Requirements 14.1, 14.2**

### Property 42: Skeleton Depth Limit
*For any* skeleton-enabled search, the skeleton depth should not exceed skeleton.max_depth.
**Validates: Requirements 14.3**

### Property 43: Skeleton Move Restriction
*For any* skeleton-enabled search, only tactic moves from the skeleton.moves list should be used in skeleton exploration.
**Validates: Requirements 14.4**

### Property 44: Style Preference Application
*For any* proof generation, when prefer_simp_over_aesop is true and simp closes the goal, a simp proof should be emitted; when false and aesop closes, an aesop proof should be emitted.
**Validates: Requirements 15.4, 15.5**

## Error Handling

### Error Types

The system uses the Result/Either pattern to represent all failure modes explicitly:

```python
@dataclass(frozen=True)
class FileNotFoundError:
    path: str
    
@dataclass(frozen=True)
class TheoremNotFoundError:
    theorem_id: str
    searched_locations: list[str]
    
@dataclass(frozen=True)
class LeanEnvironmentError:
    diagnostic: str
    
@dataclass(frozen=True)
class TimeoutError:
    phase: str
    budget_s: float
    elapsed_s: float
    
@dataclass(frozen=True)
class WorktreeError:
    operation: str
    reason: str
    
@dataclass(frozen=True)
class VerificationError:
    hint_set: HintSet
    error_output: str

Error = Union[
    FileNotFoundError,
    TheoremNotFoundError,
    LeanEnvironmentError,
    TimeoutError,
    WorktreeError,
    VerificationError
]
```

### Error Handling Strategy

1. **No Exceptions for Expected Failures**: All expected failure modes return Result[T, Error]
2. **Exceptions for Programmer Errors**: Only use exceptions for bugs (assertion failures, type errors)
3. **Error Propagation**: Use Result chaining to propagate errors up the call stack
4. **Error Context**: Each error type includes sufficient context for diagnosis
5. **Structured Errors**: All errors are enumerable and testable

### Timeout Handling

Each phase has a timeout decorator that:
1. Starts a timer when the phase begins
2. Monitors elapsed time during execution
3. Raises a timeout signal when budget is exceeded
4. Catches the signal and returns TimeoutError with partial results
5. Ensures cleanup occurs even on timeout

### Cleanup Guarantees

The system uses context managers and try-finally blocks to ensure:
1. Worktrees are always cleaned up (unless keep_artifacts=true)
2. Lean processes are always terminated
3. File handles are always closed
4. Temporary files are always removed

## Testing Strategy

### Dual Testing Approach

The system requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests** focus on:
- Specific examples of correct behavior
- Edge cases (empty hint sets, single-hint sets, maximum-size sets)
- Error conditions (missing files, invalid theorems, Lean errors)
- Integration points between components
- Specific candidate sources (goal_symbols, local_context, etc.)

**Property-Based Tests** focus on:
- Universal properties that hold for all inputs
- Comprehensive input coverage through randomization
- Invariants that must be preserved
- Behavioral consistency across input variations

### Property-Based Testing Configuration

**Library**: Use Hypothesis (Python), fast-check (TypeScript), or QuickCheck (Haskell) depending on implementation language

**Test Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with: `Feature: search-annotations-tool, Property {N}: {property_text}`
- Deterministic seed for reproducibility
- Shrinking enabled to find minimal failing examples

**Example Property Test Structure**:
```python
from hypothesis import given, strategies as st

@given(
    file_path=st.text(),
    theorem_id=st.text()
)
def test_property_1_file_validation_correctness(file_path, theorem_id):
    """Feature: search-annotations-tool, Property 1: File Validation Correctness
    
    For any file path provided as input, the system should correctly 
    identify whether the file exists and is readable.
    """
    result = search_annotations_handler.validate_file(file_path)
    
    if os.path.exists(file_path) and os.access(file_path, os.R_OK):
        assert result.is_ok()
    else:
        assert result.is_err()
        assert isinstance(result.error, FileNotFoundError)
```

### Test Coverage Goals

- **Core Domain**: 100% coverage with property tests for all business logic
- **Adapters**: Unit tests for error handling and edge cases
- **Integration**: End-to-end tests for complete workflows
- **Error Paths**: Explicit tests for all error types

### Testing Minimization Algorithm

The delta-debugging minimization is particularly critical and requires:
1. Property test: minimized set always closes the goal
2. Property test: removing any hint from minimized set causes failure
3. Property test: minimization is idempotent (minimizing twice = minimizing once)
4. Unit tests: specific examples with known minimal sets

### Testing Search Strategies

Both beam and greedy strategies require:
1. Property test: search respects max_hints limit
2. Property test: search respects max_steps limit
3. Property test: search terminates within budget
4. Property test: beam maintains width invariant
5. Property test: greedy grows incrementally
6. Unit tests: specific search scenarios with known outcomes

### Testing Determinism

Determinism is critical and requires:
1. Property test: identical inputs produce identical outputs
2. Property test: JSON field ordering is stable
3. Property test: hint ordering is stable
4. Unit tests: specific examples verified for exact output match
