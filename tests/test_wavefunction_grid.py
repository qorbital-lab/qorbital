"""Tests for wavefunction_grid extraction."""

import numpy as np
import pytest

from qorbital.chemistry.density import (
    compute_density,
    wavefunction_grid,
    wavefunction_grid_from_statevector,
)
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import MolecularIntegrals, compute_integrals


@pytest.fixture(scope="module")
def h2_integrals() -> MolecularIntegrals:
    return compute_integrals("H2", bond_length=0.735, basis="sto-3g")


@pytest.fixture(scope="module")
def h2_statevector(h2_integrals: MolecularIntegrals) -> np.ndarray:
    qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
    matrix = qh.qubit_op.to_matrix()
    _, eigvecs = np.linalg.eigh(matrix)
    return eigvecs[:, 0]


@pytest.fixture(scope="module")
def h2_density(h2_statevector, h2_integrals):
    return compute_density(
        h2_statevector, h2_integrals, grid_points=30, atom_string="H2"
    )


class TestWavefunctionGrid:
    def test_returns_complex_array(self, h2_density, h2_integrals):
        wf = wavefunction_grid(h2_density, h2_integrals, "H2")
        assert wf.psi.dtype == np.complex128
        assert wf.psi.shape == h2_density.grid_shape

    def test_real_for_ground_state(self, h2_density, h2_integrals):
        wf = wavefunction_grid(h2_density, h2_integrals, "H2")
        assert np.allclose(wf.psi.imag, 0.0, atol=1e-10)

    def test_occupation_matches_natural_orbital(self, h2_density, h2_integrals):
        wf = wavefunction_grid(h2_density, h2_integrals, "H2")
        assert wf.occupation == pytest.approx(
            h2_density.natural_occupations[0], abs=1e-6
        )

    def test_psi_nonzero_where_density_high(self, h2_density, h2_integrals):
        wf = wavefunction_grid(h2_density, h2_integrals, "H2")
        density_from_psi = np.abs(wf.psi) ** 2
        assert np.max(density_from_psi) > 0.01
        peak_psi = np.argmax(density_from_psi.ravel())
        peak_rho = np.argmax(h2_density.density.ravel())
        assert peak_psi == peak_rho

    def test_convenience_wrapper(self, h2_statevector, h2_integrals):
        wf = wavefunction_grid_from_statevector(
            h2_statevector, h2_integrals, "H2", grid_points=20
        )
        assert wf.psi.shape == (20, 20, 20)

    def test_phase_injection(self, h2_density, h2_integrals):
        wf = wavefunction_grid(h2_density, h2_integrals, "H2", phase=0.5)
        assert not np.allclose(wf.psi.imag, 0.0)
