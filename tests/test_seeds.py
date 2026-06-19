"""Tests for quantum-equilibrium trajectory seeds."""

import numpy as np

from qorbital.bohmian.seeds import sample_superposition_seeds
from qorbital.chemistry.superposition import build_superposition_state


class TestSuperpositionSeeds:
    def test_seeds_inside_grid_bounds(self):
        state = build_superposition_state("H2", bond_length=0.735, grid_points=20)
        seeds = sample_superposition_seeds(state, 30, rng=np.random.default_rng(0))
        origin = state.origin_angstrom
        spacing = state.spacing_angstrom
        nx, ny, nz = state.grid_shape
        max_corner = origin + spacing * np.array([nx, ny, nz])
        assert seeds.shape == (30, 3)
        assert np.all(seeds >= origin - 1e-9)
        assert np.all(seeds <= max_corner + 1e-9)

    def test_hardware_ground_superposition_source(self):
        from qorbital.chemistry.hamiltonian import build_hamiltonian
        from qorbital.chemistry.integrals import compute_integrals
        from qorbital.chemistry.superposition import (
            build_superposition_from_ground_state,
        )

        integrals = compute_integrals("H2", bond_length=0.735)
        qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        matrix = qh.qubit_op.to_matrix()
        _, eigvecs = np.linalg.eigh(matrix)
        sv = eigvecs[:, 0]
        state = build_superposition_from_ground_state(
            sv, integrals, "H2", grid_points=20
        )
        assert state.source == "hardware_ground+hf_lumo"
        seeds = sample_superposition_seeds(state, 10, rng=np.random.default_rng(1))
        assert seeds.shape == (10, 3)
