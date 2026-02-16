# Observability Module

This module provides ports and adapters for observability concerns following hexagonal architecture principles.

## Overview

The observability module enables the core domain to collect metadata about the execution environment (git commit, tool versions, etc.) without depending on specific implementation details.

## Architecture

```
observability/
├── __init__.py              # Module exports
├── ports.py                 # Abstract interfaces (MetadataCollector)
├── metadata_collector.py    # Subprocess implementation
└── README.md               # This file
```

### Hexagonal Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Core Domain                          │
│  (ProbeCommandHandler, VerifyCommandHandler, etc.)     │
│                                                         │
│  Depends on: MetadataCollector (Protocol)              │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Port (Abstract Interface)
                     │
┌────────────────────▼────────────────────────────────────┐
│              Observability Adapter                      │
│         SubprocessMetadataCollector                     │
│                                                         │
│  Implementation: Uses subprocess + threading            │
└─────────────────────────────────────────────────────────┘
```

## Components

### Port: `MetadataCollector`

Abstract interface defined in `ports.py`:

```python
class MetadataCollector(Protocol):
    """Port for collecting environment metadata."""

    def collect_version_info(self) -> dict[str, str]:
        """
        Collect version metadata from the environment.

        Returns:
            Dictionary with optional keys:
            - repo_commit: Git commit hash
            - lean_version: Lean version string
            - lake_version: Lake version string
        """
        ...
```

### Adapter: `SubprocessMetadataCollector`

Implementation in `metadata_collector.py`:

```python
class SubprocessMetadataCollector:
    """
    Collects metadata using subprocess commands.

    Uses threading to avoid Windows pipe deadlock issues.
    """

    def collect_version_info(self) -> dict[str, str]:
        """Collect git commit, lean version, lake version."""
        ...
```

## Usage

### In Domain Handlers

Domain handlers receive the metadata collector via dependency injection:

```python
class ProbeCommandHandler:
    def __init__(
        self,
        validator: ProofValidator,
        workspace_provider: WorkspaceProvider,
        classifier: AutomationClassifier,
        artifact_store: ArtifactStore | None = None,
        metadata_collector: MetadataCollector | None = None,  # Optional
    ):
        self.metadata_collector = metadata_collector
        # ...

    def _build_metadata(self, lean_result: Any) -> dict[str, Any]:
        """Build metadata section with version information."""
        if self.metadata_collector is None:
            return {}

        return self.metadata_collector.collect_version_info()
```

### In Composition Root (Tools)

Tools wire up the metadata collector when creating handlers:

```python
from ...observability import SubprocessMetadataCollector

# Create metadata collector
metadata_collector = SubprocessMetadataCollector()

# Wire into handler
handler = ProbeCommandHandler(
    lean_runner=lean_runner,
    workspace_provider=workspace_provider,
    classifier=classifier,
    artifact_store=artifact_store,
    metadata_collector=metadata_collector,  # Inject here
)
```

## Windows Pipe Deadlock Issue

### The Problem

When the MCP server runs as a subprocess (e.g., spawned by GitHub Copilot), nested subprocess calls can deadlock on Windows:

1. **MCP server** is spawned as subprocess by IDE
2. **MCP server** spawns nested subprocess (git/lean/lake)
3. **Nested subprocess** writes output to pipe
4. **Pipe buffer fills** (4KB on Windows vs 64KB on Linux)
5. **Nested subprocess blocks** waiting for parent to read
6. **Parent (MCP server) blocks** waiting for child to finish
7. **DEADLOCK!**

### The Solution

`SubprocessMetadataCollector` uses threading to read subprocess output asynchronously:

```python
def _run_command_safe(self, cmd: list[str], timeout: float = 1.0) -> str | None:
    """Run command with timeout, avoiding pipe deadlock using threads."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Read output in separate thread to avoid blocking
    stdout_data = []
    def read_stdout():
        stdout_data.append(proc.stdout.read())

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stdout_thread.start()

    # Wait for process with timeout
    proc.wait(timeout=timeout)
    stdout_thread.join(timeout=0.5)

    return stdout_data[0].strip() if proc.returncode == 0 and stdout_data else None
```

**Key insight**: The separate thread reads from the pipe while the main thread waits for the process, preventing the pipe buffer from filling up and causing deadlock.

### Platform Support

- **Windows**: Uses threading to avoid pipe deadlock ✅
- **Linux**: Works correctly (threading adds minimal overhead) ✅
- **macOS**: Works correctly (threading adds minimal overhead) ✅

## Benefits

### 1. Separation of Concerns
Observability logic is isolated from core domain logic.

### 2. Testability
Easy to mock `MetadataCollector` in tests:

```python
class MockMetadataCollector:
    def collect_version_info(self) -> dict[str, str]:
        return {
            "repo_commit": "test-commit",
            "lean_version": "test-lean",
            "lake_version": "test-lake",
        }

handler = ProbeCommandHandler(
    lean_runner=mock_lean_runner,
    workspace_provider=mock_workspace_provider,
    classifier=mock_classifier,
    metadata_collector=MockMetadataCollector(),  # Test double
)
```

### 3. Reusability
All handlers use the same implementation - no code duplication.

### 4. Extensibility
Easy to add new metadata sources without changing core domain:

```python
class EnvironmentMetadataCollector:
    """Collect metadata from environment variables."""

    def collect_version_info(self) -> dict[str, str]:
        return {
            "repo_commit": os.getenv("GIT_COMMIT", ""),
            "lean_version": os.getenv("LEAN_VERSION", ""),
            "lake_version": os.getenv("LAKE_VERSION", ""),
        }
```

### 5. Platform-Agnostic
Core domain doesn't know about Windows vs Linux - adapter handles platform differences.

## Error Handling

The metadata collector **never raises exceptions**:

- Missing tools (git, lean, lake) → Missing keys in result
- Command timeouts → Missing keys in result
- Command failures → Missing keys in result

This ensures metadata collection never breaks the main workflow.

## Use Cases

### Debugging
"This bug only happens with Lean 4.26.0-rc1"

### Reproducibility
"Let me recreate the exact environment from the artifact metadata"

### Troubleshooting
"Oh, they're on the wrong git commit"

### Auditing
"Which version was used for this proof?"

### Change Tracking
"Did this work before we upgraded Lake?"

## Future Enhancements

Potential additions to the observability module:

1. **Metrics Collection**: Track execution times, success rates, etc.
2. **Tracing**: Distributed tracing for multi-step workflows
3. **Structured Logging**: Consistent log formatting across the codebase
4. **Health Checks**: System health monitoring
5. **Performance Profiling**: Identify bottlenecks

## References

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Dependency Injection](https://en.wikipedia.org/wiki/Dependency_injection)
- [Windows Subprocess Pipe Deadlock](https://bugs.python.org/issue1256)
