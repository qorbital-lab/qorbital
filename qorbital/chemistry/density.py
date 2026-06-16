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


def _molecule_meta(atom_string: str) -> tuple[str, int, int]:
    """Resolve atom string and charge/spin for registry molecules."""
    from qorbital.chemistry.molecules import (
        MOLECULE_REGISTRY,
        get_molecule_params,
        resolve_atom_string,
    )

    resolved = resolve_atom_string(atom_string)
    charge, spin = 0, 0
    if atom_string in MOLECULE_REGISTRY:
        params = get_molecule_params(atom_string)
        charge, spin = params.charge, params.spin
    return resolved, charge, spin


def compute_density(
    statevector: NDArray[np.complex128],
    integrals: MolecularIntegrals,
    grid_points: int = 50,
    padding: float = 3.0,
    atom_string: str | None = None,
    basis: str = "sto-3g",
    charge: int = 0,
    spin: int = 0,
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

    resolved, charge, spin = _molecule_meta(atom_string)

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

    mol = gto.M(
        atom=resolved, basis=basis, charge=charge, spin=spin, unit="Angstrom"
    )
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


@dataclass(frozen=True)
class WavefunctionGrid:
    """Single-particle wavefunction amplitude on a uniform 3D Cartesian grid.

    For a real ground-state natural orbital the values are real; the array
    dtype is complex128 so callers can inject phase for non-stationary Bohmian
    visualisation.
    """

    psi: NDArray[np.complex128]
    grid_shape: tuple[int, int, int]
    origin: NDArray[np.float64]
    spacing: NDArray[np.float64]
    occupation: float
    orbital_index: int


def wavefunction_grid(
    density_grid: ElectronDensityGrid,
    integrals: MolecularIntegrals,
    atom_string: str,
    basis: str = "sto-3g",
    orbital_index: int = 0,
    phase: NDArray[np.complex128] | complex | None = None,
    charge: int = 0,
    spin: int = 0,
) -> WavefunctionGrid:
    """Evaluate the highest-occupation natural orbital on the density grid.

    Transforms ``natural_orbitals_mo[:, orbital_index]`` to the AO basis via
    ``integrals.mo_coefficients`` and evaluates ``psi(r) = sum_i C_i phi_i(r)``.

    For a real ground state ``psi`` is real and Bohmian velocity
    ``Im(grad psi / psi)`` vanishes (stationary trajectories).  Pass an
    optional ``phase`` (scalar or per-grid-point array) to produce a complex
    wavefunction suitable for non-trivial Bohmian motion.

    The squared magnitude integrates to approximately the natural orbital
    occupation number (not the full electron density).
    """
    resolved, charge, spin = _molecule_meta(atom_string)
    mo_coeff = integrals.mo_coefficients
    no_mo = density_grid.natural_orbitals_mo[:, orbital_index]
    no_ao = mo_coeff @ no_mo

    mol = gto.M(
        atom=resolved, basis=basis, charge=charge, spin=spin, unit="Angstrom"
    )
    grid_bohr = density_grid.grid_points * _ANGSTROM_TO_BOHR
    ao_vals = mol.eval_gto("GTOval_sph", grid_bohr)
    psi_flat = ao_vals @ no_ao.astype(np.complex128)

    if phase is not None:
        if np.isscalar(phase) or isinstance(phase, (complex, float, int)):
            psi_flat = psi_flat * np.exp(1j * float(phase))
        else:
            psi_flat = psi_flat * np.exp(1j * np.asarray(phase, dtype=np.float64))

    psi_3d = psi_flat.reshape(density_grid.grid_shape)
    occupation = float(density_grid.natural_occupations[orbital_index])

    return WavefunctionGrid(
        psi=psi_3d,
        grid_shape=density_grid.grid_shape,
        origin=density_grid.origin.copy(),
        spacing=density_grid.spacing.copy(),
        occupation=occupation,
        orbital_index=orbital_index,
    )


def wavefunction_grid_from_statevector(
    statevector: NDArray[np.complex128],
    integrals: MolecularIntegrals,
    atom_string: str,
    grid_points: int = 50,
    padding: float = 3.0,
    basis: str = "sto-3g",
    orbital_index: int = 0,
    phase: NDArray[np.complex128] | complex | None = None,
) -> WavefunctionGrid:
    """Convenience wrapper: compute_density then wavefunction_grid."""
    density = compute_density(
        statevector,
        integrals,
        grid_points=grid_points,
        padding=padding,
        atom_string=atom_string,
        basis=basis,
    )
    return wavefunction_grid(
        density,
        integrals,
        atom_string=atom_string,
        basis=basis,
        orbital_index=orbital_index,
        phase=phase,
    )
