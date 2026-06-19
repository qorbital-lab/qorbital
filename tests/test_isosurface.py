"""Tests for isosurface level selection."""

import numpy as np
import pytest

from qorbital.chemistry.density import compute_density
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.viz.isosurface import (
    integrated_electron_count,
    isovalue_enclosing_fraction,
)


@pytest.fixture
def h2_density():
    integrals = compute_integrals("H2", bond_length=0.735)
    qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
    matrix = qh.qubit_op.to_matrix()
    _, eigvecs = np.linalg.eigh(matrix)
    sv = eigvecs[:, 0]
    return compute_density(sv, integrals, grid_points=40, atom_string="H2")


class TestIsovalueFromFraction:
    def test_integrated_electron_count_h2(self, h2_density):
        count = integrated_electron_count(h2_density.density, h2_density.spacing)
        assert count == pytest.approx(h2_density.total_electrons, rel=0.05)

    def test_enclosing_fraction_monotone(self, h2_density):
        iso90, frac90 = isovalue_enclosing_fraction(
            h2_density.density, h2_density.spacing, 0.9
        )
        iso50, frac50 = isovalue_enclosing_fraction(
            h2_density.density, h2_density.spacing, 0.5
        )
        assert iso90 <= iso50
        assert frac90 == pytest.approx(0.9, abs=0.02)
        assert frac50 == pytest.approx(0.5, abs=0.02)
