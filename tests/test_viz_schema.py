"""Tests for ADR-004 visualization schema and fixtures."""

from pathlib import Path

import pytest

from qorbital.viz.fixtures import grid_mock_bundle, h2_mock_bundle, write_h2_fixture
from qorbital.viz.schema import (
    SCHEMA_VERSION,
    MeshSurface,
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
