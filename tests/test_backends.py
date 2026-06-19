"""Tests for the VQE backend / estimator factory (B7)."""

import os

import pytest
from qiskit.primitives import StatevectorEstimator

from qorbital.vqe.backends import (
    IONQ_API_KEY_ENV,
    Backend,
    make_estimator,
    make_local_estimator,
)

_HAS_IONQ_KEY = bool(
    os.getenv(IONQ_API_KEY_ENV)
    or os.getenv("QISKIT_IONQ_API_TOKEN")
    or os.getenv("IONQ_API_TOKEN")
)
_requires_key = pytest.mark.skipif(
    not _HAS_IONQ_KEY, reason=f"requires {IONQ_API_KEY_ENV} (no hardware in CI)"
)


class TestLocalEstimator:
    def test_aer_returns_statevector(self):
        assert isinstance(make_estimator(Backend.AER), StatevectorEstimator)

    def test_make_local_estimator_is_statevector(self):
        assert isinstance(make_local_estimator(), StatevectorEstimator)


class TestIonQEstimator:
    def test_missing_key_raises(self, monkeypatch):
        for env_var in (IONQ_API_KEY_ENV, "QISKIT_IONQ_API_TOKEN", "IONQ_API_TOKEN"):
            monkeypatch.delenv(env_var, raising=False)
        with pytest.raises(RuntimeError, match=IONQ_API_KEY_ENV):
            make_estimator(Backend.IONQ_SIM)

    @pytest.mark.hardware
    @_requires_key
    def test_ionq_sim_returns_real_primitive(self):
        from qiskit.primitives import BackendEstimatorV2

        est = make_estimator(Backend.IONQ_SIM, shots=500)
        assert isinstance(est, BackendEstimatorV2)
        # BackendV1.name is a method, not a string attribute.
        assert est.backend.name() == "ionq_simulator"

    @pytest.mark.hardware
    @_requires_key
    def test_ionq_aria_maps_to_qpu(self):
        from qiskit.primitives import BackendEstimatorV2

        est = make_estimator(Backend.IONQ_ARIA)
        assert isinstance(est, BackendEstimatorV2)
        assert est.backend.name() == "ionq_qpu.aria-1"
