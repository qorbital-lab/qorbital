"""Measure the spin-free 1-RDM of a converged circuit on an Estimator (B10).

This is the *noise* density path of the sprint: instead of rebuilding an exact
statevector and reading the 1-RDM off it (the deterministic *reference* path,
:func:`qorbital.vqe.solver.statevector_from_params`), we evaluate the 1-RDM
``a+_p a_q`` expectation values term-by-term on a backend with shots.  Repeated
on hardware this yields a different noisy 1-RDM each time -> the uncertainty
ensemble (assembled in :mod:`qorbital.bohmian.noise_ensemble`).

Hermiticity.  A bare ``+_p -_q`` (``p != q``) maps to a *non-Hermitian*
``SparsePauliOp``.  ``Statevector.expectation_value`` tolerates that (it returns
a complex number), which is why the exact path in :mod:`qorbital.chemistry.density`
can use single ladder operators.  An :class:`~qiskit.primitives.BaseEstimatorV2`,
however, measures a Hermitian observable with shots and returns a real value, so
feeding it a non-Hermitian operator is invalid.  For a *real* ground state (true
for every registry molecule at its VQE optimum) the spin-free 1-RDM is
real-symmetric, so we measure only Hermitian combinations, summed over both spin
sectors:

* diagonal (``p == q``): the number operator ``a+_p a_p`` -> ``gamma_pp``
* off-diagonal (``p < q``): ``a+_p a_q + a+_q a_p`` -> ``2 * gamma_pq`` (symmetric),
  so ``gamma_pq = gamma_qp = <.> / 2``

giving ``n_orb*(n_orb+1)/2`` observables, all evaluated in a single batched PUB.
Complex wavefunctions would also need the antisymmetric ``i(a+_p a_q - a+_q a_p)``
term; that is out of scope (documented non-goal).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qiskit.primitives import BaseEstimatorV2
from qiskit.quantum_info import SparsePauliOp
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_nature.second_q.mappers import QubitMapper
from qiskit_nature.second_q.operators import FermionicOp

from qorbital.chemistry.hamiltonian import QubitHamiltonian, make_mapper
from qorbital.vqe.solver import _build_ansatz


@dataclass(frozen=True)
class MeasuredRDM:
    """One measured spin-free 1-RDM plus the provenance to replay it offline.

    ``rdm1_mo`` is the symmetric real 1-RDM in the MO basis (the artifact the
    density grid needs).  The remaining fields capture everything required to
    reconstruct the run without touching the device again: the per-term
    expectation values and standard errors, the upper-triangular ``(p, q)`` pairs
    they correspond to, the backend job ids, the mapper metadata, and the
    converged ansatz parameters.
    """

    rdm1_mo: NDArray[np.float64]
    term_evs: NDArray[np.float64]
    term_stds: NDArray[np.float64]
    term_pairs: list[tuple[int, int]]
    job_ids: list[str]
    num_spatial_orbitals: int
    mapping: str
    two_qubit_reduction: bool
    shots: int | None
    backend: str
    parameters: NDArray[np.float64]


def _hermitian_rdm_observables(
    num_spatial_orbitals: int, mapper: QubitMapper
) -> list[tuple[int, int, SparsePauliOp]]:
    """Hermitian, spin-summed 1-RDM observables for upper-triangular ``(p, q)``.

    Returns ``(p, q, qubit_op)`` triples where ``qubit_op`` measures
    ``gamma_pp`` (diagonal) or ``gamma_pq + gamma_qp = 2*gamma_pq`` (off-diagonal),
    summed over both spin sectors.  ``mapper`` must be the same mapper that
    produced the circuit (parity + 2-qubit reduction changes the qubit count and
    operator basis), exactly as in :func:`qorbital.chemistry.density._extract_rdm1`.
    """
    n_orb = num_spatial_orbitals
    n_so = 2 * n_orb
    terms: list[tuple[int, int, SparsePauliOp]] = []

    for p in range(n_orb):
        for q in range(p, n_orb):
            labels: dict[str, float] = {}
            for off in (0, n_orb):
                labels[f"+_{p + off} -_{q + off}"] = 1.0
                if q != p:
                    labels[f"+_{q + off} -_{p + off}"] = 1.0
            ferm_op = FermionicOp(labels, num_spin_orbitals=n_so)
            terms.append((p, q, mapper.map(ferm_op)))

    return terms


def _backend_label(estimator: BaseEstimatorV2) -> str:
    """Best-effort human-readable backend name for provenance."""
    backend = getattr(estimator, "backend", None)
    if backend is None:
        return type(estimator).__name__
    name = getattr(backend, "name", None)
    if callable(name):  # IonQ BackendV1 exposes name() as a method
        return str(name())
    return str(name) if name else type(backend).__name__


def _read_shots(estimator: BaseEstimatorV2) -> int | None:
    """Best-effort shot count from the estimator's backend options."""
    backend = getattr(estimator, "backend", None)
    options = getattr(backend, "options", None)
    shots = getattr(options, "shots", None) if options is not None else None
    return int(shots) if shots is not None else None


def _job_ids(job: Any) -> list[str]:
    jid = getattr(job, "job_id", None)
    if callable(jid):
        try:
            return [str(jid())]
        except Exception:  # noqa: BLE001 - provenance is best-effort
            return []
    return [str(jid)] if jid else []


def measure_rdm1(
    qubit_hamiltonian: QubitHamiltonian,
    parameters: NDArray[np.float64],
    estimator: BaseEstimatorV2,
) -> MeasuredRDM:
    """Measure the spin-free 1-RDM of the converged ansatz on ``estimator``.

    Mirrors :func:`qorbital.vqe.solver.evaluate_energy_on_estimator`: the ansatz
    is rebuilt with :func:`_build_ansatz` so the mapper/qubit count matches
    ``parameters``.  When the estimator wraps a real device (it exposes
    ``.backend``) the ansatz is transpiled to the device gateset and the
    observables are mapped onto the transpiled layout (``BackendEstimatorV2`` does
    not lower the UCCSD ``EvolvedOps`` block, which IonQ rejects).  An exact
    ``StatevectorEstimator`` has no ``.backend`` and handles the high-level ansatz
    directly, so the transpile step is skipped -- this is what lets the same
    function serve both the exact correctness test and the hardware path.

    All ``n_orb*(n_orb+1)/2`` observables are submitted in a single batched PUB;
    the returned :class:`MeasuredRDM` carries the reconstructed symmetric RDM plus
    the per-term values for offline replay.
    """
    mapper = make_mapper(
        qubit_hamiltonian.mapping,
        qubit_hamiltonian.num_particles,
        qubit_hamiltonian.two_qubit_reduction,
    )
    ansatz = _build_ansatz(qubit_hamiltonian)
    terms = _hermitian_rdm_observables(qubit_hamiltonian.num_spatial_orbitals, mapper)

    backend = getattr(estimator, "backend", None)
    if backend is not None:
        pass_manager = generate_preset_pass_manager(
            optimization_level=1, backend=backend
        )
        circuit = pass_manager.run(ansatz)
        observables = [op.apply_layout(circuit.layout) for (_, _, op) in terms]
    else:
        circuit = ansatz
        observables = [op for (_, _, op) in terms]

    params = np.asarray(parameters, dtype=float)
    job = estimator.run([(circuit, observables, [params])])
    pub_result = job.result()[0]
    evs = np.asarray(pub_result.data.evs, dtype=float).reshape(-1)
    raw_stds = getattr(pub_result.data, "stds", None)
    stds = (
        np.asarray(raw_stds, dtype=float).reshape(-1)
        if raw_stds is not None
        else np.zeros_like(evs)
    )

    if evs.shape[0] != len(terms):
        msg = (
            f"Estimator returned {evs.shape[0]} expectation values for "
            f"{len(terms)} observables; the batched-PUB broadcast did not match. "
            "Fall back to one PUB per observable for this primitive version."
        )
        raise RuntimeError(msg)

    n_orb = qubit_hamiltonian.num_spatial_orbitals
    rdm1 = np.zeros((n_orb, n_orb), dtype=np.float64)
    pairs: list[tuple[int, int]] = []
    for (p, q, _), ev in zip(terms, evs, strict=True):
        pairs.append((p, q))
        if p == q:
            rdm1[p, p] = ev
        else:
            value = ev / 2.0
            rdm1[p, q] = value
            rdm1[q, p] = value

    return MeasuredRDM(
        rdm1_mo=rdm1,
        term_evs=evs,
        term_stds=stds,
        term_pairs=pairs,
        job_ids=_job_ids(job),
        num_spatial_orbitals=n_orb,
        mapping=qubit_hamiltonian.mapping.value
        if hasattr(qubit_hamiltonian.mapping, "value")
        else str(qubit_hamiltonian.mapping),
        two_qubit_reduction=qubit_hamiltonian.two_qubit_reduction,
        shots=_read_shots(estimator),
        backend=_backend_label(estimator),
        parameters=params,
    )
