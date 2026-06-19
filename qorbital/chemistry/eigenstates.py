"""Exact eigenstates of a qubit Hamiltonian via dense diagonalization."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qorbital.chemistry.hamiltonian import QubitHamiltonian


def lowest_eigenstates(
    qubit_hamiltonian: QubitHamiltonian,
    k: int = 2,
) -> list[tuple[NDArray[np.complex128], float]]:
    """Return the ``k`` lowest-energy eigenpairs of a qubit Hamiltonian.

    Diagonalises ``qubit_hamiltonian.qubit_op`` in the mapper basis (Jordan-Wigner,
    parity, parity + two-qubit reduction, etc.).  Energies are **electronic only**;
    add ``nuclear_repulsion_energy`` to recover the total molecular energy.

    Returns:
        Ascending-energy list of ``(statevector, energy)`` pairs.  Each statevector
        is a 1D complex array of length ``2**num_qubits``.
    """
    dim = 2**qubit_hamiltonian.num_qubits
    if k < 1 or k > dim:
        raise ValueError(f"k must satisfy 1 <= k <= {dim}, got {k}")

    matrix = qubit_hamiltonian.qubit_op.to_matrix()
    vals, vecs = np.linalg.eigh(matrix)

    return [(vecs[:, i].astype(np.complex128), float(vals[i].real)) for i in range(k)]
