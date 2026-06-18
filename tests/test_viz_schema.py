"""Tests for ADR-004 visualization schema and fixtures."""

from pathlib import Path

import pytest

from qorbital.viz.fixtures import (
    grid_mock_bundle,
    h2_mock_bundle,
    write_h2_fixture,
    write_h2_grid_fixture,
)
from qorbital.viz.schema import (
    SCHEMA_VERSION,
    MeshSurface,
    TrajectorySet,
    bundle_from_dict,
    bundle_to_dict,
    load_bundle,
)


def test_h2_mock_bundle_mesh():
    bundle = h2_mock_bundle()
    assert bundle.schema_version == SCHEMA_VERSION
    assert bundle.molecule.id == "H2"
    assert len(bundle.molecule.atoms) == 2
    assert isinstance(bundle.density, MeshSurface)
    assert len(bundle.density.vertices) > 0
    assert len(bundle.density.faces) > 0
    assert bundle.density.vertex_scalars is not None


def test_round_trip_dict():
    bundle = h2_mock_bundle()
    restored = bundle_from_dict(bundle_to_dict(bundle))
    assert restored.molecule.id == bundle.molecule.id
    assert len(restored.density.vertices) == len(bundle.density.vertices)


def test_write_and_load_fixture(tmp_path: Path):
    path = tmp_path / "h2.json"
    write_h2_fixture(path)
    loaded = load_bundle(path)
    assert loaded.molecule.bond_length_angstrom == pytest.approx(0.74)


def test_grid_bundle_kind():
    bundle = grid_mock_bundle()
    assert bundle.density.kind == "grid"


def test_committed_web_fixture():
    fixture = (
        Path(__file__).resolve().parents[1]
        / "qorbital"
        / "viz"
        / "web"
        / "fixtures"
        / "h2_mesh_v0.json"
    )
    assert fixture.is_file(), "expected committed fixture h2_mesh_v0.json to exist"
    loaded = load_bundle(fixture)
    assert loaded.molecule.id == "H2"


def test_write_h2_grid_fixture(tmp_path: Path):
    json_path, bin_path = write_h2_grid_fixture(tmp_path)
    loaded = load_bundle(json_path)
    assert loaded.density.kind == "grid"
    assert bin_path.stat().st_size == 21 * 21 * 21 * 4


def test_unsupported_schema_version():
    data = bundle_to_dict(h2_mock_bundle())
    data["schema_version"] = "9.0.0"
    with pytest.raises(ValueError, match="unsupported schema_version"):
        bundle_from_dict(data)


def test_density_kind_is_required():
    data = bundle_to_dict(h2_mock_bundle())
    data["density"].pop("kind")
    with pytest.raises(ValueError, match="density.kind is required"):
        bundle_from_dict(data)


def test_atom_position_coerced_to_float():
    data = bundle_to_dict(h2_mock_bundle())
    data["molecule"]["atoms"][0]["position"] = [0, "1.5", -2]
    parsed = bundle_from_dict(data)
    assert parsed.molecule.atoms[0].position == [0.0, 1.5, -2.0]


def test_mesh_shape_validated():
    data = bundle_to_dict(h2_mock_bundle())
    data["density"]["vertices"][0] = [0.0, 1.0]
    with pytest.raises(ValueError, match="mesh vertex"):
        bundle_from_dict(data)


def test_trajectory_set_superposition_round_trip():
    bundle = h2_mock_bundle()
    period = 10.47
    times = [0.0, period / 2.0, period]
    bundle.trajectories = TrajectorySet(
        particles=20,
        steps=3,
        dt=period / 2.0,
        paths="h2_trajectories.bin",
        times=times,
        period=period,
        state_indices=[0, 1],
        E0=-1.857,
        E1=-1.256,
        c0=0.7071067811865475,
        c1=0.7071067811865475,
        omega=0.601,
        source="exact_diag",
    )
    restored = bundle_from_dict(bundle_to_dict(bundle))
    assert restored.trajectories is not None
    traj = restored.trajectories
    assert traj.particles == 20
    assert traj.steps == 3
    assert traj.times == pytest.approx(times)
    assert traj.period == pytest.approx(period)
    assert traj.state_indices == [0, 1]
    assert traj.E0 == pytest.approx(-1.857)
    assert traj.E1 == pytest.approx(-1.256)
    assert traj.c0 == pytest.approx(0.7071067811865475)
    assert traj.c1 == pytest.approx(0.7071067811865475)
    assert traj.omega == pytest.approx(0.601)
    assert traj.source == "exact_diag"

    payload = bundle_to_dict(bundle)
    traj_payload = payload["trajectories"]
    assert "times" in traj_payload
    assert "period" in traj_payload
    assert "E0" in traj_payload
    assert "coefficients" not in traj_payload


def test_legacy_bundle_loads_without_superposition_fields():
    root = Path(__file__).resolve().parents[1]
    fixture = root / "data" / "bundles" / "h2" / "h2_bundle.json"
    loaded = load_bundle(fixture)
    assert loaded.trajectories is not None
    traj = loaded.trajectories
    assert traj.particles == 20
    assert traj.steps == 100
    assert traj.dt == pytest.approx(0.1)
    assert traj.paths == "h2_trajectories.bin"
    assert traj.times is None
    assert traj.period is None
    assert traj.state_indices is None
    assert traj.E0 is None
    assert traj.E1 is None
    assert traj.c0 is None
    assert traj.c1 is None
    assert traj.omega is None
    assert traj.source is None
