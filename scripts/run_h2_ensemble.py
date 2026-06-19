"""Run the H2 VQE hardware campaign on IonQ Forte Enterprise (B11).

Defaults to the real ``ionq_forte`` QPU (``qpu.forte-enterprise-1``); pass
``--backend ionq_sim`` to validate against the cloud simulator (shot noise, no
credits) before spending QPU time.  Each run optimises locally and submits only
the converged circuit (locked sprint decision), so this spends QPU credits per
run -- queue early (status.ionq.co).

Beyond the equilibrium ensemble it can emit a shot-count ladder
(``--shot-ladder``) for the "sharpen-with-shots" story: one converged-circuit
run per rung at increasing shot counts.
"""

from __future__ import annotations

import argparse
import uuid

from qorbital.vqe.backends import Backend
from qorbital.vqe.submit import submit_vqe

#: Shots for the sharpen-with-shots ladder (one converged-circuit run per rung).
DEFAULT_SHOT_LADDER = [100, 1000, 10000, 100000]


def run_h2_ensemble(
    n_runs: int = 10,
    shots: int = 5000,
    noisy_shots: int = 500,
    n_noisy: int = 2,
    max_iterations: int = 100,
    backend: Backend | str = Backend.IONQ_FORTE,
    shot_ladder: list[int] | None = None,
) -> None:
    """Submit independent H2 VQE runs and persist logs.

    ``n_noisy`` of the ``n_runs`` runs use ``noisy_shots`` (low shot count) so
    node "wobble" is visible; the rest use ``shots``.  When ``shot_ladder`` is
    given, one extra converged-circuit run is submitted per rung.
    """
    for i in range(n_runs):
        run_shots = noisy_shots if i < n_noisy else shots
        submit_vqe(
            "H2",
            backend=backend,
            shots=run_shots,
            max_iterations=max_iterations,
            run_id=f"h2_ensemble_{i:02d}_{uuid.uuid4().hex[:6]}",
        )
        print(f"Completed H2 ensemble run {i + 1}/{n_runs} ({run_shots} shots)")

    if shot_ladder:
        for rung, ladder_shots in enumerate(shot_ladder):
            submit_vqe(
                "H2",
                backend=backend,
                shots=ladder_shots,
                max_iterations=max_iterations,
                run_id=f"h2_ladder_{ladder_shots}_{uuid.uuid4().hex[:6]}",
            )
            print(
                f"Completed H2 shot-ladder rung {rung + 1}/{len(shot_ladder)} "
                f"({ladder_shots} shots)"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="H2 VQE hardware ensemble")
    parser.add_argument(
        "--backend",
        default=Backend.IONQ_FORTE.value,
        choices=[b.value for b in Backend],
        help="Execution backend (default: ionq_forte; use ionq_sim to validate)",
    )
    parser.add_argument("--n-runs", type=int, default=10)
    parser.add_argument("--shots", type=int, default=5000)
    parser.add_argument("--noisy-shots", type=int, default=500)
    parser.add_argument("--n-noisy", type=int, default=2)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument(
        "--shot-ladder",
        type=int,
        nargs="*",
        default=None,
        metavar="SHOTS",
        help=(
            "Emit a shot-count ladder (one run per rung). Pass values "
            f"(e.g. {' '.join(map(str, DEFAULT_SHOT_LADDER))}) or no values to "
            "use the default ladder."
        ),
    )
    args = parser.parse_args()

    # nargs="*" gives [] when the flag is passed bare; treat that as the default
    # ladder, and None (flag absent) as "no ladder".
    shot_ladder = args.shot_ladder
    if shot_ladder is not None and len(shot_ladder) == 0:
        shot_ladder = DEFAULT_SHOT_LADDER

    run_h2_ensemble(
        n_runs=args.n_runs,
        shots=args.shots,
        noisy_shots=args.noisy_shots,
        n_noisy=args.n_noisy,
        max_iterations=args.max_iterations,
        backend=args.backend,
        shot_ladder=shot_ladder,
    )


if __name__ == "__main__":
    main()
