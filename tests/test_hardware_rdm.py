"""Tests for the hardware 1-RDM measurement primitive (B10).

The non-hardware tests are the real correctness gate: ``measure_rdm1`` run on an
exact ``StatevectorEstimator`` must reproduce the statevector ``_extract_rdm1`` to
machine precision, which validates the Hermitian observable construction and the
symmetric reconstruction without touching any device.
"""

import os

import numpy as np
import pytest
from qiskit.primitives import StatevectorEstimator
from qiskit.providers.fake_provider import GenericBackendV2

from qorbital.chemistry.density import _extract_rdm1
from qorbital.chemistry.hamiltonian import build_hamiltonian, make_mapper
from qorbital.vqe.backends import IONQ_API_KEY_ENV, Backend, make_estimator
from qorbital.vqe.hardware_rdm import (
    MeasuredRDM,
    _hermitian_rdm_observables,
    measure_rdm1,
)
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
def h2_converged():
    """Converged H2/JW Hamiltonian, parameters, and exact statevector 1-RDM."""
    qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
    result = run_vqe_from_hamiltonian(qh, max_iterations=50)
    mapper = make_mapper(qh.mapping, qh.num_particles, qh.two_qubit_reduction)
    exact = _extract_rdm1(result.optimal_statevector, qh.num_spatial_orbitals, mapper)
    return qh, result.optimal_parameters, exact


class TestMeasureRDMExact:
    """measure_rdm1 on an exact estimator == statevector extraction."""

    def test_matches_exact_statevector(self, h2_converged):
        qh, params, exact = h2_converged
        measured = measure_rdm1(qh, params, StatevectorEstimator())
        np.testing.assert_allclose(measured.rdm1_mo, exact, atol=1e-6)

    def test_returns_dataclass(self, h2_converged):
        qh, params, _ = h2_converged
        assert isinstance(measure_rdm1(qh, params, StatevectorEstimator()), MeasuredRDM)

    def test_symmetric(self, h2_converged):
        qh, params, _ = h2_converged
        measured = measure_rdm1(qh, params, StatevectorEstimator())
        np.testing.assert_allclose(measured.rdm1_mo, measured.rdm1_mo.T, atol=1e-10)

    def test_trace_matches_electrons(self, h2_converged):
        qh, params, _ = h2_converged
        measured = measure_rdm1(qh, params, StatevectorEstimator())
        assert np.trace(measured.rdm1_mo) == pytest.approx(sum(qh.num_particles))

    def test_provenance_populated(self, h2_converged):
        qh, params, _ = h2_converged
        measured = measure_rdm1(qh, params, StatevectorEstimator())
        n_orb = qh.num_spatial_orbitals
        assert measured.num_spatial_orbitals == n_orb
        assert measured.mapping == "jordan_wigner"
        assert measured.term_evs.shape == (n_orb * (n_orb + 1) // 2,)
        assert measured.term_stds.shape == measured.term_evs.shape
        assert len(measured.parameters) == len(params)


class TestObservables:
    def test_observable_count(self):
        qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        mapper = make_mapper(qh.mapping, qh.num_particles, qh.two_qubit_reduction)
        n_orb = qh.num_spatial_orbitals
        terms = _hermitian_rdm_observables(n_orb, mapper)
        assert len(terms) == n_orb * (n_orb + 1) // 2

    def test_all_hermitian(self):
        qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        mapper = make_mapper(qh.mapping, qh.num_particles, qh.two_qubit_reduction)
        for _, _, op in _hermitian_rdm_observables(qh.num_spatial_orbitals, mapper):
            mat = op.to_matrix()
            np.testing.assert_allclose(mat, mat.conj().T, atol=1e-12)

    def test_lih_observables_mapper_aware(self):
        """Parity + 2-qubit reduction: observables match the reduced qubit count."""
        qh = build_hamiltonian(
            "LiH", bond_length=1.596, mapping="parity", two_qubit_reduction=True
        )
        mapper = make_mapper(qh.mapping, qh.num_particles, qh.two_qubit_reduction)
        terms = _hermitian_rdm_observables(qh.num_spatial_orbitals, mapper)
        assert terms[0][2].num_qubits == qh.qubit_op.num_qubits


class _StubData:
    def __init__(self, evs):
        self.evs = evs


class _StubJob:
    def __init__(self, evs):
        self._evs = evs

    def result(self):
        return [type("PubResult", (), {"data": _StubData(self._evs)})()]


class _StubEstimator:
    """Returns a fixed EV vector; ``.backend`` lets the ISA transpile run."""

    def __init__(self, evs):
        self._evs = np.asarray(evs)
        self.backend = GenericBackendV2(num_qubits=4, seed=0)

    def run(self, pubs):
        return _StubJob(self._evs)


class TestReconstructionWiring:
    """EVs map to the right matrix positions (diagonal direct, off-diagonal /2)."""

    def test_ev_to_matrix_positions(self):
        qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        # Pairs are (0,0), (0,1), (1,1) for 2 spatial orbitals.
        evs = np.array([1.4, 0.6, 0.2])
        params = np.zeros(qh.qubit_op.num_qubits)
        measured = measure_rdm1(qh, params, _StubEstimator(evs))
        assert measured.term_pairs == [(0, 0), (0, 1), (1, 1)]
        assert measured.rdm1_mo[0, 0] == pytest.approx(1.4)
        assert measured.rdm1_mo[1, 1] == pytest.approx(0.2)
        assert measured.rdm1_mo[0, 1] == pytest.approx(0.3)
        assert measured.rdm1_mo[1, 0] == pytest.approx(0.3)


@pytest.mark.hardware
@_requires_key
def test_measure_rdm_on_ionq_sim(h2_converged):
    qh, params, exact = h2_converged
    measured = measure_rdm1(qh, params, make_estimator(Backend.IONQ_SIM, shots=2000))
    np.testing.assert_allclose(measured.rdm1_mo, measured.rdm1_mo.T, atol=1e-9)
    assert np.trace(measured.rdm1_mo) == pytest.approx(sum(qh.num_particles), abs=0.3)
    # Genuine shot noise: not exactly the exact RDM.
    assert not np.allclose(measured.rdm1_mo, exact, atol=1e-6)
