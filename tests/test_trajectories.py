"""Tests for trajectory bundle export."""

import struct

import numpy as np
import pytest

from qorbital.chemistry.density import compute_density
from qorbital.chemistry.hamiltonian import build_hamiltonian
from qorbital.chemistry.integrals import compute_integrals
from qorbital.viz.schema import load_bundle
from qorbital.viz.trajectories import (
    build_molecule_bundle,
    density_grid_to_sidecar,
    trajectories_to_sidecar,
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
