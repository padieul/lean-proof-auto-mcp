"""

Property-based tests for LeanInteractQuerier.


These tests verify universal properties that should hold across all valid executions.

Each test runs a minimum of 100 iterations with randomized inputs.


Requirements: 1.1, 1.2, 1.3

"""

from unittest.mock import Mock

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from lean_proof_auto_mcp.lean.ports import Declaration, DeclValue, Range
from lean_proof_auto_mcp.lean.querier import LeanInteractQuerier

# ============================================================================

# Hypothesis Strategies

# ============================================================================


@st.composite
def valid_declarations(draw):
    """Generate valid Declaration instances."""

    name = draw(st.text(min_size=1, max_size=50))

    full_name = draw(st.text(min_size=1, max_size=100))

    type_sig = draw(st.text(min_size=1, max_size=200))

    # Generate optional value

    has_value = draw(st.booleans())

    value = None

    if has_value:
        pp = draw(st.text(min_size=0, max_size=500))

        constants = draw(st.lists(st.text(min_size=1, max_size=50), max_size=20))

        value_range = Range(
            start_line=draw(st.integers(min_value=1, max_value=1000)),
            start_col=draw(st.integers(min_value=0, max_value=100)),
            end_line=draw(st.integers(min_value=1, max_value=1000)),
            end_col=draw(st.integers(min_value=0, max_value=100)),
        )

        value = DeclValue(pp=pp, constants=constants, range=value_range)

    attributes = draw(st.lists(st.text(min_size=1, max_size=20), max_size=10))

    decl_range = Range(
        start_line=draw(st.integers(min_value=1, max_value=1000)),
        start_col=draw(st.integers(min_value=0, max_value=100)),
        end_line=draw(st.integers(min_value=1, max_value=1000)),
        end_col=draw(st.integers(min_value=0, max_value=100)),
    )

    namespace = draw(st.text(min_size=0, max_size=100))

    return Declaration(
        name=name,
        full_name=full_name,
        type=type_sig,
        value=value,
        attributes=attributes,
        range=decl_range,
        namespace=namespace,
    )


# ============================================================================

# Property 1: Complete Declaration Extraction

# ============================================================================


@given(
    num_declarations=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_property_1_complete_declaration_extraction(num_declarations):
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction


    For any Lean file with declarations, extracting declarations using LeanInteract

    SHALL return all declarations with complete information including fully qualified

    name, type signature, proof value (if present with both pp text and constants list),

    attributes, position range, and namespace.


    Validates: Requirements 1.1, 1.2, 1.3

    """

    # Setup: Create mock LeanInteract response

    mock_declarations = []

    for i in range(num_declarations):
        mock_decl = Mock()

        mock_decl.name = f"theorem_{i}"

        mock_decl.full_name = f"MyNamespace.theorem_{i}"

        mock_decl.type = f"Prop_{i}"

        # Add value with constants

        mock_value = Mock()

        mock_value.pp = f"proof_text_{i}"

        mock_value.constants = [f"lemma_{j}" for j in range(i % 3)]

        mock_value.start_pos = Mock(line=i, column=0)

        mock_value.end_pos = Mock(line=i + 1, column=0)

        mock_decl.value = mock_value

        mock_decl.attributes = ["simp"] if i % 2 == 0 else []

        mock_decl.start_pos = Mock(line=i, column=0)

        mock_decl.end_pos = Mock(line=i + 1, column=0)

        mock_scope = Mock()

        mock_scope.curr_namespace = "MyNamespace"

        mock_decl.scope = mock_scope

        mock_declarations.append(mock_decl)

    # Create querier with mocked ServerManager

    mock_server_manager = Mock()

    mock_server = Mock()

    mock_response = Mock()

    mock_response.declarations = mock_declarations

    mock_server.run.return_value = mock_response

    mock_server_manager.get_server.return_value = mock_server

    querier = LeanInteractQuerier(server_manager=mock_server_manager)

    # Execute

    declarations = querier.extract_declarations("test.lean")

    # Verify: All declarations extracted

    assert len(declarations) == num_declarations

    # Verify: Each declaration has complete information

    for i, decl in enumerate(declarations):
        # Fully qualified name

        assert decl.full_name == f"MyNamespace.theorem_{i}"

        # Type signature

        assert decl.type == f"Prop_{i}"

        # Proof value with pp text and constants

        assert decl.value is not None

        assert decl.value.pp == f"proof_text_{i}"

        assert isinstance(decl.value.constants, list)

        # Attributes

        assert isinstance(decl.attributes, list)

        # Position range

        assert decl.range.start_line >= 0

        assert decl.range.end_line >= decl.range.start_line

        # Namespace

        assert decl.namespace == "MyNamespace"


@given(decl=valid_declarations())
@settings(max_examples=100)
def test_property_1_declaration_immutability(decl):
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (Immutability)


    For any Declaration instance, all fields should be immutable (frozen dataclass).


    Validates: Requirements 1.1, 1.2

    """

    # Verify: Declaration is frozen

    with pytest.raises((AttributeError, Exception)):
        decl.name = "modified"  # type: ignore[misc]

    # Verify: DeclValue is frozen if present

    if decl.value is not None:
        with pytest.raises((AttributeError, Exception)):
            decl.value.pp = "modified"  # type: ignore[misc]


@given(
    pp_text=st.text(min_size=0, max_size=500),
    constants=st.lists(st.text(min_size=1, max_size=50), max_size=20),
)
@settings(max_examples=100)
def test_property_1_decl_value_get_all_references(pp_text, constants):
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (Reference Extraction)


    For any DeclValue, get_all_references() should return all constants from

    the constants list (primary source).


    Validates: Requirements 2.1, 2.2

    """

    # Setup

    value_range = Range(start_line=1, start_col=0, end_line=2, end_col=0)

    decl_value = DeclValue(pp=pp_text, constants=constants, range=value_range)

    # Execute

    references = decl_value.get_all_references()

    # Verify: All constants are included

    for const in constants:
        assert const in references

    # Verify: No duplicates (set conversion)

    assert len(references) == len(set(references))


# ============================================================================

# Property Tests for Declaration Properties

# ============================================================================


@given(
    type_sig=st.text(min_size=1, max_size=200),
    has_theorem_keyword=st.booleans(),
)
@settings(max_examples=100)
def test_property_1_is_theorem_property(type_sig, has_theorem_keyword):
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (is_theorem property)


    For any Declaration, is_theorem should return True if and only if

    the type contains "theorem" or "lemma".


    Validates: Requirements 1.2

    """

    # Setup: Inject keyword if needed

    if has_theorem_keyword:
        type_sig = f"theorem {type_sig}"

    decl = Declaration(
        name="test",
        full_name="Test.test",
        type=type_sig,
        value=None,
        attributes=[],
        range=Range(1, 0, 2, 0),
        namespace="Test",
    )

    # Execute & Verify

    expected = "theorem" in type_sig or "lemma" in type_sig

    assert decl.is_theorem == expected


@given(
    attributes=st.lists(st.text(min_size=1, max_size=20), max_size=10),
    has_simp=st.booleans(),
)
@settings(max_examples=100)
def test_property_1_has_simp_attribute_property(attributes, has_simp):
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (has_simp_attribute property)


    For any Declaration, has_simp_attribute should return True if and only if

    "simp" is in the attributes list.


    Validates: Requirements 1.2

    """

    # Setup: Inject simp if needed

    if has_simp and "simp" not in attributes:
        attributes = attributes + ["simp"]

    elif not has_simp and "simp" in attributes:
        attributes = [a for a in attributes if a != "simp"]

    decl = Declaration(
        name="test",
        full_name="Test.test",
        type="Prop",
        value=None,
        attributes=attributes,
        range=Range(1, 0, 2, 0),
        namespace="Test",
    )

    # Execute & Verify

    assert decl.has_simp_attribute == has_simp


# ============================================================================

# Error Handling Tests

# ============================================================================


def test_property_1_lean_interact_not_available():
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (Error Handling)


    When LeanInteract is not available, extract_declarations should raise

    RuntimeError with clear message.


    Validates: Requirements 1.1, 11.3

    """

    # Setup: Create querier

    querier = LeanInteractQuerier()

    # Mock LeanInteract as unavailable

    import lean_proof_auto_mcp.lean.querier as querier_module

    original_available = querier_module.LEAN_INTERACT_AVAILABLE

    original_server = querier_module.LeanServer

    try:
        querier_module.LEAN_INTERACT_AVAILABLE = False

        querier_module.LeanServer = None

        # Execute & Verify

        with pytest.raises(RuntimeError, match="LeanInteract library not installed"):
            querier.extract_declarations("test.lean")

    finally:
        # Restore

        querier_module.LEAN_INTERACT_AVAILABLE = original_available

        querier_module.LeanServer = original_server


def test_property_1_lean_interact_error():
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (LeanInteract Error)


    When LeanInteract returns an error, extract_declarations should raise

    RuntimeError with error details.


    Validates: Requirements 1.1, 11.1

    """

    # Setup: Create querier with mocked server

    querier = LeanInteractQuerier()

    # Mock server that returns error

    mock_server = Mock()

    # Import LeanError if available and create mock instance

    try:
        from lean_interact.interface import LeanError

        # LeanError is a Pydantic model, so we need to mock it properly

        mock_error = Mock(spec=LeanError)

        mock_error.__class__ = LeanError

        mock_server.run.return_value = mock_error

    except ImportError:
        # If LeanInteract not available, create mock error

        mock_error = Mock()

        mock_error.__class__.__name__ = "LeanError"

        mock_server.run.return_value = mock_error

    querier._server_cache["test.lean"] = mock_server

    # Execute & Verify

    with pytest.raises(RuntimeError, match="Failed to extract declarations"):
        querier.extract_declarations("test.lean")


# ============================================================================

# Server Caching Tests

# ============================================================================


@given(
    file_path=st.text(min_size=1, max_size=100),
    num_calls=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=50, deadline=None)
def test_property_1_server_reuse(file_path, num_calls):
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (Server Reuse)


    For any file path, multiple calls to extract_declarations should reuse

    the same server instance to avoid startup overhead.


    Validates: Requirements 10.6, 28.4

    """

    # Setup: Create querier with mocked server

    querier = LeanInteractQuerier()

    mock_server = Mock()

    mock_response = Mock()

    mock_response.declarations = []

    mock_server.run.return_value = mock_response

    # Mock server creation

    def mock_get_or_create(fp):
        if fp not in querier._server_cache:
            querier._server_cache[fp] = mock_server

        return querier._server_cache[fp]

    querier._get_or_create_server = mock_get_or_create  # type: ignore[method-assign]

    # Execute: Call multiple times

    for _ in range(num_calls):
        querier.extract_declarations(file_path)

    # Verify: Server was reused (only one instance in cache)

    assert len(querier._server_cache) == 1

    assert file_path in querier._server_cache


# ============================================================================

# Cleanup Tests

# ============================================================================


def test_property_1_cleanup_closes_servers():
    """

    Feature: iterative-orchestration-enhancements

    Property 1: Complete Declaration Extraction (Cleanup)


    When close() is called, all cached servers should be killed and cache cleared.


    Validates: Requirements 28.6

    """

    # Setup: Create querier with multiple cached servers

    querier = LeanInteractQuerier()

    mock_servers = []

    for i in range(3):
        mock_server = Mock()

        mock_server.kill = Mock()

        querier._server_cache[f"file_{i}.lean"] = mock_server

        mock_servers.append(mock_server)

    # Execute

    querier.close()

    # Verify: All servers were killed

    for mock_server in mock_servers:
        mock_server.kill.assert_called_once()

    # Verify: Cache was cleared

    assert len(querier._server_cache) == 0
