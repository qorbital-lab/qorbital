"""Shared pytest configuration."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "superposition: B4 two-state velocity tests")
    config.addinivalue_line(
        "markers", "integrator: B5 time-dependent trajectory integration tests"
    )
    config.addinivalue_line("markers", "periodic: B5 periodicity checks")
