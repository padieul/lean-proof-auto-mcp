# Design Document: Iterative Orchestration Enhancements

## Overview

This design describes the architectural migration of the lean-proof-auto-mcp system to use LeanInteract as its sole foundation for Lean interaction, enabling LLM-guided proof refactoring through iterative orchestration.

### Problem Statement

The current system uses regex-based parsing for hint extraction, achieving only ~70% accuracy. This prevents reliable extraction of lemmas from original proofs, limiting the system's ability to suggest appropriate hints for automation. Additionally, the system provides minimal feedback (success/fail only), preventing LLMs from iterating effectively on proof attempts.

### Solution Approach

Replace all Lean interaction with LeanInteract-based queries, achieving 95%+ accuracy for hint extraction. Provide rich feedback mechanisms including proof states, partial progress tracking, and tactical suggestions. Enable fast iteration cycles through new validation tools.

### Key Innovations

1. **LeanInteract Foundation**: All Lean interaction via LeanInteract REPL, no regex parsing
2. **Accurate Hint Extraction**: Use `declaration.value.constants` for 95%+ accuracy
3. **Rich Feedback**: Proof states, partial progress, tactical suggestions for LLM iteration
4. **Fast Validation**: 10-second validation cycles for rapid iteration
5. **Three-Layer Architecture**: Clean separation between MCP tools, business logic, and Lean interaction

### Success Criteria

- 20-35% overall refactoring success rate across theorem complexity tiers
- 95%+ accuracy for hint extraction from original proofs
- Average 2-3 LLM iterations per successful refactoring
- < 50 second full iteration cycle (search + validate)
- < 5% false positive rate for refactored proofs

## Architecture

### Three-Layer Hexagonal Architecture

The system follows hexagonal architecture with three distinct layers:

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                        │
│              (LLM-facing interface)                      │
│                                                          │
│  • search_automated_proof (enhanced)                    │
│  • try_automated_proof (new)                            │
│  • get_proof_context (new)                              │
│  • probe (migrated to LeanInteract)                     │
│  • probe_file (migrated to LeanInteract)                │
│  • verify (migrated to LeanInteract)                    │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│              Core Domain Layer                           │
│         (Business logic, hexagonal)                      │
│                                                          │
│  • CandidateGenerator (refactored)                      │
│  • ContextExtractor (new)                               │
│  • FeedbackBuilder (new)                                │
│  • SearchOrchestrator (enhanced)                        │
│  • MinimizationEngine (existing)                        │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│            LeanInteract Adapter Layer                    │
│       (All Lean interaction via LeanInteract)            │
│                                                          │
│  • LeanInteractQuerier                                  │
│  • ProofStateInspector                                  │
│  • ProofValidator                                       │
│  • ServerManager                                        │
└──────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**MCP Tool Layer**:
- Exposes tools to LLM via Model Context Protocol
- Validates input parameters
- Translates between MCP format and domain objects
- Returns structured JSON responses
- No business logic or Lean interaction

**Core Domain Layer**:
- Implements business logic for proof refactoring
- Orchestrates search strategies
- Builds feedback and suggestions
- Manages candidate generation and ranking
- Independent of MCP and LeanInteract details
- Uses dependency injection for all external dependencies

**LeanInteract Adapter Layer**:
- Encapsulates all LeanInteract interaction
- Manages LeanInteract server lifecycle
- Translates between domain objects and LeanInteract types
- Handles errors and timeouts
- Provides abstract interfaces (ports) to Core Domain Layer

### Dependency Flow

Dependencies flow inward: MCP Tool Layer → Core Domain Layer ← LeanInteract Adapter Layer

The Core Domain Layer depends only on abstract interfaces (protocols), not concrete implementations. This enables:
- Testing core logic without LeanInteract
- Swapping LeanInteract for alternative implementations
- Clear separation of concerns

### Metadata Collection Integration

All command handlers in the Core Domain Layer accept an optional `MetadataCollector` port for collecting environment metadata (git commit, lean version, lake version). This follows the existing pattern used by probe, probe_file, verify, and search_annotations handlers.

**Pattern**:
```python
class SearchAutomatedProofHandler:
    def __init__(
        self,
        candidate_gen: CandidateGenerator,
        feedback_builder: FeedbackBuilder,
        validator: ProofValidator,
        metadata_collector: MetadataCollector | None = None,  # Optional
    ):
        self.metadata_collector = metadata_collector
        # ...
    
    def _build_metadata(self) -> dict[str, str]:
        """Build metadata section with version information."""
        if self.metadata_collector is None:
            return {}
        return self.metadata_collector.collect_version_info()
```

**Wiring at Composition Root** (in MCP tool layer):
```python
from ...observability import SubprocessMetadataCollector

# Create metadata collector
metadata_collector = SubprocessMetadataCollector()

# Wire into handler
handler = SearchAutomatedProofHandler(
    candidate_gen=candidate_gen,
    feedback_builder=feedback_builder,
    validator=validator,
    metadata_collector=metadata_collector,  # Inject here
)
```

This ensures:
- Consistent metadata across all tools
- Testability (easy to mock MetadataCollector)
- Graceful degradation (works without metadata collector)
- Reusability (same implementation for all tools)

## Components and Interfaces

### Observability Module (Existing)

The system uses the existing observability module for metadata collection. This module follows hexagonal architecture principles and is already used by probe, probe_file, verify, and search_annotations tools.

#### MetadataCollector Port

**Purpose**: Abstract interface for collecting environment metadata.

**Interface** (from `src/lean_proof_auto_mcp/observability/ports.py`):
```python
from typing import Protocol

class MetadataCollector(Protocol):
    """Port for collecting environment metadata."""
    
    def collect_version_info(self) -> dict[str, str]:
        """
        Collect version metadata from the environment.
        
        Returns:
            Dictionary with optional keys:
            - repo_commit: Git commit hash (if in a git repository)
            - lean_version: Lean version string (if lean is available)
            - lake_version: Lake version string (if lake is available)
        
        Note:
            This method never raises exceptions. If a tool is not
            available or a command fails, the corresponding key is
            simply omitted from the returned dictionary.
        """
        ...
```

#### SubprocessMetadataCollector Adapter

**Purpose**: Collect metadata using subprocess commands with threading to avoid Windows pipe deadlock.

**Implementation** (from `src/lean_proof_auto_mcp/observability/metadata_collector.py`):
- Runs `git rev-parse HEAD`, `lean --version`, `lake --version`
- Uses threading to read subprocess output asynchronously
- 1-second timeout per command
- Thread-safe implementation
- Never raises exceptions - missing tools result in missing keys

**Key Features**:
- **Windows Compatibility**: Uses threading to avoid pipe buffer deadlock when MCP server runs as subprocess
- **Graceful Degradation**: Missing tools (git, lean, lake) result in missing keys, not errors
- **Performance**: 1-second timeout per command ensures fast execution
- **Reliability**: Thread-safe, handles all error conditions

**Usage Pattern**:
All new handlers SHALL follow the existing pattern:
1. Accept `MetadataCollector | None` as optional constructor parameter
2. Store as instance variable
3. Call `collect_version_info()` in `_build_metadata()` method
4. Return empty dict if collector is None
5. Include metadata in result structure

**Wiring**:
All MCP tools SHALL create `SubprocessMetadataCollector()` at composition root and inject into handlers.

### LeanInteract Adapter Layer

#### LeanInteractQuerier

**Purpose**: Extract declarations and references from Lean files using LeanInteract.

**Interface**:
```python
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class Declaration:
    name: str
    full_name: str
    type: str
    value: DeclValue | None
    attributes: list[str]
    range: Range
    namespace: str

@dataclass(frozen=True)
class DeclValue:
    pp: str  # Pretty-printed proof text
    constants: list[str]  # Constants/lemmas used
    range: Range

class LeanInteractQuerier(Protocol):
    def extract_declarations(self, file_path: str) -> list[Declaration]:
        """Extract all declarations from a file using FileCommand(declarations=True)."""
        ...
    
    def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
        """Extract lemma references from a proof using value.constants + text parsing."""
        ...
    
    def get_theorem_context(self, file_path: str, theorem_id: str) -> TheoremContext:
        """Get full context for a theorem including scope and hypotheses."""
        ...
```

**Implementation Strategy**:
- Use `FileCommand(declarations=True)` for declaration extraction
- Primary: Use `declaration.value.constants` for proof references
- Fallback: Parse `declaration.value.pp` text for additional references
- Validate all references against `response.declarations`

#### ProofStateInspector

**Purpose**: Inspect proof states and apply tactics using LeanInteract.

**Interface**:
```python
@dataclass(frozen=True)
class ProofState:
    goal: str
    hypotheses: list[str]
    type_context: str
    goals_remaining: int

@dataclass(frozen=True)
class TacticResult:
    success: bool
    new_proof_state: ProofState | None
    error_message: str | None

class ProofStateInspector(Protocol):
    def get_initial_proof_state(self, theorem: Declaration) -> ProofState:
        """Get initial proof state using Command with sorry."""
        ...
    
    def apply_tactic(self, proof_state_id: int, tactic: str) -> TacticResult:
        """Apply a tactic using ProofStep."""
        ...
```

**Implementation Strategy**:
- Use `Command` with `sorry` to get initial proof state
- Use `ProofStep(tactic=..., proof_state=...)` for tactic application
- Parse proof state from response to extract goals and hypotheses

#### ProofValidator

**Purpose**: Validate proof attempts using LeanInteract.

**Interface**:
```python
@dataclass(frozen=True)
class ValidationResult:
    status: str  # "success" | "error" | "incomplete" | "timeout"
    error_message: str | None
    error_location: tuple[int, int] | None  # (line, column)
    proof_state: ProofState | None
    suggestions: list[str]

class ProofValidator(Protocol):
    def validate_proof(
        self, 
        theorem_statement: str, 
        proof_attempt: str,
        timeout_s: float = 10.0
    ) -> ValidationResult:
        """Validate a proof attempt using Command."""
        ...
```

**Implementation Strategy**:
- Use `Command` to validate proof
- Parse error messages for location and suggestions
- Extract proof state if incomplete
- Return structured result with actionable feedback

#### ServerManager

**Purpose**: Manage LeanInteract server lifecycle.

**Interface**:
```python
class ServerManager(Protocol):
    def get_server(self, file_path: str) -> LeanInteractServer:
        """Get or create server instance for file."""
        ...
    
    def restart_server(self, file_path: str) -> None:
        """Restart crashed server."""
        ...
    
    def shutdown_all(self) -> None:
        """Shutdown all server instances."""
        ...
```

**Implementation Strategy**:
- Maintain one server instance per file to avoid startup overhead
- Detect crashes and restart automatically
- Use lean-interact-runner as execution wrapper
- Log all interactions for debugging

### Core Domain Layer

#### CandidateGenerator (Refactored)

**Purpose**: Generate hint candidates from multiple sources using LeanInteract.

**Interface**:
```python
@dataclass(frozen=True)
class Candidate:
    name: str
    hint_type: str  # "add_safe" | "add_simp" | "add_unfold" | "add_unsafe"
    source: str  # "goal_symbols" | "local_context" | "same_namespace" | "original_proof_refs"
    rank: float

class CandidateGenerator:
    def __init__(self, querier: LeanInteractQuerier):
        self.querier = querier
    
    def generate_candidates(
        self,
        file_path: str,
        theorem_id: str,
        sources: list[str],
        max_per_source: int
    ) -> list[Candidate]:
        """Generate candidates from specified sources."""
        ...
```

**Implementation Strategy**:
- **goal_symbols**: Extract from theorem type using LeanInteract + parsing
- **local_context**: Extract from proof state hypotheses using LeanInteract
- **same_namespace**: Extract from file declarations using LeanInteract
- **original_proof_refs**: Extract from proof value.constants using LeanInteract
- Infer hint types from declaration attributes (not names)
- Rank candidates by relevance

#### ContextExtractor (New)

**Purpose**: Extract rich context for LLM reasoning.

**Interface**:
```python
@dataclass(frozen=True)
class ProofContext:
    theorem_statement: str
    original_proof: str
    hypotheses: list[str]
    in_scope: list[str]
    namespace: str
    similar_proofs: list[SimilarProof]

@dataclass(frozen=True)
class SimilarProof:
    theorem_id: str
    similarity: float
    theorem_statement: str
    proof: str
    hints_used: list[str]

class ContextExtractor:
    def __init__(self, querier: LeanInteractQuerier):
        self.querier = querier
    
    def extract_context(
        self,
        file_path: str,
        theorem_id: str,
        include_similar: bool = False
    ) -> ProofContext:
        """Extract full context for a theorem."""
        ...
```

**Implementation Strategy**:
- Extract theorem statement and proof from declarations
- Extract hypotheses from initial proof state
- Extract in-scope declarations from file
- Find similar proofs by comparing type signatures
- Cache context for performance

#### FeedbackBuilder (New)

**Purpose**: Build structured feedback from search results.

**Interface**:
```python
@dataclass(frozen=True)
class SearchFeedback:
    status: str  # "success" | "partial" | "fail"
    hints_found: list[Candidate]
    partial_progress: PartialProgress | None
    current_goal: str | None
    suggestions: list[Suggestion]

@dataclass(frozen=True)
class PartialProgress:
    hints_that_helped: list[tuple[str, str]]  # (hint, impact)
    goal_complexity_reduction: float
    progress_score: float

@dataclass(frozen=True)
class Suggestion:
    type: str  # "tactic" | "hint" | "strategy"
    suggestion: str
    confidence: float
    reasoning: str

class FeedbackBuilder:
    def build_search_feedback(
        self,
        search_result: SearchResult,
        proof_state: ProofState | None
    ) -> SearchFeedback:
        """Build structured feedback from search results."""
        ...
```

**Implementation Strategy**:
- Track which hints reduced goal complexity
- Calculate progress score based on goal reduction
- Generate tactical suggestions based on proof structure
- Provide confidence scores for suggestions
- Include reasoning for each suggestion

#### SearchOrchestrator (Enhanced)

**Purpose**: Orchestrate search strategies with configurable parameters.

**Interface**:
```python
@dataclass(frozen=True)
class SearchConfig:
    search_depth: str
    search_budget_s: float
    max_candidates: int
    candidate_sources: list[str]
    automation_mode: str
    search_strategy: str
    return_proof_states: bool
    return_partial_progress: bool

class SearchOrchestrator:
    def __init__(
        self,
        candidate_gen: CandidateGenerator,
        feedback_builder: FeedbackBuilder,
        validator: ProofValidator,
        metadata_collector: MetadataCollector | None = None,  # Optional
    ):
        self.candidate_gen = candidate_gen
        self.feedback_builder = feedback_builder
        self.validator = validator
        self.metadata_collector = metadata_collector
    
    def search(
        self,
        file_path: str,
        theorem_id: str,
        config: SearchConfig
    ) -> SearchResult:
        """Execute search with given configuration."""
        ...
    
    def _build_metadata(self) -> dict[str, str]:
        """Build metadata section with version information."""
        if self.metadata_collector is None:
            return {}
        return self.metadata_collector.collect_version_info()
```

**Implementation Strategy**:
- Generate candidates from configured sources
- Execute search strategy (greedy, beam, exhaustive)
- Track partial progress during search
- Build rich feedback for LLM
- Support configurable timeouts and budgets
- Collect metadata using MetadataCollector port

### MCP Tool Layer

#### search_automated_proof Tool

**Purpose**: Enhanced search tool with LLM-controlled parameters.

**Signature**:
```python
@mcp_tool
def search_automated_proof(
    file: str,
    theorem_id: str,
    search_depth: str = "normal",
    search_budget_s: float = 30.0,
    max_candidates: int = 50,
    candidate_sources: list[str] = [
        "goal_symbols",
        "local_context", 
        "same_namespace",
        "original_proof_refs"
    ],
    automation_mode: str = "aesop",
    return_proof_states: bool = True,
    return_partial_progress: bool = True,
    # ... additional parameters
) -> dict:
    """Search for automated proof with rich feedback."""
    ...
```

**Implementation**:
- Validate parameters
- Build SearchConfig from parameters
- Delegate to SearchOrchestrator
- Format response with rich feedback
- Note: search_annotations is removed and returns an error

#### try_automated_proof Tool

**Purpose**: Fast validation of LLM-generated proof attempts.

**Signature**:
```python
@mcp_tool
def try_automated_proof(
    file: str,
    theorem_id: str,
    proof_attempt: str,
    timeout_s: float = 10.0,
    return_proof_state: bool = True
) -> dict:
    """Validate a proof attempt with detailed feedback."""
    ...
```

**Implementation**:
- Validate parameters
- Delegate to ProofValidator
- Format ValidationResult as JSON
- Include tactical suggestions
- Return within timeout

#### get_proof_context Tool

**Purpose**: Extract rich context for LLM reasoning.

**Signature**:
```python
@mcp_tool
def get_proof_context(
    file: str,
    theorem_id: str,
    include_similar_proofs: bool = True
) -> dict:
    """Get rich context about a theorem."""
    ...
```

**Implementation**:
- Validate parameters
- Delegate to ContextExtractor
- Format ProofContext as JSON
- Include similar proofs if requested
- Cache results for performance

## Data Models

### Declaration Model

```python
@dataclass(frozen=True)
class Declaration:
    """A Lean declaration (theorem, lemma, definition)."""
    name: str  # Short name
    full_name: str  # Fully qualified name
    type: str  # Type signature
    value: DeclValue | None  # Proof/definition body
    attributes: list[str]  # [simp], [instance], etc.
    range: Range  # Position in file
    namespace: str  # Current namespace
    
    @property
    def is_theorem(self) -> bool:
        return "theorem" in self.type or "lemma" in self.type
    
    @property
    def has_simp_attribute(self) -> bool:
        return "simp" in self.attributes
```

### DeclValue Model

```python
@dataclass(frozen=True)
class DeclValue:
    """The value (proof/definition body) of a declaration."""
    pp: str  # Pretty-printed text
    constants: list[str]  # Constants/lemmas referenced
    range: Range  # Position in file
    
    def get_all_references(self) -> list[str]:
        """Get all references (constants + parsed from pp)."""
        # Primary: use constants list
        refs = set(self.constants)
        # Fallback: parse pp text
        refs.update(self._parse_references_from_text())
        return list(refs)
```

### ProofState Model

```python
@dataclass(frozen=True)
class ProofState:
    """The state of a proof at a given point."""
    goal: str  # Current goal
    hypotheses: list[str]  # Available hypotheses
    type_context: str  # Type context
    goals_remaining: int  # Number of goals left
    
    def complexity_score(self) -> float:
        """Estimate goal complexity (higher = more complex)."""
        # Based on goal length, nesting depth, etc.
        return len(self.goal) + self.goal.count("∀") * 10
```

### Candidate Model

```python
@dataclass(frozen=True)
class Candidate:
    """A hint candidate for automation."""
    name: str  # Fully qualified name
    hint_type: str  # "add_safe" | "add_simp" | "add_unfold" | "add_unsafe"
    source: str  # Where it came from
    rank: float  # Relevance score (higher = more relevant)
    declaration: Declaration | None  # Full declaration if available
    
    def to_hint_annotation(self) -> str:
        """Convert to Lean hint annotation."""
        return f"{self.hint_type} {self.name}"
```

### SearchResult Model

```python
@dataclass(frozen=True)
class SearchResult:
    """Result of a search operation."""
    outcome: str  # "closed" | "partial" | "not_closed"
    best_hint_set: list[Candidate] | None
    attempts: int  # Number of combinations tried
    time_s: float  # Time taken
    proof_states: tuple[ProofState, ProofState] | None  # (initial, after_hints)
    partial_progress: PartialProgress | None
    search_trace: list[SearchStep] | None
    metadata: dict[str, str]  # Version info from MetadataCollector
```

### ValidationResult Model

```python
@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a proof attempt."""
    status: str  # "success" | "error" | "incomplete" | "timeout"
    error_message: str | None
    error_location: tuple[int, int] | None  # (line, column)
    proof_state: ProofState | None  # If incomplete
    suggestions: list[Suggestion]
    time_s: float
    metadata: dict[str, str]  # Version info from MetadataCollector
```

### TheoremContext Model

```python
@dataclass(frozen=True)
class TheoremContext:
    """Rich context about a theorem."""
    theorem_statement: str
    original_proof: str
    hypotheses: list[str]
    in_scope: list[str]  # Declarations in scope
    namespace: str
    similar_proofs: list[SimilarProof]
    metadata: dict[str, str]  # Version info from MetadataCollector
```

### Configuration Models

```python
@dataclass(frozen=True)
class SearchConfig:
    """Configuration for search operation."""
    search_depth: str  # "quick" | "normal" | "deep" | "exhaustive"
    search_budget_s: float
    max_candidates: int
    candidate_sources: list[str]
    max_candidates_per_source: int
    automation_mode: str  # "aesop" | "simp" | "omega" | "grind"
    automation_secondary: str | None
    search_strategy: str  # "greedy" | "beam" | "exhaustive"
    beam_width: int
    max_search_steps: int
    max_hints_in_set: int
    allow_simp_hints: bool
    allow_unfold_hints: bool
    allow_unsafe_hints: bool
    minimize_hints: bool
    minimize_budget_s: float
    return_proof_states: bool
    return_partial_progress: bool
    return_context: bool
    return_similar_proofs: bool
    return_search_trace: bool
    
    @staticmethod
    def from_depth(depth: str) -> "SearchConfig":
        """Create config from depth preset."""
        presets = {
            "quick": (10.0, 20, 50, 5.0),
            "normal": (30.0, 50, 100, 30.0),
            "deep": (60.0, 100, 200, 60.0),
            "exhaustive": (120.0, 200, 500, 120.0)
        }
        budget, candidates, steps, min_budget = presets[depth]
        return SearchConfig(
            search_depth=depth,
            search_budget_s=budget,
            max_candidates=candidates,
            max_search_steps=steps,
            minimize_budget_s=min_budget,
            # ... other defaults
        )
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Complete Declaration Extraction

*For any* Lean file with declarations, extracting declarations using LeanInteract SHALL return all declarations with complete information including fully qualified name, type signature, proof value (if present with both pp text and constants list), attributes, position range, and namespace.

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Accurate Proof Reference Extraction

*For any* declaration with a proof value, extracting proof references SHALL use value.constants as primary source with pp text parsing as fallback, validate all references against the file's declaration list, and return only valid references.

**Validates: Requirements 2.3**

### Property 3: Complete Context Extraction

*For any* theorem identifier in a file, extracting theorem context SHALL return the complete theorem statement from declaration.type, all hypotheses from the initial proof state, all declarations visible in scope, and the current namespace from declaration.scope.curr_namespace.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

### Property 4: Search Depth Configuration Consistency

*For any* search_depth value (quick, normal, deep, exhaustive), the system SHALL apply the corresponding preset parameters (search_budget_s, max_candidates, max_search_steps, minimize_budget_s) consistently, and allow individual parameter overrides to take precedence over presets.

**Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**

### Property 5: Candidate Source Extraction Accuracy

*For any* enabled candidate source (goal_symbols, local_context, same_namespace, original_proof_refs), the system SHALL extract candidates using LeanInteract-based methods and respect the max_candidates_per_source limit for each source.

**Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.7**

### Property 6: Conditional Return Value Completeness

*For any* search result, when a return parameter (return_proof_states, return_partial_progress, return_context, return_similar_proofs, return_search_trace) is true, the system SHALL include the corresponding data in the response, and SHALL always include tactical suggestions with confidence scores and reasoning regardless of parameters.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**

### Property 7: Validation Result Structure Completeness

*For any* proof validation attempt, the system SHALL return a ValidationResult with status (success/error/incomplete/timeout), and SHALL include appropriate additional data based on status: error_message and location for errors, proof_state and remaining goals for incomplete, partial results for timeout, and verification confirmation for success, plus tactical suggestions in all cases.

**Validates: Requirements 7.3, 7.4, 7.5, 7.6, 7.7, 17.1, 17.2, 17.3, 17.4, 17.5**

### Property 8: Proof State Completeness

*For any* proof state extraction or tactic application, the system SHALL return a ProofState containing the current goal, all hypotheses, type context, and number of goals remaining, with all goals and their indices when multiple goals exist.

**Validates: Requirements 16.1, 16.2, 16.3, 16.4**

### Property 9: Similar Proof Discovery Accuracy

*For any* theorem when similar proofs are requested, the system SHALL compute similarity scores based on theorem structure and type signatures, return only proofs with scores ≥ 0.7, include theorem statement, proof body, and hints used for each, and rank them by similarity score in descending order.

**Validates: Requirements 18.1, 18.2, 18.3, 18.4**

### Property 10: Search Strategy Behavior Consistency

*For any* search strategy (greedy, beam, exhaustive), the system SHALL execute the strategy according to its specification: greedy explores in rank order stopping at first success, beam maintains beam_width parallel paths, and exhaustive tries all combinations up to max_search_steps.

**Validates: Requirements 19.2, 19.3, 19.4**

### Property 11: Automation Mode Selection

*For any* automation_mode value (aesop, simp, omega, grind), the system SHALL use the specified automation for proof attempts, and SHALL use automation_secondary as fallback when primary automation fails and secondary is configured.

**Validates: Requirements 20.2, 20.3, 20.4, 20.5, 20.6**

### Property 12: Hint Type Filtering

*For any* hint type parameter (allow_simp_hints, allow_unfold_hints, allow_unsafe_hints), when disabled, the system SHALL exclude candidates of that type from search, and SHALL infer hint types from declaration attributes obtained via LeanInteract.

**Validates: Requirements 21.4, 21.5**

### Property 13: Hint Set Minimization Correctness

*For any* successful search result when minimize_hints is true, the system SHALL attempt to reduce the hint set by removing hints one at a time, validate that the proof still closes after each removal, complete within minimize_budget_s, and preserve proof correctness throughout minimization.

**Validates: Requirements 22.2, 22.3, 22.5**

### Property 14: Metadata Completeness

*For any* search result, the system SHALL return complete metadata including Lean version, Lake version, workspace mode, search_depth, candidate_sources, automation_mode, and timing information for all phases (viability check, baseline probe, candidate generation, search execution, minimization), collected using the MetadataCollector port.

**Validates: Requirements 23.1, 23.2, 23.3, 29.1, 29.3**

### Property 15: Error Handling Without Crashes

*For any* invalid input, timeout condition, or LeanInteract failure, the system SHALL return a descriptive error message or partial results with appropriate status, and SHALL NOT crash or raise unhandled exceptions.

**Validates: Requirements 11.2, 11.3**

### Property 16: Feedback Builder Completeness

*For any* search result with partial progress, the Feedback_Builder SHALL identify which hints helped and their impact, calculate goal complexity reduction as a percentage, generate tactical suggestions with confidence scores between 0.0 and 1.0, and provide reasoning for all suggestions.

**Validates: Requirements 13.2, 13.3, 13.4, 13.5**

### Property 17: Original Proof Preservation

*For any* theorem that cannot be refactored, the system SHALL preserve the original proof unchanged and return a result indicating the refactoring was not successful.

**Validates: Requirements 14.5**

### Property 18: LeanInteract Foundation Consistency

*For all* Lean interactions across all components, the system SHALL route interactions through the LeanInteract Adapter Layer, SHALL NOT use direct Lean CLI calls or regex parsing of Lean output, and SHALL use lean-interact-runner as the execution wrapper.

**Validates: Requirements 28.1, 28.2, 28.3**

### Property 19: Server Instance Reuse

*For any* file being processed, the system SHALL maintain a single LeanInteract server instance for that file across multiple operations, detect server crashes and restart automatically, and log all LeanInteract requests and responses.

**Validates: Requirements 10.6, 28.4, 28.5, 28.6**

### Property 20: Dependency Injection Architecture

*For all* Core Domain Layer components, dependencies SHALL be received through constructor injection, SHALL depend only on abstract interfaces (protocols), and SHALL NOT instantiate their own dependencies or depend on MCP tool interfaces or LeanInteract implementation details.

**Validates: Requirements 9.2, 9.5**

### Property 21: Metadata Collection Consistency

*For all* command handlers (SearchAutomatedProofHandler, TryAutomatedProofHandler, GetProofContextHandler, and existing handlers), when MetadataCollector is provided, the handler SHALL call collect_version_info() and include the result in the response metadata section, and when MetadataCollector is None, the handler SHALL return empty metadata without errors, maintaining consistency with existing tools (probe, probe_file, verify, search_annotations).

**Validates: Requirements 29.2, 29.3, 29.4, 29.7**

## Error Handling

### Error Categories

**1. LeanInteract Errors**:
- Server crashes: Detect and restart automatically
- Timeouts: Return partial results with timeout status
- Communication failures: Retry with exponential backoff
- Invalid responses: Log and return structured error

**2. Validation Errors**:
- Syntax errors: Return error message with location
- Type errors: Return error message with context
- Incomplete proofs: Return proof state with remaining goals
- Timeouts: Return partial validation result

**3. Input Validation Errors**:
- Invalid file paths: Return descriptive error
- Invalid theorem IDs: Return error with suggestions
- Invalid parameters: Return error with valid ranges
- Missing dependencies: Return error with installation instructions

**4. Search Errors**:
- No candidates found: Return empty result with suggestions
- All candidates fail: Return best partial result
- Search timeout: Return best result found so far
- Minimization timeout: Return best minimized set found

### Error Handling Strategy

**Result/Either Pattern**:
All operations that can fail return Result types:
```python
@dataclass(frozen=True)
class Ok:
    value: T

@dataclass(frozen=True)
class Err:
    error: ErrorInfo

Result = Ok | Err
```

**Error Propagation**:
- Adapter Layer: Catch LeanInteract exceptions, convert to Result types
- Core Domain Layer: Propagate Result types, no exceptions
- MCP Tool Layer: Convert Result types to JSON error responses

**Graceful Degradation**:
1. Try primary approach (e.g., value.constants for references)
2. Fall back to secondary approach (e.g., pp text parsing)
3. If both fail, return partial results with error information
4. Never crash, always return structured response

**Logging**:
- Log all LeanInteract interactions (request/response)
- Log all errors with full context
- Log performance metrics (timing, candidates tried)
- Log deprecation warnings

## Testing Strategy

### Dual Testing Approach

The system requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests**:
- Specific examples demonstrating correct behavior
- Edge cases (empty proofs, no references, no similar proofs)
- Error conditions (crashes, timeouts, invalid input)
- Integration points between layers
- Tool registration and parameter validation
- Deprecation warnings and redirects

**Property-Based Tests**:
- Universal properties across all inputs
- Comprehensive input coverage through randomization
- Minimum 100 iterations per property test
- Each test references its design document property

### Property-Based Testing Configuration

**Library Selection**:
- Python: Use `hypothesis` library
- Configure 100+ iterations per test
- Use appropriate strategies for Lean-specific types

**Test Tagging**:
Each property test must include a comment tag:
```python
# Feature: iterative-orchestration-enhancements, Property 1: Complete Declaration Extraction
@given(lean_file=lean_file_strategy())
def test_complete_declaration_extraction(lean_file):
    ...
```

### Test Organization

**Adapter Layer Tests**:
- Mock LeanInteract responses
- Test error handling and retries
- Test server lifecycle management
- Test timeout handling

**Core Domain Layer Tests**:
- Test with mock adapters (no real LeanInteract)
- Test business logic in isolation
- Test candidate generation and ranking
- Test feedback building
- Test search orchestration

**MCP Tool Layer Tests**:
- Test parameter validation
- Test JSON response formatting
- Test deprecation warnings
- Test error response structure

**Integration Tests**:
- Test end-to-end workflows with real LeanInteract
- Test on real mathlib theorems
- Measure success rates by complexity tier
- Validate refactored proofs with Lean

**Benchmark Tests**:
- Test accuracy targets (95%+ for hint extraction)
- Test success rate targets (20-35% overall)
- Test performance targets (search times, iteration cycles)
- Test false positive rate (< 5%)

### Test Coverage Requirements

- Minimum 80% code coverage
- 100% coverage of error handling paths
- All 20 correctness properties have property-based tests
- All edge cases have unit tests
- All tools have integration tests

### Migration Testing

**Regression Tests**:
- All existing tests for probe, probe_file, verify must pass after migration
- All existing search_annotations tests must be updated and pass
- No functionality regressions

**Static Analysis Tests**:
- Verify no regex-based parsing in candidate generation
- Verify no direct Lean CLI calls
- Verify all Lean interaction goes through adapter layer
- Verify dependency injection is used correctly
- Verify no forbidden dependencies (Core → MCP, Core → LeanInteract impl)

**Performance Regression Tests**:
- Verify performance is not worse than before migration
- Verify server reuse reduces startup overhead
- Verify iteration cycles meet timing requirements

## Implementation Notes

### Phase 1: LeanInteract Adapter Layer

**Priority**: P0 (Critical)

**Components**:
1. LeanInteractQuerier implementation
2. ProofStateInspector implementation
3. ProofValidator implementation
4. ServerManager implementation

**Key Decisions**:
- Use `FileCommand(declarations=True)` not `extract_decls=True`
- Primary: value.constants, Fallback: pp text parsing
- One server instance per file
- Automatic crash detection and restart
- Reuse existing SubprocessMetadataCollector from observability module

**Testing**:
- Mock LeanInteract for unit tests
- Integration tests with real LeanInteract
- Test all error conditions

### Phase 2: Core Domain Refactoring

**Priority**: P0 (Critical)

**Components**:
1. Refactor CandidateGenerator to use LeanInteractQuerier
2. Implement ContextExtractor
3. Implement FeedbackBuilder
4. Enhance SearchOrchestrator

**Key Decisions**:
- Remove all regex-based parsing
- Infer hint types from attributes
- Build rich feedback with suggestions
- Support all four candidate sources
- Accept MetadataCollector as optional parameter in all handlers
- Follow existing pattern from probe/verify/search_annotations

**Testing**:
- Unit tests with mock querier
- Property tests for candidate generation
- Test feedback building logic
- Test metadata collection with and without collector

### Phase 3: MCP Tool Enhancement

**Priority**: P0 (Critical)

**Components**:
1. Enhance search_automated_proof (replace search_annotations)
2. Implement try_automated_proof
3. Implement get_proof_context
4. Add deprecation handling

**Key Decisions**:
- Maintain backward compatibility
- Log deprecation warnings
- Support all new parameters
- Return rich feedback
- Wire SubprocessMetadataCollector at composition root for all tools
- Ensure metadata format matches existing tools

**Testing**:
- Test parameter validation
- Test JSON response format
- Test deprecation warnings
- Integration tests
- Test metadata inclusion in all responses

### Phase 4: Existing Tool Migration

**Priority**: P1 (High)

**Components**:
1. Migrate probe to use LeanInteract
2. Migrate probe_file to use LeanInteract
3. Migrate verify to use LeanInteract

**Key Decisions**:
- Maintain existing interfaces
- Route through adapter layer
- Preserve functionality

**Testing**:
- Regression tests
- Verify no functionality loss

### Phase 5: Test Suite Migration

**Priority**: P1 (High)

**Components**:
1. Update search_annotations tests
2. Remove regex-based tests
3. Add LeanInteract-based tests
4. Add property-based tests

**Key Decisions**:
- Mock adapter layer, not LeanInteract directly
- Test all 20 correctness properties
- Maintain 80%+ coverage

**Testing**:
- Meta-tests for coverage
- Static analysis tests

## Dependencies

### External Dependencies

- **LeanInteract**: Python library for Lean 4 interaction (required)
- **lean-interact-runner**: Execution wrapper for LeanInteract (required)
- **Lean 4**: Version 4.26.0-rc1 or later (required)
- **Lake**: Version 5.0.0 or later (required)
- **hypothesis**: Property-based testing library (dev dependency)

### Internal Dependencies

- **Current MCP server infrastructure**: Must integrate with existing MCP server
- **Current workspace configuration**: Must support existing workspace formats
- **Current minimization engine**: Will be reused with new candidate generator

### Dependency Management

- Use dependency injection throughout
- Abstract all external dependencies behind protocols
- Enable testing without real dependencies
- Support graceful degradation when dependencies unavailable

## Performance Considerations

### Optimization Strategies

**1. Server Reuse**:
- Maintain one LeanInteract server per file
- Avoid repeated startup overhead (seconds per file)
- Cache server instances in ServerManager

**2. Parallel Processing**:
- Validate multiple proof attempts in parallel
- Process multiple theorems in parallel for batch operations
- Use asyncio for concurrent LeanInteract operations

**3. Caching**:
- Cache declaration extraction results per file
- Cache theorem context for repeated access
- Cache similar proof computations

**4. Early Termination**:
- Stop search on first success for greedy strategy
- Respect time budgets strictly
- Return partial results on timeout

### Performance Targets

- Quick search: ≤ 15 seconds
- Normal search: ≤ 40 seconds
- Deep search: ≤ 90 seconds
- Validation: ≤ 10 seconds
- Full iteration cycle: ≤ 50 seconds (normal depth)
- Server startup amortized across operations

### Performance Monitoring

- Log timing for all phases
- Track candidate generation time
- Track search execution time
- Track minimization time
- Monitor server startup overhead
- Alert on performance regressions

## Security Considerations

### Input Validation

- Validate all file paths (no path traversal)
- Validate theorem IDs (no injection)
- Validate proof attempts (no arbitrary code execution)
- Sanitize all user input before passing to LeanInteract

### Resource Limits

- Enforce timeouts on all operations
- Limit maximum candidates per source
- Limit maximum search steps
- Limit maximum hint set size
- Prevent resource exhaustion

### Error Information Disclosure

- Don't expose internal paths in errors
- Don't expose system information in errors
- Sanitize error messages for external consumption
- Log full details internally only

## Deployment Considerations

### Backward Compatibility

- Maintain existing tool interfaces
- Provide deprecation warnings for old tools
- Support gradual migration
- Document migration path

### Rollout Strategy

1. Deploy with feature flag (disabled by default)
2. Enable for internal testing
3. Gradual rollout to users
4. Monitor success rates and performance
5. Full deployment after validation

### Monitoring

- Track success rates by complexity tier
- Track iteration counts
- Track performance metrics
- Track error rates
- Alert on anomalies

### Rollback Plan

- Keep old implementation available
- Support instant rollback via feature flag
- Maintain compatibility with old data formats
- Document rollback procedure
