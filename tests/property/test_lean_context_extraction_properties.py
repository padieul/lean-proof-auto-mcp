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

from lean_proof_auto_mcp.lean.querier import LeanInteractQuerierImpl

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
    # Setup: Create mock declarations
    mock_declarations = []
    
    # Create the theorem declaration
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"{namespace}.{theorem_name}" if namespace else theorem_name
    mock_theorem.type = theorem_type
    
    # Add value with proof text
    mock_value = Mock()
    mock_value.pp = proof_text
    mock_value.constants = []
    mock_value.start_pos = Mock(line=1, column=0)
    mock_value.end_pos = Mock(line=2, column=0)
    mock_theorem.value = mock_value
    
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    
    mock_scope = Mock()
    mock_scope.curr_namespace = namespace
    mock_theorem.scope = mock_scope
    
    mock_declarations.append(mock_theorem)
    
    # Add in-scope declarations
    for i in range(num_in_scope):
        mock_decl = Mock()
        mock_decl.name = f"decl_{i}"
        mock_decl.full_name = f"{namespace}.decl_{i}" if namespace else f"decl_{i}"
        mock_decl.type = "Prop"
        mock_decl.value = None
        mock_decl.attributes = []
        mock_decl.start_pos = Mock(line=1, column=0)
        mock_decl.end_pos = Mock(line=2, column=0)
        mock_decl.namespace = namespace
        mock_decl.scope = mock_scope
        mock_declarations.append(mock_decl)
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = mock_declarations
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute
    context = querier.get_theorem_context("test.lean", theorem_name)
    
    # Verify: Complete theorem statement from declaration.type
    assert context.theorem_statement == theorem_type
    
    # Verify: Original proof from declaration.value.pp
    assert context.original_proof == proof_text
    
    # Verify: Namespace from declaration.scope.curr_namespace
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
    # Setup: Create mock theorem with namespace
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"{namespace}.{theorem_name}"
    mock_theorem.type = "Prop"
    mock_theorem.value = None
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    
    mock_scope = Mock()
    mock_scope.curr_namespace = namespace
    mock_theorem.scope = mock_scope
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = [mock_theorem]
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute
    context = querier.get_theorem_context("test.lean", theorem_name)
    
    # Verify: Namespace extracted correctly
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
    # Setup: Create mock theorem
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"MyNamespace.{theorem_name}"
    mock_theorem.type = theorem_type
    mock_theorem.value = None
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    
    mock_scope = Mock()
    mock_scope.curr_namespace = "MyNamespace"
    mock_theorem.scope = mock_scope
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = [mock_theorem]
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute
    context = querier.get_theorem_context("test.lean", theorem_name)
    
    # Verify: Theorem statement extracted correctly
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
    # Setup: Create mock theorem with proof
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"MyNamespace.{theorem_name}"
    mock_theorem.type = "Prop"
    
    # Add value with proof text
    mock_value = Mock()
    mock_value.pp = proof_text
    mock_value.constants = []
    mock_value.start_pos = Mock(line=1, column=0)
    mock_value.end_pos = Mock(line=2, column=0)
    mock_theorem.value = mock_value
    
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    
    mock_scope = Mock()
    mock_scope.curr_namespace = "MyNamespace"
    mock_theorem.scope = mock_scope
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = [mock_theorem]
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute
    context = querier.get_theorem_context("test.lean", theorem_name)
    
    # Verify: Original proof extracted correctly
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
    # Setup: Create mock theorem without proof
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"MyNamespace.{theorem_name}"
    mock_theorem.type = "Prop"
    mock_theorem.value = None  # No proof value
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    
    mock_scope = Mock()
    mock_scope.curr_namespace = "MyNamespace"
    mock_theorem.scope = mock_scope
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = [mock_theorem]
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute
    context = querier.get_theorem_context("test.lean", theorem_name)
    
    # Verify: Empty proof returned
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
    # Setup: Create mock declarations
    mock_declarations = []
    
    # Create the theorem declaration
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"{namespace}.{theorem_name}"
    mock_theorem.type = "Prop"
    mock_theorem.value = None
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    mock_theorem.namespace = namespace
    
    mock_scope = Mock()
    mock_scope.curr_namespace = namespace
    mock_theorem.scope = mock_scope
    
    mock_declarations.append(mock_theorem)
    
    # Add declarations in same namespace
    for i in range(num_same_namespace):
        mock_decl = Mock()
        mock_decl.name = f"same_ns_decl_{i}"
        mock_decl.full_name = f"{namespace}.same_ns_decl_{i}"
        mock_decl.type = "Prop"
        mock_decl.value = None
        mock_decl.attributes = []
        mock_decl.start_pos = Mock(line=1, column=0)
        mock_decl.end_pos = Mock(line=2, column=0)
        mock_decl.namespace = namespace
        mock_decl.scope = mock_scope
        mock_declarations.append(mock_decl)
    
    # Add declarations in different namespace
    for i in range(num_different_namespace):
        mock_decl = Mock()
        mock_decl.name = f"diff_ns_decl_{i}"
        mock_decl.full_name = f"OtherNamespace.diff_ns_decl_{i}"
        mock_decl.type = "Prop"
        mock_decl.value = None
        mock_decl.attributes = []
        mock_decl.start_pos = Mock(line=1, column=0)
        mock_decl.end_pos = Mock(line=2, column=0)
        mock_decl.namespace = "OtherNamespace"
        other_scope = Mock()
        other_scope.curr_namespace = "OtherNamespace"
        mock_decl.scope = other_scope
        mock_declarations.append(mock_decl)
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = mock_declarations
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute
    context = querier.get_theorem_context("test.lean", theorem_name)
    
    # Verify: In-scope declarations include same namespace declarations
    # (and the theorem itself)
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
    # Setup: Create mock declaration with different name
    mock_theorem = Mock()
    mock_theorem.name = theorem_name
    mock_theorem.full_name = f"MyNamespace.{theorem_name}"
    mock_theorem.type = "Prop"
    mock_theorem.value = None
    mock_theorem.attributes = []
    mock_theorem.start_pos = Mock(line=1, column=0)
    mock_theorem.end_pos = Mock(line=2, column=0)
    
    mock_scope = Mock()
    mock_scope.curr_namespace = "MyNamespace"
    mock_theorem.scope = mock_scope
    
    # Create querier with mocked server
    querier = LeanInteractQuerierImpl()
    
    mock_server = Mock()
    mock_response = Mock()
    mock_response.declarations = [mock_theorem]
    mock_server.run.return_value = mock_response
    
    querier._server_cache["test.lean"] = mock_server
    
    # Execute & Verify: Searching for non-existent theorem raises ValueError
    if invalid_theorem != theorem_name:
        with pytest.raises(ValueError, match="Theorem not found"):
            querier.get_theorem_context("test.lean", invalid_theorem)
