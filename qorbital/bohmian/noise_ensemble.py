"""Hardware noise ensemble: repeated 1-RDM measurement -> uncertainty cloud (B10).

This is the orchestrator for the sprint's *noise* density path.  The measurement
primitive (:func:`qorbital.vqe.hardware_rdm.measure_rdm1`) lives in ``vqe``; this
module lives in ``bohmian`` because it also needs trajectory generation
(:func:`qorbital.bohmian.trajectories.generate_trajectories`), keeping imports
flowing one direction (chemistry -> vqe -> bohmian -> viz).

For a converged circuit we measure the 1-RDM ``M`` times on a backend with shots.
On real hardware each run differs (genuine device noise); each noisy 1-RDM ->
a different density -> different Bohmian trajectories.  The spread across the M
trajectory sets is the uncertainty cloud consumed by F5
(:func:`qorbital.bohmian.uncertainty.compute_uncertainty_cloud`).

Offline reproducibility.  ``BackendEstimatorV2`` returns expectation values, not
raw shot bitstrings, so literal "raw counts" are not recoverable through that
interface.  Instead we cache the faithful, self-describing artifact: the per-run
noisy 1-RDM plus full provenance (per-term expectation values and standard
errors, the ``(p, q)`` term map, backend job ids, mapper metadata, converged
parameters).  Re-running with the same ``cache_path`` rebuilds densities and
trajectories deterministically with zero device calls.  A Sampler-based raw-count
path is a possible future enhancement (B11) if true bitstring counts are needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from qorbital.bohmian.trajectories import generate_trajectories
from qorbital.bohmian.uncertainty import UncertaintyCloud, compute_uncertainty_cloud
from qorbital.chemistry.density import ElectronDensityGrid, density_from_rdm1
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import DEFAULT_BOND_LENGTHS
from qorbital.vqe.backends import Backend, make_estimator
from qorbital.vqe.hardware_rdm import MeasuredRDM, measure_rdm1
from qorbital.vqe.solver import run_vqe_from_hamiltonian


@dataclass(frozen=True)
class NoiseEnsemble:
    """M measured 1-RDMs and the densities/trajectories rebuilt from them."""

    measured_rdms: list[MeasuredRDM]
    densities: list[ElectronDensityGrid]
    trajectory_sets: list[NDArray[np.float64]]
    origin: NDArray[np.float64]
    spacing: NDArray[np.float64]
    grid_shape: tuple[int, int, int]
    molecule: str
    bond: float
    shots: int | None
    backend: str

    @property
    def m(self) -> int:
        return len(self.measured_rdms)


def _build_member(
    measured: MeasuredRDM,
    integrals: object,
    molecule: str,
    bond: float,
    grid_points: int,
) -> tuple[ElectronDensityGrid, NDArray[np.float64]]:
    """Noisy RDM -> density grid -> Bohmian trajectories (deterministic, no device)."""
    density = density_from_rdm1(
        measured.rdm1_mo, integrals, molecule, grid_points=grid_points
    )
    trajectories = generate_trajectories(density, integrals, molecule, bond=bond)
    return density, trajectories


def _save_cache(cache_path: Path, measured: list[MeasuredRDM], meta: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        cache_path,
        rdms=np.stack([m.rdm1_mo for m in measured]),
        term_evs=np.stack([m.term_evs for m in measured]),
        term_stds=np.stack([m.term_stds for m in measured]),
        parameters=measured[0].parameters,
        term_pairs=np.array(measured[0].term_pairs, dtype=int),
        meta=np.array(json.dumps(meta)),
    )


def _measured_from_cache(cache_path: Path) -> tuple[list[MeasuredRDM], dict]:
    data = np.load(cache_path, allow_pickle=False)
    meta = json.loads(str(data["meta"]))
    rdms = data["rdms"]
    term_evs = data["term_evs"]
    term_stds = data["term_stds"]
    parameters = data["parameters"]
    pairs = [(int(p), int(q)) for p, q in data["term_pairs"]]
    job_ids = meta.get("job_ids", [[] for _ in range(len(rdms))])

    measured = [
        MeasuredRDM(
            rdm1_mo=rdms[i],
            term_evs=term_evs[i],
            term_stds=term_stds[i],
            term_pairs=pairs,
            job_ids=job_ids[i] if i < len(job_ids) else [],
            num_spatial_orbitals=int(meta["num_spatial_orbitals"]),
            mapping=meta["mapping"],
            two_qubit_reduction=bool(meta["two_qubit_reduction"]),
            shots=meta.get("shots"),
            backend=meta["backend"],
            parameters=parameters,
        )
        for i in range(len(rdms))
    ]
    return measured, meta


def measure_rdm_ensemble(
    molecule: str,
    *,
    bond: float | None = None,
    charge: int = 0,
    spin: int = 0,
    mapping: str = "jordan_wigner",
    two_qubit_reduction: bool = False,
    m: int = 8,
    shots: int = 1000,
    backend: Backend | str = Backend.IONQ_SIM,
    parameters: NDArray[np.float64] | None = None,
    grid_points: int = 30,
    max_iterations: int = 100,
    cache_path: Path | str | None = None,
) -> NoiseEnsemble:
    """Measure the 1-RDM ``m`` times and assemble the noise ensemble.

    If ``cache_path`` exists, the ensemble is replayed from the cached per-run
    RDMs (no device calls).  Otherwise the converged parameters are obtained
    (``parameters`` if given, else a single local VQE optimisation), the 1-RDM is
    measured ``m`` times on ``backend`` with ``shots``, and the result is cached
    to ``cache_path`` when provided.  Validate on ``Backend.IONQ_SIM`` (shot noise,
    no credits) before any QPU run.
    """
    if bond is None:
        bond = DEFAULT_BOND_LENGTHS[molecule]
    cache_path = Path(cache_path) if cache_path is not None else None

    integrals = compute_integrals(molecule, bond_length=bond, charge=charge, spin=spin)

    if cache_path is not None and cache_path.exists():
        measured, meta = _measured_from_cache(cache_path)
        bond = float(meta.get("bond", bond))
    else:
        qh = build_hamiltonian(
            molecule,
            bond_length=bond,
            charge=charge,
            spin=spin,
            mapping=mapping,
            two_qubit_reduction=two_qubit_reduction,
        )
        if parameters is None:
            vqe_result = run_vqe_from_hamiltonian(qh, max_iterations=max_iterations)
            parameters = vqe_result.optimal_parameters

        measured = []
        for _ in range(m):
            # Fresh estimator per run so a real backend re-seeds shot noise each
            # execution; for AER (exact statevector) the runs are identical.
            estimator = make_estimator(backend, shots=shots)
            measured.append(measure_rdm1(qh, parameters, estimator))

        if cache_path is not None:
            meta = {
                "molecule": molecule,
                "bond": bond,
                "charge": charge,
                "spin": spin,
                "mapping": measured[0].mapping,
                "two_qubit_reduction": measured[0].two_qubit_reduction,
                "grid_points": grid_points,
                "shots": measured[0].shots,
                "backend": measured[0].backend,
                "num_spatial_orbitals": measured[0].num_spatial_orbitals,
                "job_ids": [m_.job_ids for m_ in measured],
            }
            _save_cache(cache_path, measured, meta)

    densities: list[ElectronDensityGrid] = []
    trajectory_sets: list[NDArray[np.float64]] = []
    for mr in measured:
        density, trajectories = _build_member(
            mr, integrals, molecule, bond, grid_points
        )
        densities.append(density)
        trajectory_sets.append(trajectories)

    return NoiseEnsemble(
        measured_rdms=measured,
        densities=densities,
        trajectory_sets=trajectory_sets,
        origin=densities[0].origin,
        spacing=densities[0].spacing,
        grid_shape=densities[0].grid_shape,
        molecule=molecule,
        bond=bond,
        shots=measured[0].shots,
        backend=measured[0].backend,
    )


def ensemble_to_cloud(ensemble: NoiseEnsemble) -> UncertaintyCloud:
    """Histogram the ensemble's trajectory sets into an F5 uncertainty cloud."""
    return compute_uncertainty_cloud(
        ensemble.trajectory_sets,
        ensemble.origin,
        ensemble.spacing,
        ensemble.grid_shape,
    )
