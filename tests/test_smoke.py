# tests/test_smoke.py


def test_import_and_version():
    import lean_proof_auto_mcp

    assert hasattr(lean_proof_auto_mcp, "__version__")
    assert lean_proof_auto_mcp.__version__ == "0.2.0"
