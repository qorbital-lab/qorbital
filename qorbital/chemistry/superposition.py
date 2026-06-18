"""Eigenstate projection onto a common grid and superposition data contract."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from qorbital.chemistry.density import (
    _ANGSTROM_TO_BOHR,
    ElectronDensityGrid,
    WavefunctionGrid,
    compute_density,
)
from qorbital.chemistry.eigenstates import lowest_eigenstates
from qorbital.chemistry.hamiltonian import (
    QubitHamiltonian,
    QubitMapping,
    build_hamiltonian,
)
from qorbital.chemistry.integrals import MolecularIntegrals, compute_integrals
from qorbital.chemistry.molecules import get_molecule_params

_HBAR = 1.0
_DEFAULT_C = 1.0 / math.sqrt(2.0)
SuperpositionSource = Literal["exact_diag", "hardware_ground+exact_excited"]


@dataclass(frozen=True)
class SuperpositionState:
    """Canonical two-state superposition payload for B4, B6, and F1.

    Grid metadata is in atomic units (Bohr).  Energies are electronic
    eigenvalues in Hartree (add nuclear repulsion for total molecular energy).
    """

    origin: NDArray[np.float64]
    spacing: NDArray[np.float64]
    grid_shape: tuple[int, int, int]
    phi0: NDArray[np.complex128]
    phi1: NDArray[np.complex128]
    state_indices: tuple[int, int]
    E0: float
    E1: float
    c0: float
    c1: float
    omega: float
    source: SuperpositionSource

    @property
    def origin_angstrom(self) -> NDArray[np.float64]:
        return self.origin / _ANGSTROM_TO_BOHR

    @property
    def spacing_angstrom(self) -> NDArray[np.float64]:
        return self.spacing / _ANGSTROM_TO_BOHR


def _volume_element(spacing: NDArray[np.float64]) -> float:
    return float(np.prod(spacing))


def _normalize_on_grid(
    psi: NDArray[np.complex128], spacing_bohr: NDArray[np.float64]
) -> NDArray[np.complex128]:
    dV = _volume_element(spacing_bohr)
    norm = math.sqrt(float(np.sum(np.abs(psi) ** 2) * dV))
    if norm < 1e-30:
        msg = "cannot normalize a vanishing wavefunction on the grid"
        raise ValueError(msg)
    return psi / norm


def grid_overlap(
    psi_a: NDArray[np.complex128],
    psi_b: NDArray[np.complex128],
    spacing_bohr: NDArray[np.float64],
) -> complex:
    """Discrete L2 inner product on a uniform Cartesian grid (Bohr)."""
    dV = _volume_element(spacing_bohr)
    return complex(np.vdot(psi_a.ravel(), psi_b.ravel()) * dV)


def assert_common_grid(wf0: WavefunctionGrid, wf1: WavefunctionGrid) -> None:
    """Raise if two wavefunction grids do not share identical axes."""
    if wf0.grid_shape != wf1.grid_shape:
        msg = (
            f"grid_shape mismatch: {wf0.grid_shape!r} vs {wf1.grid_shape!r}; "
            "phi0 and phi1 must share a common grid"
        )
        raise ValueError(msg)
    if not np.allclose(wf0.origin, wf1.origin):
        msg = "grid origin mismatch between phi0 and phi1"
        raise ValueError(msg)
    if not np.allclose(wf0.spacing, wf1.spacing):
        msg = "grid spacing mismatch between phi0 and phi1"
        raise ValueError(msg)


def _wavefunction_to_bohr(
    wf: WavefunctionGrid,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    return wf.origin * _ANGSTROM_TO_BOHR, wf.spacing * _ANGSTROM_TO_BOHR


def natural_orbital_is_usable(
    density: ElectronDensityGrid, wf: WavefunctionGrid
) -> bool:
    """Return False when natural-orbital projection is unreliable (LiH fallback)."""
    if not np.all(np.isfinite(wf.psi)):
        return False
    occ = density.natural_occupations
    if not np.all(np.isfinite(occ)):
        return False
    if float(occ[0]) < 1e-6:
        return False
    if len(occ) > 1 and abs(float(occ[0]) - float(occ[1])) < 0.05:
        return False
    return True


def project_eigenpair_to_grid(
    statevector: NDArray[np.complex128],
    integrals: MolecularIntegrals,
    atom_string: str,
    *,
    reference_grid: ElectronDensityGrid,
    basis: str = "sto-3g",
    mapping: QubitMapping | str = QubitMapping.JORDAN_WIGNER,
    two_qubit_reduction: bool = False,
    orbital_index: int = 0,
) -> WavefunctionGrid:
    """Project one eigenvector onto the same axes as ``reference_grid``."""
    density = compute_density(
        statevector,
        integrals,
        grid_points=reference_grid.grid_shape[0],
        padding=_padding_from_grid(reference_grid, atom_string, basis),
        atom_string=atom_string,
        basis=basis,
        mapping=mapping,
        two_qubit_reduction=two_qubit_reduction,
    )
    if not np.allclose(density.origin, reference_grid.origin):
        msg = "eigenpair density grid origin does not match reference grid"
        raise ValueError(msg)
    if not np.allclose(density.spacing, reference_grid.spacing):
        msg = "eigenpair density grid spacing does not match reference grid"
        raise ValueError(msg)
    from qorbital.bohmian.projection import project_natural_orbital

    return project_natural_orbital(
        density,
        integrals,
        atom_string,
        basis=basis,
        orbital_index=orbital_index,
    )


def _padding_from_grid(
    grid: ElectronDensityGrid,
    atom_string: str,
    basis: str,
) -> float:
    """Recover padding used to build an existing density grid."""
    from pyscf import gto

    from qorbital.chemistry.density import _molecule_meta

    resolved, charge, spin = _molecule_meta(atom_string)
    mol = gto.M(atom=resolved, basis=basis, charge=charge, spin=spin, unit="Angstrom")
    atom_coords_ang = mol.atom_coords() / _ANGSTROM_TO_BOHR
    span = grid.extent[:, 1] - grid.extent[:, 0]
    molecule_span = atom_coords_ang.max(axis=0) - atom_coords_ang.min(axis=0)
    padding_per_axis = (span - molecule_span) / 2.0
    return float(np.mean(padding_per_axis))


def build_superposition_state(
    atom_string: str,
    *,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    grid_points: int = 50,
    padding: float = 3.0,
    mapping: QubitMapping | str | None = None,
    two_qubit_reduction: bool | None = None,
    source: SuperpositionSource = "exact_diag",
    c0: float | None = None,
    c1: float | None = None,
    qubit_hamiltonian: QubitHamiltonian | None = None,
    integrals: MolecularIntegrals | None = None,
) -> SuperpositionState:
    """Build the two-state superposition contract from exact diagonalization.

    For each lowest eigenvector, extract the mapper-aware 1-RDM, take the
    dominant natural orbital, and evaluate it on a grid shared by phi0 and phi1.
    LiH falls back to HF HOMO/LUMO when natural orbitals fail quality checks.
    """
    from qorbital.bohmian.projection import project_hf_mo, project_natural_orbital

    params = get_molecule_params(atom_string)
    resolved_mapping = mapping if mapping is not None else params.mapping
    resolved_2qr = (
        two_qubit_reduction
        if two_qubit_reduction is not None
        else params.two_qubit_reduction
    )

    if integrals is None:
        integrals = compute_integrals(
            atom_string,
            bond_length=bond_length,
            basis=basis,
            charge=params.charge,
            spin=params.spin,
        )
    if qubit_hamiltonian is None:
        qubit_hamiltonian = build_hamiltonian(
            atom_string,
            bond_length=bond_length,
            basis=basis,
            charge=params.charge,
            spin=params.spin,
            mapping=resolved_mapping,
            two_qubit_reduction=resolved_2qr,
        )

    (sv0, e0), (sv1, e1) = lowest_eigenstates(qubit_hamiltonian, k=2)

    density0 = compute_density(
        sv0,
        integrals,
        grid_points=grid_points,
        padding=padding,
        atom_string=atom_string,
        basis=basis,
        mapping=resolved_mapping,
        two_qubit_reduction=resolved_2qr,
    )
    density1 = compute_density(
        sv1,
        integrals,
        grid_points=grid_points,
        padding=padding,
        atom_string=atom_string,
        basis=basis,
        mapping=resolved_mapping,
        two_qubit_reduction=resolved_2qr,
    )

    wf0 = project_natural_orbital(density0, integrals, atom_string, basis=basis)
    origin_bohr, spacing_bohr = _wavefunction_to_bohr(wf0)
    phi0_norm = _normalize_on_grid(wf0.psi, spacing_bohr)

    n_orbitals = len(density1.natural_occupations)
    best_wf1: WavefunctionGrid | None = None
    best_overlap = float("inf")
    for orbital_index in range(n_orbitals):
        candidate = project_natural_orbital(
            density1,
            integrals,
            atom_string,
            basis=basis,
            orbital_index=orbital_index,
        )
        phi_candidate = _normalize_on_grid(candidate.psi, spacing_bohr)
        overlap = abs(grid_overlap(phi0_norm, phi_candidate, spacing_bohr))
        if overlap < best_overlap:
            best_overlap = overlap
            best_wf1 = candidate

    if best_wf1 is None:
        msg = "no natural orbital available for excited-state projection"
        raise ValueError(msg)
    wf1 = best_wf1
    assert_common_grid(wf0, wf1)

    use_fallback = atom_string == "LiH" and (
        not natural_orbital_is_usable(density0, wf0)
        or not natural_orbital_is_usable(density1, wf1)
    )
    if use_fallback:
        n_occ = integrals.num_particles[0]
        wf0 = project_hf_mo(
            density0, integrals, atom_string, mo_index=n_occ - 1, basis=basis
        )
        wf1 = project_hf_mo(
            density1, integrals, atom_string, mo_index=n_occ, basis=basis
        )
        assert_common_grid(wf0, wf1)

    origin_bohr, spacing_bohr = _wavefunction_to_bohr(wf0)
    phi0 = _normalize_on_grid(wf0.psi, spacing_bohr)
    phi1 = _normalize_on_grid(wf1.psi, spacing_bohr)

    coeff0 = _DEFAULT_C if c0 is None else c0
    coeff1 = _DEFAULT_C if c1 is None else c1

    return SuperpositionState(
        origin=origin_bohr,
        spacing=spacing_bohr,
        grid_shape=wf0.grid_shape,
        phi0=phi0,
        phi1=phi1,
        state_indices=(0, 1),
        E0=e0,
        E1=e1,
        c0=coeff0,
        c1=coeff1,
        omega=(e1 - e0) / _HBAR,
        source=source,
    )
