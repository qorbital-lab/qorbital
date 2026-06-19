"""Tests for the VQE submission wrapper and the real IonQ submit path (B9)."""

import json
import os

import numpy as np
import pytest
from qiskit.providers.fake_provider import GenericBackendV2

from qorbital.vqe.backends import IONQ_API_KEY_ENV, Backend
from qorbital.vqe.submit import _best_effort_cost, submit_vqe

_HAS_IONQ_KEY = bool(
    os.getenv(IONQ_API_KEY_ENV)
    or os.getenv("QISKIT_IONQ_API_TOKEN")
    or os.getenv("IONQ_API_TOKEN")
)
_requires_key = pytest.mark.skipif(
    not _HAS_IONQ_KEY, reason=f"requires {IONQ_API_KEY_ENV} (no hardware in CI)"
)

STUB_EV = -1.857275


class _StubData:
    def __init__(self, evs):
        self.evs = evs


class _StubPubResult:
    def __init__(self, evs):
        self.data = _StubData(evs)


class _StubJob:
    def __init__(self, evs):
        self._evs = evs

    def result(self):
        return [_StubPubResult(self._evs)]


class _StubEstimator:
    """Mimics a BackendEstimatorV2: exposes ``.backend`` and a PUB ``run``.

    ``.backend`` is a real :class:`GenericBackendV2` so the ISA transpilation in
    ``evaluate_energy_on_estimator`` runs end-to-end (H2/JW UCCSD needs 4
    qubits); ``run`` returns a fixed result so the measured energy is
    deterministic.
    """

    def __init__(self, evs):
        self._evs = evs
        self.backend = GenericBackendV2(num_qubits=4, seed=0)

    def run(self, pubs):
        return _StubJob(self._evs)


class _MetaJob:
    def __init__(self, metadata):
        self._metadata = metadata


class TestBestEffortCost:
    def test_reads_cost_usd(self):
        assert _best_effort_cost([_MetaJob({"cost_usd": 0.42})]) == pytest.approx(0.42)

    def test_sums_across_jobs(self):
        jobs = [_MetaJob({"cost": 0.1}), _MetaJob({"cost": 0.25})]
        assert _best_effort_cost(jobs) == pytest.approx(0.35)

    def test_none_when_absent(self):
        assert _best_effort_cost([_MetaJob({}), object()]) is None

    def test_ignores_non_numeric(self):
        assert _best_effort_cost([_MetaJob({"cost_usd": "n/a"})]) is None


class TestIonQSubmitWiring:
    """The measured energy must come from the estimator, not synthetic noise."""

    def test_energy_from_estimator_no_gaussian(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "qorbital.vqe.submit.make_estimator",
            lambda backend, shots: _StubEstimator(np.array([STUB_EV])),
        )

        log = submit_vqe(
            "H2",
            backend=Backend.IONQ_SIM,
            shots=1000,
            output_dir=tmp_path,
            run_id="stub_h2",
        )

        # Electronic energy is exactly the stubbed expectation value: a residual
        # gaussian-noise branch would have perturbed the total instead.
        assert log.electronic_energy == pytest.approx(STUB_EV)
        assert log.energy == pytest.approx(STUB_EV + log.nuclear_repulsion_energy)
        assert log.cost_credits is None
        assert log.backend == "ionq_sim"

        # Round-trips to disk under the molecule directory.
        written = json.loads((tmp_path / "stub_h2.json").read_text())
        assert written["electronic_energy"] == pytest.approx(STUB_EV)

    def test_aer_keeps_exact_local_energy(self, tmp_path, monkeypatch):
        # AER must never reach the IonQ path / require a key.
        monkeypatch.setattr(
            "qorbital.vqe.submit.make_estimator",
            lambda *a, **k: pytest.fail("AER must not build an IonQ estimator"),
        )

        log = submit_vqe(
            "H2",
            backend=Backend.AER,
            output_dir=tmp_path,
            run_id="aer_h2",
        )

        assert log.energy == pytest.approx(-1.137, abs=5e-3)
        assert log.cost_credits is None
        assert log.backend == "aer"


@pytest.mark.hardware
@_requires_key
def test_submit_ionq_sim_real(tmp_path):
    log = submit_vqe(
        "H2",
        backend=Backend.IONQ_SIM,
        shots=1000,
        max_iterations=30,
        output_dir=tmp_path,
    )
    assert log.energy < 0.0
    assert log.backend == "ionq_sim"
