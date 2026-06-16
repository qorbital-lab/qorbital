"""Tests for VQE backends, submission, PES, HF density, and data loader."""

import json
from pathlib import Path

import numpy as np
import pytest

from qorbital.bohmian.uncertainty import compute_uncertainty_cloud
from qorbital.chemistry.hartree_fock import compute_hf_density
from qorbital.chemistry.pes import compute_pes, load_pes, save_pes
from qorbital.data.loader import load_runs
from qorbital.vqe.backends import Backend, make_estimator
from qorbital.vqe.submit import RunLog, submit_vqe


class TestBackends:
    def test_aer_estimator(self):
        est = make_estimator(Backend.AER)
        assert est is not None

    def test_ionq_sim_estimator(self):
        est = make_estimator(Backend.IONQ_SIM, shots=500)
        assert est is not None

    def test_h2_vqe_aer_backend(self):
        from qorbital.vqe.solver import run_vqe

        result = run_vqe("H2", backend=Backend.AER, max_iterations=30)
        assert result.total_energy == pytest.approx(-1.137, abs=0.01)

    @pytest.mark.slow
    def test_h2_vqe_ionq_sim_backend(self):
        from qorbital.vqe.solver import run_vqe

        result = run_vqe(
            "H2", backend=Backend.IONQ_SIM, shots=1000, max_iterations=30
        )
        assert result.total_energy < 0.0


class TestSubmit:
    def test_submit_writes_log(self, tmp_path):
        log = submit_vqe(
            "H2",
            backend=Backend.AER,
            shots=100,
            max_iterations=20,
            output_dir=tmp_path,
            run_id="test_run",
        )
        assert isinstance(log, RunLog)
        log_path = tmp_path / "test_run.json"
        assert log_path.exists()
        data = json.loads(log_path.read_text())
        assert data["molecule"] == "H2"
        assert "energy" in data


class TestPES:
    @pytest.mark.slow
    def test_compute_and_cache(self, tmp_path):
        lengths = [0.6, 0.735, 0.9]
        pes = compute_pes("H2", lengths, backend=Backend.AER, max_iterations=20)
        assert len(pes) == 3
        path = save_pes("H2", pes, output_dir=tmp_path)
        loaded = load_pes("H2", pes_dir=tmp_path)
        assert len(loaded) == 3


class TestHartreeFock:
    def test_hf_density_overlays(self):
        hf = compute_hf_density("H2", bond_length=0.735, grid_points=20)
        assert hf.grid_shape == (20, 20, 20)
        assert hf.integrated_density == pytest.approx(2.0, abs=0.1)


class TestLoader:
    def test_load_runs(self, tmp_path):
        log = {
            "run_id": "abc",
            "molecule": "H2",
            "energy": -1.13,
            "timestamp": "2026-01-01T00:00:00",
        }
        h2_dir = tmp_path / "h2"
        h2_dir.mkdir()
        (h2_dir / "abc.json").write_text(json.dumps(log))
        runs = load_runs("H2", runs_dir=tmp_path)
        assert len(runs) == 1
        assert runs[0]["run_id"] == "abc"


class TestUncertainty:
    def test_histogram_cloud(self):
        origin = np.array([0.0, 0.0, 0.0])
        spacing = np.array([0.5, 0.5, 0.5])
        shape = (10, 10, 10)
        ensembles = [
            np.array([[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]]),
            np.array([[[0.0, 0.0, 0.5], [0.5, 0.0, 0.5]]]),
        ]
        cloud = compute_uncertainty_cloud(ensembles, origin, spacing, shape)
        assert cloud.density.shape == shape
        assert cloud.density.sum() == pytest.approx(1.0, abs=1e-6)
