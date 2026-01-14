---
inclusion: always
---

# Code Conventions — Core Design Patterns

This document defines the **mandatory design patterns** used throughout the codebase. These are architectural constraints, not stylistic preferences. The goal is to make complexity **explicit, bounded, and testable**.

## 1. Hexagonal Architecture (Boundaries)

**Design Principle:** Separate core logic from all external concerns using explicit boundaries.

**Rules:**
- Core logic must not depend on frameworks, filesystems, network APIs, or external processes
- All external interaction happens through abstract ports (interfaces)
- Adapters implement those ports and depend inward toward the core

**Example:**
```python
from typing import Protocol

class Gateway(Protocol):
    def send(self, msg: str) -> None: ...

class UseCase:
    def __init__(self, gateway: Gateway):
        self.gateway = gateway

    def run(self) -> None:
        self.gateway.send("hello")

class ConsoleGateway:
    def send(self, msg: str) -> None:
        print(msg)
```

**Benefits:**
- Prevents infrastructure from leaking into core logic
- Enables testing core logic without framework mocks
- Allows core reuse across multiple interfaces

## 2. Dependency Injection (Direction of Dependencies)

**Design Principle:** Objects receive their dependencies instead of constructing them.

**Rules:**
- Objects must not instantiate their own dependencies
- All wiring happens in a single composition root
- Core logic depends only on abstractions

**Example:**
```python
class Service:
    def __init__(self, repo):
        self.repo = repo

def build_app():
    repo = DatabaseRepository()
    return Service(repo)
```

**Benefits:**
- Makes dependencies explicit and testable
- Enables substitution in tests
- Prevents hidden coupling and global state

## 3. Command Pattern (Clean Entry Points)

**Design Principle:** Encapsulate each operation as a single object with a single handler.

**Rules:**
- One command per operation
- Commands are immutable data structures
- Handlers orchestrate, not contain core logic

**Example:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CreateItem:
    name: str

class CreateItemHandler:
    def handle(self, cmd: CreateItem) -> None:
        # Orchestrate the operation
        print(f"created {cmd.name}")
```

**Benefits:**
- Provides consistent execution structure
- Simplifies logging, retries, and auditing
- Makes operations first-class and testable

## 4. Strategy Pattern (Behavioral Variation)

**Design Principle:** Encapsulate interchangeable algorithms behind a common interface.

**Rules:**
- No if/else chains for behavioral variation
- Behavior differences must be modeled as strategies
- Strategies share a stable interface

**Example:**
```python
from typing import Protocol

class Scorer(Protocol):
    def score(self, x: str) -> int: ...

class LengthScorer:
    def score(self, x: str) -> int:
        return len(x)

class VowelScorer:
    def score(self, x: str) -> int:
        return sum(c in "aeiou" for c in x)
```

**Benefits:**
- Keeps code open for extension, closed for modification
- Prevents central logic from becoming unmaintainable
- Enables experimentation without rewrites

## 5. Builder Pattern (Complex Construction)

**Design Principle:** Construct complex objects step-by-step while enforcing invariants.

**Rules:**
- Builders validate before producing final objects
- Final objects are immutable
- Construction logic is hidden from consumers

**Example:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Report:
    title: str
    sections: list[str]

class ReportBuilder:
    def __init__(self):
        self._title = ""
        self._sections = []

    def title(self, t: str):
        self._title = t
        return self

    def add_section(self, s: str):
        self._sections.append(s)
        return self

    def build(self) -> Report:
        if not self._title:
            raise ValueError("Title is required")
        return Report(self._title, list(self._sections))
```

**Benefits:**
- Prevents invalid intermediate states
- Improves readability of complex construction
- Makes invariants explicit

## 6. Result/Either Pattern (Explicit Failures)

**Design Principle:** Represent success and failure explicitly in return values.

**Rules:**
- Functions that can fail return Result/Either types
- Exceptions are reserved for programmer errors
- Error types must be structured and enumerable

**Example:**
```python
from dataclasses import dataclass
from typing import Union

@dataclass(frozen=True)
class Ok:
    value: int

@dataclass(frozen=True)
class Err:
    reason: str

Result = Union[Ok, Err]

def divide(a: int, b: int) -> Result:
    if b == 0:
        return Err("division by zero")
    return Ok(a // b)
```

**Benefits:**
- Makes failure paths visible and testable
- Eliminates implicit control flow via exceptions
- Enables reliable diagnostics and recovery

## AI Assistant Guidelines

When working with this codebase:
- Always apply these patterns when creating new code
- Refactor existing code to follow these patterns when making changes
- Prefer composition over inheritance
- Keep functions pure when possible
- Use type hints consistently
- Write tests that verify pattern compliance
