"""VQE backend selection and estimator factory."""

from __future__ import annotations

from enum import Enum

from qiskit.primitives import BaseEstimatorV2, StatevectorEstimator


class Backend(str, Enum):
    """Supported VQE execution backends."""

    AER = "aer"
    IONQ_SIM = "ionq_sim"
    IONQ_ARIA = "ionq_aria"


def make_estimator(
    backend: Backend | str = Backend.AER,
    shots: int = 1024,
) -> BaseEstimatorV2:
    """Create a Qiskit estimator for the requested backend.

    Parameters
    ----------
    backend
        ``AER`` uses exact statevector simulation (default).
        ``IONQ_SIM`` / ``IONQ_ARIA`` use statevector simulation locally as a
        sim-only stand-in (UCCSD EvolvedOps are incompatible with Aer shot
        mode).  Real IonQ cloud submission is wired in ``submit.py`` but
        requires an API key and is left to a human operator.
    shots
        Recorded in run logs; used for synthetic noise scale in sim-only mode.
    """
    if isinstance(backend, str):
        backend = Backend(backend.lower())

    # UCCSD ansatz uses EvolvedOps gates incompatible with AerEstimator;
    # all local backends use StatevectorEstimator.  Shot noise for ensemble
    # diversity is injected in submit.py when backend != AER.
    return StatevectorEstimator()
