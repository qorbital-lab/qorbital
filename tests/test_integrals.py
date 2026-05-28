"""Validate molecular integrals against PySCF reference values."""

import numpy as np
import pytest

from qorbital.chemistry.integrals import MolecularIntegrals, compute_integrals

H2_REF_HF_ENERGY = -1.116998996754
H2_REF_NUCLEAR_REPULSION = 0.719969


@pytest.fixture(scope="module")
def h2_integrals() -> MolecularIntegrals:
    return compute_integrals("H2", bond_length=0.735, basis="sto-3g")


class TestH2Integrals:
    """Validate H2/STO-3G integrals against PySCF 2.13.0 reference."""

    def test_hf_energy(self, h2_integrals: MolecularIntegrals):
        assert h2_integrals.hf_energy == pytest.approx(H2_REF_HF_ENERGY, abs=1e-6)

    def test_integral_shapes(self, h2_integrals: MolecularIntegrals):
        n = h2_integrals.num_spatial_orbitals
        assert n == 2
        assert h2_integrals.one_body_integrals.shape == (n, n)
        assert h2_integrals.two_body_integrals.shape == (n, n, n, n)
        assert (
            h2_integrals.overlap_integrals.shape[0]
            == h2_integrals.mo_coefficients.shape[0]
        )

    def test_num_particles(self, h2_integrals: MolecularIntegrals):
        assert h2_integrals.num_particles == (1, 1)

    def test_nuclear_repulsion(self, h2_integrals: MolecularIntegrals):
        assert h2_integrals.nuclear_repulsion_energy == pytest.approx(
            H2_REF_NUCLEAR_REPULSION, abs=1e-4
        )

    def test_one_body_symmetry(self, h2_integrals: MolecularIntegrals):
        np.testing.assert_allclose(
            h2_integrals.one_body_integrals,
            h2_integrals.one_body_integrals.T,
            atol=1e-12,
        )

    def test_problem_returned(self, h2_integrals: MolecularIntegrals):
        assert h2_integrals.problem is not None


class TestInterfaceVariants:
    """Verify compute_integrals handles different input forms."""

    def test_raw_atom_string(self):
        result = compute_integrals("H 0 0 0; H 0 0 0.735")
        assert result.num_particles == (1, 1)
        assert result.hf_energy == pytest.approx(H2_REF_HF_ENERGY, abs=1e-6)

    def test_custom_basis(self):
        result = compute_integrals("H2", bond_length=0.735, basis="6-31g")
        assert result.num_spatial_orbitals == 4

    def test_lih_smoke(self):
        result = compute_integrals("LiH", bond_length=1.596, basis="sto-3g")
        assert result.num_spatial_orbitals == 6
        assert result.hf_energy < 0
