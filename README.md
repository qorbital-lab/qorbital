<img width="3168" height="1344" alt="Gemini_Generated_Image_uqo1uuqo1uuqo1uu" src="https://github.com/user-attachments/assets/6f811305-e743-4b00-9cef-052041805448" />

# qOrbital

**Interactive quantum chemistry orbital visualizer — compute molecular ground states with VQE on real quantum hardware and explore 3D electron density isosurfaces in the browser.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/qorbital-lab/qorbital/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/qorbital-lab/qorbital/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![Qiskit](https://img.shields.io/badge/Qiskit-1.0+-purple.svg)](https://qiskit.org)

<p align="center">
  <em><!-- TODO: Add a screenshot or GIF of the 3D orbital viewer here --></em>
</p>

---

## What is qOrbital?

qOrbital is an open-source Python package and interactive web demo that visualizes molecular orbitals computed on real quantum hardware. It lets you see electron trajectories flowing through quantum probability landscapes — something no existing tool offers in a browser-accessible, interactive format.

Users select a molecule (H₂, LiH, HeH⁺, BeH₂), adjust bond geometry with a slider, and watch the orbital shape respond in real time as a 3D isosurface. Behind the scenes, a full quantum chemistry pipeline runs: classical Hartree-Fock via PySCF, Hamiltonian mapping through Qiskit Nature, and ground-state energy estimation using the Variational Quantum Eigensolver (VQE) on IonQ quantum hardware.

## Features

- **Real quantum hardware** — Run VQE circuits on IonQ simulators and trapped-ion devices, not just classical approximations
- **Interactive 3D visualization** — Explore electron density isosurfaces rendered with Three.js and marching cubes, directly in your browser
- **Molecule explorer** — Select from supported molecules (H₂, LiH, HeH⁺, BeH₂) and adjust bond geometry to see how orbitals change
- **Quantum explainer mode** — Step through the VQE pipeline stage by stage to understand what the quantum computer is actually doing
- **Classical vs. quantum comparison** — Compare orbital outputs from classical Hartree-Fock with VQE results side by side
- **Python package** — Use `qorbital` as a library in your own quantum chemistry workflows

## Quickstart

### Installation

```bash
# Clone the repository
git clone https://github.com/qorbital-lab/qorbital.git
cd qorbital

# Install with uv (recommended)
uv sync

# Or install with dev extras for development
uv sync --all-extras
```

### Run the web demo

The `qorbital serve` CLI is not wired up yet. From the **repository root**, serve the viewer with:

```bash
python3 scripts/serve_viewer.py
```

Or manually:

```bash
python3 -m http.server 8000 --directory qorbital/viz/web
```

Open [http://localhost:8000](http://localhost:8000) — you should see a mock H₂ isosurface with orbit/zoom/pan controls. Press **H** to toggle the control panel. Visualization data follows [ADR-004](docs/decisions/ADR-004-data-schema.md).

Regenerate the mock fixture after schema changes:

```bash
uv run python -c "from qorbital.viz.fixtures import write_h2_fixture; write_h2_fixture('qorbital/viz/web/fixtures/h2_mesh_v0.json')"
```

When available:

```bash
uv run qorbital serve
```

### Use as a Python library

```python
import qorbital

# Set up a molecule
mol = qorbital.Molecule("H2", bond_length=0.74)

# Run VQE to find the ground state
result = qorbital.run_vqe(mol, backend="ionq_simulator")

# Compute the electron density grid
density = qorbital.compute_density(result)

# Export mesh for visualization
mesh = qorbital.to_mesh(density, isovalue=0.02)

# Render in PyVista (notebook)
from qorbital.viz.pyvista_renderer import show_h2_mock

plotter = show_h2_mock(show=False, jupyter_backend="trame")  # or "ipyvtklink"
plotter.show()
```

## How It Works

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│   PySCF     │────▶│  Qiskit Nature   │────▶│   VQE on     │────▶│  Density     │
│  Hartree-   │     │  Hamiltonian     │     │  IonQ HW /   │     │  Grid from   │
│  Fock Init  │     │  Construction    │     │  Simulator   │     │  1-RDM       │
└─────────────┘     └─────────────────┘     └──────────────┘     └──────┬───────┘
                                                                        │
                                                                        ▼
                                                                 ┌──────────────┐
                                                                 │  Three.js    │
                                                                 │  Marching    │
                                                                 │  Cubes 3D   │
                                                                 │  Render     │
                                                                 └──────────────┘
```

1. **Classical preprocessing** — PySCF computes a Hartree-Fock reference wavefunction and molecular integrals
2. **Hamiltonian mapping** — Qiskit Nature maps the fermionic Hamiltonian to qubit operators
3. **Quantum ground state** — VQE runs on IonQ hardware (or simulator) to find the ground-state energy and wavefunction
4. **Orbital reconstruction** — The one-particle reduced density matrix (1-RDM) is extracted and used to reconstruct orbital electron densities on a 3D grid
5. **Visualization** — The density grid is passed to the browser, where Three.js renders interactive isosurfaces using marching cubes

## Project Structure

Layout follows [SetupGuide.md](SetupGuide.md) §1 (canonical).

```
qorbital/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/              # CI (lint, format, pytest; no hardware)
├── qorbital/                   # main Python package
│   ├── __init__.py
│   ├── chemistry/              # PySCF + Qiskit Nature
│   ├── vqe/                    # VQE + IonQ submission
│   ├── bohmian/                # velocity field + trajectory integrator
│   ├── viz/                    # Three.js + PyVista (see viz/web/)
│   └── webapp/                 # Streamlit / Panel shell (stub)
├── notebooks/
├── data/
│   └── runs/                   # hardware run logs (JSON); see SetupGuide §6
├── docs/
│   ├── decisions/              # ADRs
│   ├── log/
│   ├── api/
│   └── tutorials/
├── tests/
├── pyproject.toml
├── uv.lock
├── CONTRIBUTING.md
├── SetupGuide.md
├── LICENSE
└── README.md
```

## Supported Molecules

| Molecule | Qubits | Description |
|----------|--------|-------------|
| H₂       | 4      | Hydrogen — the "hello world" of quantum chemistry |
| LiH      | 12     | Lithium hydride — asymmetric bonding, richer orbital structure |
| HeH⁺     | 4      | Helium hydride ion — simple but physically interesting |
| BeH₂     | 14     | Beryllium dihydride — stretch goal, larger qubit count |

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)
- [Qiskit](https://qiskit.org) 1.4+ (pinned to `<2`; see [ADR-001](docs/decisions/ADR-001-qiskit-1x-pin.md))
- [Qiskit Nature](https://qiskit-community.github.io/qiskit-nature/) 0.7.2+
- [Qiskit Aer](https://qiskit.github.io/qiskit-aer/) 0.17+ (local simulator)
- [qiskit-ionq](https://qiskit-community.github.io/qiskit-ionq/) 0.5+ (IonQ provider, `<1` for Qiskit 1.x compat)
- [PySCF](https://pyscf.org) 2.4+
- NumPy 1.24+, SciPy 1.10+
- IonQ account (for hardware runs; simulator available without one)
- Modern browser with WebGL support (for the web demo)

## Contributing

We welcome contributions! Whether it's adding new molecules, improving the visualization, or fixing bugs — feel free to open an issue or submit a PR.

```bash
# Set up development environment
git clone https://github.com/qorbital-lab/qorbital.git
cd qorbital
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check qorbital tests

# Run formatting
uv run ruff format qorbital tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SetupGuide.md](SetupGuide.md) for conventions (including: no IonQ/hardware jobs in CI).

## Acknowledgments

qOrbital is developed as part of [Qollab](https://qollab.org)'s Creative Challenge, with funding and compute credits provided by [Qollab](https://qollab.org) and [IonQ](https://ionq.com). Built with [Qiskit](https://qiskit.org) and [PySCF](https://pyscf.org).

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
