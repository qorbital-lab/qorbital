"""Generate visualization bundles for H2, HeH+, and LiH with Bohmian trajectories."""

from __future__ import annotations

import numpy as np

from qorbital.bohmian.integrator import integrate_trajectories
from qorbital.bohmian.projection import project_natural_orbital
from qorbital.bohmian.velocity import add_azimuthal_phase, velocity_field
from qorbital.chemistry.density import compute_density
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.molecules import DEFAULT_BOND_LENGTHS, get_molecule_params
from qorbital.viz.trajectories import build_molecule_bundle
from qorbital.vqe.solver import run_vqe

MOLECULE_LABELS: dict[str, str] = {
    "H2": "H₂",
    "HeH+": "HeH⁺",
    "LiH": "LiH",
}


def _generate_trajectories(
    density_grid,
    integrals,
    molecule: str,
    *,
    n_particles: int = 20,
    n_steps: int = 100,
) -> np.ndarray:
    """Generate Bohmian trajectories with azimuthal phase injection."""
    wf = project_natural_orbital(density_grid, integrals, molecule)
    psi_complex = add_azimuthal_phase(
        wf.psi, wf.origin, wf.spacing, strength=0.5
    )
    vx, vy, vz = velocity_field(psi_complex, wf.spacing)

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
    args = parser.parse_args()
    for mol in args.molecule:
        generate_bundle(mol)


if __name__ == "__main__":
    main()
