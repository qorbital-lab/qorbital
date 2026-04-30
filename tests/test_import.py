"""Smoke test: package is importable after editable install."""

import qorbital


def test_version():
    assert qorbital.__version__ == "0.1.0"
