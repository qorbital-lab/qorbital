"""Hartree-Fock classical density grids for comparison overlays."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qorbital.chemistry.density import (
    ElectronDensityGrid,
    _ANGSTROM_TO_BOHR,
    _build_grid,
)
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import get_molecule_params, resolve_atom_string
from pyscf import gto


def compute_hf_density(
    molecule: str,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    grid_points: int = 50,
    padding: float = 3.0,
) -> ElectronDensityGrid:
    """Compute Hartree-Fock electron density on a 3D grid.

    Returns an :class:`ElectronDensityGrid` in the same schema as the VQE
    pipeline so Arnav can overlay classical vs quantum densities directly.
    """
    params = get_molecule_params(molecule)
    integrals = compute_integrals(
        molecule,
        bond_length=bond_length,
        basis=basis,
        charge=params.charge,
        spin=params.spin,
    )

    n_occ = integrals.num_particles[0]
    mo_coeff = integrals.mo_coefficients
    rdm1_mo = np.zeros(
        (integrals.num_spatial_orbitals, integrals.num_spatial_orbitals)
    )
    for i in range(n_occ):
        rdm1_mo[i, i] = 2.0

    rdm1_ao = mo_coeff @ rdm1_mo @ mo_coeff.T
    total_electrons = float(np.trace(rdm1_mo))

    occupations, natural_mos = np.linalg.eigh(rdm1_mo)
    idx = np.argsort(occupations)[::-1]
    occupations = occupations[idx]
    natural_mos = natural_mos[:, idx]

    resolved = resolve_atom_string(molecule, bond_length)
    mol = gto.M(
        atom=resolved,
        basis=basis,
        charge=params.charge,
        spin=params.spin,
        unit="Angstrom",
    )
    atom_coords_ang = mol.atom_coords() / _ANGSTROM_TO_BOHR

    grid_flat, grid_shape, origin, spacing, extent = _build_grid(
        atom_coords_ang, grid_points, padding
    )

    grid_bohr = grid_flat * _ANGSTROM_TO_BOHR
    ao_vals = mol.eval_gto("GTOval_sph", grid_bohr)
    density_flat = np.einsum("gi,ij,gj->g", ao_vals, rdm1_ao, ao_vals)
    density_flat *= _ANGSTROM_TO_BOHR**3
    density_3d = density_flat.reshape(grid_shape)

    dx, dy, dz = spacing
    integrated = float(np.sum(density_3d) * dx * dy * dz)

    return ElectronDensityGrid(
        density=density_3d,
        grid_points=grid_flat,
        grid_shape=grid_shape,
        origin=origin,
        spacing=spacing,
        extent=extent,
        total_electrons=total_electrons,
        integrated_density=integrated,
        rdm1_mo=rdm1_mo,
        rdm1_ao=rdm1_ao,
        natural_occupations=occupations,
        natural_orbitals_mo=natural_mos,
    )
