# Design Document: verify MCP Tool

## Overview

The `verify` tool is the foundational Lean execution primitive that provides deterministic, sandboxed, budget-bounded verification of Lean files and theorems. It establishes the core Lean execution runtime using LeanInteract (a Python interface to the Lean REPL) and serves as infrastructure for future tools like `probe`, `probe_file`, `check_patch`, and `search_annotations`.

This design follows hexagonal architecture principles to isolate core verification logic from external concerns (filesystem, process management, Lean execution). The tool is pure infrastructure with no LLM calls, designed for reproducible verification in isolated workspaces.

## Architecture

### Hexagonal Architecture

The design separates concerns into three layers:

1. **Core Domain**: Pure verification logic, orchestration, and result formatting
2. **Ports**: Abstract interfaces defining how core interacts with external systems
3. **Adapters**: Concrete implementations of ports using specific technologies

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tool Handler                      │
│                  (verify entry point)                    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Core Domain Layer                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │         VerifyCommand (immutable)                │   │
│  │  - file_path, theorem_id, budget_s, options     │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                                │
│                         ▼                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │       VerifyCommandHandler (orchestrator)        │   │
│  │  1. Create isolated workspace                    │   │
│  │  2. Run Lean verification with timeout           │   │
│  │  3. Parse and normalize diagnostics              │   │
│  │  4. Store artifacts                              │   │
│  │  5. Format deterministic response                │   │
│  └─────────────────────────────────────────────────┘   │
│           │              │              │                │
│           ▼              ▼              ▼                │
│     ┌─────────┐   ┌──────────┐   ┌──────────┐         │
│     │  Lean   │   │Workspace │   │ Artifact │         │
│     │ Runner  │   │ Provider │   │  Store   │         │
│     │  Port   │   │   Port   │   │   Port   │         │
│     └─────────┘   └──────────┘   └──────────┘         │
└─────────┬──────────────┬──────────────┬────────────────┘
          │              │              │
          ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                    Adapter Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ LeanInteract │  │ GitWorktree  │  │  Filesystem  │ │
│  │    Runner    │  │   Provider   │  │    Store     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Design Rationale

**Why Hexagonal Architecture?**
- Isolates Lean execution complexity from core verification logic
- Enables testing without spawning Lean processes (mock adapters)
- Allows swapping LeanInteract for alternative backends
- Makes workspace isolation strategy pluggable (git worktree vs temp copy)

**Why Command Pattern?**
- Encapsulates each verification as immutable data structure
- Simplifies logging, retries, and auditing
- Makes verification operations first-class and testable
- Provides consistent execution structure

## Components and Interfaces

### Core Domain Components

#### 1. VerifyCommand (Immutable Data)

```python
@dataclass(frozen=True)
class VerifyCommand:
    """Immutable command representing a verification request."""
    file_path: str
    theorem_id: str | None = None
    budget_s: float = 30.0
    max_log_excerpt_chars: int = 2000
    store_full_logs: bool = True
    workspace_mode: str | None = None  # "worktree", "temp", or None (auto)
```

#### 2. VerifyCommandHandler (Orchestrator)

```python
class VerifyCommandHandler:
    """Orchestrates verification using injected ports."""
    
    def __init__(
        self,
        lean_runner: LeanRunner,
        workspace_provider: WorkspaceProvider,
        artifact_store: ArtifactStore,
    ):
        self.lean_runner = lean_runner
        self.workspace_provider = workspace_provider
        self.artifact_store = artifact_store
    
    def handle(self, cmd: VerifyCommand) -> VerifyResult:
        """Execute verification workflow."""
        # 1. Generate run_id
        run_id = self._generate_run_id(cmd)
        
        # 2. Create isolated workspace
        workspace = self.workspace_provider.create_workspace(cmd.file_path)
        
        try:
            # 3. Run Lean verification with timeout
            lean_result = self.lean_runner.verify_file(
                workspace_path=workspace.path,
                file_path=cmd.file_path,
                theorem_id=cmd.theorem_id,
                budget_s=cmd.budget_s,
            )
            
            # 4. Parse and normalize diagnostics
            diagnostics = self._normalize_diagnostics(lean_result.diagnostics)
            
            # 5. Determine status
            status = self._determine_status(lean_result, diagnostics)
            
            # 6. Build result
            result = VerifyResult(
                api_version="0.2.0",
                status=status,
                run_id=run_id,
                file=cmd.file_path,
                theorem_id=cmd.theorem_id,
                verification_scope_used=lean_result.scope_used,
                diagnostics=diagnostics,
                diagnostic_summary=self._build_summary(diagnostics),
                evidence=self._build_evidence(lean_result, cmd.max_log_excerpt_chars),
                metadata=self._build_metadata(workspace, lean_result),
                timing=self._build_timing(lean_result),
            )
            
            # 7. Store artifacts if requested
            if cmd.store_full_logs:
                self.artifact_store.store(run_id, cmd, result, lean_result.full_logs)
            
            # 8. Ensure deterministic output
            return self._ensure_deterministic(result)
            
        finally:
            # 9. Cleanup workspace
            self.workspace_provider.cleanup_workspace(workspace)
```

### Port Interfaces

#### 1. LeanRunner Port

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
        """
        Run Lean verification on file or theorem.
        
        Returns:
            LeanRunResult with status, diagnostics, logs, timing
        
        Raises:
            TimeoutError: If verification exceeds budget
            LeanExecutionError: If Lean process fails
        """
        ...
```

#### 2. WorkspaceProvider Port

```python
class WorkspaceProvider(Protocol):
    """Abstract interface for workspace isolation."""
    
    def create_workspace(self, file_path: str) -> Workspace:
        """
        Create isolated workspace for verification.
        
        Returns:
            Workspace with path and metadata
        """
        ...
    
    def cleanup_workspace(self, workspace: Workspace) -> None:
        """Clean up workspace resources."""
        ...
```

#### 3. ArtifactStore Port

```python
class ArtifactStore(Protocol):
    """Abstract interface for artifact storage."""
    
    def store(
        self,
        run_id: str,
        command: VerifyCommand,
        result: VerifyResult,
        full_logs: str,
    ) -> None:
        """Store verification artifacts under run_id directory."""
        ...
```

### Adapter Implementations

#### 1. LeanInteractRunner (Adapter)

```python
class LeanInteractRunner:
    """Concrete implementation using LeanInteract library."""
    
    def __init__(self, timeout_buffer_ms: int = 100):
        self.timeout_buffer_ms = timeout_buffer_ms
    
    def verify_file(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str | None,
        budget_s: float,
    ) -> LeanRunResult:
        """
        Execute Lean verification using LeanInteract.
        
        Strategy:
        1. If theorem_id provided, create abridged file up to theorem end
        2. Initialize LeanServer in workspace context (lake env)
        3. Use FileCommand to check file (full or abridged)
        4. Parse response for errors, warnings, sorries
        5. Enforce timeout with process tree kill
        6. Return structured result
        """
        start_time = time.time()
        
        # Initialize LeanServer with project context
        server = LeanServer(
            project_path=str(workspace_path),
            timeout=budget_s,
        )
        
        try:
            # Determine verification scope
            if theorem_id:
                # Theorem-level: create abridged file
                target_file, scope_used = self._prepare_theorem_verification(
                    workspace_path, file_path, theorem_id
                )
            else:
                # File-level: verify entire file
                target_file = file_path
                scope_used = "file"
            
            # Run file verification
            response = server.run_file(target_file)
            
            # Parse diagnostics from response
            diagnostics = self._parse_diagnostics(response)
            
            # Map diagnostics back to original file if theorem-level
            if theorem_id and target_file != file_path:
                for diag in diagnostics:
                    diag["location"]["file"] = file_path
            
            elapsed = time.time() - start_time
            
            return LeanRunResult(
                status="success" if not diagnostics else "fail",
                diagnostics=diagnostics,
                scope_used=scope_used,
                full_logs=self._capture_logs(response),
                timing={"lean_execution_s": elapsed},
                exit_code=0,
            )
            
        except TimeoutError:
            elapsed = time.time() - start_time
            return LeanRunResult(
                status="timeout",
                diagnostics=[],
                scope_used="theorem" if theorem_id else "file",
                full_logs="Verification timed out",
                timing={"lean_execution_s": elapsed},
                exit_code=-1,
            )
        
        finally:
            server.close()
    
    def _prepare_theorem_verification(
        self,
        workspace_path: Path,
        file_path: str,
        theorem_id: str,
    ) -> tuple[str, str]:
        """
        Prepare theorem-level verification by creating abridged file.
        
        Returns:
            (target_file_path, scope_used)
        """
        from ..core.source import SourceText
        from ..core.indexer import build_index
        
        # Parse file to find theorem
        source = SourceText(path=file_path, text=Path(file_path).read_text())
        index = build_index(source)
        theorem = index.find_theorem(theorem_id)
        
        if not theorem:
            raise ValueError(f"Theorem not found: {theorem_id}")
        
        # Extract content up to theorem end
        lines = source.text.splitlines(keepends=True)
        abridged_content = "".join(lines[:theorem.decl_span.end_line])
        
        # Create temporary file in workspace
        temp_file = workspace_path / f"_verify_{theorem_id}.lean"
        temp_file.write_text(abridged_content)
        
        return str(temp_file), "theorem"
```

#### 2. GitWorktreeProvider (Adapter)

```python
class GitWorktreeProvider:
    """Concrete implementation using git worktree."""
    
    def __init__(self, worktree_dir: Path):
        self.worktree_dir = worktree_dir
    
    def create_workspace(self, file_path: str) -> Workspace:
        """
        Create git worktree for isolated verification.
        
        Strategy:
        1. Generate unique worktree name
        2. Run: git worktree add <path> HEAD
        3. Return Workspace with path and metadata
        """
        workspace_id = self._generate_workspace_id()
        worktree_path = self.worktree_dir / workspace_id
        
        # Create worktree
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "HEAD"],
            check=True,
            capture_output=True,
        )
        
        return Workspace(
            path=worktree_path,
            workspace_id=workspace_id,
            mode="worktree",
        )
    
    def cleanup_workspace(self, workspace: Workspace) -> None:
        """Remove git worktree."""
        subprocess.run(
            ["git", "worktree", "remove", str(workspace.path), "--force"],
            check=True,
            capture_output=True,
        )
```

#### 3. FilesystemArtifactStore (Adapter)

```python
class FilesystemArtifactStore:
    """Concrete implementation using filesystem."""
    
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
    
    def store(
        self,
        run_id: str,
        command: VerifyCommand,
        result: VerifyResult,
        full_logs: str,
    ) -> None:
        """
        Store artifacts under run_id directory.
        
        Structure:
        artifacts/
          <run_id>/
            request.json
            result.json
            lean_output.log
        """
        run_dir = self.artifacts_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Store request
        with open(run_dir / "request.json", "w") as f:
            json.dump(dataclasses.asdict(command), f, indent=2)
        
        # Store result
        with open(run_dir / "result.json", "w") as f:
            json.dump(dataclasses.asdict(result), f, indent=2)
        
        # Store full logs
        with open(run_dir / "lean_output.log", "w") as f:
            f.write(full_logs)
```

## Data Models

### Input Schema

```json
{
  "file": "string (required)",
  "theorem_id": "string | null (optional)",
  "budget_s": "number (optional, default: 30.0)",
  "max_log_excerpt_chars": "number (optional, default: 2000)",
  "store_full_logs": "boolean (optional, default: true)",
  "workspace_mode": "string | null (optional, values: 'worktree' | 'temp' | null)"
}
```

### Output Schema

```json
{
  "api_version": "0.2.0",
  "status": "success | fail | timeout | error",
  "run_id": "string",
  "file": "string",
  "theorem_id": "string | null",
  "verification_scope_used": "file | theorem | file_fallback",
  "diagnostics": [
    {
      "severity": "error | warning | info",
      "message": "string",
      "location": {
        "file": "string",
        "line": "number",
        "col": "number",
        "end_line": "number | null",
        "end_col": "number | null"
      }
    }
  ],
  "diagnostic_summary": {
    "error_count": "number",
    "warning_count": "number",
    "info_count": "number"
  },
  "evidence": {
    "stdout_excerpt": "string",
    "stderr_excerpt": "string",
    "notes": ["string"]
  },
  "metadata": {
    "workspace_mode": "worktree | temp",
    "workspace_id": "string",
    "repo_commit": "string | null",
    "lean_version": "string | null",
    "lake_version": "string | null"
  },
  "timing": {
    "total_s": "number",
    "lean_execution_s": "number",
    "overhead_s": "number"
  }
}
```

### Internal Data Structures

```python
@dataclass(frozen=True)
class LeanRunResult:
    """Result from Lean execution."""
    status: str  # "success", "fail", "timeout"
    diagnostics: list[dict]
    scope_used: str  # "file", "theorem", "file_fallback"
    full_logs: str
    timing: dict[str, float]
    exit_code: int

@dataclass(frozen=True)
class Workspace:
    """Isolated workspace metadata."""
    path: Path
    workspace_id: str
    mode: str  # "worktree" or "temp"

@dataclass(frozen=True)
class VerifyResult:
    """Final verification result."""
    api_version: str
    status: str
    run_id: str
    file: str
    theorem_id: str | None
    verification_scope_used: str
    diagnostics: list[dict]
    diagnostic_summary: dict
    evidence: dict
    metadata: dict
    timing: dict
```

## Execution Strategy

### LeanInteract Integration

LeanInteract provides programmatic access to Lean 4 through the Lean REPL. The execution strategy:

1. **Initialization**: Create `LeanServer` instance with project path
   - LeanInteract automatically runs in `lake env` context
   - Ensures imports are built before checking file
   - Handles Lean toolchain detection via elan

2. **File Verification**: Use `FileCommand` to check entire file
   - Command: `server.run_file(file_path)`
   - Returns structured response with errors, warnings, sorries
   - Captures stdout/stderr from Lean process

3. **Response Parsing**: Extract diagnostics from LeanInteract response
   - Parse `messages` array for errors/warnings
   - Parse `sorries` array for incomplete proofs
   - Normalize locations to standard format

4. **Timeout Enforcement**: LeanInteract supports timeout parameter
   - Set timeout on LeanServer initialization
   - LeanInteract kills Lean process on timeout
   - Catch TimeoutError and return timeout status

5. **Cleanup**: Close LeanServer to terminate Lean process
   - Always call `server.close()` in finally block
   - Ensures no orphaned Lean processes

### Theorem-Level Verification Strategy

**Implementation Approach**: Create temporary file with content up to theorem end.

Since LeanInteract doesn't support verifying individual theorems within a file, we implement theorem-level verification by:

1. **Extract theorem scope**: Use the theorem's location (decl_start, decl_end) from indexer
2. **Create temporary file**: Copy file content from line 1 to theorem's end_line
3. **Verify temporary file**: Run LeanInteract on the abridged file
4. **Map diagnostics back**: Adjust line numbers to match original file

**Detailed Strategy**:

```python
def verify_theorem(
    workspace_path: Path,
    file_path: str,
    theorem_id: str,
    budget_s: float,
) -> LeanRunResult:
    """Verify a specific theorem by creating temporary abridged file."""
    
    # 1. Parse original file to find theorem location
    source = SourceText(path=file_path, text=read_file(file_path))
    index = build_index(source)
    theorem = index.find_theorem(theorem_id)
    
    if not theorem:
        raise ValueError(f"Theorem not found: {theorem_id}")
    
    # 2. Extract content up to theorem end
    lines = source.text.splitlines(keepends=True)
    abridged_content = "".join(lines[:theorem.decl_span.end_line])
    
    # 3. Create temporary file in workspace
    temp_file = workspace_path / f"_verify_{theorem_id}.lean"
    temp_file.write_text(abridged_content)
    
    # 4. Verify temporary file with LeanInteract
    server = LeanServer(project_path=str(workspace_path), timeout=budget_s)
    try:
        response = server.run_file(str(temp_file))
        diagnostics = parse_diagnostics(response)
        
        # 5. Map diagnostics back to original file
        # (line numbers already match since we preserved line structure)
        for diag in diagnostics:
            diag["location"]["file"] = file_path
        
        return LeanRunResult(
            status="success" if not diagnostics else "fail",
            diagnostics=diagnostics,
            scope_used="theorem",
            full_logs=capture_logs(response),
            timing={"lean_execution_s": response.elapsed},
            exit_code=0,
        )
    finally:
        server.close()
        temp_file.unlink()  # Clean up temporary file
```

**Benefits**:
- Enables theorem-level verification for future tools (probe, probe_file)
- Faster than full file verification (only checks dependencies + theorem)
- Diagnostics are scoped to relevant code
- Works with LeanInteract's file-based verification

**Limitations**:
- Requires parsing file to find theorem location (uses existing indexer)
- Creates temporary file (cleaned up after verification)
- May miss errors in code after the theorem (acceptable for theorem-level scope)

**Fallback Behavior**:
- If theorem_id is invalid or not found → return error with code "theorem_not_found"
- If indexer fails to parse file → fall back to full file verification with note

### Workspace Isolation Strategy

**Git Worktree Approach** (Preferred):
- Use `git worktree add` to create isolated copy
- Advantages: Fast, shares .git objects, preserves git context
- Disadvantages: Requires git repository

**Temp Copy Approach** (Fallback):
- Copy entire project to temp directory
- Advantages: Works without git, simple
- Disadvantages: Slower, duplicates files

**Auto-Detection Logic**:
```python
def detect_workspace_mode() -> str:
    if is_git_repository():
        return "worktree"
    else:
        return "temp"
```

## Determinism Rules

To ensure identical outputs for identical inputs:

### 1. Diagnostic Sorting

Sort diagnostics by:
1. File path (lexicographic)
2. Line number (numeric)
3. Column number (numeric)
4. Severity (error < warning < info)
5. Message (lexicographic, tie-breaker)

```python
def sort_diagnostics(diagnostics: list[dict]) -> list[dict]:
    severity_order = {"error": 0, "warning": 1, "info": 2}
    
    return sorted(
        diagnostics,
        key=lambda d: (
            d["location"]["file"],
            d["location"]["line"],
            d["location"]["col"],
            severity_order.get(d["severity"], 3),
            d["message"],
        ),
    )
```

### 2. Log Excerpt Truncation

Deterministic truncation strategy:
- Take first N characters (configurable via `max_log_excerpt_chars`)
- If truncated, append "... (truncated)"
- Never truncate mid-line (find last newline before N)

```python
def truncate_log(log: str, max_chars: int) -> str:
    if len(log) <= max_chars:
        return log
    
    # Find last newline before max_chars
    truncate_point = log.rfind("\n", 0, max_chars)
    if truncate_point == -1:
        truncate_point = max_chars
    
    return log[:truncate_point] + "\n... (truncated)"
```

### 3. JSON Key Ordering

Use `sort_keys=True` when serializing JSON:
```python
json.dumps(result, sort_keys=True, indent=2)
```

### 4. Run ID Generation

Run ID includes timestamp but response content is stable:
```python
def generate_run_id(file_path: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
    return f"verify-{timestamp}-{file_hash}"
```

### 5. Notes Normalization

Reuse existing `normalize_notes` from `core.format`:
- Trim each note to max 200 characters
- Cap at 10 notes total
- Sort notes lexicographically

## Error Handling

### Error Categories

1. **Input Validation Errors**
   - Status: `error`
   - Examples: Missing file, invalid budget_s, malformed theorem_id
   - Return immediately without Lean execution

2. **Workspace Errors**
   - Status: `error`
   - Examples: Git worktree creation failed, temp directory unavailable
   - Clean up partial resources

3. **Lean Execution Errors**
   - Status: `fail`
   - Examples: Compilation errors, type errors, sorry in proof
   - Return diagnostics from Lean

4. **Timeout Errors**
   - Status: `timeout`
   - Examples: Verification exceeds budget_s
   - Kill Lean process, clean up workspace

5. **Internal Errors**
   - Status: `error`
   - Examples: LeanInteract crash, unexpected exception
   - Return error diagnostic with stack trace excerpt

### Error Response Format

All errors return valid JSON with consistent structure:

```json
{
  "api_version": "0.2.0",
  "status": "error",
  "run_id": "verify-20250101-120000-abc123",
  "file": "path/to/file.lean",
  "theorem_id": null,
  "verification_scope_used": "none",
  "diagnostics": [
    {
      "severity": "error",
      "message": "Detailed error message",
      "location": null
    }
  ],
  "diagnostic_summary": {
    "error_count": 1,
    "warning_count": 0,
    "info_count": 0
  },
  "evidence": {
    "stdout_excerpt": "",
    "stderr_excerpt": "Error details...",
    "notes": ["error_category: input_validation"]
  },
  "metadata": {},
  "timing": {}
}
```

### Error Codes (in notes)

Structured error codes for programmatic handling:
- `input_validation_error`: Invalid input parameters
- `workspace_creation_failed`: Cannot create isolated workspace
- `lean_execution_failed`: Lean process crashed
- `timeout_exceeded`: Verification exceeded budget
- `theorem_scope_not_supported`: Theorem-level verification unavailable
- `internal_error`: Unexpected exception

### Process Cleanup Guarantees

Ensure no leaked resources:

```python
def handle_with_cleanup(cmd: VerifyCommand) -> VerifyResult:
    workspace = None
    lean_server = None
    
    try:
        workspace = workspace_provider.create_workspace(cmd.file_path)
        lean_server = lean_runner.create_server(workspace.path)
        
        # ... verification logic ...
        
    except Exception as e:
        # Log error, build error response
        return build_error_response(e)
    
    finally:
        # Always cleanup, even on exception
        if lean_server:
            lean_server.close()
        if workspace:
            workspace_provider.cleanup_workspace(workspace)
```

## Testing Strategy

### Dual Testing Approach

The verify tool requires both unit tests and property-based tests:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
- Schema validation with valid/invalid inputs
- Timeout enforcement with known slow files
- Workspace isolation with concurrent invocations
- Error handling for missing files, invalid theorems
- Integration with mathlib fixtures

**Property Tests**: Verify universal properties across all inputs
- Determinism: Same input → same output (modulo run_id/timestamp)
- Timeout accuracy: Actual timeout within 100ms of budget
- Process cleanup: No orphaned processes after any execution
- Diagnostic sorting: Always sorted by (file, line, col, severity, message)
- JSON validity: All responses are valid JSON

### Property-Based Testing Configuration

- Library: `hypothesis` (Python property-based testing)
- Minimum iterations: 100 per property test
- Each test references design property number
- Tag format: `# Feature: lean-verify-tool, Property N: <property_text>`

### Test Categories

1. **Contract Tests**: Validate JSON schema compliance
2. **Determinism Tests**: Verify identical outputs for identical inputs
3. **Timeout Tests**: Verify budget enforcement and process cleanup
4. **Workspace Tests**: Verify isolation and cleanup
5. **Integration Tests**: Verify with real Lean files (mathlib fixtures)
6. **Error Tests**: Verify error handling for all failure modes



## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

The following properties define the correctness criteria for the verify tool. Each property is universally quantified and references the requirements it validates.

### Property 1: Response Schema Compliance

*For any* verification request (valid or invalid), the response SHALL conform to the output JSON schema with required fields: api_version, status, run_id, file, diagnostics, diagnostic_summary, evidence, metadata, and timing.

**Validates: Requirements 1.1, 8.3**

### Property 2: Status Value Validity

*For any* verification response, the status field SHALL be exactly one of: "success", "fail", "timeout", or "error".

**Validates: Requirements 1.1**

### Property 3: Workspace Isolation

*For any* verification request, the tool SHALL create an isolated workspace and SHALL NOT modify any files in the original working tree.

**Validates: Requirements 1.2, 6.1, 6.2**

### Property 4: Timeout Enforcement

*For any* verification request with budget_s=B, if Lean execution exceeds B seconds, the tool SHALL return status="timeout" and SHALL terminate all Lean processes within 100ms of the budget.

**Validates: Requirements 1.3, 4.2, 4.3**

### Property 5: Process and Workspace Cleanup

*For any* verification request (success, failure, or timeout), the tool SHALL clean up all Lean processes and workspace resources, leaving no orphaned processes or temporary directories.

**Validates: Requirements 4.4, 6.3**

### Property 6: Diagnostic Structure

*For any* verification response containing diagnostics, each diagnostic SHALL have fields: severity (one of "error", "warning", "info"), message (non-empty string), and location (with file, line, col, and optional end_line, end_col).

**Validates: Requirements 1.4, 5.1, 5.2, 5.3**

### Property 7: Deterministic Diagnostic Sorting

*For any* verification response with multiple diagnostics, the diagnostics array SHALL be sorted by (file, line, col, severity, message) in that order, with lexicographic tie-breaking for messages at the same location.

**Validates: Requirements 3.1, 3.2**

### Property 8: Deterministic Output

*For any* two verification requests with identical inputs (same file, same repo state, same parameters), the responses SHALL be identical except for run_id and timestamp fields. Specifically: diagnostics order, log truncation points, and JSON key order SHALL be identical.

**Validates: Requirements 3.3, 3.4, 3.5, 8.5**

### Property 9: Log Excerpt Truncation

*For any* verification response, the stdout_excerpt and stderr_excerpt fields SHALL NOT exceed max_log_excerpt_chars, and if truncated, SHALL truncate at the last newline before the limit and append "... (truncated)".

**Validates: Requirements 1.6, 7.2**

### Property 10: Artifact Storage Completeness

*For any* verification request with store_full_logs=true, the tool SHALL create a directory under run_id containing exactly three files: request.json, result.json, and lean_output.log.

**Validates: Requirements 1.5, 7.1**

### Property 11: Artifact Storage Control

*For any* verification request with store_full_logs=false, the tool SHALL NOT create any artifact files.

**Validates: Requirements 7.5**

### Property 12: Diagnostic Summary Consistency

*For any* verification response, the diagnostic_summary counts (error_count, warning_count, info_count) SHALL exactly match the count of diagnostics with each severity level in the diagnostics array.

**Validates: Requirements 5.4**

### Property 13: Evidence Structure

*For any* verification response, the evidence section SHALL contain fields: stdout_excerpt (string), stderr_excerpt (string), and notes (array of strings).

**Validates: Requirements 5.5**

### Property 14: Metadata Structure

*For any* verification response, the metadata section SHALL contain fields: workspace_mode, workspace_id, and MAY contain repo_commit, lean_version, lake_version.

**Validates: Requirements 6.5, 8.4**

### Property 15: Concurrent Execution Safety

*For any* set of N concurrent verification requests, each SHALL complete successfully with isolated workspaces, and no verification SHALL interfere with another (no shared state, no race conditions).

**Validates: Requirements 6.4**

### Property 16: Theorem Scope Support

*For any* verification request with valid theorem_id, the tool SHALL create an abridged file containing content up to the theorem's end line and verify only that scope, returning verification_scope_used="theorem".

**Validates: Requirements 2.1, 2.2**

### Property 17: Theorem Not Found Handling

*For any* verification request with invalid or non-existent theorem_id, the tool SHALL return error status with diagnostic message indicating the theorem was not found.

**Validates: Requirements 2.3**

### Property 18: Run ID Uniqueness

*For any* two verification requests (even with identical inputs), the run_id values SHALL be distinct.

**Validates: Requirements 1.5, 7.3**

### Property 19: Artifact Persistence

*For any* verification request with store_full_logs=true, the artifact directory SHALL exist and contain all files after the tool returns control to the caller.

**Validates: Requirements 7.4**

## Testing Strategy

The verify tool requires a dual testing approach combining unit tests and property-based tests to ensure comprehensive coverage.

### Unit Tests

Unit tests verify specific examples, edge cases, and integration points:

**Schema Validation Tests**:
- Valid input with all fields → success response
- Valid input with minimal fields → success with defaults
- Invalid input (missing file) → error response
- Invalid input (negative budget_s) → error response

**Timeout Tests**:
- File that completes within budget → success
- File that exceeds budget → timeout status
- Timeout cleanup → no orphaned processes

**Workspace Isolation Tests**:
- Verification with git repository → worktree mode
- Verification without git → temp mode
- Original files unchanged after verification
- Workspace cleaned up after completion

**Error Handling Tests**:
- Missing file → error with diagnostic
- Invalid theorem_id → error or fallback
- Lean crash → error with stderr excerpt
- Workspace creation failure → error response

**Integration Tests with Mathlib Fixtures**:
- Valid mathlib file → success with no errors
- File with type error → fail with error diagnostic
- File with sorry → success with warning diagnostic
- File with imports → success (imports resolved)

**Artifact Tests**:
- store_full_logs=true → artifacts created
- store_full_logs=false → no artifacts
- Artifact structure → request.json, result.json, lean_output.log
- Artifact content → matches request and response

### Property-Based Tests

Property tests verify universal properties across randomized inputs using the `hypothesis` library. Each test runs a minimum of 100 iterations.

**Configuration**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

@settings(max_examples=100)
@given(
    file_path=st.text(min_size=1),
    budget_s=st.floats(min_value=0.1, max_value=60.0),
)
def test_property_N(file_path, budget_s):
    # Feature: lean-verify-tool, Property N: <property_text>
    ...
```

**Property Test Suite**:

1. **Response Schema Compliance** (Property 1)
   - Generate random valid/invalid inputs
   - Verify all responses have required fields
   - Tag: `# Feature: lean-verify-tool, Property 1: Response schema compliance`

2. **Deterministic Output** (Property 8)
   - Run same verification twice
   - Compare responses (excluding run_id, timestamps)
   - Verify identical diagnostics, excerpts, JSON keys
   - Tag: `# Feature: lean-verify-tool, Property 8: Deterministic output`

3. **Timeout Enforcement** (Property 4)
   - Generate files with varying complexity
   - Set budget_s below expected completion time
   - Verify timeout status and timing accuracy
   - Tag: `# Feature: lean-verify-tool, Property 4: Timeout enforcement`

4. **Process Cleanup** (Property 5)
   - Run verification (success, fail, timeout)
   - Check for orphaned Lean processes
   - Check for leaked workspace directories
   - Tag: `# Feature: lean-verify-tool, Property 5: Process and workspace cleanup`

5. **Diagnostic Sorting** (Property 7)
   - Generate files with multiple errors
   - Verify diagnostics sorted by (file, line, col, severity, message)
   - Tag: `# Feature: lean-verify-tool, Property 7: Deterministic diagnostic sorting`

6. **Diagnostic Summary Consistency** (Property 12)
   - Run verification on any file
   - Count diagnostics by severity
   - Verify counts match diagnostic_summary
   - Tag: `# Feature: lean-verify-tool, Property 12: Diagnostic summary consistency`

7. **Concurrent Execution Safety** (Property 15)
   - Run N verifications concurrently (N=2-10)
   - Verify all complete successfully
   - Verify no workspace collisions
   - Tag: `# Feature: lean-verify-tool, Property 15: Concurrent execution safety`

8. **Artifact Storage Completeness** (Property 10)
   - Run verification with store_full_logs=true
   - Verify artifact directory exists
   - Verify all three files present
   - Tag: `# Feature: lean-verify-tool, Property 10: Artifact storage completeness`

### Test Fixtures

**Mathlib Test Files**:
- `valid_theorem.lean`: Simple valid theorem
- `type_error.lean`: File with type error
- `sorry_proof.lean`: File with incomplete proof
- `slow_verification.lean`: File that takes >5 seconds
- `import_heavy.lean`: File with many imports

**Mock Adapters for Unit Tests**:
- `MockLeanRunner`: Returns predefined results without spawning Lean
- `MockWorkspaceProvider`: Creates in-memory workspaces
- `MockArtifactStore`: Stores artifacts in memory

### Test Organization

```
tests/
  unit/
    test_verify_command.py          # Command validation
    test_verify_handler.py          # Handler orchestration
    test_lean_interact_runner.py   # LeanInteract adapter
    test_workspace_provider.py      # Workspace isolation
    test_artifact_store.py          # Artifact storage
  
  property/
    test_verify_properties.py       # All property-based tests
  
  integration/
    test_verify_mathlib.py          # Integration with real Lean files
    test_verify_concurrent.py       # Concurrent execution
  
  mcp_contract/
    test_verify_schema.py           # JSON schema validation
  
  fixtures/
    lean/
      valid_theorem.lean
      type_error.lean
      sorry_proof.lean
      slow_verification.lean
      import_heavy.lean
```

### Coverage Goals

- Unit test coverage: >90% of core logic
- Property test coverage: All 18 correctness properties
- Integration test coverage: All major Lean file types
- Contract test coverage: 100% of JSON schema

### Continuous Integration

All tests run on:
- Every commit (unit tests, property tests with 100 iterations)
- Pull requests (full suite including integration tests)
- Nightly builds (property tests with 1000 iterations for deeper coverage)
