"""Smoke test: package is importable after editable install."""

import qorbital
import qorbital.bohmian
import qorbital.chemistry
import qorbital.viz
import qorbital.vqe
import qorbital.webapp


def test_version():
    assert qorbital.__version__ == "0.1.0"
