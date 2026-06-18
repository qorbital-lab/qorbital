"""Validate exact eigenstate extraction via dense diagonalization."""

import numpy as np
import pytest

from qorbital.chemistry.eigenstates import lowest_eigenstates
from qorbital.chemistry.hamiltonian import QubitHamiltonian, build_hamiltonian

H2_REF_ELECTRONIC_GROUND_STATE = -1.8572750302023797


@pytest.fixture(scope="module")
def h2_jw() -> QubitHamiltonian:
    return build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")


@pytest.fixture(scope="module")
def h2_parity_2qr() -> QubitHamiltonian:
    return build_hamiltonian(
        "H2", bond_length=0.735, mapping="parity", two_qubit_reduction=True
    )


class TestLowestEigenstates:
    def test_returns_k_pairs(self, h2_jw: QubitHamiltonian):
        pairs = lowest_eigenstates(h2_jw, k=2)
        assert len(pairs) == 2
        for psi, _energy in pairs:
            assert psi.shape == (2**h2_jw.num_qubits,)
            assert psi.dtype == np.complex128

    def test_energies_ascending(self, h2_jw: QubitHamiltonian):
        (_psi0, e0), (_psi1, e1) = lowest_eigenstates(h2_jw, k=2)
        assert e0 <= e1

    def test_orthonormal(self, h2_jw: QubitHamiltonian):
        pairs = lowest_eigenstates(h2_jw, k=2)
        for i, (psi_i, _) in enumerate(pairs):
            for j, (psi_j, _) in enumerate(pairs):
                overlap = np.vdot(psi_i, psi_j)
                expected = 1.0 if i == j else 0.0
                np.testing.assert_allclose(overlap, expected, atol=1e-10)

    def test_energy_expectation(self, h2_jw: QubitHamiltonian):
        matrix = h2_jw.qubit_op.to_matrix()
        for psi, energy in lowest_eigenstates(h2_jw, k=2):
            expected = float(np.real(np.vdot(psi, matrix @ psi)))
            np.testing.assert_allclose(energy, expected, atol=1e-10)

    def test_matches_eigvalsh(self, h2_jw: QubitHamiltonian):
        matrix = h2_jw.qubit_op.to_matrix()
        ref = np.linalg.eigvalsh(matrix)[:2]
        energies = [energy for _psi, energy in lowest_eigenstates(h2_jw, k=2)]
        np.testing.assert_allclose(energies, ref, atol=1e-10)

    def test_h2_ground_energy(self, h2_jw: QubitHamiltonian):
        _psi0, e0 = lowest_eigenstates(h2_jw, k=1)[0]
        np.testing.assert_allclose(e0, H2_REF_ELECTRONIC_GROUND_STATE, atol=1e-10)

    def test_parity_2qr_same_ground(
        self, h2_jw: QubitHamiltonian, h2_parity_2qr: QubitHamiltonian
    ):
        _, e0_jw = lowest_eigenstates(h2_jw, k=1)[0]
        _, e0_p2qr = lowest_eigenstates(h2_parity_2qr, k=1)[0]
        np.testing.assert_allclose(e0_jw, e0_p2qr, atol=1e-10)

    def test_full_hilbert_space(self, h2_parity_2qr: QubitHamiltonian):
        pairs = lowest_eigenstates(h2_parity_2qr, k=4)
        assert len(pairs) == 4

    def test_invalid_k_raises(self, h2_jw: QubitHamiltonian):
        with pytest.raises(ValueError, match="k must satisfy"):
            lowest_eigenstates(h2_jw, k=0)
        with pytest.raises(ValueError, match="k must satisfy"):
            lowest_eigenstates(h2_jw, k=17)
