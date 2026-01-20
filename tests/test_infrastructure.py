"""Test infrastructure validation - ensures jsonschema and hypothesis are available."""


def test_jsonschema_available():
    """Verify jsonschema library is available."""
    from jsonschema import validate  # type: ignore[import-untyped]

    # Simple schema validation test
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    instance = {"name": "test"}
    validate(instance=instance, schema=schema)


def test_hypothesis_available():
    """Verify hypothesis library is available."""
    from hypothesis import given
    from hypothesis import strategies as st

    @given(st.integers())
    def check_identity(x):
        assert x == x

    check_identity()


def test_pytest_working():
    """Verify pytest is working."""
    assert True
