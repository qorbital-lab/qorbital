"""Bohmian trajectory generation from an electron density grid.

Shared single-run trajectory builder: project the dominant natural orbital,
inject an azimuthal phase so the (otherwise stationary, real) ground state has a
non-zero Bohmian velocity field, then integrate seeded particles.  Used by both
the bundle generator (``scripts/generate_bundles.py``) and the hardware noise
ensemble (:mod:`qorbital.bohmian.noise_ensemble`).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qorbital.bohmian.integrator import integrate_trajectories
from qorbital.bohmian.projection import project_natural_orbital
from qorbital.bohmian.velocity import add_azimuthal_phase, velocity_field
from qorbital.chemistry.density import ElectronDensityGrid
from qorbital.chemistry.integrals import MolecularIntegrals
from qorbital.chemistry.molecules import DEFAULT_BOND_LENGTHS

#: Default trajectory integration controls, shared across call sites.
N_PARTICLES = 20
N_STEPS = 100
DT = 0.1


def generate_trajectories(
    density_grid: ElectronDensityGrid,
    integrals: MolecularIntegrals,
    molecule: str,
    *,
    bond: float | None = None,
    n_particles: int = N_PARTICLES,
    n_steps: int = N_STEPS,
) -> NDArray[np.float64]:
    """Generate Bohmian trajectories with azimuthal phase injection.

    Returns an array of shape ``(n_particles, n_steps, 3)`` (positions in
    Angstrom) suitable for the viewer and for
    :func:`qorbital.bohmian.uncertainty.compute_uncertainty_cloud`.
    """
    wf = project_natural_orbital(density_grid, integrals, molecule)
    psi_complex = add_azimuthal_phase(wf.psi, wf.origin, wf.spacing, strength=0.5)
    vx, vy, vz = velocity_field(psi_complex, wf.spacing)

    if bond is None:
        bond = DEFAULT_BOND_LENGTHS[molecule]
    seeds = np.array(
        [[0.0, 0.0, z] for z in np.linspace(-bond * 0.3, bond * 0.3, n_particles)]
    )
    return integrate_trajectories(
        vx, vy, vz, wf.origin, wf.spacing, seeds, t_span=(0.0, 5.0), n_steps=n_steps
    )
