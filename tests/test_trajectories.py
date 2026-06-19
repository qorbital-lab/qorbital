"""Tests for trajectory bundle export."""

import struct

import numpy as np
import pytest

from qorbital.bohmian.velocity import superposition_period
from qorbital.chemistry.density import compute_density
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.chemistry.superposition import build_superposition_state
from qorbital.viz.schema import _trajectory_to_dict, load_bundle
from qorbital.viz.trajectories import (
    build_molecule_bundle,
    density_grid_to_sidecar,
    trajectories_to_sidecar,
    trajectory_set_from_superposition,
)


@pytest.fixture
def h2_density():
    integrals = compute_integrals("H2", bond_length=0.735)
    qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
    matrix = qh.qubit_op.to_matrix()
    _, eigvecs = np.linalg.eigh(matrix)
    sv = eigvecs[:, 0]
    return compute_density(sv, integrals, grid_points=15, atom_string="H2")


class TestTrajectoryExport:
    def test_sidecar_binary_format(self, tmp_path, h2_density):
        traj = np.random.randn(5, 10, 3).astype(np.float64)
        traj_set = trajectories_to_sidecar(traj, tmp_path, "test_traj.bin")
        assert traj_set.particles == 5
        assert traj_set.steps == 10
        raw = (tmp_path / "test_traj.bin").read_bytes()
        values = struct.unpack(f"<{5 * 10 * 3}f", raw)
        assert len(values) == 150

    def test_density_sidecar(self, tmp_path, h2_density):
        grid = density_grid_to_sidecar(h2_density, tmp_path, "test_dens.bin")
        assert grid.shape == list(h2_density.grid_shape)
        assert (tmp_path / "test_dens.bin").exists()

    def test_bundle_roundtrip(self, tmp_path, h2_density):
        traj = np.zeros((3, 5, 3))
        _, json_path = build_molecule_bundle(
            "H2",
            "H₂",
            bond_length=0.735,
            density=h2_density,
            trajectories=traj,
            output_dir=tmp_path,
        )
        bundle = load_bundle(json_path)
        assert bundle.molecule.id == "H2"
        assert bundle.trajectories is not None
        assert bundle.trajectories.particles == 3

    def test_bundle_includes_hf_comparison(self, tmp_path, h2_density):
        traj = np.zeros((3, 5, 3))
        _, json_path = build_molecule_bundle(
            "H2",
            "H₂",
            bond_length=0.735,
            density=h2_density,
            trajectories=traj,
            output_dir=tmp_path,
        )
        bundle = load_bundle(json_path)
        assert bundle.comparison is not None
        assert bundle.comparison.kind == "grid"
        assert (tmp_path / "h2_comparison.bin").exists()
        assert bundle.comparison.shape == list(h2_density.grid_shape)
        assert bundle.comparison.origin == list(h2_density.origin)
        assert bundle.comparison.spacing == list(h2_density.spacing)

    def test_sidecar_without_superposition_unchanged(self, tmp_path):
        traj = np.zeros((3, 5, 3))
        traj_set = trajectories_to_sidecar(traj, tmp_path, "plain.bin", dt=0.1)
        payload = _trajectory_to_dict(traj_set)
        assert payload.keys() == {
            "particles",
            "steps",
            "dt",
            "paths",
            "path_layout",
            "color_by",
        }

    def test_sidecar_with_superposition_metadata(self, tmp_path):
        state = build_superposition_state("H2", bond_length=0.735, grid_points=15)
        n_steps = 50
        period = superposition_period(state.E0, state.E1)
        times = np.linspace(0.0, period, n_steps)
        traj = np.zeros((5, n_steps, 3))
        traj_set = trajectory_set_from_superposition(
            traj, tmp_path, "super.bin", state, times
        )
        assert traj_set.state_indices == [0, 1]
        assert traj_set.E0 == pytest.approx(state.E0)
        assert traj_set.E1 == pytest.approx(state.E1)
        assert traj_set.c0 == pytest.approx(state.c0)
        assert traj_set.c1 == pytest.approx(state.c1)
        assert traj_set.omega == pytest.approx(state.omega)
        assert traj_set.source == state.source
        assert traj_set.period == pytest.approx(period)
        assert traj_set.times == pytest.approx(times.tolist())
        assert traj_set.dt == pytest.approx(period / (n_steps - 1))
        assert traj_set.steps == n_steps
        payload = _trajectory_to_dict(traj_set)
        assert "E0" in payload
        assert "c0" in payload
        assert "coefficients" not in payload
