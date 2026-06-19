"""Tests for the hardware noise ensemble orchestrator (B10).

Non-hardware tests run on the exact AER/statevector path (all members identical,
so they exercise assembly + caching, not variance); the hardware-marked test
checks that real shot noise produces a non-zero spread.
"""

import os

import numpy as np
import pytest

import qorbital.bohmian.noise_ensemble as ne
from qorbital.bohmian.noise_ensemble import (
    NoiseEnsemble,
    ensemble_to_cloud,
    measure_rdm_ensemble,
)
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.vqe.backends import IONQ_API_KEY_ENV, Backend
from qorbital.vqe.solver import run_vqe_from_hamiltonian

_HAS_IONQ_KEY = bool(
    os.getenv(IONQ_API_KEY_ENV)
    or os.getenv("QISKIT_IONQ_API_TOKEN")
    or os.getenv("IONQ_API_TOKEN")
)
_requires_key = pytest.mark.skipif(
    not _HAS_IONQ_KEY, reason=f"requires {IONQ_API_KEY_ENV} (no hardware in CI)"
)


@pytest.fixture(scope="module")
def h2_params():
    """Converged H2 parameters, computed once to skip per-test VQE re-runs."""
    qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
    return run_vqe_from_hamiltonian(qh, max_iterations=50).optimal_parameters


@pytest.fixture(scope="module")
def aer_ensemble(h2_params):
    return measure_rdm_ensemble(
        "H2", m=3, backend=Backend.AER, grid_points=20, parameters=h2_params
    )


class TestEnsembleAssembly:
    def test_produces_m_members(self, aer_ensemble):
        assert isinstance(aer_ensemble, NoiseEnsemble)
        assert aer_ensemble.m == 3
        assert len(aer_ensemble.densities) == 3
        assert len(aer_ensemble.trajectory_sets) == 3

    def test_trajectory_shape(self, aer_ensemble):
        traj = aer_ensemble.trajectory_sets[0]
        assert traj.ndim == 3 and traj.shape[2] == 3

    def test_feeds_uncertainty_cloud(self, aer_ensemble):
        cloud = ensemble_to_cloud(aer_ensemble)
        assert cloud.density.shape == aer_ensemble.grid_shape
        assert cloud.density.sum() == pytest.approx(1.0, abs=1e-6)


class TestCaching:
    def test_roundtrip_no_device_calls(self, tmp_path, h2_params, monkeypatch):
        cache = tmp_path / "h2_ens.npz"
        first = measure_rdm_ensemble(
            "H2",
            m=3,
            backend=Backend.AER,
            grid_points=20,
            parameters=h2_params,
            cache_path=cache,
        )
        assert cache.exists()

        # A second run must replay from cache without constructing any estimator.
        def _boom(*_args, **_kwargs):
            raise AssertionError("cache replay must not touch the device")

        monkeypatch.setattr(ne, "make_estimator", _boom)
        second = measure_rdm_ensemble(
            "H2",
            m=3,
            backend=Backend.AER,
            grid_points=20,
            parameters=h2_params,
            cache_path=cache,
        )
        assert second.m == 3
        np.testing.assert_allclose(
            second.measured_rdms[0].rdm1_mo, first.measured_rdms[0].rdm1_mo
        )
        np.testing.assert_allclose(
            second.measured_rdms[0].term_evs, first.measured_rdms[0].term_evs
        )


@pytest.mark.hardware
@_requires_key
def test_ionq_sim_ensemble_has_variance(h2_params):
    ensemble = measure_rdm_ensemble(
        "H2",
        m=3,
        shots=1000,
        backend=Backend.IONQ_SIM,
        grid_points=20,
        parameters=h2_params,
    )
    rdms = np.stack([mr.rdm1_mo for mr in ensemble.measured_rdms])
    # Shot noise => the M runs are not all identical.
    assert np.std(rdms, axis=0).max() > 0.0
