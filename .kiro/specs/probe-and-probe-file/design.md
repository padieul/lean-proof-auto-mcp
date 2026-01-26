# Design Document: Probe and Probe_File Tools

## Overview

The probe and probe_file tools extend the verify execution primitive into empirical measurement of automation behavior. These tools answer a single question: What actually happens if we try automation here, under controlled conditions?

The probe tool runs exactly one automation attempt (aesop, aesop?, or grind) on a single theorem and classifies the outcome deterministically. The probe_file tool runs probe across many theorems in a file to produce a heatmap of automation behavior for triage and prioritization.

These tools are measurement primitives that:
- Do not change code
- Do not search
- Do not annotate
- Provide deterministic, structured classification of automation outcomes
- Reuse verify's execution infrastructure for consistency

The tools fit into the pipeline as: scan_file → scan_theorem → rank_targets → probe/probe_file (empirical measurement) → search_annotations (only for promising cases).

## Architecture

The design follows hexagonal architecture with clear separation between core domain logic, ports (abstract interfaces), and adapters (concrete implementations).

### Architectural Layers

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                        │
│  (probe.py, probe_file.py - entry points, validation)   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Core Domain Layer                      │
│  (probe_domain.py - commands, handlers, result types)   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      Port Layer                          │
│  (LeanRunner, WorkspaceProvider - abstract interfaces)  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Adapter Layer                         │
│  (LeanInteractRunner, WorkspaceProvider - concrete)     │
└─────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Hexagonal Architecture**: Core logic depends only on abstract ports, not concrete implementations
2. **Dependency Injection**: All dependencies are injected through constructors
3. **Command Pattern**: Each operation is encapsulated as an immutable command object
4. **Result/Either Pattern**: Explicit success/failure representation in return values
5. **Strategy Pattern**: Classification logic is encapsulated as a pluggable strategy


### Infrastructure Reuse

The probe tools reuse verify's infrastructure:
- **LeanInteractRunner**: Same Lean execution mechanism
- **WorkspaceProvider**: Same workspace isolation (git worktree or temp copy)
- **Timeout enforcement**: Same hard wall-clock budget mechanism
- **Diagnostic parsing**: Same normalization and sorting logic

This reuse ensures:
- Consistent behavior across tools
- Reduced maintenance burden
- Proven reliability from verify's implementation

## Components and Interfaces

### Core Domain Components

#### ProbeCommand

Immutable command representing a probe request:

```python
@dataclass(frozen=True)
class ProbeCommand:
    """Command for single-theorem automation probe.
    
    Attributes:
        file_path: Path to Lean file
        theorem_id: Theorem identifier to probe
        mode: Automation mode (aesop, aesop?, grind)
        budget_s: Time budget in seconds
        trace_config: Optional trace configuration for debugging
    """
    file_path: str
    theorem_id: str
    mode: str  # "aesop" | "aesop?" | "grind"
    budget_s: float = 10.0
    trace_config: dict[str, bool] | None = None
    
    def __post_init__(self) -> None:
        """Validate command parameters."""
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if not self.theorem_id:
            raise ValueError("theorem_id must be non-empty")
        if self.mode not in ("aesop", "aesop?", "grind"):
            raise ValueError("mode must be 'aesop', 'aesop?', or 'grind'")
        if self.budget_s <= 0:
            raise ValueError("budget_s must be positive")
```


#### ProbeResult

Immutable result from a probe attempt:

```python
@dataclass(frozen=True)
class ProbeResult:
    """Result from single-theorem automation probe.
    
    Attributes:
        api_version: API version string
        status: Overall status (success, fail, timeout, error)
        run_id: Unique identifier for this probe run
        probe_result: Detailed probe outcome
        diagnostics: List of diagnostic messages
        timing: Timing information
        metadata: Metadata about execution environment
    """
    api_version: str
    status: str
    run_id: str
    probe_result: ProbeOutcome
    diagnostics: list[dict]
    timing: dict[str, float]
    metadata: dict[str, Any]
```

#### ProbeOutcome

Structured outcome of automation attempt:

```python
@dataclass(frozen=True)
class ProbeOutcome:
    """Structured outcome of automation attempt.
    
    Attributes:
        mode: Automation mode used
        outcome: Raw outcome (closed, not_closed, timeout, error)
        classification: Deterministic classification (trivial, promising, failed, timed_out)
        suggested_script: Optional suggested script (for aesop? mode)
    """
    mode: str
    outcome: str  # "closed" | "not_closed" | "timeout" | "error"
    classification: str  # "trivial" | "promising" | "failed" | "timed_out"
    suggested_script: str | None = None
```


#### ProbeFileCommand

Immutable command for batch probing:

```python
@dataclass(frozen=True)
class ProbeFileCommand:
    """Command for batch automation probing.
    
    Attributes:
        file_path: Path to Lean file
        mode: Automation mode (aesop, aesop?, grind)
        budget_s_per: Time budget per theorem in seconds
        limit: Maximum number of theorems to probe
        ordering: Ordering mode (file_order, rank_targets)
    """
    file_path: str
    mode: str
    budget_s_per: float = 5.0
    limit: int = 50
    ordering: str = "file_order"
    
    def __post_init__(self) -> None:
        """Validate command parameters."""
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if self.mode not in ("aesop", "aesop?", "grind"):
            raise ValueError("mode must be 'aesop', 'aesop?', or 'grind'")
        if self.budget_s_per <= 0:
            raise ValueError("budget_s_per must be positive")
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.ordering not in ("file_order", "rank_targets"):
            raise ValueError("ordering must be 'file_order' or 'rank_targets'")
```

#### ProbeFileResult

Immutable result from batch probing:

```python
@dataclass(frozen=True)
class ProbeFileResult:
    """Result from batch automation probing.
    
    Attributes:
        api_version: API version string
        status: Overall status (success, partial, error)
        file: Path to probed file
        summary: Summary statistics
        results: Per-theorem results
        metadata: Metadata about execution
    """
    api_version: str
    status: str
    file: str
    summary: dict[str, int]
    results: list[dict]
    metadata: dict[str, Any]
```


### Port Interfaces

The probe tools reuse existing ports from verify:

#### LeanRunner (Reused)

```python
class LeanRunner(Protocol):
    """Abstract interface for running Lean verification."""
    
    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """Run Lean verification on file or theorem."""
        ...
```

#### WorkspaceProvider (Reused)

```python
class WorkspaceProvider(Protocol):
    """Abstract interface for workspace isolation."""
    
    def create_workspace(self, file_path: str) -> Workspace:
        """Create isolated workspace for verification."""
        ...
    
    def cleanup_workspace(self, workspace: Workspace) -> None:
        """Clean up workspace resources."""
        ...
```

### New Port: AutomationClassifier

```python
class AutomationClassifier(Protocol):
    """Abstract interface for classifying automation outcomes.
    
    This port encapsulates the logic for deterministically classifying
    automation attempts into categories (trivial, promising, failed, timed_out).
    """
    
    def classify(
        self,
        outcome: str,
        diagnostics: list[dict],
        timing: dict[str, float],
        budget_s: float,
    ) -> str:
        """Classify automation outcome.
        
        Args:
            outcome: Raw outcome (closed, not_closed, timeout, error)
            diagnostics: Diagnostic messages from Lean
            timing: Timing information
            budget_s: Time budget that was allocated
        
        Returns:
            Classification string (trivial, promising, failed, timed_out)
        """
        ...
```


### Command Handlers

#### ProbeCommandHandler

Orchestrates single-theorem probing:

```python
class ProbeCommandHandler:
    """Orchestrates single-theorem automation probing.
    
    This handler implements the core probe workflow:
    1. Generate unique run_id
    2. Create isolated workspace
    3. Construct automation harness
    4. Run Lean with automation tactic
    5. Parse and classify outcome
    6. Build structured result
    7. Ensure workspace cleanup
    """
    
    def __init__(
        self,
        lean_runner: LeanRunner,
        workspace_provider: WorkspaceProvider,
        classifier: AutomationClassifier,
    ):
        """Initialize handler with dependency injection."""
        self.lean_runner = lean_runner
        self.workspace_provider = workspace_provider
        self.classifier = classifier
    
    def handle(self, cmd: ProbeCommand) -> ProbeResult:
        """Execute probe workflow."""
        # Implementation details in next section...
```

#### ProbeFileCommandHandler

Orchestrates batch probing:

```python
class ProbeFileCommandHandler:
    """Orchestrates batch automation probing.
    
    This handler implements the batch probe workflow:
    1. Enumerate theorems using scan_file
    2. Apply ordering (file_order or rank_targets)
    3. Apply limit
    4. For each theorem, call ProbeCommandHandler
    5. Aggregate results into summary
    6. Return both per-theorem and file-level statistics
    """
    
    def __init__(
        self,
        probe_handler: ProbeCommandHandler,
        scan_file_fn: Callable,
        rank_targets_fn: Callable | None = None,
    ):
        """Initialize handler with dependency injection."""
        self.probe_handler = probe_handler
        self.scan_file_fn = scan_file_fn
        self.rank_targets_fn = rank_targets_fn
    
    def handle(self, cmd: ProbeFileCommand) -> ProbeFileResult:
        """Execute batch probe workflow."""
        # Implementation details in next section...
```


## Data Models

### Automation Harness Construction

The probe tool constructs a minimal Lean harness to test automation:

```lean
-- For theorem-level probing
import <original_file>

-- Focus on target theorem
set_option trace.aesop true  -- if trace enabled

theorem <theorem_name> : <theorem_type> := by
  <automation_tactic>  -- aesop, aesop?, or grind
```

The harness is constructed by:
1. Parsing the original file to find the theorem
2. Extracting the theorem signature (name and type)
3. Replacing the proof with the automation tactic
4. Writing to a temporary file in the workspace

### Classification Logic

The AutomationClassifier uses deterministic rules to classify outcomes:

```python
class HeuristicClassifier:
    """Heuristic-based automation classifier.
    
    Classification rules:
    - trivial: Automation closes goal in < 20% of budget
    - promising: Automation fails but produces shallow subgoals (< 3 levels)
    - failed: Automation fails decisively (deep subgoals or no progress)
    - timed_out: Budget exhausted
    - error: Toolchain or execution error
    """
    
    def classify(
        self,
        outcome: str,
        diagnostics: list[dict],
        timing: dict[str, float],
        budget_s: float,
    ) -> str:
        """Classify automation outcome using heuristics."""
        # Timeout classification
        if outcome == "timeout":
            return "timed_out"
        
        # Error classification
        if outcome == "error":
            return "error"
        
        # Success classification
        if outcome == "closed":
            elapsed = timing.get("lean_execution_s", 0.0)
            # Trivial if solved quickly (< 20% of budget)
            if elapsed < budget_s * 0.2:
                return "trivial"
            else:
                return "trivial"  # Still trivial if it closed
        
        # Failure classification (outcome == "not_closed")
        # Analyze diagnostics to determine if promising
        subgoal_depth = self._estimate_subgoal_depth(diagnostics)
        if subgoal_depth <= 3:
            return "promising"
        else:
            return "failed"
    
    def _estimate_subgoal_depth(self, diagnostics: list[dict]) -> int:
        """Estimate subgoal depth from diagnostics.
        
        This is a heuristic based on:
        - Number of unsolved goals messages
        - Nesting level of goal contexts
        - Presence of "shallow" vs "deep" goal indicators
        """
        # Implementation uses diagnostic message patterns...
```


### Theorem Enumeration

For probe_file, theorems are enumerated using scan_file:

```python
def enumerate_theorems(
    file_path: str,
    ordering: str,
    limit: int,
    scan_file_fn: Callable,
    rank_targets_fn: Callable | None,
) -> list[str]:
    """Enumerate theorems for batch probing.
    
    Args:
        file_path: Path to Lean file
        ordering: Ordering mode (file_order, rank_targets)
        limit: Maximum number of theorems
        scan_file_fn: Function to call scan_file
        rank_targets_fn: Optional function to call rank_targets
    
    Returns:
        List of theorem_ids in specified order
    """
    # Call scan_file to get all theorems
    scan_result = scan_file_fn({"file": file_path})
    if scan_result["status"] != "success":
        raise RuntimeError(f"scan_file failed: {scan_result}")
    
    theorems = scan_result["theorems"]
    
    # Apply ordering
    if ordering == "file_order":
        # Use file order (already sorted by scan_file)
        theorem_ids = [t["theorem_id"] for t in theorems]
    elif ordering == "rank_targets":
        # Use rank_targets to prioritize
        if rank_targets_fn is None:
            raise ValueError("rank_targets_fn required for rank_targets ordering")
        
        rank_result = rank_targets_fn({
            "file": file_path,
            "objective": "maximize_success",
            "limit": len(theorems),
        })
        if rank_result["status"] != "success":
            raise RuntimeError(f"rank_targets failed: {rank_result}")
        
        theorem_ids = [t["theorem_id"] for t in rank_result["ranking"]]
    else:
        raise ValueError(f"Invalid ordering: {ordering}")
    
    # Apply limit
    return theorem_ids[:limit]
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Workspace Isolation

*For any* theorem and automation mode, when probe is invoked, the system should create an isolated workspace using the same workspace provider as verify, and the workspace should be cleaned up after execution regardless of outcome.

**Validates: Requirements 1.1, 7.4**

### Property 2: Harness Structure Validity

*For any* theorem, when probe constructs an automation harness, the harness should contain exactly one import statement, exactly one theorem declaration with the target theorem's signature, and exactly one automation tactic invocation.

**Validates: Requirements 1.2**

### Property 3: Infrastructure Reuse

*For any* probe invocation, the system should use the same LeanInteractRunner instance type and diagnostic parsing logic as verify, ensuring consistent behavior across tools.

**Validates: Requirements 1.3, 6.4**

### Property 4: Hard Timeout Enforcement

*For any* budget and theorem, when probe runs automation, if the execution exceeds the budget, the Lean process should be terminated immediately and the elapsed time should not significantly exceed the budget (within timeout buffer).

**Validates: Requirements 1.4, 8.2**

### Property 5: Result Completeness

*For any* probe invocation, the result should contain all required fields: api_version, status, run_id, probe_result (with mode, outcome, classification), diagnostics, timing (with elapsed_ms and budget_s), and metadata (with workspace_mode, lean_version, lake_version, repo_commit).

**Validates: Requirements 1.5, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8**

### Property 6: No Source Modification

*For any* probe invocation, the source file's content hash before and after probe execution should be identical, proving that probe never modifies source code.

**Validates: Requirements 1.6**

### Property 7: Mode Validation

*For any* input mode, probe should accept the mode if and only if it is one of "aesop", "aesop?", or "grind", rejecting all other values with a validation error.

**Validates: Requirements 1.8, 3.1**

### Property 8: Trivial Classification

*For any* automation run where the goal closes in less than 20% of the budget, the classification should be "trivial".

**Validates: Requirements 2.1**

### Property 9: Promising Classification

*For any* automation run that fails but produces diagnostics indicating shallow subgoals (depth ≤ 3), the classification should be "promising".

**Validates: Requirements 2.2**

### Property 10: Failed Classification

*For any* automation run that fails and produces diagnostics indicating deep subgoals (depth > 3) or no progress, the classification should be "failed".

**Validates: Requirements 2.3**


### Property 11: Timeout Classification

*For any* automation run where the budget is exhausted, the classification should be "timed_out".

**Validates: Requirements 2.4**

### Property 12: Error Classification

*For any* automation run where a toolchain or execution error occurs, the classification should be "error".

**Validates: Requirements 2.5**

### Property 13: Deterministic Classification

*For any* identical probe inputs (same file, theorem, mode, budget), running probe twice should produce identical classifications and outcomes.

**Validates: Requirements 2.6**

### Property 14: Aesop? Suggested Script

*For any* probe invocation with mode="aesop?" where the automation succeeds, the probe_result should contain a non-empty suggested_script field.

**Validates: Requirements 3.5**

### Property 15: Scan_File Integration

*For any* probe_file invocation, the system should call scan_file to enumerate theorems and use its output in stable order (sorted by theorem_id).

**Validates: Requirements 4.1**

### Property 16: Batch Probe Invocation

*For any* probe_file invocation with N theorems enumerated, the system should call probe exactly N times (or limit times if limit < N), once for each theorem with the specified mode and budget_s_per.

**Validates: Requirements 4.2**

### Property 17: Per-Theorem Budget Isolation

*For any* probe_file invocation with multiple theorems, each theorem should receive its own independent budget allocation, and one theorem timing out should not affect the budget of subsequent theorems.

**Validates: Requirements 4.3**

### Property 18: Summary Aggregation Correctness

*For any* probe_file invocation, the summary counts (total, closed, promising, failed, timed_out) should exactly match the sum of individual theorem results with those classifications.

**Validates: Requirements 4.4**

### Property 19: Probe_File Result Completeness

*For any* probe_file invocation, the result should contain all required fields: api_version, status, file, summary (with total, closed, promising, failed, timed_out), results array (with theorem_id, outcome, classification, elapsed_ms for each), and metadata.

**Validates: Requirements 4.5, 5.2, 5.3, 5.4**

### Property 20: Partial Success Handling

*For any* probe_file invocation where some theorems fail with errors, the system should continue processing remaining theorems and return status="partial" with all successfully probed results.

**Validates: Requirements 4.6**

### Property 21: Deterministic Result Ordering

*For any* probe_file invocation, running it twice with the same parameters should produce results in the same order.

**Validates: Requirements 4.7**

### Property 22: Ordering Mode Support

*For any* probe_file invocation, when ordering="file_order", results should be ordered by file position, and when ordering="rank_targets", results should be ordered by rank_targets score (descending).

**Validates: Requirements 5.5**


### Property 23: Limit Enforcement

*For any* probe_file invocation with limit=L and N theorems available, the system should process at most min(L, N) theorems.

**Validates: Requirements 5.6**

### Property 24: No External Filesystem Mutation

*For any* probe invocation, no files outside the isolated workspace should be created, modified, or deleted during execution.

**Validates: Requirements 7.1**

### Property 25: Stateless Execution

*For any* two consecutive probe invocations with different inputs, the second invocation's result should not depend on any state from the first invocation.

**Validates: Requirements 7.2**

### Property 26: Diagnostic Ordering

*For any* probe invocation, diagnostics should be sorted deterministically by (file, line, column, severity_order, message) where severity_order maps error→0, warning→1, info→2.

**Validates: Requirements 9.1**

### Property 27: Severity Normalization

*For any* probe invocation, all diagnostic severity values should be one of "error", "warning", or "info", with raw severity strings normalized to these standard values.

**Validates: Requirements 9.3**

### Property 28: Invalid Input Handling

*For any* invalid probe input (empty file_path, empty theorem_id, invalid mode, non-positive budget), the system should return status="error" with validation details and never raise an unhandled exception.

**Validates: Requirements 10.3, 10.5**


## Error Handling

The probe tools follow the Result/Either pattern for explicit error handling:

### Error Categories

1. **Validation Errors**: Invalid input parameters (empty strings, invalid modes, non-positive budgets)
   - Return status="error" with validation details
   - Never proceed to execution

2. **Theorem Not Found**: Specified theorem_id doesn't exist in file
   - Return status="error" with descriptive message
   - Include file and theorem_id in error context

3. **Toolchain Errors**: Lean or Lake execution failures
   - Return status="error" with diagnostic information
   - Include stderr output in diagnostics

4. **Timeout Errors**: Budget exhausted during execution
   - Return status="timeout" with classification="timed_out"
   - Include partial diagnostics if available

5. **Workspace Errors**: Workspace creation or cleanup failures
   - Return status="error" with workspace details
   - Ensure cleanup attempt even on error

### Error Handling Strategy

```python
def handle(self, cmd: ProbeCommand) -> ProbeResult:
    """Execute probe workflow with comprehensive error handling."""
    # Validation errors (early return)
    try:
        self._validate_command(cmd)
    except ValueError as e:
        return self._build_error_result(cmd, "validation_error", str(e))
    
    # Workspace creation errors
    workspace = None
    try:
        workspace = self.workspace_provider.create_workspace(cmd.file_path)
    except Exception as e:
        return self._build_error_result(cmd, "workspace_error", str(e))
    
    try:
        # Execution errors (caught and converted to error results)
        try:
            lean_result = self.lean_runner.verify_file(
                workspace.path, cmd.file_path, cmd.theorem_id, cmd.budget_s
            )
        except TimeoutError:
            # Timeout is expected, convert to timeout result
            return self._build_timeout_result(cmd)
        except ValueError as e:
            # Theorem not found or invalid
            return self._build_error_result(cmd, "theorem_not_found", str(e))
        except Exception as e:
            # Toolchain or execution error
            return self._build_error_result(cmd, "execution_error", str(e))
        
        # Classification and result building (should not fail)
        classification = self.classifier.classify(
            lean_result.status, lean_result.diagnostics, lean_result.timing, cmd.budget_s
        )
        return self._build_success_result(cmd, lean_result, classification)
    
    finally:
        # Cleanup always runs, errors are logged but not propagated
        if workspace:
            try:
                self.workspace_provider.cleanup_workspace(workspace)
            except Exception as e:
                logger.warning(f"Workspace cleanup failed: {e}")
```


### Probe_File Error Handling

Probe_file implements partial success semantics:

```python
def handle(self, cmd: ProbeFileCommand) -> ProbeFileResult:
    """Execute batch probe with partial success support."""
    # Enumerate theorems (fail fast if scan_file fails)
    try:
        theorem_ids = self._enumerate_theorems(cmd)
    except Exception as e:
        return self._build_error_result(cmd, str(e))
    
    # Probe each theorem (collect errors but continue)
    results = []
    errors = []
    
    for theorem_id in theorem_ids:
        try:
            probe_cmd = ProbeCommand(
                file_path=cmd.file_path,
                theorem_id=theorem_id,
                mode=cmd.mode,
                budget_s=cmd.budget_s_per,
            )
            probe_result = self.probe_handler.handle(probe_cmd)
            results.append(self._extract_summary(probe_result))
        except Exception as e:
            errors.append({"theorem_id": theorem_id, "error": str(e)})
            # Continue processing remaining theorems
    
    # Determine status
    if len(results) == 0:
        status = "error"
    elif len(errors) > 0:
        status = "partial"
    else:
        status = "success"
    
    return self._build_result(cmd, results, errors, status)
```


## Testing Strategy

The probe tools require both unit tests and property-based tests for comprehensive coverage.

### Unit Testing

Unit tests focus on specific examples, edge cases, and integration points:

1. **Command Validation**
   - Test valid inputs are accepted
   - Test invalid inputs are rejected with appropriate errors
   - Test boundary values (zero budget, empty strings)

2. **Classification Logic**
   - Test trivial classification with quick success
   - Test promising classification with shallow subgoals
   - Test failed classification with deep subgoals
   - Test timeout classification
   - Test error classification

3. **Integration Points**
   - Test workspace provider integration
   - Test lean runner integration
   - Test scan_file integration (for probe_file)
   - Test rank_targets integration (for probe_file)

4. **Error Handling**
   - Test theorem not found error
   - Test toolchain error handling
   - Test workspace error handling
   - Test partial success in probe_file

### Property-Based Testing

Property tests verify universal properties across randomized inputs:

**Configuration**: Minimum 100 iterations per property test

**Test Library**: Use Hypothesis for Python property-based testing

**Property Test Examples**:

```python
from hypothesis import given, strategies as st
import hypothesis

# Property 6: No Source Modification
@given(
    file_path=st.text(min_size=1),
    theorem_id=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@hypothesis.settings(max_examples=100)
def test_no_source_modification(file_path, theorem_id, mode, budget_s):
    """Feature: probe-and-probe-file-tools, Property 6: No Source Modification
    
    For any probe invocation, the source file's content hash before and after 
    probe execution should be identical.
    """
    # Setup: Create test file
    test_file = create_test_file(file_path)
    hash_before = compute_hash(test_file)
    
    # Execute: Run probe
    cmd = ProbeCommand(
        file_path=file_path,
        theorem_id=theorem_id,
        mode=mode,
        budget_s=budget_s,
    )
    handler = create_probe_handler()
    result = handler.handle(cmd)
    
    # Verify: Hash unchanged
    hash_after = compute_hash(test_file)
    assert hash_before == hash_after, "Source file was modified"
```


# Property 13: Deterministic Classification
@given(
    file_path=st.text(min_size=1),
    theorem_id=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
@hypothesis.settings(max_examples=100)
def test_deterministic_classification(file_path, theorem_id, mode, budget_s):
    """Feature: probe-and-probe-file-tools, Property 13: Deterministic Classification
    
    For any identical probe inputs, running probe twice should produce 
    identical classifications and outcomes.
    """
    # Setup: Create command
    cmd = ProbeCommand(
        file_path=file_path,
        theorem_id=theorem_id,
        mode=mode,
        budget_s=budget_s,
    )
    handler = create_probe_handler()
    
    # Execute: Run probe twice
    result1 = handler.handle(cmd)
    result2 = handler.handle(cmd)
    
    # Verify: Identical classifications
    assert result1.probe_result.classification == result2.probe_result.classification
    assert result1.probe_result.outcome == result2.probe_result.outcome

# Property 18: Summary Aggregation Correctness
@given(
    file_path=st.text(min_size=1),
    mode=st.sampled_from(["aesop", "aesop?", "grind"]),
    budget_s_per=st.floats(min_value=0.1, max_value=10.0),
    limit=st.integers(min_value=1, max_value=50),
)
@hypothesis.settings(max_examples=100)
def test_summary_aggregation_correctness(file_path, mode, budget_s_per, limit):
    """Feature: probe-and-probe-file-tools, Property 18: Summary Aggregation Correctness
    
    For any probe_file invocation, the summary counts should exactly match 
    the sum of individual theorem results with those classifications.
    """
    # Setup: Create command
    cmd = ProbeFileCommand(
        file_path=file_path,
        mode=mode,
        budget_s_per=budget_s_per,
        limit=limit,
    )
    handler = create_probe_file_handler()
    
    # Execute: Run probe_file
    result = handler.handle(cmd)
    
    # Verify: Summary matches individual results
    closed_count = sum(1 for r in result.results if r["classification"] == "trivial")
    promising_count = sum(1 for r in result.results if r["classification"] == "promising")
    failed_count = sum(1 for r in result.results if r["classification"] == "failed")
    timed_out_count = sum(1 for r in result.results if r["classification"] == "timed_out")
    
    assert result.summary["closed"] == closed_count
    assert result.summary["promising"] == promising_count
    assert result.summary["failed"] == failed_count
    assert result.summary["timed_out"] == timed_out_count
    assert result.summary["total"] == len(result.results)
```


### Test Organization

```
tests/
├── unit/
│   ├── test_probe_command.py          # Command validation
│   ├── test_probe_handler.py          # Handler logic
│   ├── test_classifier.py             # Classification logic
│   ├── test_probe_file_handler.py     # Batch handler logic
│   └── test_error_handling.py         # Error scenarios
├── property/
│   ├── test_probe_properties.py       # Properties 1-14, 24-28
│   └── test_probe_file_properties.py  # Properties 15-23
└── integration/
    ├── test_probe_integration.py      # End-to-end probe tests
    └── test_probe_file_integration.py # End-to-end probe_file tests
```

### Test Data Strategy

1. **Fixtures**: Use pytest fixtures for common test data (sample Lean files, theorem declarations)
2. **Generators**: Use Hypothesis strategies for property-based test data generation
3. **Mocks**: Mock LeanRunner and WorkspaceProvider for unit tests
4. **Real Lean Files**: Use real Lean files from test corpus for integration tests

### Coverage Goals

- **Line Coverage**: Minimum 90% for core domain logic
- **Branch Coverage**: Minimum 85% for error handling paths
- **Property Coverage**: All 28 properties implemented as property tests
- **Integration Coverage**: All MCP tool entry points tested end-to-end
