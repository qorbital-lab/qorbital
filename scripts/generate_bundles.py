"""Generate visualization bundles for H2, HeH+, and LiH with Bohmian trajectories.

Two modes:

* default — run a fresh VQE per molecule and write one bundle each.
* ``--ensemble`` — replay the recorded IonQ-style VQE runs in
  ``data/runs/<mol>/`` (one statevector per run) into per-run Bohmian
  trajectory sidecars plus an ``<mol>_ensemble.json`` manifest. Overlaying the
  members in the viewer produces the hardware-noise "uncertainty cloud".
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from qorbital.bohmian.integrator import integrate_superposition_trajectories_from_state
from qorbital.bohmian.seeds import sample_superposition_seeds
from qorbital.bohmian.velocity import superposition_period
from qorbital.chemistry.density import compute_density
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import DEFAULT_BOND_LENGTHS, get_molecule_params
from qorbital.chemistry.superposition import (
    SuperpositionState,
    build_superposition_from_ground_state,
)
from qorbital.viz.schema import SCHEMA_VERSION
from qorbital.viz.trajectories import (
    build_molecule_bundle,
    trajectory_set_from_superposition,
)
from qorbital.vqe.solver import run_vqe, statevector_from_params

MOLECULE_LABELS: dict[str, str] = {
    "H2": "H₂",
    "HeH+": "HeH⁺",
    "LiH": "LiH",
}

_GRID_POINTS: dict[str, int] = {
    "H2": 50,
    "HeH+": 50,
    "LiH": 64,
}

# Trajectory integration controls, shared by single-run and ensemble paths.
_N_PARTICLES = 20
_N_STEPS = 100
_N_PERIODS = 2.0


def _density_mapping(molecule: str) -> tuple[str, bool]:
    params = get_molecule_params(molecule)
    mapping = params.mapping
    two_qubit_reduction = params.two_qubit_reduction
    if molecule == "LiH":
        mapping = "jordan_wigner"
        two_qubit_reduction = False
    return mapping, two_qubit_reduction


def _generate_trajectories(
    ground_statevector: np.ndarray,
    integrals,
    molecule: str,
    *,
    bond: float | None = None,
    ground_energy: float | None = None,
    grid_points: int | None = None,
    n_particles: int = _N_PARTICLES,
    n_steps: int = _N_STEPS,
    n_periods: float = _N_PERIODS,
) -> tuple[np.ndarray, SuperpositionState, np.ndarray]:
    """Integrate honest superposition Bohmian trajectories from |psi(t0)|^2 seeds."""
    if bond is None:
        bond = DEFAULT_BOND_LENGTHS[molecule]
    if grid_points is None:
        grid_points = _GRID_POINTS.get(molecule, 50)

    mapping, two_qubit_reduction = _density_mapping(molecule)
    superposition = build_superposition_from_ground_state(
        ground_statevector,
        integrals,
        molecule,
        bond_length=bond,
        grid_points=grid_points,
        mapping=mapping,
        two_qubit_reduction=two_qubit_reduction,
        ground_energy=ground_energy,
    )
    seeds = sample_superposition_seeds(superposition, n_particles, t=0.0)
    period = superposition_period(superposition.E0, superposition.E1)
    times = np.linspace(0.0, n_periods * period, n_steps)
    trajectories = integrate_superposition_trajectories_from_state(
        superposition,
        seeds,
        n_periods=n_periods,
        n_steps=n_steps,
    )
    return trajectories, superposition, times


def generate_bundle(molecule: str) -> None:
    """Run full pipeline and write bundle for a molecule."""
    params = get_molecule_params(molecule)
    bond = DEFAULT_BOND_LENGTHS[molecule]
    mapping, two_qubit_reduction = _density_mapping(molecule)
    grid_points = _GRID_POINTS.get(molecule, 50)

    vqe_result = run_vqe(
        molecule,
        bond_length=bond,
        charge=params.charge,
        spin=params.spin,
        mapping=mapping,
        two_qubit_reduction=two_qubit_reduction,
    )
    integrals = compute_integrals(
        molecule,
        bond_length=bond,
        charge=params.charge,
        spin=params.spin,
    )
    density = compute_density(
        vqe_result.optimal_statevector,
        integrals,
        grid_points=grid_points,
        atom_string=molecule,
    )
    trajectories, superposition, times = _generate_trajectories(
        vqe_result.optimal_statevector,
        integrals,
        molecule,
        bond=bond,
        ground_energy=vqe_result.total_energy,
        grid_points=grid_points,
    )

    build_molecule_bundle(
        molecule,
        label=MOLECULE_LABELS.get(molecule, molecule),
        bond_length=bond,
        density=density,
        trajectories=trajectories,
        energy_hartree=vqe_result.total_energy,
        reference_energies={"hf": integrals.hf_energy},
        superposition=superposition,
        trajectory_times=times,
    )
    print(f"Bundle written for {molecule}")


def generate_ensemble(
    molecule: str,
    *,
    runs_dir: Path | None = None,
    output_dir: Path | None = None,
    bond_tol: float = 0.02,
    max_runs: int | None = None,
) -> None:
    """Replay recorded VQE runs at the equilibrium bond into a trajectory ensemble.

    Each eligible run (Jordan-Wigner mapped, bond within ``bond_tol`` of the
    equilibrium geometry) becomes one Bohmian trajectory sidecar. A manifest
    lists the members for the viewer to overlay.
    """
    params = get_molecule_params(molecule)
    equilibrium = DEFAULT_BOND_LENGTHS[molecule]
    grid_points = _GRID_POINTS.get(molecule, 50)
    if runs_dir is None:
        runs_dir = Path("data/runs") / molecule.lower()
    if output_dir is None:
        output_dir = Path("data/bundles") / molecule.lower()
    output_dir.mkdir(parents=True, exist_ok=True)

    run_files = sorted(runs_dir.glob("*.json"))
    if not run_files:
        print(f"No runs found for {molecule} in {runs_dir}; skipping ensemble.")
        return

    integrals_cache: dict[float, object] = {}
    members: list[dict] = []

    for run_file in run_files:
        if max_runs is not None and len(members) >= max_runs:
            break
        run = json.loads(run_file.read_text())
        bond = float(run.get("bond_length", equilibrium))
        if abs(bond - equilibrium) > bond_tol:
            continue
        mapper = run.get("mapper", "jordan_wigner")
        if mapper not in (None, "jordan_wigner"):
            print(f"  skip {run_file.name}: mapper {mapper!r} not JW-replayable")
            continue
        final = run.get("ansatz_params", {}).get("final")
        if final is None:
            print(f"  skip {run_file.name}: no final ansatz params")
            continue

        try:
            statevector = statevector_from_params(
                molecule, bond, params.charge, params.spin, final
            )
        except ValueError as exc:
            print(f"  skip {run_file.name}: {exc}")
            continue

        key = round(bond, 4)
        integrals = integrals_cache.get(key)
        if integrals is None:
            integrals = compute_integrals(
                molecule,
                bond_length=bond,
                charge=params.charge,
                spin=params.spin,
            )
            integrals_cache[key] = integrals

        trajectories, superposition, times = _generate_trajectories(
            statevector,
            integrals,
            molecule,
            bond=bond,
            ground_energy=run.get("energy"),
            grid_points=grid_points,
        )

        index = len(members)
        sidecar = f"{molecule.lower()}_ens_{index:02d}.bin"
        traj_set = trajectory_set_from_superposition(
            trajectories, output_dir, sidecar, superposition, times
        )
        members.append(
            {
                "run_id": run.get("run_id", run_file.stem),
                "paths": sidecar,
                "particles": traj_set.particles,
                "steps": traj_set.steps,
                "dt": traj_set.dt,
                "shots": run.get("shots"),
                "backend": run.get("backend"),
                "energy_hartree": run.get("energy"),
                "bond_length": bond,
            }
        )
        print(f"  member {index}: {run.get('run_id', run_file.stem)} -> {sidecar}")

    if not members:
        print(f"No eligible ensemble members for {molecule}; nothing written.")
        return

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "molecule": molecule,
        "label": MOLECULE_LABELS.get(molecule, molecule),
        "bond_length_angstrom": equilibrium,
        "path_layout": "particle-major",
        "color_by": "speed",
        "particles": members[0]["particles"],
        "steps": members[0]["steps"],
        "dt": members[0]["dt"],
        "runs": members,
    }
    manifest_path = output_dir / f"{molecule.lower()}_ensemble.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Ensemble manifest written for {molecule}: {len(members)} members")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate visualization bundles")
    parser.add_argument(
        "--molecule",
        nargs="+",
        choices=["H2", "HeH+", "LiH"],
        default=["H2", "HeH+", "LiH"],
        help="Molecules to generate (default: all)",
    )
    parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Replay recorded VQE runs into a trajectory ensemble + manifest",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Cap the number of ensemble members per molecule",
    )
    args = parser.parse_args()
    for mol in args.molecule:
        if args.ensemble:
            generate_ensemble(mol, max_runs=args.max_runs)
        else:
            generate_bundle(mol)


if __name__ == "__main__":
    main()
