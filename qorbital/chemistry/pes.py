"""Potential energy surface generation with caching."""

from __future__ import annotations

import json
from pathlib import Path

from qorbital.chemistry.molecules import get_molecule_params
from qorbital.vqe.backends import Backend
from qorbital.vqe.solver import run_vqe


def compute_pes(
    molecule: str,
    bond_lengths: list[float],
    backend: Backend | str = Backend.AER,
    shots: int = 1024,
    basis: str = "sto-3g",
    max_iterations: int = 100,
) -> list[tuple[float, float]]:
    """Compute PES points ``[(bond_length, energy), ...]`` via VQE."""
    params = get_molecule_params(molecule)
    results: list[tuple[float, float]] = []
    for r in bond_lengths:
        vqe_result = run_vqe(
            molecule,
            bond_length=r,
            basis=basis,
            charge=params.charge,
            spin=params.spin,
            mapping=params.mapping,
            two_qubit_reduction=params.two_qubit_reduction,
            backend=backend,
            shots=shots,
            max_iterations=max_iterations,
        )
        results.append((r, vqe_result.total_energy))
    return results


def save_pes(
    molecule: str,
    pes: list[tuple[float, float]],
    output_dir: Path | None = None,
) -> Path:
    """Cache PES results to ``data/pes/<molecule>.json``."""
    if output_dir is None:
        output_dir = Path("data/pes")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{molecule.lower()}.json"
    payload = {
        "molecule": molecule,
        "points": [{"bond_length": r, "energy": e} for r, e in pes],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_pes(molecule: str, pes_dir: Path | None = None) -> list[tuple[float, float]]:
    """Load cached PES from disk."""
    if pes_dir is None:
        pes_dir = Path("data/pes")
    path = pes_dir / f"{molecule.lower()}.json"
    if not path.exists():
        msg = f"No cached PES for {molecule!r} at {path}"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(p["bond_length"], p["energy"]) for p in data["points"]]
