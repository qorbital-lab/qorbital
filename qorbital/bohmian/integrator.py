"""RK45 trajectory integration through a Bohmian velocity field."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import integrate
from scipy.interpolate import RegularGridInterpolator


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
