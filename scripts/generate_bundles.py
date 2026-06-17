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
from qiskit.quantum_info import Statevector

from qorbital.bohmian.integrator import integrate_trajectories
from qorbital.bohmian.projection import project_natural_orbital
from qorbital.bohmian.velocity import add_azimuthal_phase, velocity_field
from qorbital.chemistry.density import compute_density
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import DEFAULT_BOND_LENGTHS, get_molecule_params
from qorbital.viz.schema import SCHEMA_VERSION
from qorbital.viz.trajectories import build_molecule_bundle, trajectories_to_sidecar
from qorbital.vqe.solver import _build_ansatz, run_vqe

MOLECULE_LABELS: dict[str, str] = {
    "H2": "H₂",
    "HeH+": "HeH⁺",
    "LiH": "LiH",
}

# Trajectory integration controls, shared by single-run and ensemble paths.
_N_PARTICLES = 20
_N_STEPS = 100
_DT = 0.1


def _generate_trajectories(
    density_grid,
    integrals,
    molecule: str,
    *,
    bond: float | None = None,
    n_particles: int = _N_PARTICLES,
    n_steps: int = _N_STEPS,
) -> np.ndarray:
    """Generate Bohmian trajectories with azimuthal phase injection."""
    wf = project_natural_orbital(density_grid, integrals, molecule)
    psi_complex = add_azimuthal_phase(
        wf.psi, wf.origin, wf.spacing, strength=0.5
    )
    vx, vy, vz = velocity_field(psi_complex, wf.spacing)

    if bond is None:
        bond = DEFAULT_BOND_LENGTHS[molecule]
    seeds = np.array(
        [[0.0, 0.0, z] for z in np.linspace(-bond * 0.3, bond * 0.3, n_particles)]
    )
    return integrate_trajectories(
        vx, vy, vz, wf.origin, wf.spacing, seeds, t_span=(0.0, 5.0), n_steps=n_steps
    )


def generate_bundle(molecule: str) -> None:
    """Run full pipeline and write bundle for a molecule."""
    params = get_molecule_params(molecule)
    bond = DEFAULT_BOND_LENGTHS[molecule]

    mapping = params.mapping
    two_qubit_reduction = params.two_qubit_reduction
    if molecule == "LiH":
        # compute_density only supports JW-mapped statevectors today.
        mapping = "jordan_wigner"
        two_qubit_reduction = False

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
        grid_points=30,
        atom_string=molecule,
    )
    trajectories = _generate_trajectories(density, integrals, molecule)

    build_molecule_bundle(
        molecule,
        label=MOLECULE_LABELS.get(molecule, molecule),
        bond_length=bond,
        density=density,
        trajectories=trajectories,
        energy_hartree=vqe_result.total_energy,
        reference_energies={"hf": integrals.hf_energy},
    )
    print(f"Bundle written for {molecule}")


def _statevector_from_params(
    molecule: str,
    bond: float,
    charge: int,
    spin: int,
    final_params,
) -> np.ndarray:
    """Rebuild a JW statevector from a run's recorded final ansatz parameters.

    Density extraction only supports Jordan-Wigner statevectors, so the
    replay uses JW regardless of the run's original mapper; the recorded UCCSD
    parameters are mapper-agnostic for the registry molecules used here.
    """
    qh = build_hamiltonian(
        molecule,
        bond_length=bond,
        charge=charge,
        spin=spin,
        mapping="jordan_wigner",
        two_qubit_reduction=False,
    )
    ansatz = _build_ansatz(qh)
    params = np.asarray(final_params, dtype=float)
    if params.shape[0] != ansatz.num_parameters:
        raise ValueError(
            f"{molecule}: run has {params.shape[0]} params but JW UCCSD ansatz "
            f"expects {ansatz.num_parameters}; cannot replay under JW."
        )
    bound = ansatz.assign_parameters(params)
    return np.asarray(Statevector(bound), dtype=np.complex128)


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
            statevector = _statevector_from_params(
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

        density = compute_density(
            statevector, integrals, grid_points=30, atom_string=molecule
        )
        trajectories = _generate_trajectories(
            density, integrals, molecule, bond=bond
        )

        index = len(members)
        sidecar = f"{molecule.lower()}_ens_{index:02d}.bin"
        traj_set = trajectories_to_sidecar(
            trajectories, output_dir, sidecar, dt=_DT
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
