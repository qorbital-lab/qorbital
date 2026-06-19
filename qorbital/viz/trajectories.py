"""Serialize Bohmian trajectories into ADR-004 visualization bundles."""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from qorbital.bohmian.velocity import superposition_period
from qorbital.chemistry.density import ElectronDensityGrid
from qorbital.chemistry.hartree_fock import compute_hf_density
from qorbital.chemistry.superposition import SuperpositionState
from qorbital.viz.isosurface import (
    integrated_electron_count,
    isovalue_enclosing_fraction,
)
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
    *,
    times: NDArray[np.float64] | None = None,
    superposition: SuperpositionState | None = None,
    period: float | None = None,
) -> TrajectorySet:
    """Write trajectories as a float32 sidecar and return a TrajectorySet."""
    n_particles, n_steps, _ = trajectories.shape
    sidecar_path = directory / filename
    _write_float32_sidecar(sidecar_path, trajectories.astype(np.float32))

    times_list: list[float] | None = None
    resolved_dt = dt
    if times is not None:
        times_arr = np.asarray(times, dtype=np.float64).ravel()
        if times_arr.shape[0] != n_steps:
            msg = (
                f"times length {times_arr.shape[0]} must match trajectory steps "
                f"{n_steps}"
            )
            raise ValueError(msg)
        times_list = [float(t) for t in times_arr]
        if n_steps > 1:
            resolved_dt = float((times_arr[-1] - times_arr[0]) / (n_steps - 1))

    resolved_period = period
    state_indices: list[int] | None = None
    e0: float | None = None
    e1: float | None = None
    c0: float | None = None
    c1: float | None = None
    omega: float | None = None
    source: str | None = None
    if superposition is not None:
        state_indices = [int(i) for i in superposition.state_indices]
        e0 = superposition.E0
        e1 = superposition.E1
        c0 = superposition.c0
        c1 = superposition.c1
        omega = superposition.omega
        source = superposition.source
        if resolved_period is None:
            resolved_period = superposition_period(e0, e1)

    return TrajectorySet(
        particles=n_particles,
        steps=n_steps,
        dt=resolved_dt,
        paths=filename,
        path_layout="particle-major",
        color_by="speed",
        times=times_list,
        period=resolved_period,
        state_indices=state_indices,
        E0=e0,
        E1=e1,
        c0=c0,
        c1=c1,
        omega=omega,
        source=source,
    )


def trajectory_set_from_superposition(
    trajectories: NDArray[np.float64],
    directory: Path,
    filename: str,
    state: SuperpositionState,
    times: NDArray[np.float64],
) -> TrajectorySet:
    """Write superposition trajectories with B3-aligned metadata."""
    return trajectories_to_sidecar(
        trajectories,
        directory,
        filename,
        superposition=state,
        times=times,
    )


def density_grid_to_sidecar(
    density: ElectronDensityGrid,
    directory: Path,
    filename: str,
    *,
    enclosed_fraction: float = 0.9,
) -> DensityGrid:
    """Pack an ElectronDensityGrid into a DensityGrid sidecar."""
    sidecar_path = directory / filename
    _write_float32_sidecar(sidecar_path, density.density.astype(np.float32))
    default_isovalue, _ = isovalue_enclosing_fraction(
        density.density, density.spacing, enclosed_fraction
    )
    electron_count = integrated_electron_count(density.density, density.spacing)
    return DensityGrid(
        origin=density.origin.tolist(),
        spacing=density.spacing.tolist(),
        shape=list(density.grid_shape),
        values=filename,
        value_encoding="float32-le",
        units="electron_density_au",
        default_isovalue=default_isovalue,
        electron_count=electron_count,
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
    superposition: SuperpositionState | None = None,
    trajectory_times: NDArray[np.float64] | None = None,
) -> tuple[VisualizationBundle, Path]:
    """Build and write a complete visualization bundle for a molecule."""
    if output_dir is None:
        output_dir = Path("data/bundles") / molecule_id.lower()
    output_dir.mkdir(parents=True, exist_ok=True)

    density_sidecar = f"{molecule_id.lower()}_density.bin"
    density_grid = density_grid_to_sidecar(density, output_dir, density_sidecar)

    hf_density = compute_hf_density(
        molecule_id,
        bond_length=bond_length,
        grid_points=density.grid_shape[0],
        padding=3.0,
    )
    comparison_sidecar = f"{molecule_id.lower()}_comparison.bin"
    comparison_grid = density_grid_to_sidecar(
        hf_density, output_dir, comparison_sidecar
    )

    traj_set = None
    if trajectories is not None:
        traj_sidecar = f"{molecule_id.lower()}_trajectories.bin"
        if superposition is not None and trajectory_times is not None:
            traj_set = trajectory_set_from_superposition(
                trajectories,
                output_dir,
                traj_sidecar,
                superposition,
                trajectory_times,
            )
        else:
            traj_set = trajectories_to_sidecar(
                trajectories, output_dir, traj_sidecar, dt=dt
            )

    offsets = _NUCLEUS_OFFSETS.get(molecule_id, [])
    if offsets and molecule_id == "H2":
        # Use the same [0, bond] data-frame convention as HeH+/LiH so the drawn
        # atoms share one frame with the PySCF density grid and the |psi|^2 seeds
        # (which live in the geometry frame centered on the bond midpoint).
        atoms = [
            AtomSpec(symbol="H", position=[0.0, 0.0, 0.0]),
            AtomSpec(symbol="H", position=[0.0, 0.0, bond_length]),
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
        comparison=comparison_grid,
        provenance=Provenance(
            run_id=f"{molecule_id.lower()}_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}",
            created_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )

    json_path = output_dir / f"{molecule_id.lower()}_bundle.json"
    save_bundle(bundle, json_path)
    return bundle, json_path
