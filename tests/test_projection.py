"""Validate eigenstate grid projection and superposition contract."""

import math

import numpy as np
import pytest

from qorbital.chemistry.density import (
    _ANGSTROM_TO_BOHR,
    WavefunctionGrid,
    compute_density,
    wavefunction_grid,
)
from qorbital.chemistry.eigenstates import lowest_eigenstates
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.superposition import (
    SuperpositionState,
    assert_common_grid,
    build_superposition_state,
    grid_overlap,
)


@pytest.fixture(scope="module")
def h2_superposition() -> SuperpositionState:
    return build_superposition_state("H2", bond_length=0.735, grid_points=30)


class TestSuperpositionContract:
    def test_contract_fields(self, h2_superposition: SuperpositionState):
        state = h2_superposition
        assert state.state_indices == (0, 1)
        assert state.omega == pytest.approx(state.E1 - state.E0, abs=1e-12)
        assert state.c0 == pytest.approx(1.0 / math.sqrt(2.0), abs=1e-12)
        assert state.c1 == pytest.approx(1.0 / math.sqrt(2.0), abs=1e-12)
        assert state.source == "exact_diag"
        assert state.E0 < state.E1

    def test_grid_in_bohr(self, h2_superposition: SuperpositionState):
        state = h2_superposition
        np.testing.assert_allclose(
            state.origin_angstrom * _ANGSTROM_TO_BOHR,
            state.origin,
            atol=1e-10,
        )
        np.testing.assert_allclose(
            state.spacing_angstrom * _ANGSTROM_TO_BOHR,
            state.spacing,
            atol=1e-10,
        )

    def test_phi0_phi1_same_grid(self, h2_superposition: SuperpositionState):
        state = h2_superposition
        assert state.phi0.shape == state.grid_shape
        assert state.phi1.shape == state.grid_shape

    def test_h2_phi0_matches_ground_density(self, h2_superposition: SuperpositionState):
        integrals = compute_integrals("H2", bond_length=0.735)
        qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        sv0, _ = lowest_eigenstates(qh, k=1)[0]
        density = compute_density(sv0, integrals, grid_points=30, atom_string="H2")
        wf_ref = wavefunction_grid(density, integrals, "H2")

        peak_phi0 = int(np.argmax(np.abs(h2_superposition.phi0) ** 2))
        peak_ref = int(np.argmax(np.abs(wf_ref.psi) ** 2))
        assert peak_phi0 == peak_ref

    def test_h2_phi0_phi1_orthogonal(self, h2_superposition: SuperpositionState):
        overlap = grid_overlap(
            h2_superposition.phi0,
            h2_superposition.phi1,
            h2_superposition.spacing,
        )
        assert abs(overlap) < 0.05

    def test_h2_phi0_normalized(self, h2_superposition: SuperpositionState):
        dV = float(np.prod(h2_superposition.spacing))
        norm_sq = float(np.sum(np.abs(h2_superposition.phi0) ** 2) * dV)
        assert norm_sq == pytest.approx(1.0, abs=1e-6)

    def test_invalid_grid_mismatch_raises(self):
        wf0 = WavefunctionGrid(
            psi=np.ones((2, 2, 2), dtype=np.complex128),
            grid_shape=(2, 2, 2),
            origin=np.array([0.0, 0.0, 0.0]),
            spacing=np.array([1.0, 1.0, 1.0]),
            occupation=2.0,
            orbital_index=0,
        )
        wf1 = WavefunctionGrid(
            psi=np.ones((2, 2, 2), dtype=np.complex128),
            grid_shape=(2, 2, 2),
            origin=np.array([0.1, 0.0, 0.0]),
            spacing=np.array([1.0, 1.0, 1.0]),
            occupation=2.0,
            orbital_index=0,
        )
        with pytest.raises(ValueError, match="origin mismatch"):
            assert_common_grid(wf0, wf1)


class TestLiHProjection:
    @pytest.mark.slow
    def test_parity_2qr_lih_finite(self):
        state = build_superposition_state("LiH", bond_length=1.596, grid_points=40)
        assert np.all(np.isfinite(state.phi0))
        assert np.all(np.isfinite(state.phi1))
        assert state.source == "exact_diag"
        assert state.phi0.shape == state.phi1.shape == state.grid_shape
