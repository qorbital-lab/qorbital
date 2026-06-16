"""Serialize Bohmian trajectories into ADR-004 visualization bundles."""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from qorbital.chemistry.density import ElectronDensityGrid
from qorbital.viz.schema import (
    SCHEMA_VERSION,
    AtomSpec,
    BackendInfo,
    DensityGrid,
    MoleculeSpec,
    Provenance,
    TrajectorySet,
    VisualizationBundle,
    save_bundle,
)

# Element positions for registry molecules (Angstrom, along z-axis)
_NUCLEUS_OFFSETS: dict[str, list[tuple[str, list[float]]]] = {
    "H2": [
        ("H", [0.0, 0.0, -0.3675]),
        ("H", [0.0, 0.0, 0.3675]),
    ],
    "HeH+": [
        ("He", [0.0, 0.0, 0.0]),
        ("H", [0.0, 0.0, 0.772]),
    ],
    "LiH": [
        ("Li", [0.0, 0.0, 0.0]),
        ("H", [0.0, 0.0, 1.596]),
    ],
}


def _write_float32_sidecar(path: Path, values: NDArray[np.float32]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack(f"<{values.size}f", *values.ravel()))


def trajectories_to_sidecar(
    trajectories: NDArray[np.float64],
    directory: Path,
    filename: str,
    dt: float = 0.1,
) -> TrajectorySet:
    """Write trajectories as a float32 sidecar and return a TrajectorySet."""
    n_particles, n_steps, _ = trajectories.shape
    sidecar_path = directory / filename
    _write_float32_sidecar(sidecar_path, trajectories.astype(np.float32))
    return TrajectorySet(
        particles=n_particles,
        steps=n_steps,
        dt=dt,
        paths=filename,
        path_layout="particle-major",
        color_by="speed",
    )


def density_grid_to_sidecar(
    density: ElectronDensityGrid,
    directory: Path,
    filename: str,
) -> DensityGrid:
    """Pack an ElectronDensityGrid into a DensityGrid sidecar."""
    sidecar_path = directory / filename
    _write_float32_sidecar(sidecar_path, density.density.astype(np.float32))
    return DensityGrid(
        origin=density.origin.tolist(),
        spacing=density.spacing.tolist(),
        shape=list(density.grid_shape),
        values=filename,
        value_encoding="float32-le",
        units="electron_density_au",
        default_isovalue=0.02,
    )


def build_molecule_bundle(
    molecule_id: str,
    label: str,
    bond_length: float,
    density: ElectronDensityGrid,
    trajectories: NDArray[np.float64] | None,
    *,
    method: str = "vqe",
    energy_hartree: float | None = None,
    reference_energies: dict[str, float] | None = None,
    backend_name: str = "aer",
    output_dir: Path | None = None,
    dt: float = 0.1,
) -> tuple[VisualizationBundle, Path]:
    """Build and write a complete visualization bundle for a molecule."""
    if output_dir is None:
        output_dir = Path("data/bundles") / molecule_id.lower()
    output_dir.mkdir(parents=True, exist_ok=True)

    density_sidecar = f"{molecule_id.lower()}_density.bin"
    density_grid = density_grid_to_sidecar(density, output_dir, density_sidecar)

    traj_set = None
    if trajectories is not None:
        traj_sidecar = f"{molecule_id.lower()}_trajectories.bin"
        traj_set = trajectories_to_sidecar(
            trajectories, output_dir, traj_sidecar, dt=dt
        )

    offsets = _NUCLEUS_OFFSETS.get(molecule_id, [])
    if offsets and molecule_id == "H2":
        half = bond_length / 2.0
        atoms = [
            AtomSpec(symbol="H", position=[0.0, 0.0, -half]),
            AtomSpec(symbol="H", position=[0.0, 0.0, half]),
        ]
    elif offsets and molecule_id == "HeH+":
        atoms = [
            AtomSpec(symbol="He", position=[0.0, 0.0, 0.0]),
            AtomSpec(symbol="H", position=[0.0, 0.0, bond_length]),
        ]
    elif offsets and molecule_id == "LiH":
        atoms = [
            AtomSpec(symbol="Li", position=[0.0, 0.0, 0.0]),
            AtomSpec(symbol="H", position=[0.0, 0.0, bond_length]),
        ]
    else:
        atoms = [AtomSpec(symbol="X", position=[0.0, 0.0, 0.0])]

    bundle = VisualizationBundle(
        schema_version=SCHEMA_VERSION,
        molecule=MoleculeSpec(
            id=molecule_id,
            label=label,
            bond_length_angstrom=bond_length,
            basis="sto-3g",
            atoms=atoms,
        ),
        method=method,
        density=density_grid,
        backend=BackendInfo(provider="qorbital", name=backend_name),
        energy_hartree=energy_hartree,
        reference_energies=reference_energies,
        trajectories=traj_set,
        provenance=Provenance(
            run_id=f"{molecule_id.lower()}_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}",
            created_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )

    json_path = output_dir / f"{molecule_id.lower()}_bundle.json"
    save_bundle(bundle, json_path)
    return bundle, json_path
