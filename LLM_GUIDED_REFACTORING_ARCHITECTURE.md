# LLM-Guided Proof Refactoring with LeanInteract

**Status**: Proposed Architecture  
**Date**: January 29, 2026  
**Goal**: Refactor 20-30% of mathlib proofs to use automation  

---

## Executive Summary

This document describes a human-AI collaborative system for refactoring Lean 4 proofs. The system combines:

- **LeanInteract REPL**: Accurate proof state inspection and declaration extraction
- **Deterministic Search**: Fast hint discovery through automation
- **LLM Reasoning**: Creative tactical proof generation
- **Iterative Refinement**: Feedback-driven improvement loops

The key insight is that **regex-based parsing is unreliable**. Instead, we use LeanInteract to query Lean's actual environment, getting real declarations, types, and proof states. This enables accurate hint extraction and rich feedback for LLM-guided refactoring.

---

## The Problem

### Current Limitations

**Regex-Based Hint Extraction**:
- ❌ Cannot understand Lean syntax (misses things in comments, strings)
- ❌ Cannot distinguish lemma references from other identifiers
- ❌ No type information (guesses hint types from names)
- ❌ Cannot see what's in scope at proof location
- ❌ Fragile and unreliable

**Result**: `search_annotations` with `original_proof_refs` enabled still fails to extract lemmas from proofs like:
```lean
lemma AddSubgroup.inertia_map_subtype ... := by
  rw [← AddSubgroup.subgroupOf_inertia, Subgroup.subgroupOf_map_subtype]
```

### The Fundamental Gap

**Tactics vs Hints**:
- **Tactics** = Explicit instructions ("rewrite backwards with lemma1, then forwards with lemma2")
- **Hints** = Suggestions ("these lemmas might help, figure it out")

Most mathlib proofs use tactics. Pure automation with hints can only handle structurally simple proofs. We need LLM reasoning to bridge this gap.

---

## The Solution

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                        │
│              (LLM-facing interface)                      │
│                                                          │
│  Tool 1: search_automated_proof                         │
│    - Deterministic hint search                          │
│    - Returns proof states + partial progress            │
│                                                          │
│  Tool 2: try_automated_proof                            │
│    - Validate LLM-generated proofs                      │
│    - Fast feedback (10s timeout)                        │
│                                                          │
│  Tool 3: get_proof_context (new)                        │
│    - Extract theorem context                            │
│    - Find similar proofs for pattern matching           │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│              Core Domain Layer                           │
│         (Business logic, hexagonal)                      │
│                                                          │
│  • CandidateGenerator (refactored)                      │
│    - Uses LeanInteract, not regex                       │
│    - Accurate hint extraction                           │
│                                                          │
│  • ContextExtractor (new)                               │
│    - Rich context for LLM reasoning                     │
│    - Similar proof discovery                            │
│                                                          │
│  • FeedbackBuilder (new)                                │
│    - Structured feedback from proof attempts            │
│    - Tactical suggestions                               │
│                                                          │
│  • ProofValidator (new)                                 │
│    - Validate proof attempts                            │
│    - Extract error messages and suggestions             │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│            LeanInteract Adapter Layer                    │
│       (All Lean interaction via LeanInteract)            │
│                                                          │
│  • LeanInteractQuerier                                  │
│    - extract_declarations(file) → list[Declaration]     │
│    - get_proof_references(file, theorem) → list[str]    │
│    - get_theorem_context(file, theorem) → Context       │
│                                                          │
│  • ProofStateInspector                                  │
│    - get_initial_proof_state(theorem) → ProofState      │
│    - apply_tactic(state, tactic) → TacticResult         │
│                                                          │
│  • ProofValidator                                       │
│    - validate_proof(statement, proof) → ValidationResult│
└──────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. LeanInteract Adapter Layer

**Purpose**: Replace all regex-based parsing with LeanInteract queries

#### LeanInteractQuerier

Uses LeanInteract's `FileCommand(declarations=True)` to get real declarations:

```python
def extract_declarations(self, file_path: str) -> list[Declaration]:
    """
    Extract all declarations from a file.
    
    Returns Declaration objects with:
    - name: Fully qualified name
    - type: Theorem type/statement  
    - value: Proof body (DeclValue with pp text and constants list)
    - attributes: [simp], [instance], etc.
    - range: Position info (start/finish line/column)
    """
```

**Key benefit**: No more regex! Lean parses the file for us.

```python
def get_proof_references(self, file_path: str, theorem_id: str) -> list[str]:
    """
    Extract lemma references from a proof.
    
    Strategy B (Hybrid):
    - Primary: Use decl.value.constants (list of lemmas used)
    - Fallback: Parse decl.value.pp text for additional refs
    - Validation: Check against response.declarations
    
    Returns fully-qualified names referenced in proof.
    """
```

**Key benefit**: Accurate extraction using value.constants + text parsing fallback.

```python
def get_theorem_context(self, file_path: str, theorem_id: str) -> TheoremContext:
    """
    Get full context for a theorem.
    
    Returns:
    - theorem_statement: Full type signature (from decl.type)
    - hypotheses: Available hypotheses (from proof state)
    - in_scope: Declarations visible at this location (from scope info)
    - namespace: Current namespace (from decl.scope.curr_namespace)
    """
```

**Key benefit**: LLM can see what's available, not guess.

**Implementation note**: Combines `FileCommand(declarations=True)` for declarations with `Command` + `sorry` for proof state hypotheses.

#### ProofStateInspector

Uses LeanInteract's tactic mode (`ProofStep`) to inspect proof states:

```python
def get_initial_proof_state(self, theorem: Declaration) -> ProofState:
    """
    Get the initial proof state for a theorem.
    
    Uses: Command to create theorem with sorry, extract proof_state
    Returns: goal, hypotheses, type_context
    """
```

```python
def apply_tactic(self, proof_state_id: int, tactic: str) -> TacticResult:
    """
    Apply a tactic and get resulting proof state.
    
    Uses: ProofStep(tactic=..., proof_state=...)
    Returns: success, new_proof_state, goals_remaining
    """
```

**Key benefit**: Can step through proofs, see intermediate states.

#### ProofValidator

Uses LeanInteract's `Command` to validate proof attempts:

```python
def validate_proof(
    self, 
    theorem_statement: str, 
    proof_attempt: str,
    timeout_s: float = 10.0
) -> ValidationResult:
    """
    Validate a proof attempt.
    
    Returns:
    - status: "success" | "error" | "incomplete" | "timeout"
    - error_message: If failed
    - proof_state: Current state (if incomplete)
    - suggestions: Hints for fixing
    """
```

**Key benefit**: Fast validation with detailed feedback.

---

### 2. Core Domain Layer

**Purpose**: Business logic for proof refactoring, independent of Lean interaction details

#### CandidateGenerator (Refactored)

**Before** (regex-based):
```python
def _extract_from_proof(self, theorem_decl, config):
    proof_text = self.source.get_span_text(theorem_decl.proof_span)
    identifiers = re.findall(r"\b([A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+)\b", proof_text)
    # ❌ Fragile, inaccurate
```

**After** (LeanInteract-based):
```python
def _extract_from_proof(self, file_path, theorem_id, config):
    # Get actual proof references from Lean
    references = self.querier.get_proof_references(file_path, theorem_id)
    
    # For each reference, get actual type information
    for ref in references:
        decls = self.querier.extract_declarations(file_path)
        ref_decl = next(d for d in decls if d.name == ref)
        
        # Infer hint type from actual declaration attributes
        hint_type = self._infer_from_declaration(ref_decl, config)
        # ✅ Accurate, type-aware
```

**Key improvement**: Uses real Lean data, not text parsing.

#### ContextExtractor (New)

Extracts rich context for LLM reasoning:

```python
def extract_context(self, file_path: str, theorem_id: str) -> ProofContext:
    """
    Returns:
    - theorem_statement: Full type
    - original_proof: Original proof body
    - hypotheses: Available hypotheses
    - in_scope: Declarations in scope
    - similar_proofs: Similar theorems for pattern matching
    - namespace: Current namespace
    """
```

**Key benefit**: LLM can pattern-match against similar proofs.

#### FeedbackBuilder (New)

Builds structured feedback for LLM:

```python
def build_search_feedback(self, search_result, proof_state) -> SearchFeedback:
    """
    Returns:
    - status: success/partial/fail
    - hints_found: List of hints
    - partial_progress: What worked partially
    - current_goal: Current proof state
    - suggestions: Tactical suggestions for LLM
    """
```

**Key benefit**: LLM gets actionable feedback, not just success/fail.

---

### 3. MCP Tool Layer

**Purpose**: LLM-facing interface for proof refactoring

#### Tool 1: search_automated_proof

**What changed**:
- Now uses LeanInteract for hint extraction (not regex)
- Returns proof states and partial progress
- Provides tactical suggestions
- LLM controls search parameters dynamically

##### Complete Parameter Comparison

##### OLD VERSION Parameters

```python
@tool
def search_annotations(
    file: str,                    # Required: File path
    theorem_id: str,              # Required: Theorem identifier
    
    # Fixed automation config
    mode: str = "local_only",     # Fixed: "local_only" or "suggest_global"
    automation: dict = {          # Fixed automation settings
        "primary": "aesop",
        "secondary": None
    },
    
    # Fixed budgets
    budgets: dict = {
        "viability_check_s": 5.0,
        "baseline_probe_s": 10.0,
        "search_total_s": 300.0,
        "candidate_trial_s": 5.0,
        "minimize_total_s": 60.0,
        "final_verify_s": 10.0
    },
    
    # Fixed search config
    search: dict = {
        "strategy": "greedy",
        "beam_width": 3,
        "max_steps": 100,
        "max_hints": 10,
        "stop_on_first_close": True
    },
    
    # Fixed candidate sources (NO original_proof_refs by default!)
    candidates: dict = {
        "sources": ["goal_symbols", "local_context", "same_namespace"],
        "max_candidates_per_source": 20,
        "allow_simp_hints": True,
        "allow_unfold_hints": True
    }
)
```

**Problems with OLD version**:
- ❌ `original_proof_refs` NOT enabled by default
- ❌ Fixed budgets (can't adjust for simple vs complex theorems)
- ❌ No control over search depth
- ❌ Returns minimal feedback (just success/fail)
- ❌ Uses regex for hint extraction

---

##### ENHANCED VERSION Parameters

```python
@tool
def search_automated_proof(
    # Required parameters (unchanged)
    file: str,                    # Required: File path
    theorem_id: str,              # Required: Theorem identifier
    
    # LLM-controlled search parameters (NEW!)
    search_budget_s: float = 30.0,              # LLM decides: quick (10s) vs deep (60s)
    max_candidates: int = 50,                   # LLM decides: focused (20) vs exhaustive (100)
    search_depth: str = "normal",               # NEW: "quick" | "normal" | "deep" | "exhaustive"
    
    # LLM-controlled candidate sources (ENHANCED!)
    candidate_sources: list[str] = [
        "goal_symbols",           # Extract from goal statement (via lean interact)
        "local_context",          # Extract from hypotheses (via lean interact)
        "same_namespace",         # Extract from same namespace (via lean interact)
        "original_proof_refs"     # NEW: Extract from original proof (LeanInteract!)
    ],
    max_candidates_per_source: int = 20,        # LLM can adjust per-source limit
    
    # LLM-controlled hint types (ENHANCED!)
    allow_simp_hints: bool = True,              # Include simp lemmas
    allow_unfold_hints: bool = True,            # Include definitions to unfold
    allow_unsafe_hints: bool = True,           # NEW: Allow unsafe aesop rules
    
    # LLM-controlled automation (ENHANCED!)
    automation_mode: str = "aesop",             # "aesop" | "simp" | "omega" | "grind"
    automation_secondary: str | None = None,    # Try secondary automation if primary fails
    
    # LLM-controlled search strategy (ENHANCED!)
    search_strategy: str = "greedy",            # "greedy" | "beam" | "exhaustive"
    beam_width: int = 3,                        # For beam search
    max_search_steps: int = 100,                # Max hint combinations to try
    max_hints_in_set: int = 10,                 # Max hints in final set
    stop_on_first_close: bool = True,           # Stop when first solution found
    
    # NEW: Rich feedback control
    return_proof_states: bool = True,           # Return proof states for LLM analysis
    return_partial_progress: bool = True,       # Return what hints helped partially
    return_context: bool = False,               # Include full theorem context
    return_similar_proofs: bool = False,        # Include similar proofs for pattern matching
    return_search_trace: bool = False,          # Include detailed search trace
    
    # NEW: Minimization control
    minimize_hints: bool = True,                # Try to minimize hint set
    minimize_budget_s: float = 30.0,            # Time budget for minimization
    
    # Advanced: Workspace configuration (unchanged)
    workspace: dict | None = None
) -> dict:
    """
    Enhanced search for proof hints using LeanInteract.
    
    LLM can dynamically control:
    - Search depth and budget
    - Candidate sources (including original_proof_refs!)
    - Hint types and automation mode
    - Feedback detail level
    """
```

**Improvements in ENHANCED version**:
- ✅ `original_proof_refs` available and uses LeanInteract
- ✅ LLM controls search depth dynamically
- ✅ Rich feedback options (proof states, partial progress)
- ✅ Flexible automation modes
- ✅ Search strategy control

---

##### Candidate Source Data Origins

Each candidate source gets its data from different mechanisms. Understanding this is crucial for the architecture:

###### 1. `goal_symbols` - **Hybrid: LeanInteract + Static Analysis**

**Data Source**: 
- **Primary**: LeanInteract's `extract_declarations()` gets the theorem declaration with full type information
- **Secondary**: Static parsing of the type signature to extract identifiers

**How it works**:
```python
# Step 1: Get theorem from LeanInteract
decls = lean_querier.extract_declarations(file_path)
theorem = next(d for d in decls if d.name == theorem_id)

# Step 2: Parse theorem.type (the goal statement)
# theorem.type = "∀ (I : AddSubgroup M) (H : Subgroup G), (I.inertia H).map H.subtype = I.inertia G ⊓ H"

# Step 3: Extract type names (static analysis)
type_names = extract_type_names(theorem.type)
# → ["AddSubgroup", "Subgroup", "inertia", "map", "subtype"]

# Step 4: Query LeanInteract for each name to verify it exists
for name in type_names:
    if lean_querier.declaration_exists(name):
        candidates.append(name)
```

**Why hybrid**:
- LeanInteract gives us the accurate type signature
- Static parsing extracts identifiers from the type
- LeanInteract validates that identifiers are real declarations

**OLD version**: Pure regex on source text (unreliable)
**ENHANCED version**: LeanInteract + smart parsing (accurate)

---

###### 2. `local_context` - **Pure LeanInteract**

**Data Source**: 
- **LeanInteract's `ProofStateInspector.get_initial_proof_state()`**

**How it works**:
```python
# Step 1: Get initial proof state from LeanInteract
proof_state = proof_state_inspector.get_initial_proof_state(theorem)

# Step 2: Extract hypotheses from proof state
# proof_state.hypotheses = [
#   "I : AddSubgroup M",
#   "H : Subgroup G",
#   "h1 : I.inertia H ⊆ G"
# ]

# Step 3: Extract declaration names from hypotheses
for hyp in proof_state.hypotheses:
    # Parse "h1 : I.inertia H ⊆ G" → extract "inertia", "⊆"
    names = extract_names_from_hypothesis(hyp)
    candidates.extend(names)
```

**Why pure LeanInteract**:
- Proof state is runtime information (not in source text)
- Only Lean knows what hypotheses are available
- Cannot be extracted statically

**OLD version**: Tried to parse proof text with regex (failed)
**ENHANCED version**: Uses LeanInteract proof states (accurate)

---

###### 3. `same_namespace` - **Pure LeanInteract**

**Data Source**: 
- **LeanInteract's `extract_declarations()` for entire file**

**How it works**:
```python
# Step 1: Get all declarations from file via LeanInteract
all_decls = lean_querier.extract_declarations(file_path)

# Step 2: Filter to same namespace
theorem_namespace = get_namespace(theorem_id)  # "AddSubgroup"

same_namespace_decls = [
    d for d in all_decls 
    if d.name.startswith(theorem_namespace + ".")
]

# Step 3: Rank by relevance
for decl in same_namespace_decls:
    if is_relevant_to_theorem(decl, theorem):
        candidates.append(decl.name)
```

**Why pure LeanInteract**:
- Need accurate list of all declarations in file
- Need to know their namespaces
- Need their types to determine relevance

**OLD version**: File indexer with regex (missed declarations)
**ENHANCED version**: LeanInteract gives complete, accurate list

---

###### 4. `original_proof_refs` - **Pure LeanInteract** ⭐ **KEY IMPROVEMENT**

**Data Source**: 
- **LeanInteract's `extract_declarations()` with proof value**

**How it works**:
```python
# Step 1: Get theorem declaration with proof from LeanInteract
decls = lean_querier.extract_declarations(file_path)
theorem = next(d for d in decls if d.name == theorem_id)

# Step 2: Extract references from proof value (Strategy B: Hybrid)
# theorem.value is a DeclValue object with:
# - pp: Pretty-printed text like "by rw [← AddSubgroup.subgroupOf_inertia, ...]"
# - constants: List of constants used ["AddSubgroup.subgroupOf_inertia", "Subgroup.subgroupOf_map_subtype"]
# - range: Position info

# Primary: Use constants list directly
references = theorem.value.constants
# → ["AddSubgroup.subgroupOf_inertia", "Subgroup.subgroupOf_map_subtype"]

# Fallback: Parse pp text for additional references
proof_text = theorem.value.pp
additional_refs = extract_identifiers_from_text(proof_text)

# Combine and validate
all_refs = list(set(references + additional_refs))

# Step 3: For each reference, get its declaration info
for ref in all_refs:
    ref_decl = next(d for d in decls if d.full_name == ref)
    # Now we know: is it a lemma? does it have [simp]? etc.
    candidates.append(create_candidate(ref_decl))
```

**Why pure LeanInteract**:
- Proof value includes constants list (most reliable)
- Proof text available for fallback parsing
- Only Lean knows what's actually referenced
- Can validate all references against declarations

**OLD version**: Regex on proof text (completely unreliable)
```python
# OLD: Tried to extract with regex
proof_text = "by rw [← AddSubgroup.subgroupOf_inertia, Subgroup.subgroupOf_map_subtype]"
identifiers = re.findall(r"\b([A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)+)\b", proof_text)
# ❌ Misses things in comments, strings
# ❌ Matches non-lemmas
# ❌ No type information
```

**ENHANCED version**: LeanInteract value.constants + text parsing (accurate)
```python
# ENHANCED: LeanInteract gives proof value with constants
proof_value = theorem.value  # DeclValue from Lean
references = proof_value.constants  # Primary source
additional = parse_identifiers(proof_value.pp)  # Fallback
# ✅ Accurate parsing
# ✅ Only actual references
# ✅ Full type information
```

**This is the CRITICAL improvement** - why the refactor is necessary!

---

###### Summary Table: Data Source Origins

| Candidate Source | Data Origin | LeanInteract? | Static Analysis? | Why This Approach |
|------------------|-------------|---------------|------------------|-------------------|
| `goal_symbols` | Theorem type signature | ✅ Primary | ✅ Secondary | LeanInteract gets type, static parsing extracts names |
| `local_context` | Proof state hypotheses | ✅ Only | ❌ No | Runtime info, only Lean knows |
| `same_namespace` | File declarations | ✅ Only | ❌ No | Need complete, accurate list |
| `original_proof_refs` | Proof value (constants + text) | ✅ Only | ❌ No | **CRITICAL**: value.constants + value.pp parsing |

**Note**: `nearby_decls` was removed as it provides weak signal and adds noise for the refactoring use case.

---

##### Key Architectural Insight

**The refactor is necessary because**:

1. **`original_proof_refs` is the most valuable source** (has the actual lemmas used)
2. **Regex cannot extract from proofs reliably** (syntax is too complex)
3. **LeanInteract gives us proof value with constants list** (accurate extraction via value.constants)
4. **Other sources benefit from LeanInteract too** (more accurate, more context)

**Before refactor**:
```
original_proof_refs (regex) → ❌ Finds 0-1 lemmas (unreliable)
goal_symbols (regex) → ⚠️ Finds 2-3 symbols (partial)
local_context (regex) → ❌ Cannot extract (no proof state)
same_namespace (file indexer) → ⚠️ Finds 10-15 decls (incomplete)
```

**After refactor**:
```
original_proof_refs (LeanInteract) → ✅ Finds 2-5 lemmas (accurate!)
goal_symbols (LeanInteract + parsing) → ✅ Finds 3-5 symbols (accurate)
local_context (LeanInteract) → ✅ Finds 5-10 hypotheses (accurate)
same_namespace (LeanInteract) → ✅ Finds 20-30 decls (complete)
```

**Result**: 10x more candidates, 100% accuracy, enables 20-30% refactoring success rate.

---

The `search_depth` parameter provides convenient presets:

```python
# Quick search (10-15s total)
search_depth="quick"
→ search_budget_s=10.0
→ max_candidates=20
→ max_search_steps=50
→ minimize_budget_s=5.0

# Normal search (30-40s total)
search_depth="normal"  # DEFAULT
→ search_budget_s=30.0
→ max_candidates=50
→ max_search_steps=100
→ minimize_budget_s=30.0

# Deep search (60-90s total)
search_depth="deep"
→ search_budget_s=60.0
→ max_candidates=100
→ max_search_steps=200
→ minimize_budget_s=60.0

# Exhaustive search (120-180s total)
search_depth="exhaustive"
→ search_budget_s=120.0
→ max_candidates=200
→ max_search_steps=500
→ minimize_budget_s=120.0
```

---

##### LLM Tool Call Variations

###### Recommended: MVP Strategy (Start Here!)

```python
# LLM reasoning: "Start with the most valuable sources"
search_automated_proof(
    file="Algebra/Group/Subgroup/Basic.lean",
    theorem_id="Subgroup.mem_closure_iff",
    search_depth="normal",
    candidate_sources=[
        "original_proof_refs",               # PRIMARY: Original proof has the answer!
        "goal_symbols"                       # SECONDARY: Type classes from goal
    ],
    max_candidates_per_source=20,            # Focused search
    search_budget_s=10.0,                    # Fast
    return_proof_states=True,
    return_partial_progress=True
)
```

**Use case**: **Start here for 80% of theorems!** These 2 sources cover most cases.

**Why this works**:
- `original_proof_refs` gives you the lemmas that were actually used
- `goal_symbols` catches type classes needed for automation
- Fast search (10s budget)
- Covers 70-80% of refactoring cases

---

###### Variation 1: Quick Exploration (Simple Theorems)

```python
# LLM reasoning: "This looks like a simple reflexivity proof"
search_automated_proof(
    file="Data/List/Basic.lean",
    theorem_id="List.append_nil",
    search_depth="quick",                    # Fast search
    candidate_sources=["goal_symbols"],      # Just check goal
    return_proof_states=False,               # Don't need details
    return_partial_progress=False
)
```

**Use case**: Trivial theorems, quick check if automation works

---

###### Variation 2: Standard Search (Most Theorems)

```python
# LLM reasoning: "Standard theorem, try normal search"
search_automated_proof(
    file="Algebra/Group/Subgroup/Basic.lean",
    theorem_id="Subgroup.mem_closure_iff",
    search_depth="normal",                   # Default depth
    candidate_sources=[
        "original_proof_refs",               # Start with original proof
        "goal_symbols",                      # Add goal symbols
        "local_context"                      # Add hypotheses if needed
    ],
    return_proof_states=True,                # Need to see progress
    return_partial_progress=True             # Want to know what helped
)
```

**Use case**: When MVP (2 sources) didn't close the proof, add `local_context`

---

###### Variation 3: Deep Search (Complex Theorems)

```python
# LLM reasoning: "Complex proof, need thorough search with all sources"
search_automated_proof(
    file="Algebra/Group/Subgroup/Basic.lean",
    theorem_id="AddSubgroup.inertia_map_subtype",
    search_depth="deep",                     # Thorough search
    search_budget_s=60.0,                    # More time
    candidate_sources=[
        "original_proof_refs",               # Original proof
        "goal_symbols",                      # Goal symbols
        "local_context",                     # Hypotheses
        "same_namespace"                     # All 4 sources!
    ],
    max_candidates_per_source=50,            # More candidates
    allow_unsafe_hints=True,                 # Try unsafe rules too
    automation_secondary="simp",             # Try simp if aesop fails
    return_proof_states=True,
    return_partial_progress=True,
    return_search_trace=True                 # Want detailed trace
)
```

**Use case**: When 2-3 sources didn't work, use all 4 sources for complex theorems

---

###### Variation 4: Context-Rich Search (Pattern Matching)

```python
# LLM reasoning: "Want to see similar proofs for pattern matching"
search_automated_proof(
    file="Data/List/Basic.lean",
    theorem_id="List.length_map",
    search_depth="normal",
    candidate_sources=[
        "goal_symbols",
        "local_context",
        "same_namespace",
        "original_proof_refs"
    ],
    return_proof_states=True,
    return_partial_progress=True,
    return_context=True,                     # Include full context
    return_similar_proofs=True               # Show similar proofs!
)
```

**Use case**: LLM wants to learn from similar proofs

---

###### Variation 5: Simp-Focused Search

```python
# LLM reasoning: "This looks like a simp lemma chain"
search_automated_proof(
    file="Data/List/Basic.lean",
    theorem_id="List.map_append",
    search_depth="normal",
    automation_mode="simp",                  # Use simp instead of aesop
    candidate_sources=[
        "goal_symbols",
        "same_namespace",
        "original_proof_refs"
    ],
    allow_simp_hints=True,
    allow_unfold_hints=True,
    max_hints_in_set=15                      # Allow more simp lemmas
)
```

**Use case**: Theorems that look like simp lemma applications

---

###### Variation 6: Focused Search (Original Proof Only)

```python
# LLM reasoning: "Original proof has the answer, focus there"
search_automated_proof(
    file="Algebra/Group/Subgroup/Basic.lean",
    theorem_id="Subgroup.closure_le",
    search_depth="quick",
    candidate_sources=["original_proof_refs"],  # ONLY original proof
    max_candidates_per_source=10,               # Just top candidates
    search_budget_s=5.0,                        # Very fast
    return_proof_states=True
)
```

**Use case**: When you know the original proof has all the hints needed

---

##### Return Value Comparison

###### OLD VERSION Returns

```json
{
  "api_version": "0.1.0",
  "status": "success" | "fail" | "timeout",
  "run_id": "abc123",
  "file": "path/to/file.lean",
  "theorem_id": "Theorem.name",
  
  // Minimal viability info
  "viability": {
    "status": "success",
    "outcome": "closed" | "not_closed"
  },
  
  // Minimal baseline info
  "baseline": {
    "outcome": "closed" | "not_closed",
    "classification": "trivial" | "promising" | "failed"
  },
  
  // Minimal search result
  "search_result": {
    "outcome": "closed" | "partial" | "not_closed",
    "best_hint_set": {
      "hints": [
        {"name": "Hint1", "type": "add_safe", "source": "goal_symbols"}
      ]
    } | null
  },
  
  // Minimal proof patch
  "proof_patch": {
    "lean_code": "by aesop (add_safe Hint1)"
  } | null,
  
  // Minimal timing
  "timing": {
    "total_s": 35.2
  },
  
  // Artifacts paths
  "artifacts": {
    "request_path": "...",
    "result_path": "...",
    "logs_path": "..."
  }
}
```

**Problems with OLD returns**:
- ❌ No proof states (can't see what's happening)
- ❌ No partial progress (don't know what helped)
- ❌ No suggestions (LLM doesn't know what to try next)
- ❌ Minimal context (can't reason about the proof)

---

###### ENHANCED VERSION Returns

```json
{
  "api_version": "0.2.0",
  "status": "success" | "partial" | "fail" | "timeout",
  "run_id": "abc123",
  "file": "path/to/file.lean",
  "theorem_id": "Theorem.name",
  
  // Enhanced viability info
  "viability": {
    "status": "success",
    "outcome": "closed" | "not_closed",
    "time_s": 0.5
  },
  
  // Enhanced baseline info
  "baseline": {
    "outcome": "closed" | "not_closed",
    "classification": "trivial" | "promising" | "failed",
    "time_s": 5.2,
    "automation_used": "aesop"
  },
  
  // Enhanced search result
  "search_result": {
    "outcome": "closed" | "partial" | "not_closed",
    "best_hint_set": {
      "hints": [
        {
          "name": "AddSubgroup.subgroupOf_inertia",
          "type": "add_safe",
          "source": "original_proof_refs",  // NEW: Shows source!
          "rank": 8.0                       // NEW: Shows ranking!
        },
        {
          "name": "Subgroup.subgroupOf_map_subtype",
          "type": "add_safe",
          "source": "original_proof_refs",
          "rank": 8.0
        }
      ]
    } | null,
    "attempts": 105,                        // NEW: How many tried
    "time_s": 25.3
  },
  
  // NEW: Proof states (if requested)
  "proof_states": {
    "initial": {
      "goal": "⊢ (I.inertia H).map H.subtype = I.inertia G ⊓ H",
      "hypotheses": [
        "I : AddSubgroup M",
        "H : Subgroup G"
      ],
      "type_context": "AddSubgroup M, Subgroup G"
    },
    "after_hints": {
      "goal": "⊢ (simplified goal)" | null,
      "closed": false,
      "goals_remaining": 1
    }
  } | null,
  
  // NEW: Partial progress (if requested)
  "partial_progress": {
    "hints_that_helped": [
      {
        "hint": "AddSubgroup.subgroupOf_inertia",
        "impact": "reduced_goal_complexity",
        "goal_before": "⊢ complex goal",
        "goal_after": "⊢ simpler goal"
      }
    ],
    "goal_complexity_reduction": 0.30,      // 30% reduction
    "progress_score": 0.45                  // 45% toward solution
  } | null,
  
  // NEW: Tactical suggestions (always included)
  "suggestions": [
    {
      "type": "tactic",
      "suggestion": "Try: by rw [AddSubgroup.subgroupOf_inertia]; aesop",
      "confidence": 0.8,
      "reasoning": "Original proof uses rewrite with this lemma"
    },
    {
      "type": "hint",
      "suggestion": "Consider adding: Subgroup.map_subtype",
      "confidence": 0.6,
      "reasoning": "Similar proofs use this lemma"
    },
    {
      "type": "strategy",
      "suggestion": "Try: constructor tactic first (goal is ↔)",
      "confidence": 0.7,
      "reasoning": "Goal is a bi-implication"
    }
  ],
  
  // Enhanced proof patch
  "proof_patch": {
    "lean_code": "by aesop (add_safe AddSubgroup.subgroupOf_inertia, add_safe Subgroup.subgroupOf_map_subtype)",
    "style": "compact",
    "automation": "aesop",
    "hint_count": 2
  } | null,
  
  // NEW: Context (if requested)
  "context": {
    "theorem_statement": "∀ (I : AddSubgroup M) (H : Subgroup G), ...",
    "original_proof": "by rw [← AddSubgroup.subgroupOf_inertia, Subgroup.subgroupOf_map_subtype]",
    "namespace": "AddSubgroup",
    "in_scope": [
      "AddSubgroup.subgroupOf_inertia",
      "Subgroup.subgroupOf_map_subtype",
      "AddSubgroup.inertia",
      "..."
    ]
  } | null,
  
  // NEW: Similar proofs (if requested)
  "similar_proofs": [
    {
      "theorem_id": "Subgroup.inertia_map",
      "similarity": 0.85,
      "theorem_statement": "...",
      "proof": "by rw [← Subgroup.subgroupOf_inertia]",
      "hints_used": ["Subgroup.subgroupOf_inertia"]
    }
  ] | null,
  
  // NEW: Search trace (if requested)
  "search_trace": [
    {
      "step": 1,
      "hint_set": ["AddSubgroup.subgroupOf_inertia"],
      "outcome": "partial",
      "time_s": 0.5
    },
    {
      "step": 2,
      "hint_set": ["AddSubgroup.subgroupOf_inertia", "Subgroup.subgroupOf_map_subtype"],
      "outcome": "partial",
      "time_s": 0.8
    }
  ] | null,
  
  // Enhanced timing
  "timing": {
    "total_s": 35.2,
    "viability_check_s": 0.5,
    "baseline_probe_s": 5.2,
    "candidate_generation_s": 2.1,
    "search_execution_s": 25.3,
    "minimization_s": 2.1
  },
  
  // Metadata
  "metadata": {
    "lean_version": "4.26.0-rc1",
    "lake_version": "5.0.0",
    "workspace_mode": "none",
    "search_depth": "normal",
    "candidate_sources": ["goal_symbols", "local_context", "same_namespace", "original_proof_refs"],
    "automation_mode": "aesop"
  },
  
  // Artifacts paths
  "artifacts": {
    "request_path": "...",
    "result_path": "...",
    "logs_path": "..."
  }
}
```

**Improvements in ENHANCED returns**:
- ✅ Proof states (LLM can see what's happening)
- ✅ Partial progress (LLM knows what helped)
- ✅ Tactical suggestions (LLM knows what to try next)
- ✅ Rich context (LLM can reason about the proof)
- ✅ Similar proofs (LLM can pattern-match)
- ✅ Search trace (LLM can understand search process)
- ✅ Detailed metadata (LLM knows what was tried)

---

###### Key Differences Summary

| Feature | OLD Version | ENHANCED Version |
|---------|-------------|------------------|
| **Hint Extraction** | Regex-based ❌ | LeanInteract-based ✅ |
| **original_proof_refs** | Not enabled by default ❌ | Available and accurate ✅ |
| **Search Control** | Fixed parameters ❌ | LLM-controlled ✅ |
| **Proof States** | Not returned ❌ | Returned with details ✅ |
| **Partial Progress** | Not tracked ❌ | Tracked and reported ✅ |
| **Suggestions** | None ❌ | Tactical suggestions ✅ |
| **Context** | Minimal ❌ | Rich context available ✅ |
| **Similar Proofs** | Not available ❌ | Pattern matching support ✅ |
| **Search Trace** | Not available ❌ | Detailed trace available ✅ |
| **Feedback Quality** | Success/fail only ❌ | Rich, actionable feedback ✅ |

**Key benefit**: Enhanced version gives LLM everything it needs to reason about proofs and iterate effectively.

#### Tool 2: try_automated_proof

**Purpose**: Validate LLM-generated proof attempts

```python
@tool
def try_automated_proof(
    file: str,
    theorem_id: str,
    proof_attempt: str,  # LLM-generated proof
    timeout_s: float = 10.0,
    return_proof_state: bool = True,
) -> dict:
    """
    Try an LLM-generated proof and return detailed feedback.
    
    Args:
    - proof_attempt: e.g., "by rw [h1]; aesop"
    
    Returns:
    {
      "status": "success" | "error" | "incomplete" | "timeout",
      "proof_attempt": "by ...",
      
      # If success:
      "verified": true,
      
      # If error:
      "error_message": "unknown identifier 'h1'",
      "error_location": {"line": 1, "column": 10},
      
      # If incomplete:
      "proof_state": {
        "goal": "⊢ remaining_goal",
        "hypotheses": ["h1 : ...", "h2 : ..."]
      },
      
      # Always:
      "suggestions": [
        "Use full name: AddSubgroup.h1",
        "Try: by rw [h1, h2]"
      ]
    }
    """
```

**Key benefit**: Fast feedback loop for LLM iteration.

#### Tool 3: get_proof_context (New)

**Purpose**: Provide rich context for LLM reasoning

```python
@tool
def get_proof_context(
    file: str,
    theorem_id: str,
    include_similar_proofs: bool = True,
) -> dict:
    """
    Get rich context about a theorem.
    
    Returns:
    {
      "theorem_id": "AddSubgroup.inertia_map_subtype",
      "theorem_statement": "∀ (I : AddSubgroup M) ...",
      "original_proof": "by rw [← ..., ...]",
      
      "hypotheses": ["I : AddSubgroup M", "H : Subgroup G"],
      "in_scope": ["AddSubgroup.subgroupOf_inertia", ...],
      "namespace": "AddSubgroup",
      
      "similar_proofs": [
        {
          "theorem_id": "Subgroup.inertia_map",
          "similarity": 0.85,
          "proof": "by rw [← ...]"
        }
      ]
    }
    """
```

**Key benefit**: LLM can pattern-match against similar proofs.

---

## Workflow Example

### Example 1: Simple Refactoring with Annotations

```
Original theorem:
theorem List.append_assoc (l₁ l₂ l₃ : List α) : 
  (l₁ ++ l₂) ++ l₃ = l₁ ++ (l₂ ++ l₃) := by
  induction l₁ with
  | nil => rfl
  | cons h t ih => simp [ih]

User: "Refactor List.append_assoc"

┌─────────────────────────────────────────────────────────┐
│ Step 1: LLM calls get_proof_context                     │
└─────────────────────────────────────────────────────────┘
  → Returns: theorem statement, original proof, similar proofs
  
LLM sees:
  - Original uses induction + simp
  - Similar proofs in List module use automation
  - Type: associativity property

┌─────────────────────────────────────────────────────────┐
│ Step 2: LLM calls search_automated_proof                │
└─────────────────────────────────────────────────────────┘
  → Extracts: List.append_nil, List.cons_append, List.append_assoc (recursive)
  → Tests hint combinations
  → Returns: "success"
  
LLM sees:
  - Status: success
  - Proof: "by aesop (add_safe List.append_nil, add_safe List.cons_append)"

┌─────────────────────────────────────────────────────────┐
│ Step 3: LLM calls try_automated_proof to verify         │
└─────────────────────────────────────────────────────────┘
  Attempt: "by aesop (add_safe List.append_nil, add_safe List.cons_append)"
  
  → LeanInteract validates proof
  → Returns: "success" ✓

Result: Refactored to "by aesop (add_safe List.append_nil, add_safe List.cons_append)"
```

### Example 2: Iterative Refinement with Annotations

```
Original theorem:
theorem Subgroup.mem_closure_iff (s : Set G) (x : G) :
  x ∈ closure s ↔ ∀ H : Subgroup G, s ⊆ H → x ∈ H := by
  constructor
  · intro h H hs
    exact closure_le.mp (le_refl _) h hs
  · intro h
    exact h (closure s) subset_closure

User: "Refactor Subgroup.mem_closure_iff"

┌─────────────────────────────────────────────────────────┐
│ Step 1: LLM calls search_automated_proof                │
└─────────────────────────────────────────────────────────┘
  → Extracts: closure_le, subset_closure, le_refl
  → Tests combinations
  → Returns: "partial"
  
LLM sees:
  - Found hints: closure_le, subset_closure
  - Status: partial (didn't close)
  - Suggestion: "Try with constructor tactic first"

┌─────────────────────────────────────────────────────────┐
│ Step 2: LLM generates first attempt                     │
└─────────────────────────────────────────────────────────┘
  Attempt: "by aesop (add_safe closure_le, add_safe subset_closure)"
  
  → try_automated_proof returns: "incomplete"
  → Proof state: "⊢ x ∈ closure s ↔ ..."
  → Suggestion: "Need to split ↔ first"

┌─────────────────────────────────────────────────────────┐
│ Step 3: LLM refines with constructor                    │
└─────────────────────────────────────────────────────────┘
  Attempt: "by constructor <;> aesop (add_safe closure_le, add_safe subset_closure)"
  
  → try_automated_proof returns: "incomplete"
  → Proof state: First goal closed, second goal: "⊢ x ∈ closure s"
  → Suggestion: "Add le_refl hint"

┌─────────────────────────────────────────────────────────┐
│ Step 4: LLM adds missing hint                           │
└─────────────────────────────────────────────────────────┘
  Attempt: "by constructor <;> aesop (add_safe closure_le, add_safe subset_closure, add_safe le_refl)"
  
  → try_automated_proof returns: "success" ✓

Result: Refactored to "by constructor <;> aesop (add_safe closure_le, add_safe subset_closure, add_safe le_refl)"
```

### Example 3: Pure Automation Success

```
Original theorem:
theorem Nat.add_comm (n m : Nat) : n + m = m + n := by
  induction n with
  | zero => simp
  | succ n ih => simp [Nat.add_succ, ih]

User: "Refactor Nat.add_comm"

┌─────────────────────────────────────────────────────────┐
│ Step 1: LLM calls search_automated_proof                │
└─────────────────────────────────────────────────────────┘
  → Extracts: Nat.add_zero, Nat.zero_add, Nat.add_succ, Nat.succ_add
  → Tests combinations
  → Returns: "success"
  
LLM sees:
  - Status: success
  - Proof: "by aesop (add_safe Nat.add_zero, add_safe Nat.zero_add, 
                      add_safe Nat.add_succ, add_safe Nat.succ_add)"

┌─────────────────────────────────────────────────────────┐
│ Step 2: LLM calls try_proof to verify                   │
└─────────────────────────────────────────────────────────┘
  Attempt: "by aesop (add_safe Nat.add_zero, add_safe Nat.zero_add, 
                      add_safe Nat.add_succ, add_safe Nat.succ_add)"
  
  → try_proof returns: "success" ✓

Result: Refactored to "by aesop (add_safe Nat.add_zero, add_safe Nat.zero_add, 
                                 add_safe Nat.add_succ, add_safe Nat.succ_add)"
```

### Example 4: Discovering Simp Lemmas

```
Original theorem:
theorem List.length_map (f : α → β) (l : List α) : 
  (l.map f).length = l.length := by
  induction l with
  | nil => rfl
  | cons h t ih => simp [List.length, List.map, ih]

User: "Refactor List.length_map"

┌─────────────────────────────────────────────────────────┐
│ Step 1: LLM calls search_annotations                    │
└─────────────────────────────────────────────────────────┘
  → Extracts: List.length_nil, List.length_cons, List.map_nil, List.map_cons
  → Tests combinations
  → Returns: "success"
  
LLM sees:
  - Status: success
  - Proof: "by aesop (add_simp List.length_nil, add_simp List.length_cons,
                      add_simp List.map_nil, add_simp List.map_cons)"

┌─────────────────────────────────────────────────────────┐
│ Step 2: LLM calls try_proof to verify                   │
└─────────────────────────────────────────────────────────┘
  Attempt: "by aesop (add_simp List.length_nil, add_simp List.length_cons,
                      add_simp List.map_nil, add_simp List.map_cons)"
  
  → try_proof returns: "success" ✓

Result: Refactored to "by aesop (add_simp List.length_nil, add_simp List.length_cons,
                                 add_simp List.map_nil, add_simp List.map_cons)"
```

---

## Key Design Principles

### 1. Separation of Concerns

**Deterministic Search** (search_annotations):
- Fast, exhaustive within bounds
- Finds "obvious" solutions
- Provides structured feedback

**Creative Generation** (LLM):
- Handles tactical reasoning
- Learns from feedback
- Tries novel approaches

**Validation** (try_proof):
- Quick feedback loop
- Real Lean verification
- Concrete success/failure

### 2. Fast Feedback Loops

- `search_annotations`: 30s max (deterministic search)
- `try_proof`: 10s max (quick validation)
- Total iteration: ~40s (LLM can try multiple approaches)

### 3. Rich Feedback

Not just success/fail:
- Proof states (see what the goal looks like)
- Partial progress (what hints helped)
- Tactical suggestions (what to try next)
- Error messages (what went wrong)

### 4. Composable Tools

- Each tool does one thing well
- LLM orchestrates the combination
- Can add new tools without changing existing ones

### 5. Graceful Degradation

```
Try 1: Pure automation (search_annotations)
  ↓ If fails
Try 2: Automation + hints (try_proof with hints)
  ↓ If fails
Try 3: Tactics + automation (try_proof with tactics)
  ↓ If fails
Try 4: Keep original proof (admit defeat gracefully)
```

---

## Expected Success Rates

### Tier 1: Trivial Theorems (5-10%)

**Characteristics**:
- Reflexivity, symmetry, transitivity
- Constructor applications
- Simple type class resolution

**Approach**:
- `search_annotations` closes immediately
- No LLM iteration needed

**Example**:
```lean
theorem refl (n : Nat) : n = n := by rfl
→ by aesop
```

### Tier 2: Simple Theorems (10-15%)

**Characteristics**:
- Forward reasoning
- Type class resolution with hints
- Simple rewrites

**Approach**:
- `search_annotations` finds hints
- LLM tries 1-2 proof attempts
- Success via `try_proof`

**Example**:
```lean
theorem trans (h1 : a = b) (h2 : b = c) : a = c := by exact Eq.trans h1 h2
→ by aesop
```

### Tier 3: Medium Theorems (5-10%)

**Characteristics**:
- Rewrite chains
- Tactics + automation
- Pattern matching from similar proofs

**Approach**:
- `search_annotations` gives partial progress
- LLM generates tactical proofs
- 3-5 iterations via `try_proof`
- Success!

**Example**:
```lean
theorem complex : ... := by
  rw [lemma1, lemma2]
  exact lemma3
→ by rw [lemma1, lemma2]; aesop
```

### Total: 20-35%

This achieves the goal of refactoring 20-30% of mathlib!

---

## What Won't Work

### Complex Theorems (60-70%)

**Characteristics**:
- Induction/recursion
- Complex case analysis
- Calc chains
- Deep tactical reasoning

**Why they won't convert**:
- Require structural tactics (induction, cases)
- Need human insight for proof strategy
- Beyond scope of hint-based automation

**Approach**:
- Keep original proof
- Document why it can't be refactored
- Focus effort on achievable targets

---

## Implementation Phases

### Phase 1: LeanInteract Integration

**Goal**: Replace regex with LeanInteract

1. Implement `LeanInteractQuerier`
   - `extract_declarations` using `FileCommand(declarations=True)`
   - `get_proof_references` from `declaration.value.constants` + text parsing
   - `get_theorem_context` with scope information

2. Implement `ProofStateInspector`
   - `get_initial_proof_state` using `Command` with sorry
   - `apply_tactic` using `ProofStep`

3. Implement `ProofValidator`
   - `validate_proof` using `Command`
   - Parse error messages and suggestions

4. Refactor `CandidateGenerator`
   - Replace `_extract_from_proof` regex with LeanInteract
   - Use actual declaration attributes for hint type inference

**Success criteria**: `original_proof_refs` correctly extracts lemmas from proofs

### Phase 2: Enhanced Feedback

**Goal**: Provide rich feedback for LLM

1. Enhance `search_annotations` tool
   - Add `return_proof_states` parameter
   - Add `return_partial_progress` parameter
   - Add tactical suggestions to output

2. Implement `ContextExtractor`
   - Extract theorem context
   - Find similar proofs
   - Provide scope information

3. Implement `FeedbackBuilder`
   - Build structured feedback from search results
   - Generate tactical suggestions
   - Track partial progress

**Success criteria**: LLM receives actionable feedback, not just success/fail

### Phase 3: New Tools

**Goal**: Enable LLM-guided iteration

1. Implement `try_proof` tool
   - Validate LLM-generated proofs
   - Return detailed error messages
   - Provide proof states for incomplete proofs

2. Implement `get_proof_context` tool
   - Extract theorem context
   - Find similar proofs
   - Provide rich context for LLM reasoning

**Success criteria**: LLM can iterate on proof attempts with fast feedback

### Phase 4: Orchestration

**Goal**: LLM-driven refactoring workflow

1. Document LLM workflow patterns
   - When to use each tool
   - How to interpret feedback
   - Iteration strategies

2. Implement progress tracking
   - Detect repeated attempts
   - Measure goal complexity reduction
   - Decide when to stop iterating

3. Add graceful degradation
   - Try automation first
   - Fall back to tactics
   - Keep original if all fails

**Success criteria**: End-to-end refactoring workflow achieves 20-30% success rate

---

## Technical Considerations

### Performance

**LeanInteract Startup**:
- Slow (~seconds per file)
- **Solution**: Reuse server instance, batch queries

**Proof Validation**:
- Fast (10s timeout)
- **Solution**: Parallel validation for multiple attempts

**Search Time**:
- Configurable (30s default)
- **Solution**: LLM controls budget based on theorem complexity

### Reliability

**LeanInteract Stability**:
- Can crash or hang
- **Solution**: Timeout handling, automatic restart

**LLM Hallucination**:
- May generate invalid Lean syntax
- **Solution**: Fast validation catches errors, LLM learns from feedback

**Infinite Loops**:
- LLM may repeat failed attempts
- **Solution**: Track attempt history, detect patterns, max iteration limit

### Cost

**LLM Calls**:
- Multiple calls per theorem
- **Solution**: Deterministic search first (cheap), LLM only for hard cases

**Compute Time**:
- ~1-2 minutes per theorem
- **Solution**: Batch processing, parallel execution

---

## Success Metrics

### Quantitative

- **Refactoring rate**: 20-30% of theorems successfully refactored
- **Iteration count**: Average 2-3 LLM iterations per successful refactoring
- **Time per theorem**: Average 1-2 minutes
- **False positive rate**: < 5% (refactored proofs that don't verify)

### Qualitative

- **Proof quality**: Refactored proofs are simpler/more maintainable
- **Automation coverage**: More proofs use automation instead of manual tactics
- **Pattern discovery**: LLM learns common refactoring patterns

---

## Risks and Mitigations

### Risk 1: Lower Success Rate Than Expected

**Risk**: Achieve only 10-15% instead of 20-30%

**Mitigation**:
- Start with easier files (Data.List, Data.Nat)
- Focus on trivial/simple theorems first
- Document what works and what doesn't
- Adjust expectations based on early results

### Risk 2: LeanInteract Reliability Issues

**Risk**: LeanInteract crashes or hangs frequently

**Mitigation**:
- Implement robust error handling
- Automatic server restart
- Fall back to regex for critical operations
- Contribute fixes upstream

### Risk 3: LLM Cost Too High

**Risk**: Too many LLM calls per theorem

**Mitigation**:
- Optimize deterministic search first
- Cache successful patterns
- Batch similar theorems
- Use cheaper models for simple cases

### Risk 4: Proof Quality Concerns

**Risk**: Refactored proofs are less maintainable

**Mitigation**:
- Human review of refactored proofs
- Preserve original proofs as comments
- Document refactoring rationale
- Revert if community feedback is negative

---

## Conclusion

This architecture enables LLM-guided proof refactoring by:

1. **Accurate hint extraction** via LeanInteract (not regex)
2. **Rich feedback** for LLM reasoning (proof states, suggestions)
3. **Fast iteration** through try_proof validation
4. **Graceful degradation** from automation to tactics

The combination of deterministic search, LLM creativity, and Lean validation creates a powerful collaborative system capable of refactoring 20-30% of mathlib proofs.

The key innovation is using LeanInteract throughout for accurate, reliable interaction with Lean, while giving the LLM the tools and feedback it needs to reason about and refactor proofs effectively.

---

## References

- LeanInteract: https://github.com/augustepoiroux/LeanInteract
- Lean 4: https://github.com/leanprover/lean4
- Mathlib4: https://github.com/leanprover-community/mathlib4

