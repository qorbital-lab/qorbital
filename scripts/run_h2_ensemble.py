"""Run H2 VQE ensemble on ionq_sim (sim-only stand-in for Forte Enterprise hardware)."""

from __future__ import annotations

import argparse
import uuid

from qorbital.vqe.backends import Backend
from qorbital.vqe.submit import submit_vqe


def run_h2_ensemble(
    n_runs: int = 10,
    shots: int = 5000,
    noisy_shots: int = 500,
    n_noisy: int = 2,
    max_iterations: int = 100,
) -> None:
    """Submit independent H2 VQE runs and persist logs."""
    for i in range(n_runs):
        run_shots = noisy_shots if i < n_noisy else shots
        submit_vqe(
            "H2",
            backend=Backend.IONQ_SIM,
            shots=run_shots,
            max_iterations=max_iterations,
            run_id=f"h2_ensemble_{i:02d}_{uuid.uuid4().hex[:6]}",
        )
        print(f"Completed H2 ensemble run {i + 1}/{n_runs} ({run_shots} shots)")


def main() -> None:
    parser = argparse.ArgumentParser(description="H2 VQE ensemble (sim-only)")
    parser.add_argument("--n-runs", type=int, default=10)
    parser.add_argument("--shots", type=int, default=5000)
    parser.add_argument("--noisy-shots", type=int, default=500)
    parser.add_argument("--n-noisy", type=int, default=2)
    parser.add_argument("--max-iterations", type=int, default=100)
    args = parser.parse_args()
    run_h2_ensemble(
        n_runs=args.n_runs,
        shots=args.shots,
        noisy_shots=args.noisy_shots,
        n_noisy=args.n_noisy,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()
