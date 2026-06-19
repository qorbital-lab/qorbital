"""Fermion-to-qubit Hamiltonian mapping via Qiskit Nature."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from qiskit.quantum_info import SparsePauliOp

from qorbital.chemistry.integrals import MolecularIntegrals


class QubitMapping(str, Enum):
    """Supported fermion-to-qubit mappings."""

    JORDAN_WIGNER = "jordan_wigner"
    PARITY = "parity"


@dataclass(frozen=True)
class QubitHamiltonian:
    """Qubit-space Hamiltonian and its metadata.

    ``qubit_op`` encodes the electronic energy only; ``nuclear_repulsion_energy``
    must be added back to recover the total molecular energy.
    """

    qubit_op: SparsePauliOp
    mapping: QubitMapping
    num_qubits: int
    num_spatial_orbitals: int
    num_particles: tuple[int, int]
    nuclear_repulsion_energy: float
    two_qubit_reduction: bool


def build_hamiltonian(
    atoms: str,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    charge: int = 0,
    spin: int = 0,
    mapping: QubitMapping | str = QubitMapping.JORDAN_WIGNER,
    two_qubit_reduction: bool = False,
) -> QubitHamiltonian:
    """Build a qubit Hamiltonian for the given molecule.

    ``atoms`` and ``bond_length`` follow the same convention as
    :func:`qorbital.chemistry.integrals.compute_integrals`.  ``mapping`` accepts
    the enum or the strings ``"jordan_wigner"`` / ``"parity"``.
    ``two_qubit_reduction=True`` is only valid with parity mapping.
    """
    from qorbital.chemistry.integrals import compute_integrals

    integrals = compute_integrals(
        atoms,
        bond_length=bond_length,
        basis=basis,
        charge=charge,
        spin=spin,
    )
    return map_integrals_to_qubit_op(integrals, mapping, two_qubit_reduction)


def make_mapper(
    mapping: QubitMapping | str,
    num_particles: tuple[int, int],
    two_qubit_reduction: bool,
):
    """Build the fermion-to-qubit mapper for the given configuration.

    Single source of truth for mapper selection. The Hamiltonian builder, the
    VQE ansatz, and 1-RDM extraction must all build operators with the *same*
    mapper, or the qubit counts and operator bases diverge (e.g. a hardcoded
    Jordan-Wigner 1-RDM operator panics against a parity+2qr statevector).

    ``two_qubit_reduction`` is only valid with parity mapping.
    """
    from qiskit_nature.second_q.mappers import JordanWignerMapper, ParityMapper

    if isinstance(mapping, str):
        mapping = QubitMapping(mapping)

    if two_qubit_reduction and mapping is not QubitMapping.PARITY:
        raise ValueError(
            "two_qubit_reduction is only supported with parity mapping, "
            f"got mapping={mapping.value!r}"
        )

    if mapping is QubitMapping.JORDAN_WIGNER:
        return JordanWignerMapper()
    if two_qubit_reduction:
        return ParityMapper(num_particles=num_particles)
    return ParityMapper()


def map_integrals_to_qubit_op(
    integrals: MolecularIntegrals,
    mapping: QubitMapping | str = QubitMapping.JORDAN_WIGNER,
    two_qubit_reduction: bool = False,
) -> QubitHamiltonian:
    """Map a pre-computed :class:`MolecularIntegrals` to a qubit Hamiltonian.

    Lower-level entry point used by VQE to avoid re-running PySCF.
    :func:`build_hamiltonian` delegates here.
    """
    if isinstance(mapping, str):
        mapping = QubitMapping(mapping)

    mapper = make_mapper(mapping, integrals.num_particles, two_qubit_reduction)

    fermionic_op = integrals.problem.hamiltonian.second_q_op()
    qubit_op: SparsePauliOp = mapper.map(fermionic_op)

    return QubitHamiltonian(
        qubit_op=qubit_op,
        mapping=mapping,
        num_qubits=qubit_op.num_qubits,
        num_spatial_orbitals=integrals.num_spatial_orbitals,
        num_particles=integrals.num_particles,
        nuclear_repulsion_energy=integrals.nuclear_repulsion_energy,
        two_qubit_reduction=two_qubit_reduction,
    )
