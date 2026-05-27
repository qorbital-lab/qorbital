"""Visualization data schema (ADR-004)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = "0.1.0"


@dataclass
class AtomSpec:
    symbol: str
    position: list[float]

    def __post_init__(self) -> None:
        if len(self.position) != 3:
            msg = "position must be [x, y, z] in Angstrom"
            raise ValueError(msg)


@dataclass
class MoleculeSpec:
    id: str
    label: str
    bond_length_angstrom: float
    basis: str
    atoms: list[AtomSpec]


@dataclass
class MeshSurface:
    kind: Literal["mesh"] = "mesh"
    isovalue: float = 0.02
    vertices: list[list[float]] = field(default_factory=list)
    faces: list[list[int]] = field(default_factory=list)
    vertex_scalars: list[float] | None = None


@dataclass
class DensityGrid:
    kind: Literal["grid"] = "grid"
    origin: list[float] = field(default_factory=lambda: [-5.0, -5.0, -5.0])
    spacing: list[float] = field(default_factory=lambda: [0.2, 0.2, 0.2])
    shape: list[int] = field(default_factory=lambda: [51, 51, 51])
    values: str = ""
    value_encoding: str = "float32-le"
    units: str = "electron_density_au"
    default_isovalue: float = 0.02


@dataclass
class TrajectorySet:
    particles: int
    steps: int
    dt: float
    paths: str
    path_layout: str = "particle-major"
    color_by: str = "speed"


@dataclass
class BackendInfo:
    provider: str
    name: str


@dataclass
class Provenance:
    run_id: str
    created_at: str
    git_sha: str = ""


@dataclass
class VisualizationBundle:
    schema_version: str
    molecule: MoleculeSpec
    method: str
    density: MeshSurface | DensityGrid
    backend: BackendInfo | None = None
    energy_hartree: float | None = None
    reference_energies: dict[str, float] | None = None
    trajectories: TrajectorySet | None = None
    comparison: MeshSurface | DensityGrid | None = None
    provenance: Provenance | None = None


def _atom_from_dict(data: dict[str, Any]) -> AtomSpec:
    position = [float(v) for v in data["position"]]
    if len(position) != 3:
        msg = "atom position must have exactly 3 elements"
        raise ValueError(msg)
    return AtomSpec(symbol=data["symbol"], position=position)


def _molecule_from_dict(data: dict[str, Any]) -> MoleculeSpec:
    return MoleculeSpec(
        id=data["id"],
        label=data["label"],
        bond_length_angstrom=float(data["bond_length_angstrom"]),
        basis=data["basis"],
        atoms=[_atom_from_dict(a) for a in data["atoms"]],
    )


def _mesh_from_dict(data: dict[str, Any]) -> MeshSurface:
    scalars = data.get("vertex_scalars")
    vertices = [list(v) for v in data["vertices"]]
    faces = [list(f) for f in data["faces"]]
    for vertex in vertices:
        if len(vertex) != 3:
            msg = "each mesh vertex must have exactly 3 values"
            raise ValueError(msg)
    for face in faces:
        if len(face) != 3:
            msg = "each mesh face must have exactly 3 indices"
            raise ValueError(msg)

    return MeshSurface(
        kind="mesh",
        isovalue=float(data.get("isovalue", 0.02)),
        vertices=[[float(v) for v in vertex] for vertex in vertices],
        faces=[[int(i) for i in face] for face in faces],
        vertex_scalars=list(scalars) if scalars is not None else None,
    )


def _grid_from_dict(data: dict[str, Any]) -> DensityGrid:
    return DensityGrid(
        kind="grid",
        origin=list(data["origin"]),
        spacing=list(data["spacing"]),
        shape=list(data["shape"]),
        values=data["values"],
        value_encoding=data.get("value_encoding", "float32-le"),
        units=data.get("units", "electron_density_au"),
        default_isovalue=float(data.get("default_isovalue", 0.02)),
    )


def density_from_dict(data: dict[str, Any]) -> MeshSurface | DensityGrid:
    if "kind" not in data:
        msg = "density.kind is required"
        raise ValueError(msg)
    kind = data["kind"]
    if kind == "grid":
        return _grid_from_dict(data)
    if kind == "mesh":
        return _mesh_from_dict(data)
    msg = f"unknown density kind: {kind!r}"
    raise ValueError(msg)


def bundle_from_dict(data: dict[str, Any]) -> VisualizationBundle:
    version = data.get("schema_version", "")
    if not version.startswith("0."):
        msg = f"unsupported schema_version: {version!r}"
        raise ValueError(msg)

    backend = None
    if raw_backend := data.get("backend"):
        backend = BackendInfo(
            provider=raw_backend["provider"],
            name=raw_backend["name"],
        )

    provenance = None
    if raw_prov := data.get("provenance"):
        provenance = Provenance(
            run_id=raw_prov["run_id"],
            created_at=raw_prov["created_at"],
            git_sha=raw_prov.get("git_sha", ""),
        )

    trajectories = None
    if raw_traj := data.get("trajectories"):
        trajectories = TrajectorySet(
            particles=int(raw_traj["particles"]),
            steps=int(raw_traj["steps"]),
            dt=float(raw_traj["dt"]),
            paths=raw_traj["paths"],
            path_layout=raw_traj.get("path_layout", "particle-major"),
            color_by=raw_traj.get("color_by", "speed"),
        )

    comparison = None
    if raw_cmp := data.get("comparison"):
        comparison = density_from_dict(raw_cmp)

    ref_energies = data.get("reference_energies")
    if ref_energies is not None:
        ref_energies = {k: float(v) for k, v in ref_energies.items()}

    return VisualizationBundle(
        schema_version=version,
        molecule=_molecule_from_dict(data["molecule"]),
        method=data["method"],
        density=density_from_dict(data["density"]),
        backend=backend,
        energy_hartree=(
            float(data["energy_hartree"]) if "energy_hartree" in data else None
        ),
        reference_energies=ref_energies,
        trajectories=trajectories,
        comparison=comparison,
        provenance=provenance,
    )


def _density_to_dict(density: MeshSurface | DensityGrid) -> dict[str, Any]:
    return asdict(density)


def bundle_to_dict(bundle: VisualizationBundle) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": bundle.schema_version,
        "molecule": {
            "id": bundle.molecule.id,
            "label": bundle.molecule.label,
            "bond_length_angstrom": bundle.molecule.bond_length_angstrom,
            "basis": bundle.molecule.basis,
            "atoms": [
                {"symbol": a.symbol, "position": a.position}
                for a in bundle.molecule.atoms
            ],
        },
        "method": bundle.method,
        "density": _density_to_dict(bundle.density),
    }
    if bundle.backend is not None:
        payload["backend"] = asdict(bundle.backend)
    if bundle.energy_hartree is not None:
        payload["energy_hartree"] = bundle.energy_hartree
    if bundle.reference_energies is not None:
        payload["reference_energies"] = bundle.reference_energies
    if bundle.trajectories is not None:
        payload["trajectories"] = asdict(bundle.trajectories)
    if bundle.comparison is not None:
        payload["comparison"] = _density_to_dict(bundle.comparison)
    if bundle.provenance is not None:
        payload["provenance"] = asdict(bundle.provenance)
    return payload


def load_bundle(path: Path) -> VisualizationBundle:
    """Load a visualization bundle from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return bundle_from_dict(data)


def save_bundle(bundle: VisualizationBundle, path: Path) -> None:
    """Write a visualization bundle to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle_to_dict(bundle), indent=2) + "\n",
        encoding="utf-8",
    )
