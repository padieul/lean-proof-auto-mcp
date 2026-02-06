"""Pytest configuration for eval investigation tests."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "eval_investigation: marks tests as eval investigation tests "
        "(excluded from CI/CD, for manual investigation only)",
    )
