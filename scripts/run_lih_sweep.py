"""Run LiH bond-length sweep on ionq_sim (sim-only stand-in for Forte Enterprise)."""

from __future__ import annotations

import argparse
import uuid

from qorbital.vqe.backends import Backend
from qorbital.vqe.submit import submit_vqe

DEFAULT_BOND_LENGTHS = [1.2, 1.4, 1.596, 1.8, 2.0]


def run_lih_sweep(
    bond_lengths: list[float] | None = None,
    runs_per_length: int = 2,
    shots: int = 5000,
    max_iterations: int = 30,
) -> None:
    """Submit LiH VQE runs at multiple bond lengths."""
    if bond_lengths is None:
        bond_lengths = DEFAULT_BOND_LENGTHS

    total = len(bond_lengths) * runs_per_length
    count = 0
    for r in bond_lengths:
        for j in range(runs_per_length):
            count += 1
            submit_vqe(
                "LiH",
                bond_length=r,
                backend=Backend.IONQ_SIM,
                shots=shots,
                max_iterations=max_iterations,
                run_id=f"lih_r{r:.3f}_{j}_{uuid.uuid4().hex[:6]}",
            )
            print(f"Completed LiH sweep {count}/{total} (R={r:.3f} Å)")


def main() -> None:
    parser = argparse.ArgumentParser(description="LiH bond-length sweep (sim-only)")
    parser.add_argument(
        "--bond-lengths",
        type=float,
        nargs="+",
        default=DEFAULT_BOND_LENGTHS,
    )
    parser.add_argument("--runs-per-length", type=int, default=2)
    parser.add_argument("--shots", type=int, default=5000)
    parser.add_argument("--max-iterations", type=int, default=30)
    args = parser.parse_args()
    run_lih_sweep(
        bond_lengths=args.bond_lengths,
        runs_per_length=args.runs_per_length,
        shots=args.shots,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()
