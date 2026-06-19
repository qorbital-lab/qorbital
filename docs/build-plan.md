# qOrbital — Segmented Build Plan (Hardware-Demo Sprint)

## Context

The `integration/3day` branch already has a working end-to-end pipeline (PySCF → Qiskit Nature → VQE → density/Bohmian → Three.js viewer + GitHub Pages), but three things block a credible "computed on quantum hardware" demo:

1. **Bohmian trajectories are static.** `velocity_field` returns `v=(ℏ/m)Im[∇ψ/ψ]`, which is identically **zero** for a real stationary ground state (`qorbital/bohmian/velocity.py:45-70`). The integrator uses a *time-independent* field (`qorbital/bohmian/integrator.py`). So "electrons moving through orbitals" — the entire creative thesis — renders nothing.
2. **IonQ is faked.** `make_estimator()` returns `StatevectorEstimator()` for *every* backend and `qiskit_ionq` is never imported, though it's a pinned dep. Run-to-run "noise" is `random.gauss(...)` in `submit.py:122-130`. There is no real hardware, so the uncertainty cloud / shot-ladder story is fictional.
3. **LiH crashes + lint debt.** 2 tests fail (`_extract_rdm1` hardcodes `JordanWignerMapper()` and builds a 12-qubit op against LiH's 10-qubit parity+2qr statevector → Rust panic), plus 11 ruff findings.

**Goal: a rough but real working demo with hardware.** Ignore non-essential polish. Credits are effectively unlimited; **wall-clock and signal quality are the binding constraints**, not cost.

### Locked decisions (carry through every segment)

- **Eigenstate source = Route B.** Diagonalize `qubit_op.to_matrix()` with `np.linalg.eigh`; take the two lowest eigenpairs `(φ₀,E₀)`, `(φ₁,E₁)`; project each to a single-particle natural-orbital grid.
- **Motion = superposition.** `Ψ(r,t)=Σₙ cₙ φₙ(r) e^(−iEₙt/ℏ)`, `c₀=c₁=1/√2`, `ω=(E₁−E₀)/ℏ`.
- **VQE optimizes on the simulator; hardware credits are spent only on the converged circuit.** No full optimizer loop on IonQ (queue latency + noise-distorted convergence + zero scientific upside for classically-trivial molecules).
- **Two density paths (do not conflate):**
  - *Reference density* (Copenhagen view, the superposition's φ₀): **noiseless Aer rebuild** from converged params → deterministic, clean.
  - *Noise ensemble* (uncertainty cloud + shot ladder): **measure the 1-RDM on hardware, repeat M times.** Each noisy RDM → different density → different trajectories → the cloud. This is *partial 1-RDM measurement* (the expectation values the density needs anyway), not full-state tomography → tractable through LiH.
- **"N hardware runs" = N independent hardware executions of the converged circuit**, not N optimizations.
- **Copenhagen density is the static ground state |φ₀|²**; only trajectories animate (no per-frame `density_t` pulsing — cut as non-essential).
- **LiH:** keep parity + 2-qubit reduction (10 qubits); project φ₀/φ₁ via natural orbitals from the (now mapper-aware) 1-RDM; **fall back to HF HOMO/LUMO superposition only if LiH natural orbitals come out messy.**
- **Hardware molecules: H₂ + LiH.** HeH⁺ stays sim-only.

---

## How to segment this document

Each **`### [ID] Title`** below is one issue-sized unit. IDs: `B#` = backend (Aryan), `F#` = frontend/viz (Arnav). Phases map to the task order:

| Phase | Theme | Segments |
|-------|-------|----------|
| 1 | Lint + test failures | B0, B1 |
| 2+3 | Route-B superposition engine (the physics fix) | B2–B6, F1–F2 |
| 2+3 | Remaining viz gaps | F3–F5 |
| 4 | Real IonQ simulator backend | B7–B8 |
| 5 | Hardware campaign + caching (H₂+LiH) | B9–B11, F6 |
| — | Future (out of scope, documented) | Future section |

Dependencies are noted per segment. Within a phase, segments can mostly run in parallel across the two tracks once contracts (B3, B7) land.

---

## Phase 1 — Lint & test failures

### [B0] Clear ruff findings
**Scope:** Fix the 11 ruff findings (9 auto-fixable). Run `uv run ruff check --fix qorbital tests scripts` then hand-fix the rest.
**Files:** `qorbital/chemistry/hartree_fock.py:6` (unused `NDArray`), `qorbital/vqe/solver.py:8` (unused `StatevectorEstimator`), `qorbital/vqe/submit.py:15` & `tests/test_molecules.py:9` (unused `MOLECULE_PARAMS`), `scripts/verify_viewer_screenshot.py:9` (unused `time`), `tests/test_integration_pipeline.py:4,66` (unused `Path`, unused `path` local), `tests/test_trajectories.py:3-4` (import sort + unused `Path`), `tests/conftest.py:7` (E501).
**Acceptance:** `uv run ruff check qorbital tests scripts` and `uv run ruff format --check` both clean.

### [B1] Make 1-RDM extraction mapper-aware (fixes the LiH crash)
**Scope:** `_extract_rdm1` (`qorbital/chemistry/density.py:37-63`) hardcodes `JordanWignerMapper()` and builds a 12-qubit op against LiH's 10-qubit parity+2qr statevector → `pyo3_runtime.PanicException: index out of bounds: len 1024 index 1088`. Thread the **actual mapper** (JW vs parity, `num_particles`, `two_qubit_reduction`) through `compute_density` → `_extract_rdm1` so the `a†_p a_q` FermionicOps map to the same qubit count as the statevector. Pull mapper metadata from `QubitHamiltonian` (`qorbital/chemistry/hamiltonian.py:20-34`).
**Reuse:** the mapper-selection logic already in `_build_ansatz` (`qorbital/vqe/solver.py:54-84`) — extract it into a shared `make_mapper(qubit_hamiltonian)` helper so solver, density, and the hardware-RDM path all agree.
**Acceptance:** `tests/test_molecules.py::TestLiH::test_natural_orbital_projection` and `::test_homo_fallback` pass; full `uv run pytest` green (108 passed). This helper is the foundation for B5 and B10.

---

## Phase 2+3 — Route-B superposition engine (backend)

### [B2] Eigenstate producer: `lowest_eigenstates`
**Status:** DONE
**Scope:** New function `lowest_eigenstates(qubit_hamiltonian, k=2)` (in `qorbital/chemistry/eigenstates.py` or extend `hamiltonian.py`). Diagonalize `qubit_op.to_matrix()` via `np.linalg.eigh`; return the `k` lowest `(eigenvector, energy)` pairs. Eigenvectors are statevectors in the Hamiltonian's mapper basis (parity+2qr for LiH).
**Acceptance:** energies match `np.linalg.eigvalsh` to ~1e-10; H₂ E₀ ≈ −1.857 Ha electronic; unit test asserts ordering and orthonormality.

### [B3] Eigenstate → grid projection + superposition contract
**Status:** DONE
**Scope:** For each eigenvector φₙ from B2, produce a real-space single-particle grid by reusing the mapper-aware 1-RDM path (B1) → diagonalize the 1-RDM → dominant natural orbital → `wavefunction_grid_from_statevector` (`qorbital/chemistry/density.py:265-291`) / `project_natural_orbital` (`qorbital/bohmian/projection.py:16-48`). Both φ₀ and φ₁ must land on a **common grid**, normalized. **Define the superposition data contract here** (consumed by B4, B6, F1): grid axes/spacing in atomic units, `state_indices=(0,1)`, `E₀/E₁`, `c₀/c₁`, `ω`, `source ∈ {exact_diag, hardware_ground+exact_excited}`.
**Reuse:** `project_homo_orbital` (`projection.py:51-92`) is the LiH fallback per the locked decision.
**Acceptance:** H₂ φ₀ matches the existing ground-state density to tolerance; φ₁ is orthogonal; LiH produces finite, sensible orbitals (or trips the documented HOMO/LUMO fallback).

### [B4] Time-dependent superposition wavefunction + velocity
**Status:** DONE
**Scope:** Add `superposition_wavefunction(phi0, phi1, E0, E1, t, c0, c1)` and a time-aware `velocity_field` path in `qorbital/bohmian/velocity.py`. Ψ(r,t) is generally complex even for real φₙ, so `Im[∇ψ/ψ]` is non-zero → trajectories move. Precompute `∇φ₀`, `∇φ₁` once. Add `superposition_period(E0,E1)` = `2π/ω`.
**Reuse:** existing gradient/cutoff machinery in `velocity_field` (`velocity.py:45-70`); `add_azimuthal_phase` (`velocity.py:73-92`) stays as an alternative for single-state demos.
**Acceptance:** for a two-state pair the velocity is non-zero and oscillates; closed-form oracle (see B5) matches.

### [B5] Time-dependent trajectory integrator
**Status:** DONE
**Scope:** Extend `integrate_trajectories` (`qorbital/bohmian/integrator.py:11-40`) so the RHS recomputes velocity at each `t` from the superposition (currently `_velocity(t,y)` ignores `t` and interpolates a static field, `integrator.py:61-88`). Either (a) rebuild v(r,t) on the grid at each step then interpolate, or (b) interpolate φₙ and ∇φₙ once and evaluate Ψ(r,t) per-step (cheaper). Sample over ~2 periods (B4). Keep `solve_ivp` RK45. Output stays `(n_particles, n_timesteps, 3)`.
**Acceptance:** 20 particles × 100 steps over 2 periods runs < 5 s; positions are **periodic** (return near start after one period); norm/probability conserved.

### [B6] Superposition tests (closed-form oracle)
**Status:** DONE
**Scope:** `tests/test_bohmian.py` additions: plane-wave velocity unit test; **two-state closed-form oracle** `v = c₀c₁ sin(ωt)(φ₁∇φ₀−φ₀∇φ₁)/|Ψ|²`; norm conservation; real H₂ eigenstate pair → trajectories **move** and are **periodic** (electron sloshing between the two H nuclei). HeH⁺ → visible **asymmetry toward He**.
**Acceptance:** all new tests pass; HeH⁺ confirmed in registry (`qorbital/chemistry/molecules.py`) with charge=+1.

---

## Phase 2+3 — Frontend: consume the superposition + close viz gaps

> The viewer **already** animates `(n_particles, n_timesteps, 3)` trajectories with a comet head + fading trail, play/pause, period-aware loop, and Copenhagen/Bohmian/Ensemble presets (`TrajectoryPaths.js`, `QorbitalApp.js:350-385`). Most "animation" work is done — the gaps are schema metadata, a scrubber, and three missing layers.

### [F1] Extend the bundle schema for superposition time-series
**Status:** DONE
**Scope:** Add `times` (or keep `dt` + `steps`), `period`, and superposition metadata (`state_indices`, `E0/E1`, `coefficients`, `omega`, `source`) to `TrajectorySet` (`qorbital/viz/schema.py:55-62`) and the writer `trajectories_to_sidecar` (`qorbital/viz/trajectories.py:47-64`). This is the F-side of the B3 contract — coordinate field names with B3 before either side codes.
**Acceptance:** round-trip serialize/deserialize test; existing bundles still load (back-compat defaults for missing fields).

### [F2] Period-aware playback + timeline scrubber
**Status:** DONE
**Scope:** Drive the animation loop from the bundle's real `period` instead of the hardcoded `TRAJECTORY_PERIOD_SECONDS=7` (`QorbitalApp.js:151-164`). Add a timeline scrubber slider → manual `progress01` (the only missing playback control; play/pause already exists).
**Acceptance:** one render loop = one physical period; scrubbing updates trajectory positions live; HUD shows `t / period`.

### [F3] Static convergence plot from run logs
**Status:** DONE
**Scope:** New `qorbital/viz/web/src/ui/ConvergencePlot.js` (canvas, mirror `PesChart.js`). Read `optimizer_history` (already in every run log, e.g. `data/runs/h2/*.json`) → energy-vs-iteration curve. Static, no live backend. Add a HUD panel.
**Acceptance:** renders a real H₂ run's convergence; updates when molecule/run changes.

### [F4] Classical (HF vs VQE) density overlay
**Status:** DONE
**Scope:** The schema already has a `comparison` field (`schema.py:~87`) that's never populated. Populate it in `build_molecule_bundle` from `compute_hf_density` (`qorbital/chemistry/hartree_fock.py`), and add a `showComparison` layer toggle + diff/overlay render in the viewer. Today only HF *energy* is shown as text (`QorbitalApp.js:647`).
**Acceptance:** toggle shows HF density alongside/diffed-against VQE density for H₂ and LiH.

### [F5] Uncertainty cloud as a diffuse field (not just overlaid lines)
**Status:** DONE
**Scope:** `EnsembleTrajectories.js` currently overlays low-opacity polylines. Add a true diffuse cloud driven by `compute_uncertainty_cloud` (`qorbital/bohmian/uncertainty.py:22-41`, returns per-voxel density + std). New `EnsembleUncertainty.js` renders the histogram field — sharp in stable regions, diffuse near nodes.
**Depends on:** B11 (real per-run densities). Until then, render from sim ensembles.
**Acceptance:** H₂ ensemble shows a visibly diffuse cloud near nodes; sharp in bonding region.

---

## Phase 4 — Real IonQ simulator backend

### [B7] Wire qiskit-ionq into the backend factory
**Scope:** Replace the all-`StatevectorEstimator` stub (`qorbital/vqe/backends.py:18-41`). For `IONQ_SIM`/`IONQ_ARIA`, instantiate the real provider (`from qiskit_ionq import IonQProvider`) and return a Sampler/Estimator bound to `ionq_simulator` / `ionq_qpu` (`aria-1`). Keep `AER`/local for the **optimization loop** (per locked decision); IonQ backends are for *evaluation/submission* of the converged circuit (B9). Read the API key from an env var (define and document the name, e.g. `IONQ_API_KEY` / `QISKIT_IONQ_API_KEY`); never hardcode.
**Acceptance:** `make_estimator(Backend.IONQ_SIM)` returns a real IonQ-backed primitive when the key is set; raises a clear error if missing; tests skip cleanly without a key (no hardware in CI).

### [B8] Document IonQ credentials & config
**Scope:** README/SetupGuide: env var name, how to set it in WSL, which devices map to which `Backend` enum value, and the "optimize-local / submit-converged" model. Confirm `qiskit-ionq>=0.5,<1` pin still resolves.
**Acceptance:** a fresh contributor can run `IONQ_API_KEY=... python -m qorbital.vqe.submit --molecule h2 --backend ionq_sim` and get a valid run log.

---

## Phase 5 — Hardware campaign + caching (H₂ + LiH)

### [B9] Real submit + poll for the converged circuit
**Status:** DONE
**Scope:** `submit.py` currently only simulates locally + injects fake gaussian noise (`submit.py:122-130`). Add the real path: optimize on sim (existing `run_vqe`), then submit the **converged ansatz circuit** to IonQ via B7, poll for completion, record measured energy + `cost_credits` into `RunLog` (`submit.py:22-42`, fields already exist). Remove/guard the synthetic-noise branch for real-hardware backends.
**Implemented:** `evaluate_energy_on_estimator` (solver.py) transpiles the converged ansatz to the device gateset (ISA pattern — `BackendEstimatorV2` does *not* lower the UCCSD `EvolvedOps` block, which IonQ rejects) and maps the observable onto the transpiled layout; `submit_vqe` builds the Hamiltonian, optimises locally, evaluates the converged circuit on the IonQ backend, overwrites the measured energy, and records best-effort `cost_credits`. Synthetic-noise branch removed.
**Hardware backend = Forte Enterprise** (`ionq_forte` → `qpu.forte-enterprise-1`); Aria is retired (Aria-1/2 are now only legacy simulator noise models).
**Acceptance:** validated on the real IonQ cloud simulator — `submit_vqe(..., backend=IONQ_SIM)` lands a real-device H₂ log (`data/runs/h2/7bd31079.json`, E ≈ −1.134 Ha @ 1000 shots; cost None on sim as expected). **Live `ionq_forte` QPU execution (real device energy + populated `cost_credits`) is deferred to B11** — gated on enabling the Forte Enterprise QPU target on the IonQ project and on queue time (see status.ionq.co).

### [B10] Hardware 1-RDM measurement (CRITICAL PATH for the noise story)
**Status:** DONE
**Scope:** New function: given a converged circuit, **measure the 1-RDM `a†_p a_q` Pauli terms on the device** (Estimator with shots, via B7) → a noisy 1-RDM → density grid (reuse mapper-aware B1). Repeat M times for the ensemble; each noisy RDM yields a different φ₀ → different trajectories. This is *partial* RDM measurement, tractable through LiH. **The Day-3 uncertainty cloud (F5) depends entirely on this — treat as critical, not nice-to-have.** Distinguish from the deterministic *reference* density (noiseless Aer rebuild via `_statevector_from_params`, `scripts/generate_bundles.py:115-144` — promote this helper into `qorbital/vqe/`).
**Implemented:** `measure_rdm1` (`qorbital/vqe/hardware_rdm.py`) measures **Hermitian, spin-summed** 1-RDM observables (`a†_p a_q + a†_q a_p` off-diagonal, `a†_p a_p` diagonal — a bare `a†_p a_q` is non-Hermitian and invalid for an Estimator; valid because the real ground-state RDM is symmetric) in a single batched PUB, mirroring B9's ISA-transpile pattern; the transpile step is skipped for an exact `StatevectorEstimator` so the same primitive serves the correctness test and hardware. `density_from_rdm1` (factored out of `compute_density`) turns a measured RDM into a grid. `measure_rdm_ensemble`/`ensemble_to_cloud` (`qorbital/bohmian/noise_ensemble.py`) repeat M times → densities → trajectories → F5 cloud. The noiseless *reference* helper is promoted to `statevector_from_params` (`qorbital/vqe/solver.py`) and `generate_trajectories` to `qorbital/bohmian/trajectories.py`.
**Caching:** EstimatorV2 returns expectation values, not shot bitstrings, so "raw counts" are not recoverable through B7's interface. The cached artifact is the per-run noisy 1-RDM **plus provenance** (per-term EVs + stds, job ids, mapper metadata, converged params) in an `.npz`; re-running with the same `cache_path` rebuilds densities/trajectories deterministically with zero device calls. A Sampler-based true-count path is a possible B11 enhancement.
**Acceptance:** M hardware executions of the H₂ converged circuit yield M *different* densities/trajectories; the spread is the cloud; reproducible offline **from cached per-run RDMs + provenance** (validated on `ionq_sim`; real Forte QPU campaign + ensemble-manifest wiring is B11).

### [B11] H₂ + LiH hardware campaign + ensemble caching
**Scope:** Run the real campaign and cache it. H₂: ~10 hardware executions of the converged circuit at equilibrium (+ a few low-shot runs so node "wobble" is visible) + a **shot-count ladder** (≈100/1k/10k/100k) for the sharpen-with-shots story. LiH: bond-length sweep (1.2/1.4/1.596/1.8/2.0 Å) × a couple runs each. **Optional flourish:** one *full* H₂ optimization on hardware purely to capture a real convergence-under-noise curve for F3 (cheap for 2 qubits; the one place hardware optimization earns its keep). Extend `run_h2_ensemble.py` / `run_lih_sweep.py` (default them to real hardware backends — `ionq_forte`) and rebuild ensembles via `generate_bundles.py --ensemble` (`generate_ensemble`, `scripts/generate_bundles.py:147-258`); serve through `prepare_pages_site.py`. **Includes the first real `ionq_forte` (`qpu.forte-enterprise-1`) QPU execution deferred from B9** — requires the Forte Enterprise QPU target enabled on the IonQ project (Project Settings → QPU Targets) and accounts for queue latency (status.ionq.co).
**Acceptance:** `data/runs/{h2,lih}/` hold real-hardware logs (real device energy + populated `cost_credits`); ensemble manifests + sidecars regenerate; viewer loads them; HeH⁺ remains sim-only.

### [F6] Sim-vs-hardware + gallery wiring
**Scope:** Use `load_runs` (`qorbital/data/loader.py:11-45`) to drive a sim-baseline-vs-hardware-ensemble view (density + trajectory difference) and finalize gallery-mode playback per molecule. Surface backend/shots/energy/credits in the run-metadata HUD.
**Acceptance:** picking H₂ or LiH shows Copenhagen + animated Bohmian + classical overlay + hardware uncertainty cloud; HUD reflects real run metadata.

---

## Future (documented, out of scope this sprint)

These are **future implementation bullets**, not active tasks — capture in a tracking issue:

- **User-submitted / live "Lab Mode" jobs** — let viewers trigger real IonQ runs from the web UI and watch trajectories accumulate live. Needs a job-submission endpoint/queue, auth/credit budgeting, and streaming results into the viewer. (Deferred per the gallery-mode-only decision.)
- **Trotterized Hamiltonian simulation for time dynamics** — replace the two-state superposition ansatz for motion with genuine Trotterized time evolution `e^(−iĤt)` of the (qubit) Hamiltonian, enabling many-state dynamics and real wavepacket propagation rather than a fixed φ₀/φ₁ beat.
- **Lindbladian (open-system) simulation** — model decoherence/dissipation via a Lindblad master equation so the visualized dynamics include environmental coupling, not just unitary evolution; connects naturally to the hardware-noise theme.

(Also previously deferred: excited-state-from-hardware via VQD/SSVQE — this sprint takes the excited state from exact diagonalization; BeH₂; PyPI release; formal ADRs.)

---

## Verification

- **Per segment:** `uv run ruff check qorbital tests scripts` + `uv run ruff format --check` + `uv run pytest` (target 108+ passing; mark hardware-touching tests to skip without `IONQ_API_KEY`).
- **Physics gate (B4–B6):** H₂ trajectories oscillate and are periodic; HeH⁺ asymmetric toward He; closed-form oracle passes; norm conserved.
- **Backend integration:** `python -m qorbital.vqe.submit --molecule h2 --backend ionq_sim --shots 1000` writes a valid run log against the *real* IonQ simulator.
- **Hardware gate (B9–B11):** real H₂ + LiH logs in `data/runs/`; M-run densities measurably differ (non-empty uncertainty cloud); shot ladder shows trajectories sharpening with shots.
- **End-to-end demo:** `python scripts/serve_viewer.py` (or the deployed Pages site) → pick H₂ or LiH → Copenhagen isosurface + **moving** Bohmian trajectories + classical overlay + hardware uncertainty cloud + convergence plot; HUD shows real backend/shots/energy/credits.

## Non-goals (do not build)

Per-frame pulsing density (`density_t`); live convergence backend (static plots only); HeH⁺ hardware runs; BeH₂; Streamlit/Panel shell (Three.js viewer is the frontend); formal ADRs; PyPI packaging; full-state tomography (partial 1-RDM measurement only).
