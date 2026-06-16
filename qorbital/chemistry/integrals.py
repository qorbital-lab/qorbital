"""Molecular integral computation via PySCF and Qiskit Nature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from qiskit_nature.second_q.problems import ElectronicStructureProblem


@dataclass(frozen=True)
class MolecularIntegrals:
    """Molecular integrals and SCF reference data for the VQE pipeline.

    Bases differ by field, so they are spelled out below to avoid misuse: the
    one- and two-body integrals are in the **MO basis**, while ``overlap_integrals``
    and ``mo_coefficients`` are in the **AO basis** (the overlap in the MO basis is
    the identity by construction, hence not useful to return).

    Attributes:
        one_body_integrals: One-body integrals ``h_pq`` in the MO basis,
            shape ``(n_mo, n_mo)``.
        two_body_integrals: Two-body integrals ``(pq|rs)`` in the MO basis,
            chemist's notation (matching PySCF), shape
            ``(n_mo, n_mo, n_mo, n_mo)``.
        nuclear_repulsion_energy: Nuclear repulsion energy, in Hartree.
        num_spatial_orbitals: Number of spatial molecular orbitals (``n_mo``).
        num_particles: ``(n_alpha, n_beta)`` electron counts.
        hf_energy: Hartree-Fock total energy, in Hartree.
        overlap_integrals: AO-basis overlap matrix ``S_uv``, shape
            ``(n_ao, n_ao)``.
        mo_coefficients: AO-to-MO transformation matrix ``C`` (columns are
            MOs expressed in the AO basis), shape ``(n_ao, n_mo)``.
        problem: The Qiskit Nature ``ElectronicStructureProblem`` for VQE.
    """

    one_body_integrals: NDArray[np.float64]
    two_body_integrals: NDArray[np.float64]
    nuclear_repulsion_energy: float
    num_spatial_orbitals: int
    num_particles: tuple[int, int]
    hf_energy: float
    overlap_integrals: NDArray[np.float64]
    mo_coefficients: NDArray[np.float64]
    problem: ElectronicStructureProblem


def compute_integrals(
    atoms: str,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    charge: int = 0,
    spin: int = 0,
) -> MolecularIntegrals:
    """Compute molecular integrals for the given molecule.

    ``atoms`` is either a registry name (``"H2"``, ``"LiH"``, ``"HeH+"``,
    ``"BeH2"``) or a raw PySCF atom string (``"H 0 0 0; H 0 0 0.735"``).
    Registry names use *bond_length* (falling back to a default) to build the
    geometry.  Two-body integrals are returned in chemist's notation (ij|kl).
    """
    from pyscf import ao2mo
    from qiskit_nature.second_q.drivers import PySCFDriver
    from qiskit_nature.units import DistanceUnit

    from qorbital.chemistry.molecules import resolve_atom_string

    atom_string = resolve_atom_string(atoms, bond_length)

    driver = PySCFDriver(
        atom=atom_string,
        basis=basis,
        charge=charge,
        spin=spin,
        unit=DistanceUnit.ANGSTROM,
    )
    problem = driver.run()

    hamiltonian = problem.hamiltonian
    electronic_integrals = hamiltonian.electronic_integrals
    one_body = np.asarray(electronic_integrals.alpha["+-"])
    n_orb = problem.num_spatial_orbitals
    two_body_packed = np.asarray(electronic_integrals.alpha["++--"])
    two_body = ao2mo.restore(1, two_body_packed, n_orb)

    # Reuse the SCF PySCFDriver.run() already performed (avoids a second kernel()).
    mean_field = driver._calc
    hf_energy = float(mean_field.e_tot)
    mo_coefficients = np.asarray(mean_field.mo_coeff)
    overlap_integrals = np.asarray(mean_field.get_ovlp())

    return MolecularIntegrals(
        one_body_integrals=one_body,
        two_body_integrals=two_body,
        nuclear_repulsion_energy=hamiltonian.nuclear_repulsion_energy,
        num_spatial_orbitals=problem.num_spatial_orbitals,
        num_particles=problem.num_particles,
        hf_energy=hf_energy,
        overlap_integrals=overlap_integrals,
        mo_coefficients=mo_coefficients,
        problem=problem,
    )
