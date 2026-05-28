import numpy as np
import pytest

from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.vqe.solver import (
    VQEIterationData,
    VQEResult,
    run_vqe,
    run_vqe_from_hamiltonian,
)

FCI_TOTAL_ENERGY_H2 = -1.137306035753


class TestVQEH2:
    @pytest.fixture(scope="class")
    def h2_result(self) -> VQEResult:
        return run_vqe("H2", bond_length=0.735, basis="sto-3g")

    def test_total_energy_matches_fci(self, h2_result):
        assert h2_result.total_energy == pytest.approx(FCI_TOTAL_ENERGY_H2, abs=1e-5)

    def test_electronic_plus_nuclear_equals_total(self, h2_result):
        total = h2_result.electronic_energy + h2_result.nuclear_repulsion_energy
        assert total == pytest.approx(h2_result.total_energy, abs=1e-12)

    def test_returns_optimal_parameters(self, h2_result):
        assert isinstance(h2_result.optimal_parameters, np.ndarray)
        assert h2_result.optimal_parameters.size > 0

    def test_returns_statevector(self, h2_result):
        sv = h2_result.optimal_statevector
        assert isinstance(sv, np.ndarray)
        assert np.issubdtype(sv.dtype, np.complexfloating)
        assert sv.shape == (16,)

    def test_statevector_is_normalised(self, h2_result):
        norm = np.linalg.norm(h2_result.optimal_statevector)
        assert norm == pytest.approx(1.0, abs=1e-10)

    def test_convergence_history_populated(self, h2_result):
        assert len(h2_result.convergence_history) > 0
        first = h2_result.convergence_history[0]
        assert isinstance(first, VQEIterationData)
        assert isinstance(first.energy, float)
        assert isinstance(first.parameters, np.ndarray)

    def test_energy_converges_downward(self, h2_result):
        energies = [it.energy for it in h2_result.convergence_history]
        assert energies[-1] <= energies[0] + 1e-6

    def test_metadata_fields(self, h2_result):
        assert h2_result.ansatz_name == "UCCSD"
        assert h2_result.optimizer_name == "SLSQP"
        assert h2_result.num_iterations > 0


def test_user_callback_is_called():
    received = []

    def my_callback(data: VQEIterationData):
        received.append(data)

    run_vqe(
        "H2",
        bond_length=0.735,
        callback=my_callback,
        max_iterations=10,
    )
    assert len(received) > 0
    assert isinstance(received[0], VQEIterationData)


def test_cobyla_fallback():
    result = run_vqe(
        "H2",
        bond_length=0.735,
        optimizer="COBYLA",
        max_iterations=100,
    )
    assert result.total_energy == pytest.approx(FCI_TOTAL_ENERGY_H2, abs=1e-4)
    assert result.optimizer_name == "COBYLA"


def test_invalid_optimizer_raises():
    with pytest.raises(ValueError, match="Unknown optimizer"):
        run_vqe("H2", bond_length=0.735, optimizer="ADAM")


def test_run_vqe_from_hamiltonian():
    qh = build_hamiltonian("H2", bond_length=0.735)
    result = run_vqe_from_hamiltonian(qh)
    assert result.total_energy == pytest.approx(FCI_TOTAL_ENERGY_H2, abs=1e-5)


def test_parity_2qr_also_converges():
    result = run_vqe(
        "H2",
        bond_length=0.735,
        mapping="parity",
        two_qubit_reduction=True,
    )
    assert result.total_energy == pytest.approx(FCI_TOTAL_ENERGY_H2, abs=1e-5)
    assert result.optimal_statevector.shape == (4,)
