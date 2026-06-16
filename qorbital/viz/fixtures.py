"""Generate mock visualization fixtures for tests and the web viewer."""

from __future__ import annotations

import math
import struct
from datetime import UTC, datetime
from pathlib import Path

from qorbital.viz.schema import (
    SCHEMA_VERSION,
    AtomSpec,
    BackendInfo,
    DensityGrid,
    MeshSurface,
    MoleculeSpec,
    Provenance,
    VisualizationBundle,
    save_bundle,
)


def _h2_sigma_density(x: float, y: float, z: float, half_bond: float) -> float:
    """Mock H₂ σ-bond density (matches browser analytic sampler)."""
    sigma_perp = 0.32
    sigma_ax = 0.5
    inv2_perp = 1.0 / (2.0 * sigma_perp * sigma_perp)
    inv2_ax = 1.0 / (2.0 * sigma_ax * sigma_ax)
    r2_perp = x * x + y * y
    g0 = math.exp(-r2_perp * inv2_perp - (z + half_bond) ** 2 * inv2_ax)
    g1 = math.exp(-r2_perp * inv2_perp - (z - half_bond) ** 2 * inv2_ax)
    return g0 + g1


def _ellipsoid_mesh(
    *,
    semi_axes: tuple[float, float, float] = (1.2, 0.6, 0.6),
    u_steps: int = 24,
    v_steps: int = 16,
) -> tuple[list[list[float]], list[list[int]], list[float]]:
    """Parametric ellipsoid centered at origin (mock σ-glass orbital lobe)."""
    vertices: list[list[float]] = []
    scalars: list[float] = []

    for i in range(u_steps + 1):
        u = math.pi * i / u_steps
        for j in range(v_steps):
            v = 2.0 * math.pi * j / v_steps
            x = semi_axes[0] * math.sin(u) * math.cos(v)
            y = semi_axes[1] * math.sin(u) * math.sin(v)
            z = semi_axes[2] * math.cos(u)
            vertices.append([x, y, z])
            scalars.append(1.0 if z >= 0 else -1.0)

    faces: list[list[int]] = []
    for i in range(u_steps):
        for j in range(v_steps):
            a = i * v_steps + j
            b = a + v_steps
            c = b + 1 if j < v_steps - 1 else b - v_steps + 1
            d = a + 1 if j < v_steps - 1 else a - v_steps + 1
            faces.append([a, b, d])
            faces.append([b, c, d])

    return vertices, faces, scalars


def h2_mock_bundle() -> VisualizationBundle:
    """Build a mock H₂ visualization bundle (mock VQE, ellipsoid isosurface)."""
    bond = 0.74
    half = bond / 2.0
    vertices, faces, scalars = _ellipsoid_mesh()

    return VisualizationBundle(
        schema_version=SCHEMA_VERSION,
        molecule=MoleculeSpec(
            id="H2",
            label="H₂",
            bond_length_angstrom=bond,
            basis="sto-3g",
            atoms=[
                AtomSpec(symbol="H", position=[0.0, 0.0, -half]),
                AtomSpec(symbol="H", position=[0.0, 0.0, half]),
            ],
        ),
        method="mock",
        backend=BackendInfo(provider="fixture", name="h2_mesh_v0"),
        energy_hartree=-1.13728,
        reference_energies={"hf": -1.11675, "fci": -1.13728},
        density=MeshSurface(
            isovalue=0.02,
            vertices=vertices,
            faces=faces,
            vertex_scalars=scalars,
        ),
        provenance=Provenance(
            run_id="fixture_h2_mesh_v0",
            created_at=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            git_sha="",
        ),
    )


def write_h2_fixture(path: str | Path) -> Path:
    """Write the standard H₂ mock bundle JSON used by the web viewer."""
    out = Path(path)
    save_bundle(h2_mock_bundle(), out)
    return out


def h2_grid_mock_bundle() -> VisualizationBundle:
    """H₂ bundle with a small DensityGrid (sidecar path only; no file write)."""
    bundle = h2_mock_bundle()
    bundle.density = DensityGrid(
        origin=[-1.6, -1.6, -1.6],
        spacing=[0.16, 0.16, 0.16],
        shape=[21, 21, 21],
        values="h2_grid_v0.bin",
        default_isovalue=0.02,
    )
    bundle.backend = BackendInfo(provider="fixture", name="h2_grid_v0")
    if bundle.provenance is not None:
        bundle.provenance.run_id = "fixture_h2_grid_v0"
    return bundle


def write_h2_grid_fixture(directory: str | Path) -> tuple[Path, Path]:
    """Write H₂ grid JSON + float32 sidecar for the web viewer."""
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = h2_grid_mock_bundle()
    grid = bundle.density
    assert isinstance(grid, DensityGrid)

    nx, ny, nz = grid.shape
    ox, oy, oz = grid.origin
    sx, sy, sz = grid.spacing
    half = bundle.molecule.bond_length_angstrom / 2.0

    values: list[float] = []
    for k in range(nz):
        z = oz + k * sz
        for j in range(ny):
            y = oy + j * sy
            for i in range(nx):
                x = ox + i * sx
                values.append(_h2_sigma_density(x, y, z, half))

    bin_path = out_dir / grid.values
    bin_path.write_bytes(struct.pack(f"<{len(values)}f", *values))

    json_path = out_dir / "h2_grid_v0.json"
    save_bundle(bundle, json_path)
    return json_path, bin_path


def grid_mock_bundle() -> VisualizationBundle:
    """Tiny density grid bundle for schema tests (no sidecar file)."""
    bundle = h2_mock_bundle()
    bundle.density = DensityGrid(
        origin=[-2.0, -2.0, -2.0],
        spacing=[0.5, 0.5, 0.5],
        shape=[9, 9, 9],
        values="",
        default_isovalue=0.02,
    )
    return bundle
