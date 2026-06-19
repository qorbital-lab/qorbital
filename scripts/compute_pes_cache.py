"""Compute and cache PES data for the bond-length slider."""

from __future__ import annotations

import argparse

import numpy as np

from qorbital.chemistry.molecules import get_molecule_params
from qorbital.chemistry.pes import compute_pes, save_pes
from qorbital.vqe.backends import Backend


def compute_pes_exact(
    molecule: str, bond_lengths: list[float]
) -> list[tuple[float, float]]:
    """Exact-diagonalization PES (fast; useful for LiH where VQE is slow)."""
    from qorbital.chemistry.hamiltonian import build_hamiltonian

    params = get_molecule_params(molecule)
    results: list[tuple[float, float]] = []
    for r in bond_lengths:
        qh = build_hamiltonian(
            molecule,
            bond_length=r,
            charge=params.charge,
            spin=params.spin,
            mapping=params.mapping,
            two_qubit_reduction=params.two_qubit_reduction,
        )
        matrix = qh.qubit_op.to_matrix()
        eigvals = np.linalg.eigh(matrix)[0]
        energy = float(eigvals[0]) + qh.nuclear_repulsion_energy
        results.append((r, energy))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute and cache PES JSON")
    parser.add_argument("--molecule", required=True, choices=["H2", "LiH", "HeH+"])
    parser.add_argument(
        "--bond-lengths",
        type=float,
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "--method",
        choices=["vqe", "exact"],
        default="vqe",
        help="vqe=slow/realistic; exact=fast reference curve",
    )
    parser.add_argument("--max-iterations", type=int, default=30)
    args = parser.parse_args()

    if args.bond_lengths is None:
        if args.molecule == "H2":
            args.bond_lengths = [
                0.55,
                0.65,
                0.735,
                0.85,
                0.95,
                1.05,
                1.15,
                1.25,
                1.35,
                1.5,
            ]
        elif args.molecule == "LiH":
            args.bond_lengths = [1.2, 1.35, 1.5, 1.596, 1.7, 1.85, 2.0, 2.2, 2.4, 2.6]
        else:
            args.bond_lengths = [
                0.6,
                0.7,
                0.772,
                0.85,
                0.95,
                1.05,
                1.15,
                1.25,
                1.4,
                1.6,
            ]

    if args.method == "exact":
        pes = compute_pes_exact(args.molecule, args.bond_lengths)
    else:
        pes = compute_pes(
            args.molecule,
            args.bond_lengths,
            backend=Backend.AER,
            max_iterations=args.max_iterations,
        )

    path = save_pes(args.molecule, pes)
    print(f"Saved {len(pes)} points to {path}")
    for r, e in pes:
        print(f"  R={r:.3f} Å  E={e:.6f} Ha")


if __name__ == "__main__":
    main()
