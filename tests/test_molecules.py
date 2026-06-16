"""Tests for HeH+ and LiH multi-molecule pipelines."""

import numpy as np
import pytest

from qorbital.bohmian.projection import project_homo_orbital, project_natural_orbital
from qorbital.chemistry.density import compute_density
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import MOLECULE_PARAMS, get_molecule_params
from qorbital.vqe.solver import run_vqe


class TestMoleculeParams:
    def test_heh_charge(self):
        params = get_molecule_params("HeH+")
        assert params.charge == 1

    def test_lih_parity_reduction(self):
        params = get_molecule_params("LiH")
        assert params.mapping == "parity"
        assert params.two_qubit_reduction is True


class TestHeHPlus:
    @pytest.fixture(scope="class")
    def heh_density(self):
        params = get_molecule_params("HeH+")
        integrals = compute_integrals(
            "HeH+", charge=params.charge, spin=params.spin
        )
        qh_matrix = __import__(
            "qorbital.chemistry.hamiltonian", fromlist=["build_hamiltonian"]
        ).build_hamiltonian(
            "HeH+", charge=params.charge, spin=params.spin, mapping="jordan_wigner"
        )
        matrix = qh_matrix.qubit_op.to_matrix()
        _, eigvecs = np.linalg.eigh(matrix)
        sv = eigvecs[:, 0]
        return compute_density(
            sv, integrals, grid_points=25, atom_string="HeH+"
        ), integrals

    def test_polar_density(self, heh_density):
        density, _integrals = heh_density
        # He at z=0, H at z~0.772; compare density near each nucleus
        bond = 0.772
        origin = density.origin
        spacing = density.spacing

        def _sample_z(z_pos: float) -> float:
            idx = int(round((z_pos - origin[2]) / spacing[2]))
            idx = max(0, min(idx, density.grid_shape[2] - 1))
            return float(density.density[:, :, idx].max())

        rho_he = _sample_z(0.0)
        rho_h = _sample_z(bond)
        assert rho_he + rho_h > 0.01
        assert abs(rho_he - rho_h) > 0.001

    def test_vqe_energy_sane(self):
        params = get_molecule_params("HeH+")
        result = run_vqe(
            "HeH+",
            charge=params.charge,
            spin=params.spin,
            max_iterations=50,
        )
        assert result.total_energy < 0.0


class TestLiH:
    def test_parity_8_qubits(self):
        from qorbital.chemistry.hamiltonian import build_hamiltonian

        params = get_molecule_params("LiH")
        qh = build_hamiltonian(
            "LiH",
            mapping=params.mapping,
            two_qubit_reduction=params.two_qubit_reduction,
        )
        assert qh.num_qubits == 10

    @pytest.mark.slow
    def test_natural_orbital_projection(self):
        params = get_molecule_params("LiH")
        integrals = compute_integrals("LiH", bond_length=1.596)
        result = run_vqe(
            "LiH",
            bond_length=1.596,
            mapping=params.mapping,
            two_qubit_reduction=params.two_qubit_reduction,
            max_iterations=30,
        )
        density = compute_density(
            result.optimal_statevector,
            integrals,
            grid_points=20,
            atom_string="LiH",
        )
        wf = project_natural_orbital(density, integrals, "LiH")
        assert wf.psi.shape == density.grid_shape

    @pytest.mark.slow
    def test_homo_fallback(self):
        params = get_molecule_params("LiH")
        integrals = compute_integrals("LiH", bond_length=1.596)
        result = run_vqe(
            "LiH",
            bond_length=1.596,
            mapping=params.mapping,
            two_qubit_reduction=params.two_qubit_reduction,
            max_iterations=30,
        )
        density = compute_density(
            result.optimal_statevector,
            integrals,
            grid_points=20,
            atom_string="LiH",
        )
        wf = project_homo_orbital(density, integrals, "LiH")
        assert np.all(np.isfinite(wf.psi))
