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
    """One- and two-body integrals in the MO basis.

    Two-body integrals use chemist's notation (ij|kl), matching PySCF convention.
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
    from pyscf import ao2mo, gto, scf
    from qiskit_nature.second_q.drivers import PySCFDriver
    from qiskit_nature.units import DistanceUnit

    from qorbital.chemistry.molecules import resolve_atom_string

    atom_string = resolve_atom_string(atoms, bond_length)

    # Qiskit Nature driver → ElectronicStructureProblem
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

    # Parallel lightweight PySCF call for HF energy and MO data
    mol = gto.M(
        atom=atom_string, basis=basis, charge=charge, spin=spin, unit="Angstrom"
    )
    mf = scf.RHF(mol)
    hf_energy = mf.kernel()

    return MolecularIntegrals(
        one_body_integrals=one_body,
        two_body_integrals=two_body,
        nuclear_repulsion_energy=hamiltonian.nuclear_repulsion_energy,
        num_spatial_orbitals=problem.num_spatial_orbitals,
        num_particles=problem.num_particles,
        hf_energy=hf_energy,
        overlap_integrals=mol.intor("int1e_ovlp"),
        mo_coefficients=mf.mo_coeff,
        problem=problem,
    )
