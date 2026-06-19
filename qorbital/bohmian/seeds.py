"""Seed particles from the quantum-equilibrium |psi(t)|^2 distribution."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qorbital.bohmian.velocity import superposition_wavefunction
from qorbital.chemistry.superposition import SuperpositionState


def sample_superposition_seeds(
    state: SuperpositionState,
    n_particles: int,
    *,
    t: float = 0.0,
    rng: np.random.Generator | None = None,
) -> NDArray[np.float64]:
    """Sample Bohmian particle seeds from |Psi(r, t)|^2 on the superposition grid.

    Positions are returned in Angstrom with uniform jitter inside each voxel.
    """
    if n_particles <= 0:
        msg = "n_particles must be positive"
        raise ValueError(msg)

    generator = rng if rng is not None else np.random.default_rng()
    psi = superposition_wavefunction(
        state.phi0,
        state.phi1,
        state.E0,
        state.E1,
        t,
        c0=state.c0,
        c1=state.c1,
    )
    prob = np.abs(psi) ** 2
    prob_flat = prob.ravel().astype(np.float64)
    total = float(prob_flat.sum())
    if total <= 0:
        msg = "superposition probability density is vanishing on the grid"
        raise ValueError(msg)
    prob_flat /= total

    nx, ny, nz = state.grid_shape
    indices = generator.choice(prob_flat.size, size=n_particles, p=prob_flat)
    origin = state.origin_angstrom
    spacing = state.spacing_angstrom

    seeds = np.zeros((n_particles, 3), dtype=np.float64)
    stride_y = nx
    stride_z = nx * ny
    for particle, flat in enumerate(indices):
        k = flat // stride_z
        rem = flat % stride_z
        j = rem // stride_y
        i = rem % stride_y
        jitter = generator.random(3)
        seeds[particle] = origin + np.array([i, j, k], dtype=np.float64) * spacing + (
            jitter * spacing
        )
    return seeds
