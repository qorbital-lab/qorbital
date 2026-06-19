"""VQE backend selection and estimator factory."""

from __future__ import annotations

import os
from enum import Enum

from qiskit.primitives import BaseEstimatorV2, StatevectorEstimator

#: Primary environment variable holding the IonQ API key.  The qiskit-ionq
#: provider also natively honours ``QISKIT_IONQ_API_TOKEN`` / ``IONQ_API_TOKEN``;
#: we accept those as fallbacks but document ``IONQ_API_KEY`` as canonical.
IONQ_API_KEY_ENV = "IONQ_API_KEY"
_IONQ_TOKEN_ENV_VARS = (IONQ_API_KEY_ENV, "QISKIT_IONQ_API_TOKEN", "IONQ_API_TOKEN")

#: Map each IonQ backend enum to the provider's device name string.
_IONQ_DEVICE_NAMES = {
    "ionq_sim": "simulator",
    "ionq_aria": "qpu.aria-1",
}


class Backend(str, Enum):
    """Supported VQE execution backends."""

    AER = "aer"
    IONQ_SIM = "ionq_sim"
    IONQ_ARIA = "ionq_aria"


def _resolve_ionq_token() -> str:
    """Return the IonQ API key from the environment or raise a clear error.

    Reads :data:`IONQ_API_KEY_ENV` first, then the qiskit-ionq native env vars
    as fallbacks.  Raising here (rather than letting the provider fail deep in
    its credential resolution) gives contributors an actionable message and
    keeps hardware-touching tests skippable in CI.
    """
    for env_var in _IONQ_TOKEN_ENV_VARS:
        token = os.getenv(env_var)
        if token:
            return token
    raise RuntimeError(
        f"No IonQ API key found. Set the {IONQ_API_KEY_ENV} environment variable "
        "to use an IonQ backend (never hardcode the key). Accepted fallbacks: "
        f"{', '.join(_IONQ_TOKEN_ENV_VARS[1:])}."
    )


def _make_ionq_estimator(backend: Backend, shots: int) -> BaseEstimatorV2:
    """Build a real IonQ-backed Estimator for the given cloud backend.

    qiskit-ionq exposes a ``BackendV1`` device but no native primitive, so we
    wrap it in qiskit's :class:`~qiskit.primitives.BackendEstimatorV2`.  Imports
    are local so AER-only / CI runs never need the cloud SDK or a key.
    """
    from qiskit.primitives import BackendEstimatorV2
    from qiskit_ionq import IonQProvider

    provider = IonQProvider(token=_resolve_ionq_token())
    device = provider.get_backend(_IONQ_DEVICE_NAMES[backend.value])
    device.set_options(shots=shots)
    return BackendEstimatorV2(backend=device)


def make_local_estimator() -> StatevectorEstimator:
    """Return the exact statevector estimator used for the VQE optimizer loop.

    Per the locked sprint decision the optimizer always runs locally; IonQ
    credits are spent only on the converged circuit (evaluation/submission).
    """
    return StatevectorEstimator()


def make_estimator(
    backend: Backend | str = Backend.AER,
    shots: int = 1024,
) -> BaseEstimatorV2:
    """Create a Qiskit estimator for the requested backend.

    Parameters
    ----------
    backend
        ``AER`` returns an exact local statevector estimator (default).
        ``IONQ_SIM`` / ``IONQ_ARIA`` return a real IonQ-backed
        :class:`~qiskit.primitives.BackendEstimatorV2` bound to
        ``ionq_simulator`` / ``ionq_qpu.aria-1`` respectively, requiring an API
        key (see :data:`IONQ_API_KEY_ENV`).  These are for *evaluation /
        submission* of the converged circuit; the VQE optimizer loop always
        uses :func:`make_local_estimator` (see ``solver.py``).
    shots
        Shot count for IonQ executions; recorded in run logs.

    Raises
    ------
    RuntimeError
        If an IonQ backend is requested without an API key in the environment.
    """
    if isinstance(backend, str):
        backend = Backend(backend.lower())

    if backend is Backend.AER:
        return StatevectorEstimator()
    return _make_ionq_estimator(backend, shots)
