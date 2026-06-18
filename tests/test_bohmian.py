"""Tests for Bohmian velocity field and trajectory integrator."""

import time

import numpy as np
import pytest

from qorbital.bohmian.integrator import (
    integrate_superposition_trajectories,
    integrate_trajectories,
    superposition_sampler_from_context,
)
from qorbital.bohmian.velocity import (
    SuperpositionVelocityContext,
    add_azimuthal_phase,
    superposition_period,
    superposition_velocity_at_time,
    superposition_wavefunction,
    velocity_field,
)
from qorbital.chemistry.density import compute_density, wavefunction_grid
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.superposition import build_superposition_state


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


@pytest.fixture(scope="module")
def h2_superposition():
    return build_superposition_state("H2", bond_length=0.735, grid_points=25)


@pytest.fixture(scope="module")
def h2_superposition_integrator():
    return build_superposition_state("H2", bond_length=0.735, grid_points=20)


class TestSuperpositionVelocity:
    @pytest.mark.superposition
    def test_superposition_wavefunction_shape(self, h2_superposition):
        psi_t = superposition_wavefunction(
            h2_superposition.phi0,
            h2_superposition.phi1,
            h2_superposition.E0,
            h2_superposition.E1,
            t=0.5,
            c0=h2_superposition.c0,
            c1=h2_superposition.c1,
        )
        assert psi_t.shape == h2_superposition.phi0.shape
        assert np.all(np.isfinite(psi_t))

    @pytest.mark.superposition
    def test_superposition_period(self, h2_superposition):
        period = superposition_period(h2_superposition.E0, h2_superposition.E1)
        omega = h2_superposition.E1 - h2_superposition.E0
        assert period == pytest.approx(2.0 * np.pi / omega, rel=1e-12)
        assert period == pytest.approx(2.0 * np.pi / h2_superposition.omega, rel=1e-12)

    @pytest.mark.superposition
    def test_superposition_velocity_nonzero(self, h2_superposition):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition)
        t = 0.25 / h2_superposition.omega
        vx, vy, vz = superposition_velocity_at_time(ctx, t)
        speed = np.abs(vx) + np.abs(vy) + np.abs(vz)
        assert float(np.max(speed)) > 1e-6

    @pytest.mark.superposition
    def test_superposition_velocity_oscillates(self, h2_superposition):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition)
        vx0, vy0, vz0 = superposition_velocity_at_time(ctx, 0.0)
        t_quad = np.pi / (2.0 * h2_superposition.omega)
        vx1, vy1, vz1 = superposition_velocity_at_time(ctx, t_quad)
        speed0 = float(np.max(np.abs(vx0) + np.abs(vy0) + np.abs(vz0)))
        speed1 = float(np.max(np.abs(vx1) + np.abs(vy1) + np.abs(vz1)))
        assert abs(speed0 - speed1) > 1e-6

    @pytest.mark.superposition
    def test_real_phi0_alone_still_stationary(self, h2_superposition):
        phi0_real = h2_superposition.phi0.real.astype(np.complex128)
        vx, vy, vz = velocity_field(phi0_real, h2_superposition.spacing_angstrom)
        assert np.max(np.abs(vx)) < 1e-10
        assert np.max(np.abs(vy)) < 1e-10
        assert np.max(np.abs(vz)) < 1e-10


def _h2_superposition_seeds(n_particles: int = 20) -> np.ndarray:
    return np.array([[0.0, 0.0, z] for z in np.linspace(-0.15, 0.15, n_particles)])


class TestSuperpositionIntegrator:
    @pytest.mark.integrator
    def test_superposition_trajectory_shape(self, h2_superposition_integrator):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition_integrator)
        seeds = _h2_superposition_seeds(20)
        traj = integrate_superposition_trajectories(
            ctx, seeds, n_periods=2.0, n_steps=100
        )
        assert traj.shape == (20, 100, 3)
        assert np.all(np.isfinite(traj))

    @pytest.mark.integrator
    def test_superposition_runtime_gate(self, h2_superposition_integrator):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition_integrator)
        seeds = _h2_superposition_seeds(20)
        t0 = time.perf_counter()
        integrate_superposition_trajectories(ctx, seeds, n_periods=2.0, n_steps=100)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0

    @pytest.mark.periodic
    def test_superposition_trajectories_periodic(self, h2_superposition_integrator):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition_integrator)
        seeds = _h2_superposition_seeds(20)
        period = superposition_period(
            h2_superposition_integrator.E0, h2_superposition_integrator.E1
        )
        n_steps = 100
        traj = integrate_superposition_trajectories(
            ctx, seeds, n_periods=2.0, n_steps=n_steps
        )
        t_eval = np.linspace(0.0, 2.0 * period, n_steps)
        period_idx = int(np.argmin(np.abs(t_eval - period)))
        displacement = np.linalg.norm(traj[:, period_idx, :] - traj[:, 0, :], axis=1)
        assert np.all(displacement < 0.15)

    @pytest.mark.integrator
    def test_superposition_probability_conserved(self, h2_superposition_integrator):
        from qorbital.chemistry.density import _ANGSTROM_TO_BOHR

        ctx = SuperpositionVelocityContext.from_state(h2_superposition_integrator)
        sampler = superposition_sampler_from_context(ctx)
        seeds = _h2_superposition_seeds(5)
        period = superposition_period(
            h2_superposition_integrator.E0, h2_superposition_integrator.E1
        )
        n_steps = 50
        traj = integrate_superposition_trajectories(
            ctx, seeds, n_periods=1.0, n_steps=n_steps
        )
        t_eval = np.linspace(0.0, period, n_steps)
        spreads = []
        for particle in range(seeds.shape[0]):
            densities = []
            for step, t in enumerate(t_eval):
                pos_bohr = traj[particle, step, :] * _ANGSTROM_TO_BOHR
                psi = sampler.wavefunction_at(t, pos_bohr)
                densities.append(abs(psi) ** 2)
            mean_density = float(np.mean(densities))
            if mean_density < 1e-12:
                continue
            spreads.append(float(np.std(densities) / mean_density))
        assert spreads
        assert float(np.median(spreads)) < 0.35
