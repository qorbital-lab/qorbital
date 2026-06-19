"""VQE submission wrapper with run-log persistence."""

from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.molecules import (
    DEFAULT_BOND_LENGTHS,
    get_molecule_params,
)
from qorbital.vqe.backends import Backend, make_estimator
from qorbital.vqe.solver import (
    VQEResult,
    evaluate_energy_on_estimator,
    run_vqe_from_hamiltonian,
)

#: IonQ backends that execute the converged circuit on the cloud.
_HARDWARE_BACKENDS = (Backend.IONQ_SIM, Backend.IONQ_ARIA)

#: Candidate keys for per-job credit cost in an IonQ job's response metadata.
#: qiskit-ionq does not parse cost itself, so we probe defensively.
_COST_KEYS = ("cost_usd", "cost", "usd")


@dataclass
class RunLog:
    """Schema for a persisted VQE run."""

    run_id: str
    molecule: str
    geometry: str
    bond_length: float
    basis: str
    mapper: str
    two_qubit_reduction: bool
    ansatz_params: dict[str, list[float]]
    backend: str
    shots: int
    optimizer_history: list[dict[str, Any]]
    energy: float
    electronic_energy: float
    nuclear_repulsion_energy: float
    cost_credits: float | None
    timestamp: str


def _result_to_log(
    result: VQEResult,
    *,
    molecule: str,
    bond_length: float,
    basis: str,
    mapper: str,
    two_qubit_reduction: bool,
    backend: str,
    shots: int,
    cost_credits: float | None = None,
    run_id: str | None = None,
) -> RunLog:
    from qorbital.chemistry.molecules import resolve_atom_string

    run_id = run_id or str(uuid.uuid4())[:8]
    history = [
        {
            "iteration": snap.iteration,
            "energy": snap.energy,
            "parameters": snap.parameters.tolist(),
        }
        for snap in result.convergence_history
    ]
    return RunLog(
        run_id=run_id,
        molecule=molecule,
        geometry=resolve_atom_string(molecule, bond_length),
        bond_length=bond_length,
        basis=basis,
        mapper=mapper,
        two_qubit_reduction=two_qubit_reduction,
        ansatz_params={
            "init": [0.0] * len(result.optimal_parameters),
            "final": result.optimal_parameters.tolist(),
        },
        backend=backend,
        shots=shots,
        optimizer_history=history,
        energy=result.total_energy,
        electronic_energy=result.electronic_energy,
        nuclear_repulsion_energy=result.nuclear_repulsion_energy,
        cost_credits=cost_credits,
        timestamp=datetime.now(tz=UTC).isoformat(),
    )


def _best_effort_cost(jobs: list[Any]) -> float | None:
    """Sum the credit cost of IonQ ``jobs``, or ``None`` if unavailable.

    Best-effort by design: qiskit-ionq stows the raw job API response on the
    private ``_metadata`` dict (populated once results are fetched) but does not
    expose a typed cost field, and the cloud *simulator* reports no cost.  We
    probe a few candidate keys and degrade to ``None`` on anything unexpected so
    a missing/renamed field never breaks a run.
    """
    total = 0.0
    found = False
    for job in jobs:
        meta = getattr(job, "_metadata", None)
        if not isinstance(meta, dict):
            continue
        for key in _COST_KEYS:
            value = meta.get(key)
            if value is not None:
                try:
                    total += float(value)
                    found = True
                except (TypeError, ValueError):
                    pass
                break
    return total if found else None


def _evaluate_on_ionq(
    qubit_hamiltonian: Any,
    parameters: Any,
    backend: Backend,
    shots: int,
) -> tuple[float, float | None]:
    """Submit the converged circuit to IonQ; return (electronic_energy, cost).

    Reuses B7's :func:`make_estimator` primitive (it submits and polls
    internally).  We transiently wrap the device's ``run`` to capture the
    submitted IonQ job objects so credit cost can be read back best-effort
    afterwards, then restore the original method.
    """
    estimator = make_estimator(backend, shots=shots)
    device = estimator.backend
    captured: list[Any] = []
    original_run = device.run

    def _capturing_run(*args: Any, **kwargs: Any) -> Any:
        job = original_run(*args, **kwargs)
        captured.append(job)
        return job

    device.run = _capturing_run
    try:
        electronic = evaluate_energy_on_estimator(
            qubit_hamiltonian, parameters, estimator
        )
    finally:
        device.run = original_run

    return electronic, _best_effort_cost(captured)


def submit_vqe(
    molecule: str,
    *,
    bond_length: float | None = None,
    basis: str = "sto-3g",
    backend: Backend | str = Backend.IONQ_SIM,
    shots: int = 1000,
    max_iterations: int = 100,
    output_dir: Path | None = None,
    run_id: str | None = None,
) -> RunLog:
    """Run VQE and persist the result as a JSON run log."""
    params = get_molecule_params(molecule)
    if bond_length is None:
        bond_length = DEFAULT_BOND_LENGTHS.get(molecule, 1.0)

    if isinstance(backend, str):
        backend = Backend(backend.lower())

    # Locked decision: always optimise on the local statevector simulator; IonQ
    # credits are spent only on the converged circuit.  Build the Hamiltonian
    # here (run_vqe discards it) so we can re-submit its qubit_op as the
    # observable for the hardware evaluation below.
    qubit_hamiltonian = build_hamiltonian(
        molecule,
        bond_length=bond_length,
        basis=basis,
        charge=params.charge,
        spin=params.spin,
        mapping=params.mapping,
        two_qubit_reduction=params.two_qubit_reduction,
    )
    result = run_vqe_from_hamiltonian(qubit_hamiltonian, max_iterations=max_iterations)

    # Real submit-and-poll: evaluate the converged circuit on the IonQ backend
    # and overwrite the energy with the measured value.  AER keeps the exact
    # local energy.  (No synthetic noise: real ionq_sim runs carry genuine shot
    # noise, which is what the ensemble/uncertainty story relies on.)
    cost_credits: float | None = None
    if backend in _HARDWARE_BACKENDS:
        electronic, cost_credits = _evaluate_on_ionq(
            qubit_hamiltonian, result.optimal_parameters, backend, shots
        )
        result.electronic_energy = electronic
        result.total_energy = electronic + qubit_hamiltonian.nuclear_repulsion_energy

    log = _result_to_log(
        result,
        molecule=molecule,
        bond_length=bond_length,
        basis=basis,
        mapper=params.mapping,
        two_qubit_reduction=params.two_qubit_reduction,
        backend=backend.value,
        shots=shots,
        cost_credits=cost_credits,
        run_id=run_id,
    )

    if output_dir is None:
        output_dir = Path("data/runs") / molecule.lower()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / f"{log.run_id}.json"
    log_path.write_text(json.dumps(asdict(log), indent=2) + "\n", encoding="utf-8")
    return log


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a VQE run and log results")
    parser.add_argument("--molecule", required=True, help="Molecule name (e.g. h2)")
    parser.add_argument(
        "--backend",
        default="ionq_sim",
        choices=[b.value for b in Backend],
    )
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--bond-length", type=float, default=None)
    parser.add_argument("--basis", default="sto-3g")
    parser.add_argument("--max-iterations", type=int, default=100)
    args = parser.parse_args()

    molecule = args.molecule
    if molecule.upper() == "H2":
        molecule = "H2"
    elif molecule.upper() in ("HEH+", "HEH"):
        molecule = "HeH+"
    elif molecule.upper() == "LIH":
        molecule = "LiH"

    log = submit_vqe(
        molecule,
        bond_length=args.bond_length,
        basis=args.basis,
        backend=args.backend,
        shots=args.shots,
        max_iterations=args.max_iterations,
    )
    print(f"Run {log.run_id} complete: E = {log.energy:.6f} Ha")


if __name__ == "__main__":
    main()
