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
from qorbital.chemistry.hamiltonian import (
    QubitHamiltonian,
    QubitMapping,
)
from qorbital.chemistry.integrals import MolecularIntegrals, compute_integrals
from qorbital.chemistry.molecules import get_molecule_params

_HBAR = 1.0
_DEFAULT_C = 1.0 / math.sqrt(2.0)
SuperpositionSource = Literal[
    "exact_diag",
    "hardware_ground+exact_excited",
    "hf_homo_lumo",
    "hardware_ground+hf_lumo",
]


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
    source: SuperpositionSource = "hf_homo_lumo",
    c0: float | None = None,
    c1: float | None = None,
    qubit_hamiltonian: QubitHamiltonian | None = None,
    integrals: MolecularIntegrals | None = None,
) -> SuperpositionState:
    """Build the two-state superposition from the HF HOMO (sigma) and LUMO (sigma*).

    The moving state is ``Psi(r,t) = c0 phi0 e^{-iE0 t} + c1 phi1 e^{-iE1 t}`` with
    ``phi0``/``phi1`` the canonical HF HOMO/LUMO molecular orbitals and ``E0``/``E1``
    their orbital energies.  The two orbitals are distinct and non-degenerate by
    construction (the HOMO-LUMO gap is positive), so the oscillation period is always
    defined.  This is deliberately *not* built from the two lowest many-body
    eigenstates of the qubit Hamiltonian: that spectrum spans every particle-number
    and spin sector, so its two lowest states can fall in the wrong sector or be
    spin-degenerate (e.g. HeH+ gives ``E0 == E1``).  HOMO/LUMO is identical code for
    H2, HeH+, and LiH (clean sigma -> sigma* charge oscillation; HeH+'s polarity
    shows up as asymmetric amplitude toward He).

    Equivariance caveat: the HF MOs are eigenfunctions of the *non-local* Fock
    operator, so the kinematic current ``j = Im(Psi* grad Psi)`` is not continuity-
    consistent.  The trajectory cloud has the correct phase, direction, and period
    but under-transports the density's amplitude.  This is modeling physics, not a
    bug (a local-Hamiltonian harmonic-oscillator control is equivariant to the grid
    floor); the motion is a qualitative visualization.

    ``mapping``/``two_qubit_reduction``/``qubit_hamiltonian`` are kept for signature
    compatibility but unused: HOMO/LUMO orbitals are mapper-free.
    """
    from qorbital.bohmian.projection import project_hf_mo
    from qorbital.chemistry.hartree_fock import compute_hf_density

    del mapping, two_qubit_reduction, qubit_hamiltonian  # mapper-free; kept for compat

    params = get_molecule_params(atom_string)
    if integrals is None:
        integrals = compute_integrals(
            atom_string,
            bond_length=bond_length,
            basis=basis,
            charge=params.charge,
            spin=params.spin,
        )

    # The HF density only fixes the common grid; phi0/phi1 are the canonical MOs.
    grid = compute_hf_density(
        atom_string,
        bond_length=bond_length,
        basis=basis,
        grid_points=grid_points,
        padding=padding,
    )

    n_occ = integrals.num_particles[0]
    homo_index = n_occ - 1
    lumo_index = n_occ
    n_mo = integrals.mo_coefficients.shape[1]
    if homo_index < 0 or lumo_index >= n_mo:
        msg = (
            f"{atom_string} has no HOMO/LUMO pair (n_mo={n_mo}, n_occ={n_occ}); "
            "cannot build a HOMO/LUMO superposition"
        )
        raise ValueError(msg)

    wf0 = project_hf_mo(grid, integrals, atom_string, mo_index=homo_index, basis=basis)
    wf1 = project_hf_mo(grid, integrals, atom_string, mo_index=lumo_index, basis=basis)
    assert_common_grid(wf0, wf1)

    origin_bohr, spacing_bohr = _wavefunction_to_bohr(wf0)
    phi0 = _normalize_on_grid(wf0.psi, spacing_bohr)
    phi1 = _normalize_on_grid(wf1.psi, spacing_bohr)

    e0 = float(integrals.mo_energies[homo_index])
    e1 = float(integrals.mo_energies[lumo_index])

    coeff0 = _DEFAULT_C if c0 is None else c0
    coeff1 = _DEFAULT_C if c1 is None else c1

    return SuperpositionState(
        origin=origin_bohr,
        spacing=spacing_bohr,
        grid_shape=wf0.grid_shape,
        phi0=phi0,
        phi1=phi1,
        state_indices=(homo_index, lumo_index),
        E0=e0,
        E1=e1,
        c0=coeff0,
        c1=coeff1,
        omega=(e1 - e0) / _HBAR,
        source=source,
    )


def build_superposition_from_ground_state(
    ground_statevector: NDArray[np.complex128],
    integrals: MolecularIntegrals,
    atom_string: str,
    *,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    grid_points: int = 50,
    padding: float = 3.0,
    mapping: QubitMapping | str | None = None,
    two_qubit_reduction: bool | None = None,
    ground_energy: float | None = None,
    c0: float | None = None,
    c1: float | None = None,
) -> SuperpositionState:
    """Build a two-state superposition from a VQE/hardware ground state + HF LUMO.

    phi0 is the dominant natural orbital of ``ground_statevector`` (so per-run
    hardware noise reshapes it -> the uncertainty cloud); phi1 is the HF LUMO
    (sigma*) on the same grid.  Energies are the HF orbital energies (E0=eps_HOMO,
    E1=eps_LUMO), giving a positive, always-defined HOMO-LUMO gap -- consistent with
    :func:`build_superposition_state` and free of the wrong-sector degeneracy that
    the two-lowest-eigenstate construction hits for HeH+.  ``ground_energy`` is kept
    for provenance but does not drive the motion (mixing a total electronic energy
    with an orbital energy would be an inconsistent gap).
    """
    del ground_energy  # provenance only; motion uses the HF orbital-energy gap

    params = get_molecule_params(atom_string)
    resolved_mapping = mapping if mapping is not None else params.mapping
    resolved_2qr = (
        two_qubit_reduction
        if two_qubit_reduction is not None
        else params.two_qubit_reduction
    )

    density0 = compute_density(
        ground_statevector,
        integrals,
        grid_points=grid_points,
        padding=padding,
        atom_string=atom_string,
        basis=basis,
        mapping=resolved_mapping,
        two_qubit_reduction=resolved_2qr,
    )
    return build_superposition_from_density(
        density0, integrals, atom_string, basis=basis, c0=c0, c1=c1
    )


def build_superposition_from_density(
    density: ElectronDensityGrid,
    integrals: MolecularIntegrals,
    atom_string: str,
    *,
    basis: str = "sto-3g",
    c0: float | None = None,
    c1: float | None = None,
) -> SuperpositionState:
    """HOMO/LUMO superposition from a (possibly noisy) density grid.

    phi0 is the dominant natural orbital of ``density`` (so a per-run hardware-noisy
    1-RDM reshapes it -> the uncertainty cloud); phi1 is the HF LUMO on the same
    grid; energies are the HF orbital energies (always-defined HOMO-LUMO gap).
    Shared by :func:`build_superposition_from_ground_state` and the hardware
    noise ensemble.
    """
    from qorbital.bohmian.projection import project_hf_mo, project_natural_orbital

    n_occ = integrals.num_particles[0]
    lumo_index = n_occ
    n_mo = integrals.mo_coefficients.shape[1]
    if lumo_index >= n_mo:
        msg = (
            f"{atom_string} has no LUMO (n_mo={n_mo}, n_occ={n_occ}); "
            "cannot build a HOMO/LUMO superposition"
        )
        raise ValueError(msg)

    wf0 = project_natural_orbital(density, integrals, atom_string, basis=basis)
    wf1 = project_hf_mo(
        density, integrals, atom_string, mo_index=lumo_index, basis=basis
    )
    assert_common_grid(wf0, wf1)

    origin_bohr, spacing_bohr = _wavefunction_to_bohr(wf0)
    phi0 = _normalize_on_grid(wf0.psi, spacing_bohr)
    phi1 = _normalize_on_grid(wf1.psi, spacing_bohr)

    e0 = float(integrals.mo_energies[n_occ - 1])
    e1 = float(integrals.mo_energies[lumo_index])

    coeff0 = _DEFAULT_C if c0 is None else c0
    coeff1 = _DEFAULT_C if c1 is None else c1

    return SuperpositionState(
        origin=origin_bohr,
        spacing=spacing_bohr,
        grid_shape=wf0.grid_shape,
        phi0=phi0,
        phi1=phi1,
        state_indices=(n_occ - 1, lumo_index),
        E0=e0,
        E1=e1,
        c0=coeff0,
        c1=coeff1,
        omega=(e1 - e0) / _HBAR,
        source="hardware_ground+hf_lumo",
    )
