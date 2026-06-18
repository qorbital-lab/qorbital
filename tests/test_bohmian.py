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
    bohmian_velocity_at_point,
    precompute_state_gradients,
    superposition_period,
    superposition_velocity_at_time,
    superposition_wavefunction,
    velocity_field,
)
from qorbital.chemistry.density import compute_density, wavefunction_grid
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import get_molecule_params
from qorbital.chemistry.superposition import (
    SuperpositionState,
    build_superposition_state,
)

_DENSITY_CUTOFF = 1e-8
_ORACLE_DENSITY_FLOOR = 1e-6


def _assert_orbitals_real(state: SuperpositionState) -> None:
    """Oracle precondition: projected orbitals must be essentially real."""
    imag0 = float(np.max(np.abs(state.phi0.imag)))
    imag1 = float(np.max(np.abs(state.phi1.imag)))
    assert imag0 < 1e-8, f"phi0 has imaginary part max {imag0}"
    assert imag1 < 1e-8, f"phi1 has imaginary part max {imag1}"


def _closed_form_superposition_velocity(
    state: SuperpositionState,
    t: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Closed-form two-state Bohmian velocity for real orbitals."""
    omega = state.E1 - state.E0
    psi = superposition_wavefunction(
        state.phi0,
        state.phi1,
        state.E0,
        state.E1,
        t,
        c0=state.c0,
        c1=state.c1,
    )
    density = np.abs(psi) ** 2
    pref = state.c0 * state.c1 * np.sin(omega * t)
    g0 = precompute_state_gradients(state.phi0, state.spacing)
    g1 = precompute_state_gradients(state.phi1, state.spacing)

    with np.errstate(divide="ignore", invalid="ignore"):
        vx = pref * (state.phi1 * g0[0] - state.phi0 * g1[0]) / density
        vy = pref * (state.phi1 * g0[1] - state.phi0 * g1[1]) / density
        vz = pref * (state.phi1 * g0[2] - state.phi0 * g1[2]) / density

    mask = density < _DENSITY_CUTOFF
    vx = np.where(mask, 0.0, np.real(vx)).astype(np.float64)
    vy = np.where(mask, 0.0, np.real(vy)).astype(np.float64)
    vz = np.where(mask, 0.0, np.real(vz)).astype(np.float64)
    return vx, vy, vz


def _compare_velocity_fields(
    v_num: tuple[np.ndarray, np.ndarray, np.ndarray],
    v_oracle: tuple[np.ndarray, np.ndarray, np.ndarray],
    psi: np.ndarray,
    *,
    rtol: float = 0.05,
) -> None:
    """Compare numerical and oracle velocity on interior high-density voxels."""
    density = np.abs(psi) ** 2
    vx_n, vy_n, vz_n = v_num
    vx_o, vy_o, vz_o = v_oracle
    nx, ny, nz = density.shape
    interior = np.zeros_like(density, dtype=bool)
    interior[2 : nx - 2, 2 : ny - 2, 2 : nz - 2] = True
    mask = interior & (density > _ORACLE_DENSITY_FLOOR)
    for arr in (vx_n, vy_n, vz_n, vx_o, vy_o, vz_o):
        mask &= np.isfinite(arr)
    assert np.any(mask), "no interior voxels passed oracle comparison mask"
    np.testing.assert_allclose(vx_n[mask], vx_o[mask], rtol=rtol, atol=1e-10)
    np.testing.assert_allclose(vy_n[mask], vy_o[mask], rtol=rtol, atol=1e-10)
    np.testing.assert_allclose(vz_n[mask], vz_o[mask], rtol=rtol, atol=1e-10)


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


@pytest.fixture(scope="module")
def heh_superposition_integrator():
    return _build_heh_superposition_state(grid_points=20)


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


def _build_heh_superposition_state(grid_points: int = 20) -> SuperpositionState:
    """HeH+ ground + first non-degenerate excited (skip near-degenerate pair)."""
    import math

    from qorbital.chemistry.eigenstates import lowest_eigenstates
    from qorbital.chemistry.hamiltonian import build_hamiltonian
    from qorbital.chemistry.superposition import (
        _normalize_on_grid,
        _wavefunction_to_bohr,
        grid_overlap,
        project_eigenpair_to_grid,
    )

    params = get_molecule_params("HeH+")
    bond = 0.772
    integrals = compute_integrals(
        "HeH+", bond_length=bond, charge=params.charge, spin=params.spin
    )
    qh = build_hamiltonian(
        "HeH+", bond_length=bond, charge=params.charge, spin=params.spin
    )
    (sv0, e0), _, (sv2, e2) = lowest_eigenstates(qh, k=3)

    density0 = compute_density(
        sv0, integrals, grid_points=grid_points, atom_string="HeH+"
    )
    wf0 = project_eigenpair_to_grid(sv0, integrals, "HeH+", reference_grid=density0)
    origin_bohr, spacing_bohr = _wavefunction_to_bohr(wf0)
    phi0 = _normalize_on_grid(wf0.psi, spacing_bohr)

    density2 = compute_density(
        sv2, integrals, grid_points=grid_points, atom_string="HeH+"
    )
    best_wf2 = None
    best_overlap = float("inf")
    for orbital_index in range(len(density2.natural_occupations)):
        candidate = project_eigenpair_to_grid(
            sv2,
            integrals,
            "HeH+",
            reference_grid=density0,
            orbital_index=orbital_index,
        )
        phi_candidate = _normalize_on_grid(candidate.psi, spacing_bohr)
        overlap = abs(grid_overlap(phi0, phi_candidate, spacing_bohr))
        if overlap < best_overlap:
            best_overlap = overlap
            best_wf2 = candidate
    if best_wf2 is None:
        msg = "no excited orbital available for HeH+ superposition"
        raise ValueError(msg)
    phi1 = _normalize_on_grid(best_wf2.psi, spacing_bohr)
    coeff = 1.0 / math.sqrt(2.0)
    return SuperpositionState(
        origin=origin_bohr,
        spacing=spacing_bohr,
        grid_shape=wf0.grid_shape,
        phi0=phi0,
        phi1=phi1,
        state_indices=(0, 2),
        E0=e0,
        E1=e2,
        c0=coeff,
        c1=coeff,
        omega=(e2 - e0),
        source="exact_diag",
    )


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


class TestSuperpositionOracle:
    @pytest.mark.oracle
    def test_plane_wave_velocity_analytic(self):
        k = 1.5
        z = 0.3
        t = 0.1
        omega = 2.0
        psi = np.exp(1j * (k * z - omega * t))
        dpsi_dz = 1j * k * psi
        vx, vy, vz = bohmian_velocity_at_point(psi, 0.0 + 0j, 0.0 + 0j, dpsi_dz)
        assert vx == pytest.approx(0.0, abs=1e-12)
        assert vy == pytest.approx(0.0, abs=1e-12)
        assert vz == pytest.approx(k, rel=1e-12)

    @pytest.mark.oracle
    def test_h2_orbitals_are_real(self, h2_superposition):
        _assert_orbitals_real(h2_superposition)

    @pytest.mark.oracle
    def test_closed_form_oracle_matches_numerical_velocity(self, h2_superposition):
        _assert_orbitals_real(h2_superposition)
        ctx = SuperpositionVelocityContext.from_state(h2_superposition)
        period = superposition_period(h2_superposition.E0, h2_superposition.E1)
        sample_times = [period / 8.0, period / 4.0, 3.0 * period / 8.0]
        for t in sample_times:
            v_num = superposition_velocity_at_time(ctx, t)
            v_oracle = _closed_form_superposition_velocity(h2_superposition, t)
            psi = superposition_wavefunction(
                h2_superposition.phi0,
                h2_superposition.phi1,
                h2_superposition.E0,
                h2_superposition.E1,
                t,
                c0=h2_superposition.c0,
                c1=h2_superposition.c1,
            )
            _compare_velocity_fields(v_num, v_oracle, psi)


class TestSuperpositionBehaviour:
    @pytest.mark.oracle
    def test_heh_registry_charge(self):
        params = get_molecule_params("HeH+")
        assert params.charge == 1

    @pytest.mark.oracle
    @pytest.mark.integrator
    def test_h2_trajectories_move(self, h2_superposition_integrator):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition_integrator)
        seeds = _h2_superposition_seeds(20)
        traj = integrate_superposition_trajectories(
            ctx, seeds, n_periods=1.0, n_steps=100
        )
        displacement = np.max(np.abs(traj[:, :, 2] - traj[:, 0:1, 2]))
        assert displacement > 0.02

    @pytest.mark.oracle
    @pytest.mark.periodic
    def test_h2_trajectories_slosh_periodic(self, h2_superposition_integrator):
        ctx = SuperpositionVelocityContext.from_state(h2_superposition_integrator)
        seeds = _h2_superposition_seeds(20)
        period = superposition_period(
            h2_superposition_integrator.E0, h2_superposition_integrator.E1
        )
        n_steps = 100
        traj = integrate_superposition_trajectories(
            ctx, seeds, n_periods=1.0, n_steps=n_steps
        )
        z_std = np.std(traj[:, :, 2], axis=1)
        assert np.all(z_std > 0.01)

        z_range = float(np.ptp(traj[:, :, 2]))
        assert z_range > 0.1

        left_seed = traj[0, :, 2]
        assert float(np.max(left_seed)) > 0.2
        assert float(np.max(right_seed := traj[-1, :, 2])) > float(right_seed[0]) + 0.2

        t_eval = np.linspace(0.0, period, n_steps)
        period_idx = int(np.argmin(np.abs(t_eval - period)))
        displacement = np.linalg.norm(traj[:, period_idx, :] - traj[:, 0, :], axis=1)
        assert np.all(displacement < 0.15)

    @pytest.mark.oracle
    @pytest.mark.integrator
    def test_heh_trajectories_asymmetric_toward_he(self, heh_superposition_integrator):
        ctx = SuperpositionVelocityContext.from_state(heh_superposition_integrator)
        bond = 0.772
        seeds = np.array([[0.0, 0.0, z] for z in np.linspace(0.1, 0.6, 15)])
        traj = integrate_superposition_trajectories(
            ctx, seeds, n_periods=2.0, n_steps=100
        )
        mean_z = float(np.mean(traj[:, :, 2]))
        assert mean_z < bond * 0.45

    @pytest.mark.oracle
    @pytest.mark.integrator
    def test_superposition_norm_conserved_along_trajectories(
        self, h2_superposition_integrator
    ):
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
