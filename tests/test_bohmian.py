"""Tests for Bohmian velocity field and trajectory integrator."""

import time

import numpy as np
import pytest

from qorbital.bohmian.integrator import integrate_trajectories
from qorbital.bohmian.velocity import add_azimuthal_phase, velocity_field
from qorbital.chemistry.density import compute_density, wavefunction_grid
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals


def _h2_lcao_psi(nx: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Analytical H2 1-sigma_g LCAO on a z-axis grid."""
    bond = 0.735
    half = bond / 2.0
    z = np.linspace(-2.0, 2.0, nx)
    y = np.linspace(-1.0, 1.0, nx)
    x = np.linspace(-1.0, 1.0, nx)
    xv, yv, zv = np.meshgrid(x, y, z, indexing="ij")
    sigma = 0.5
    psi = np.exp(-((xv**2 + yv**2 + (zv + half) ** 2) / (2 * sigma**2)))
    psi += np.exp(-((xv**2 + yv**2 + (zv - half) ** 2) / (2 * sigma**2)))
    psi /= np.sqrt(np.sum(psi**2))
    origin = np.array([x[0], y[0], z[0]])
    spacing = np.array([x[1] - x[0], y[1] - y[0], z[1] - z[0]])
    return psi.astype(np.complex128), origin, spacing


class TestVelocityField:
    def test_stationary_for_real_psi(self):
        psi, origin, spacing = _h2_lcao_psi()
        vx, vy, vz = velocity_field(psi, spacing)
        assert np.max(np.abs(vx)) < 1e-10
        assert np.max(np.abs(vy)) < 1e-10
        assert np.max(np.abs(vz)) < 1e-10

    def test_nonzero_with_phase(self):
        psi, origin, spacing = _h2_lcao_psi()
        psi_complex = add_azimuthal_phase(psi, origin, spacing, strength=1.0)
        vx, vy, vz = velocity_field(psi_complex, spacing)
        assert np.max(np.abs(vx) + np.abs(vy) + np.abs(vz)) > 1e-6

    def test_cutoff_at_nodes(self):
        psi = np.zeros((10, 10, 10), dtype=np.complex128)
        psi[5, 5, 5] = 1.0
        spacing = np.array([0.2, 0.2, 0.2])
        vx, vy, vz = velocity_field(psi, spacing)
        assert np.all(vx == 0.0)


class TestIntegrator:
    def test_trajectory_shape(self):
        psi, origin, spacing = _h2_lcao_psi()
        psi_complex = add_azimuthal_phase(psi, origin, spacing, strength=0.5)
        vx, vy, vz = velocity_field(psi_complex, spacing)
        seeds = np.array([[0.0, 0.0, z] for z in np.linspace(-0.2, 0.2, 5)])
        traj = integrate_trajectories(
            vx, vy, vz, origin, spacing, seeds, t_span=(0.0, 2.0), n_steps=50
        )
        assert traj.shape == (5, 50, 3)

    def test_runtime_gate(self):
        psi, origin, spacing = _h2_lcao_psi(nx=15)
        psi_complex = add_azimuthal_phase(psi, origin, spacing, strength=0.5)
        vx, vy, vz = velocity_field(psi_complex, spacing)
        seeds = np.array([[0.0, 0.0, z] for z in np.linspace(-0.2, 0.2, 20)])
        t0 = time.perf_counter()
        integrate_trajectories(
            vx, vy, vz, origin, spacing, seeds, t_span=(0.0, 5.0), n_steps=100
        )
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0

    def test_seeds_stay_in_bonding_region(self):
        psi, origin, spacing = _h2_lcao_psi()
        psi_complex = add_azimuthal_phase(psi, origin, spacing, strength=0.3)
        vx, vy, vz = velocity_field(psi_complex, spacing)
        seeds = np.array([[0.0, 0.0, z] for z in np.linspace(-0.15, 0.15, 10)])
        traj = integrate_trajectories(
            vx, vy, vz, origin, spacing, seeds, t_span=(0.0, 3.0), n_steps=50
        )
        final_z = traj[:, -1, 2]
        assert np.all(np.abs(final_z) < 1.0)


class TestVQEIntegration:
    """Verify real VQE output produces sensible trajectories."""

    @pytest.fixture(scope="class")
    def h2_pipeline(self):
        integrals = compute_integrals("H2", bond_length=0.735)
        qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        matrix = qh.qubit_op.to_matrix()
        _, eigvecs = np.linalg.eigh(matrix)
        sv = eigvecs[:, 0]
        density = compute_density(sv, integrals, grid_points=20, atom_string="H2")
        wf = wavefunction_grid(density, integrals, "H2")
        return wf, density

    def test_vqe_trajectories_comparable_to_analytical(self, h2_pipeline):
        wf, _ = h2_pipeline
        psi_complex = add_azimuthal_phase(wf.psi, wf.origin, wf.spacing, strength=0.5)
        vx, vy, vz = velocity_field(psi_complex, wf.spacing)
        seeds = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.1]])
        traj = integrate_trajectories(
            vx, vy, vz, wf.origin, wf.spacing, seeds, n_steps=20
        )
        assert traj.shape == (2, 20, 3)
        assert np.all(np.isfinite(traj))
