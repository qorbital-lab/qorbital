# qOrbital

Quantum chemistry orbital visualizer. Computes molecular ground states with VQE on IonQ hardware, renders 3D electron density isosurfaces + Bohmian particle trajectories in the browser. MIT licensed, built for the Qollab Creative Challenge.

## Dev Commands

```bash
uv sync --dev              # install with dev deps
uv run pytest              # all tests
uv run pytest tests/test_integrals.py -v  # single file
uv run ruff check qorbital tests          # lint
uv run ruff check --fix qorbital tests    # lint + fix
uv run ruff format qorbital tests         # format
```

Always lint and test changed files before committing. No IonQ hardware calls in tests — use Aer statevector or mocks.

## Architecture

```
PySCF → Qiskit Nature Hamiltonian → VQE (IonQ/Aer) → 1-RDM → Density/Bohmian field → Three.js/PyVista
```

- `qorbital/chemistry/` — PySCF integrals via Qiskit Nature PySCFDriver, returns ElectronicStructureProblem
- `qorbital/vqe/` — VQE with UCCSD ansatz on IonQ Aria/Forte or Aer fallback, emits parameter snapshots
- `qorbital/bohmian/` — 1-RDM extraction, density grid, Bohmian velocity field, trajectory integration (Runge-Kutta)
- `qorbital/viz/` — Copenhagen (isosurfaces) and Bohmian (trajectories) views. Web = Three.js, Python = PyVista/VTK
- `qorbital/webapp/` — Streamlit/Panel shell (stub)

### Key Files

- `SetupGuide.md` — canonical structure, label taxonomy, ADR format, hardware log spec
- `pyproject.toml` — dependency pins (Qiskit ≥1.0, Qiskit Nature ≥0.7, PySCF ≥2.4)
- `data/runs/` — JSON logs from IonQ hardware runs
- `CONTRIBUTING.md` — PR conventions

## Qiskit Nature 0.7 API

Most online examples use removed pre-0.6 imports. Always use:

```python
from qiskit_nature.second_q.drivers import PySCFDriver        # NOT qiskit_nature.drivers
from qiskit_nature.second_q.mappers import JordanWignerMapper  # NOT QubitConverter (removed)
from qiskit_nature.units import DistanceUnit
```

Driver pattern: `PySCFDriver(atom=..., basis="sto3g", unit=DistanceUnit.ANGSTROM)` → `.run()` → `ElectronicStructureProblem`. Integrals via `problem.hamiltonian.electronic_integrals`.

Docs: https://qiskit-community.github.io/qiskit-nature/tutorials/01_electronic_structure.html

## Debugging

- **Qiskit Nature ImportError**: Version mismatch. Check `uv run python -c "import qiskit_nature; print(qiskit_nature.__version__)"` — must be ≥0.7
- **PySCF segfault**: Basis string issue. PySCF wants `"sto-3g"`, Qiskit Nature normalizes both forms
- **VQE not converging**: Check optimizer (SLSQP/COBYLA), use HartreeFock initial state, print energy per iteration
- **Integral shape mismatch**: PySCF uses chemist's notation `(ij|kl)`. Triangular-packed format needs unfolding
- **Float comparison in tests**: Use `pytest.approx(expected, abs=1e-6)`, never `==`

## Do

- Pin deps with upper bounds (`>=0.7,<0.8` not `>=0.7`)
- Return structured dataclasses, not raw tuples
- Document integral convention (chemist vs physicist) at module boundaries
- Keep subpackage imports one-directional: chemistry → vqe → bohmian → viz
- Use `DistanceUnit.ANGSTROM` explicitly
- Validate against published values (H₂ RHF/STO-3G ≈ −1.11675 Ha at 0.735 Å)

## Don't

- Don't use Qiskit Nature imports from < 0.6 — they're removed
- Don't put IonQ keys in code. Environment variables only
- Don't add hardware calls in tests — CI has no IonQ access
- Don't leak PySCF internals across subpackage boundaries
- Don't hard-code geometries outside the molecule registry

## Testing

No hardware in CI. Reference values:
- H₂ at 0.735 Å, STO-3G: RHF ≈ −1.11675 Ha
- LiH at 1.596 Å, STO-3G: RHF ≈ −7.86 Ha

## Design Principle

Hardware noise is a **feature**. Each VQE run yields a different wavefunction → different trajectories. Overlaying runs produces trajectory uncertainty clouds. Don't hide noise — visualize it.

## Contractual

- Attribution required: "This effort is supported via compute credits from Qollab and IonQ."
- IonQ credits expire Aug 31, 2026. Project-use only, non-transferable
- MIT licensed, publicly available. 12-month maintenance through June 2027
- No secrets in public repos. Security incidents → notice@qollab.xyz within 72h
