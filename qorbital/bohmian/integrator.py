"""RK45 trajectory integration through a Bohmian velocity field."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray
from scipy import integrate
from scipy.interpolate import RegularGridInterpolator

from qorbital.bohmian.velocity import (
    SuperpositionVelocityContext,
    bohmian_velocity_at_point,
    superposition_period,
)
from qorbital.chemistry.density import _ANGSTROM_TO_BOHR

if TYPE_CHECKING:
    from qorbital.chemistry.superposition import SuperpositionState

_HBAR = 1.0


class _ComplexFieldInterpolator:
    """Bilinear-style complex sampling on a uniform 3D grid."""

    def __init__(
        self,
        axes: list[NDArray[np.float64]],
        field: NDArray[np.complex128],
    ) -> None:
        self._real = RegularGridInterpolator(
            axes, field.real, bounds_error=False, fill_value=0.0
        )
        self._imag = RegularGridInterpolator(
            axes, field.imag, bounds_error=False, fill_value=0.0
        )

    def __call__(self, point: NDArray[np.float64]) -> complex:
        return complex(self._real(point)[0], self._imag(point)[0])

    def batch(self, points: NDArray[np.float64]) -> NDArray[np.complex128]:
        pts = np.asarray(points, dtype=np.float64)
        return self._real(pts) + 1j * self._imag(pts)


_GradInterpolatorTriple = tuple[
    _ComplexFieldInterpolator,
    _ComplexFieldInterpolator,
    _ComplexFieldInterpolator,
]
_OrbitalSample = tuple[
    complex,
    complex,
    tuple[complex, complex, complex],
    tuple[complex, complex, complex],
]


@dataclass(frozen=True)
class _SuperpositionSampler:
    """Precomputed orbital interpolators for time-dependent Bohmian velocity."""

    phi0: _ComplexFieldInterpolator
    phi1: _ComplexFieldInterpolator
    grad_phi0: _GradInterpolatorTriple
    grad_phi1: _GradInterpolatorTriple
    E0: float
    E1: float
    c0: float
    c1: float

    @classmethod
    def from_context(cls, ctx: SuperpositionVelocityContext) -> _SuperpositionSampler:
        nx, ny, nz = ctx.phi0.shape
        axes = [
            ctx.origin_bohr[i] + np.arange(n) * ctx.spacing_bohr[i]
            for i, n in enumerate((nx, ny, nz))
        ]
        return cls(
            phi0=_ComplexFieldInterpolator(axes, ctx.phi0),
            phi1=_ComplexFieldInterpolator(axes, ctx.phi1),
            grad_phi0=(
                _ComplexFieldInterpolator(axes, ctx.grad_phi0[0]),
                _ComplexFieldInterpolator(axes, ctx.grad_phi0[1]),
                _ComplexFieldInterpolator(axes, ctx.grad_phi0[2]),
            ),
            grad_phi1=(
                _ComplexFieldInterpolator(axes, ctx.grad_phi1[0]),
                _ComplexFieldInterpolator(axes, ctx.grad_phi1[1]),
                _ComplexFieldInterpolator(axes, ctx.grad_phi1[2]),
            ),
            E0=ctx.E0,
            E1=ctx.E1,
            c0=ctx.c0,
            c1=ctx.c1,
        )

    def _sample_orbitals(self, pos_bohr: NDArray[np.float64]) -> _OrbitalSample:
        point = np.asarray(pos_bohr, dtype=np.float64)
        phi0 = self.phi0(point)
        phi1 = self.phi1(point)
        dphi0 = (
            self.grad_phi0[0](point),
            self.grad_phi0[1](point),
            self.grad_phi0[2](point),
        )
        dphi1 = (
            self.grad_phi1[0](point),
            self.grad_phi1[1](point),
            self.grad_phi1[2](point),
        )
        return phi0, phi1, dphi0, dphi1

    def wavefunction_at(self, t: float, pos_bohr: NDArray[np.float64]) -> complex:
        phi0, phi1, _, _ = self._sample_orbitals(pos_bohr)
        phase0 = np.exp(-1j * self.E0 * t / _HBAR)
        phase1 = np.exp(-1j * self.E1 * t / _HBAR)
        return self.c0 * phi0 * phase0 + self.c1 * phi1 * phase1

    def velocity_at(
        self, t: float, pos_bohr: NDArray[np.float64]
    ) -> tuple[float, float, float]:
        phi0, phi1, dphi0, dphi1 = self._sample_orbitals(pos_bohr)
        phase0 = np.exp(-1j * self.E0 * t / _HBAR)
        phase1 = np.exp(-1j * self.E1 * t / _HBAR)
        psi = self.c0 * phi0 * phase0 + self.c1 * phi1 * phase1
        dpsi_dx = self.c0 * dphi0[0] * phase0 + self.c1 * dphi1[0] * phase1
        dpsi_dy = self.c0 * dphi0[1] * phase0 + self.c1 * dphi1[1] * phase1
        dpsi_dz = self.c0 * dphi0[2] * phase0 + self.c1 * dphi1[2] * phase1
        return bohmian_velocity_at_point(psi, dpsi_dx, dpsi_dy, dpsi_dz)

    def velocity_batch(
        self, t: float, positions_bohr: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """Bohmian velocity for many particles, shape ``(n_particles, 3)``."""
        pts = np.asarray(positions_bohr, dtype=np.float64)
        phase0 = np.exp(-1j * self.E0 * t / _HBAR)
        phase1 = np.exp(-1j * self.E1 * t / _HBAR)

        phi0 = self.phi0.batch(pts)
        phi1 = self.phi1.batch(pts)
        dphi0 = (
            self.grad_phi0[0].batch(pts),
            self.grad_phi0[1].batch(pts),
            self.grad_phi0[2].batch(pts),
        )
        dphi1 = (
            self.grad_phi1[0].batch(pts),
            self.grad_phi1[1].batch(pts),
            self.grad_phi1[2].batch(pts),
        )

        psi = self.c0 * phi0 * phase0 + self.c1 * phi1 * phase1
        dpsi_dx = self.c0 * dphi0[0] * phase0 + self.c1 * dphi1[0] * phase1
        dpsi_dy = self.c0 * dphi0[1] * phase0 + self.c1 * dphi1[1] * phase1
        dpsi_dz = self.c0 * dphi0[2] * phase0 + self.c1 * dphi1[2] * phase1

        density = np.abs(psi) ** 2
        scale = 1.0
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio_x = dpsi_dx / psi
            ratio_y = dpsi_dy / psi
            ratio_z = dpsi_dz / psi
        vx = scale * np.imag(ratio_x)
        vy = scale * np.imag(ratio_y)
        vz = scale * np.imag(ratio_z)
        mask = density < 1e-8
        vx = np.where(mask, 0.0, vx)
        vy = np.where(mask, 0.0, vy)
        vz = np.where(mask, 0.0, vz)
        return np.column_stack([vx, vy, vz]).astype(np.float64)


def integrate_trajectories(
    vx: NDArray[np.float64],
    vy: NDArray[np.float64],
    vz: NDArray[np.float64],
    origin: NDArray[np.float64],
    spacing: NDArray[np.float64],
    seeds: NDArray[np.float64],
    t_span: tuple[float, float] = (0.0, 10.0),
    n_steps: int = 100,
) -> NDArray[np.float64]:
    """Integrate Bohmian trajectories through a velocity field on a regular grid.

    Parameters
    ----------
    vx, vy, vz
        Velocity components on a uniform grid, shape ``(nx, ny, nz)``.
    origin, spacing
        Grid origin and spacing (Angstrom), matching the velocity arrays.
    seeds
        Initial particle positions, shape ``(n_particles, 3)``.
    t_span
        Integration time interval ``(t0, tf)`` in atomic time units.
    n_steps
        Number of output time points (including endpoints).

    Returns
    -------
    trajectories
        Array of shape ``(n_particles, n_steps, 3)`` with positions in Angstrom.
    """
    nx, ny, nz = vx.shape
    axes = [origin[i] + np.arange(n) * spacing[i] for i, n in enumerate((nx, ny, nz))]

    interp_x = RegularGridInterpolator(axes, vx, bounds_error=False, fill_value=0.0)
    interp_y = RegularGridInterpolator(axes, vy, bounds_error=False, fill_value=0.0)
    interp_z = RegularGridInterpolator(axes, vz, bounds_error=False, fill_value=0.0)

    seeds = np.asarray(seeds, dtype=np.float64)
    n_particles = seeds.shape[0]
    t_eval = np.linspace(t_span[0], t_span[1], n_steps)
    trajectories = np.zeros((n_particles, n_steps, 3), dtype=np.float64)

    def _velocity(t: float, y: np.ndarray) -> np.ndarray:
        del t
        pos = y.reshape(n_particles, 3)
        vel = np.zeros_like(pos)
        for i in range(n_particles):
            p = pos[i]
            vel[i, 0] = float(interp_x(p)[0])
            vel[i, 1] = float(interp_y(p)[0])
            vel[i, 2] = float(interp_z(p)[0])
        return vel.ravel()

    y0 = seeds.ravel()
    result = integrate.solve_ivp(
        _velocity,
        t_span,
        y0,
        t_eval=t_eval,
        method="RK45",
        rtol=1e-6,
        atol=1e-8,
    )
    if not result.success:
        msg = f"Trajectory integration failed: {result.message}"
        raise RuntimeError(msg)

    for step in range(n_steps):
        trajectories[:, step, :] = result.y[:, step].reshape(n_particles, 3)

    return trajectories


def integrate_superposition_trajectories(
    ctx: SuperpositionVelocityContext,
    seeds: NDArray[np.float64],
    *,
    n_periods: float = 2.0,
    n_steps: int = 100,
    t0: float = 0.0,
) -> NDArray[np.float64]:
    """Integrate trajectories through a time-dependent two-state superposition.

    Seeds are in Angstrom; integration uses Bohr internally and returns Angstrom.
    """
    period = superposition_period(ctx.E0, ctx.E1)
    t_span = (t0, t0 + n_periods * period)
    sampler = _SuperpositionSampler.from_context(ctx)

    seeds_ang = np.asarray(seeds, dtype=np.float64)
    seeds_bohr = seeds_ang * _ANGSTROM_TO_BOHR
    n_particles = seeds_bohr.shape[0]
    t_eval = np.linspace(t_span[0], t_span[1], n_steps)
    trajectories = np.zeros((n_particles, n_steps, 3), dtype=np.float64)

    def _velocity(t: float, y: np.ndarray) -> np.ndarray:
        pos_bohr = y.reshape(n_particles, 3)
        vel_bohr = sampler.velocity_batch(t, pos_bohr)
        return vel_bohr.ravel()

    y0 = seeds_bohr.ravel()
    result = integrate.solve_ivp(
        _velocity,
        t_span,
        y0,
        t_eval=t_eval,
        method="RK45",
        rtol=1e-6,
        atol=1e-8,
    )
    if not result.success:
        msg = f"Superposition trajectory integration failed: {result.message}"
        raise RuntimeError(msg)

    for step in range(n_steps):
        pos_bohr = result.y[:, step].reshape(n_particles, 3)
        trajectories[:, step, :] = pos_bohr / _ANGSTROM_TO_BOHR

    return trajectories


def integrate_superposition_trajectories_from_state(
    state: SuperpositionState,
    seeds: NDArray[np.float64],
    *,
    n_periods: float = 2.0,
    n_steps: int = 100,
    t0: float = 0.0,
) -> NDArray[np.float64]:
    """Convenience wrapper around :func:`integrate_superposition_trajectories`."""
    return integrate_superposition_trajectories(
        SuperpositionVelocityContext.from_state(state),
        seeds,
        n_periods=n_periods,
        n_steps=n_steps,
        t0=t0,
    )


def superposition_sampler_from_context(
    ctx: SuperpositionVelocityContext,
) -> _SuperpositionSampler:
    """Build a sampler for tests and downstream time-series evaluation."""
    return _SuperpositionSampler.from_context(ctx)
