from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import Statevector
from qiskit_algorithms import VQE
from qiskit_algorithms.optimizers import COBYLA, SLSQP
from qiskit_nature.second_q.circuit.library import UCCSD, HartreeFock
from qiskit_nature.second_q.mappers import JordanWignerMapper, ParityMapper

from qorbital.chemistry.hamiltonian import (
    QubitHamiltonian,
    QubitMapping,
    build_hamiltonian,
)


@dataclass
class VQEIterationData:
    """Snapshot from one VQE optimisation iteration."""

    iteration: int
    parameters: NDArray[np.float64]
    energy: float  # electronic energy (no nuclear repulsion)
    metadata: dict


@dataclass
class VQEResult:
    """Container for VQE solver output."""

    total_energy: float  # electronic + nuclear repulsion
    electronic_energy: float  # raw VQE eigenvalue
    nuclear_repulsion_energy: float  # constant offset
    optimal_parameters: NDArray[np.float64]  # optimised ansatz params
    optimal_statevector: NDArray[np.complex128]  # final statevector array
    num_iterations: int  # optimizer eval count
    convergence_history: list[VQEIterationData]  # per-iteration snapshots
    optimizer_name: str  # e.g. "SLSQP"
    ansatz_name: str  # e.g. "UCCSD"


OPTIMIZER_REGISTRY: dict[str, type] = {
    "SLSQP": SLSQP,
    "COBYLA": COBYLA,
}


def _build_ansatz(qubit_hamiltonian: QubitHamiltonian) -> UCCSD:
    if (
        qubit_hamiltonian.two_qubit_reduction
        and qubit_hamiltonian.mapping is not QubitMapping.PARITY
    ):
        raise ValueError(
            "two_qubit_reduction is only supported with parity mapping, "
            f"got mapping={qubit_hamiltonian.mapping.value!r}"
        )

    if qubit_hamiltonian.mapping is QubitMapping.JORDAN_WIGNER:
        mapper = JordanWignerMapper()
    elif qubit_hamiltonian.two_qubit_reduction:
        mapper = ParityMapper(num_particles=qubit_hamiltonian.num_particles)
    else:
        mapper = ParityMapper()

    initial_state = HartreeFock(
        num_spatial_orbitals=qubit_hamiltonian.num_spatial_orbitals,
        num_particles=qubit_hamiltonian.num_particles,
        qubit_mapper=mapper,
    )

    ansatz = UCCSD(
        num_spatial_orbitals=qubit_hamiltonian.num_spatial_orbitals,
        num_particles=qubit_hamiltonian.num_particles,
        qubit_mapper=mapper,
        initial_state=initial_state,
    )

    return ansatz


def _make_callback(
    history: list[VQEIterationData],
    user_callback: Callable[[VQEIterationData], None] | None,
) -> Callable[[int, np.ndarray, float, dict], None]:
    def _cb(
        eval_count: int, parameters: np.ndarray, mean: float, metadata: dict
    ) -> None:
        snapshot = VQEIterationData(
            iteration=eval_count,
            parameters=parameters.copy(),
            energy=mean,
            metadata=metadata if isinstance(metadata, dict) else {},
        )
        history.append(snapshot)
        if user_callback is not None:
            user_callback(snapshot)

    return _cb


def run_vqe_from_hamiltonian(
    qubit_hamiltonian: QubitHamiltonian,
    optimizer: str = "SLSQP",
    max_iterations: int = 100,
    callback: Callable[[VQEIterationData], None] | None = None,
) -> VQEResult:
    ansatz = _build_ansatz(qubit_hamiltonian)

    optimizer_name = optimizer.upper()
    if optimizer_name not in OPTIMIZER_REGISTRY:
        raise ValueError(
            f"Unknown optimizer {optimizer!r}. Supported: {list(OPTIMIZER_REGISTRY)}"
        )
    opt = OPTIMIZER_REGISTRY[optimizer_name](maxiter=max_iterations)

    estimator = StatevectorEstimator()

    convergence_history: list[VQEIterationData] = []
    vqe_callback = _make_callback(convergence_history, callback)

    initial_point = np.zeros(ansatz.num_parameters)

    vqe = VQE(
        estimator=estimator,
        ansatz=ansatz,
        optimizer=opt,
        callback=vqe_callback,
        initial_point=initial_point,
    )
    result = vqe.compute_minimum_eigenvalue(operator=qubit_hamiltonian.qubit_op)

    bound_circuit = ansatz.assign_parameters(result.optimal_point)
    sv_array = np.array(Statevector(bound_circuit))

    electronic_energy = result.eigenvalue.real
    total_energy = electronic_energy + qubit_hamiltonian.nuclear_repulsion_energy

    return VQEResult(
        total_energy=total_energy,
        electronic_energy=electronic_energy,
        nuclear_repulsion_energy=qubit_hamiltonian.nuclear_repulsion_energy,
        optimal_parameters=np.array(result.optimal_point),
        optimal_statevector=sv_array,
        num_iterations=result.cost_function_evals,
        convergence_history=convergence_history,
        optimizer_name=optimizer_name,
        ansatz_name="UCCSD",
    )


def run_vqe(
    atoms: str,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    charge: int = 0,
    spin: int = 0,
    mapping: str = "jordan_wigner",
    two_qubit_reduction: bool = False,
    optimizer: str = "SLSQP",
    max_iterations: int = 100,
    callback: Callable[[VQEIterationData], None] | None = None,
) -> VQEResult:
    qh = build_hamiltonian(
        atoms,
        bond_length=bond_length,
        basis=basis,
        charge=charge,
        spin=spin,
        mapping=mapping,
        two_qubit_reduction=two_qubit_reduction,
    )
    return run_vqe_from_hamiltonian(
        qh,
        optimizer=optimizer,
        max_iterations=max_iterations,
        callback=callback,
    )
