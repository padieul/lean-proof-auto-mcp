"""
Property-based tests for theorem context extraction.

These tests verify universal properties that should hold across all valid executions.
Each test runs a minimum of 100 iterations with randomized inputs.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from unittest.mock import Mock

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range
from lean_proof_auto_mcp.lean.querier import LeanInteractQuerier


def _make_querier_with_declarations(
    file_path: str, declarations: list[Declaration]
) -> LeanInteractQuerier:
    """Create a LeanInteractQuerier with pre-populated declaration cache.

    Injects declarations directly into the cache so that
    get_theorem_context() never hits the real LeanInteract server.
    """
    mock_server_manager = Mock()
    querier = LeanInteractQuerier(mock_server_manager)
    querier._declarations_cache[file_path] = declarations
    return querier


def _decl(
    name: str,
    full_name: str = "",
    type_sig: str = "Prop",
    namespace: str = "",
    proof_pp: str | None = None,
) -> Declaration:
    """Minimal Declaration factory for property tests."""
    value = None
    if proof_pp is not None:
        value = DeclValue(pp=proof_pp, constants=[], range=Range(0, 0, 0, 0))
    return Declaration(
        name=name,
        full_name=full_name or name,
        type=type_sig,
        value=value,
        attributes=[],
        range=Range(start_line=1, start_col=0, end_line=2, end_col=0),
        namespace=namespace,
    )


# ============================================================================
# Property 3: Complete Context Extraction
# ============================================================================


@given(
    theorem_name=st.text(min_size=1, max_size=50),
    theorem_type=st.text(min_size=1, max_size=200),
    proof_text=st.text(min_size=0, max_size=500),
    namespace=st.text(min_size=0, max_size=100),
    num_in_scope=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_property_3_complete_context_extraction(
    theorem_name, theorem_type, proof_text, namespace, num_in_scope
):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction

    For any theorem identifier in a file, extracting theorem context SHALL return
    the complete theorem statement from declaration.type, all hypotheses from the
    initial proof state, all declarations visible in scope, and the current namespace
    from declaration.scope.curr_namespace.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """
    full_name = f"{namespace}.{theorem_name}" if namespace else theorem_name

    declarations = [
        _decl(
            name=theorem_name,
            full_name=full_name,
            type_sig=theorem_type,
            namespace=namespace,
            proof_pp=proof_text,
        ),
    ]

    # Add in-scope declarations (same namespace)
    for i in range(num_in_scope):
        fn = f"{namespace}.decl_{i}" if namespace else f"decl_{i}"
        declarations.append(
            _decl(name=f"decl_{i}", full_name=fn, namespace=namespace)
        )

    querier = _make_querier_with_declarations("test.lean", declarations)
    context = querier.get_theorem_context("test.lean", theorem_name)

    # Verify: Complete theorem statement from declaration.type
    assert context.theorem_statement == theorem_type

    # Verify: Original proof from declaration.value.pp
    assert context.original_proof == proof_text

    # Verify: Namespace
    assert context.namespace == namespace

    # Verify: In-scope declarations (same namespace)
    assert len(context.in_scope) >= num_in_scope

    # Verify: Hypotheses list exists (may be empty for now)
    assert isinstance(context.hypotheses, list)


@given(
    theorem_name=st.text(min_size=1, max_size=50),
    namespace=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100, deadline=None)
def test_property_3_namespace_extraction(theorem_name, namespace):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction (Namespace)

    For any theorem, the system SHALL extract the current namespace from
    declaration.scope.curr_namespace.

    Validates: Requirements 3.4
    """
    declarations = [
        _decl(
            name=theorem_name,
            full_name=f"{namespace}.{theorem_name}",
            namespace=namespace,
        ),
    ]

    querier = _make_querier_with_declarations("test.lean", declarations)
    context = querier.get_theorem_context("test.lean", theorem_name)

    assert context.namespace == namespace


@given(
    theorem_name=st.text(min_size=1, max_size=50),
    theorem_type=st.text(min_size=1, max_size=200),
)
@settings(max_examples=100, deadline=None)
def test_property_3_theorem_statement_extraction(theorem_name, theorem_type):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction (Theorem Statement)

    For any theorem, the system SHALL extract the complete theorem statement
    from declaration.type.

    Validates: Requirements 3.1
    """
    declarations = [
        _decl(
            name=theorem_name,
            full_name=f"MyNamespace.{theorem_name}",
            type_sig=theorem_type,
            namespace="MyNamespace",
        ),
    ]

    querier = _make_querier_with_declarations("test.lean", declarations)
    context = querier.get_theorem_context("test.lean", theorem_name)

    assert context.theorem_statement == theorem_type


@given(
    theorem_name=st.text(min_size=1, max_size=50),
    proof_text=st.text(min_size=1, max_size=500),
)
@settings(max_examples=100, deadline=None)
def test_property_3_original_proof_extraction(theorem_name, proof_text):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction (Original Proof)

    For any theorem with a proof value, the system SHALL extract the original
    proof from declaration.value.pp.

    Validates: Requirements 3.1
    """
    declarations = [
        _decl(
            name=theorem_name,
            full_name=f"MyNamespace.{theorem_name}",
            namespace="MyNamespace",
            proof_pp=proof_text,
        ),
    ]

    querier = _make_querier_with_declarations("test.lean", declarations)
    context = querier.get_theorem_context("test.lean", theorem_name)

    assert context.original_proof == proof_text


@given(
    theorem_name=st.text(min_size=1, max_size=50),
)
@settings(max_examples=100, deadline=None)
def test_property_3_no_proof_value(theorem_name):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction (No Proof Value)

    For any theorem without a proof value, the system SHALL return an empty
    string for original_proof.

    Validates: Requirements 3.1
    """
    declarations = [
        _decl(
            name=theorem_name,
            full_name=f"MyNamespace.{theorem_name}",
            namespace="MyNamespace",
            proof_pp=None,  # No proof
        ),
    ]

    querier = _make_querier_with_declarations("test.lean", declarations)
    context = querier.get_theorem_context("test.lean", theorem_name)

    assert context.original_proof == ""


@given(
    theorem_name=st.text(min_size=1, max_size=50),
    namespace=st.text(min_size=1, max_size=100),
    num_same_namespace=st.integers(min_value=0, max_value=10),
    num_different_namespace=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100, deadline=None)
def test_property_3_in_scope_declarations(
    theorem_name, namespace, num_same_namespace, num_different_namespace
):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction (In-Scope Declarations)

    For any theorem, the system SHALL extract all declarations visible in scope
    (same namespace or parent namespaces).

    Validates: Requirements 3.3
    """
    declarations = [
        _decl(
            name=theorem_name,
            full_name=f"{namespace}.{theorem_name}",
            namespace=namespace,
        ),
    ]

    # Add declarations in same namespace
    for i in range(num_same_namespace):
        declarations.append(
            _decl(
                name=f"same_ns_decl_{i}",
                full_name=f"{namespace}.same_ns_decl_{i}",
                namespace=namespace,
            )
        )

    # Add declarations in different namespace
    for i in range(num_different_namespace):
        declarations.append(
            _decl(
                name=f"diff_ns_decl_{i}",
                full_name=f"OtherNamespace.diff_ns_decl_{i}",
                namespace="OtherNamespace",
            )
        )

    querier = _make_querier_with_declarations("test.lean", declarations)
    context = querier.get_theorem_context("test.lean", theorem_name)

    # Verify: In-scope declarations include same namespace declarations + theorem itself
    assert len(context.in_scope) >= num_same_namespace + 1

    # Verify: Same namespace declarations are included
    for i in range(num_same_namespace):
        expected_name = f"{namespace}.same_ns_decl_{i}"
        assert expected_name in context.in_scope


@given(
    theorem_name=st.text(min_size=1, max_size=50),
    invalid_theorem=st.text(min_size=1, max_size=50).filter(lambda x: x != "test_theorem"),
)
@settings(max_examples=100, deadline=None)
def test_property_3_theorem_not_found(theorem_name, invalid_theorem):
    """
    Feature: iterative-orchestration-enhancements
    Property 3: Complete Context Extraction (Theorem Not Found)

    When a theorem is not found in the file, the system SHALL raise ValueError
    with a clear message.

    Validates: Requirements 3.5, 11.3
    """
    declarations = [
        _decl(
            name=theorem_name,
            full_name=f"MyNamespace.{theorem_name}",
            namespace="MyNamespace",
        ),
    ]

    querier = _make_querier_with_declarations("test.lean", declarations)

    # Execute & Verify: Searching for non-existent theorem raises ValueError
    if invalid_theorem != theorem_name:
        with pytest.raises(ValueError, match="Theorem not found"):
            querier.get_theorem_context("test.lean", invalid_theorem)
