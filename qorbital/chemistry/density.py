"""1-RDM extraction and electron density grids."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pyscf import gto
from qiskit.quantum_info import Statevector
from qiskit_nature.second_q.mappers import JordanWignerMapper
from qiskit_nature.second_q.operators import FermionicOp

from qorbital.chemistry.integrals import MolecularIntegrals

_ANGSTROM_TO_BOHR = 1.8897259886


@dataclass(frozen=True)
class ElectronDensityGrid:
    """Electron density evaluated on a uniform 3D Cartesian grid."""

    density: NDArray[np.float64]
    grid_points: NDArray[np.float64]
    grid_shape: tuple[int, int, int]
    origin: NDArray[np.float64]
    spacing: NDArray[np.float64]
    extent: NDArray[np.float64]
    total_electrons: float
    integrated_density: float
    rdm1_mo: NDArray[np.float64]
    rdm1_ao: NDArray[np.float64]
    natural_occupations: NDArray[np.float64]
    natural_orbitals_mo: NDArray[np.float64]


def _extract_rdm1(
    statevector: NDArray[np.complex128],
    num_spatial_orbitals: int,
    num_particles: tuple[int, int],
) -> NDArray[np.float64]:
    """Spin-free 1-RDM ``gamma_pq`` from a Jordan-Wigner mapped statevector.

    Each element is computed as the expectation value of ``a+_p a_q``
    summed over spin sectors, built as a :class:`FermionicOp` and mapped
    to qubit space before evaluation against the statevector.
    """
    n_orb = num_spatial_orbitals
    n_so = 2 * n_orb
    mapper = JordanWignerMapper()
    sv = Statevector(np.ascontiguousarray(statevector, dtype=np.complex128))

    rdm1 = np.zeros((n_orb, n_orb), dtype=np.float64)

    for sigma_offset in (0, n_orb):
        for p in range(n_orb):
            for q in range(n_orb):
                label = f"+_{p + sigma_offset} -_{q + sigma_offset}"
                ferm_op = FermionicOp({label: 1.0}, num_spin_orbitals=n_so)
                qubit_op = mapper.map(ferm_op)
                rdm1[p, q] += sv.expectation_value(qubit_op).real

    return rdm1


def _build_grid(
    atom_coords_angstrom: NDArray[np.float64],
    n_points: int,
    padding: float,
) -> tuple[
    NDArray[np.float64],
    tuple[int, int, int],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    """Build a uniform 3D Cartesian grid around the molecule (Angstroms)."""
    mins = atom_coords_angstrom.min(axis=0) - padding
    maxs = atom_coords_angstrom.max(axis=0) + padding

    extent = np.column_stack([mins, maxs])

    axes = [np.linspace(mins[i], maxs[i], n_points) for i in range(3)]
    spacing = np.array([(maxs[i] - mins[i]) / (n_points - 1) for i in range(3)])
    origin = mins.copy()

    xv, yv, zv = np.meshgrid(*axes, indexing="ij")
    grid_flat = np.column_stack([xv.ravel(), yv.ravel(), zv.ravel()])

    grid_shape = (n_points, n_points, n_points)
    return grid_flat, grid_shape, origin, spacing, extent


def compute_density(
    statevector: NDArray[np.complex128],
    integrals: MolecularIntegrals,
    grid_points: int = 50,
    padding: float = 3.0,
    atom_string: str | None = None,
    basis: str = "sto-3g",
) -> ElectronDensityGrid:
    """Compute electron density on a 3D grid from a statevector.

    ``statevector`` is the ground-state wavefunction (1D complex array of
    length ``2**n_qubits``) from VQE, exact diagonalisation, or any other
    source.  ``integrals`` supplies the MO coefficients used to transform
    the 1-RDM into the AO basis.  ``atom_string`` is either a registry
    name (``"H2"``, ``"LiH"``, ``"HeH+"``, ``"BeH2"``) or a raw PySCF
    atom string (``"H 0 0 0; H 0 0 0.735"``); it is required because
    :class:`MolecularIntegrals` does not retain the geometry needed to
    reconstruct a PySCF ``Mole`` for basis function evaluation.  Only
    Jordan-Wigner mapped statevectors are supported; closed-shell
    molecules are assumed.
    """
    if atom_string is None:
        msg = (
            "atom_string is required to reconstruct the PySCF Mole object "
            "for basis function evaluation. Pass a PySCF atom string "
            "(e.g. 'H 0 0 0; H 0 0 0.735') or a registry name (e.g. 'H2')."
        )
        raise ValueError(msg)

    from qorbital.chemistry.molecules import resolve_atom_string

    resolved = resolve_atom_string(atom_string)

    rdm1_mo = _extract_rdm1(
        statevector,
        integrals.num_spatial_orbitals,
        integrals.num_particles,
    )
    total_electrons = float(np.trace(rdm1_mo))

    mo_coeff = integrals.mo_coefficients
    rdm1_ao = mo_coeff @ rdm1_mo @ mo_coeff.T

    occupations, natural_mos = np.linalg.eigh(rdm1_mo)
    idx = np.argsort(occupations)[::-1]
    occupations = occupations[idx]
    natural_mos = natural_mos[:, idx]

    mol = gto.M(atom=resolved, basis=basis, unit="Angstrom")
    atom_coords_ang = mol.atom_coords() / _ANGSTROM_TO_BOHR

    grid_flat, grid_shape, origin, spacing, extent = _build_grid(
        atom_coords_ang, grid_points, padding
    )

    grid_bohr = grid_flat * _ANGSTROM_TO_BOHR
    ao_vals = mol.eval_gto("GTOval_sph", grid_bohr)
    density_flat = np.einsum("gi,ij,gj->g", ao_vals, rdm1_ao, ao_vals)
    # eval_gto normalises basis functions in Bohr, so rho is in electrons/Bohr^3;
    # convert to electrons/Angstrom^3 to match the Angstrom-based grid spacing.
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
