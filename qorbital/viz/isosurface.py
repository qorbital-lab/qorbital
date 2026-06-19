"""Isosurface level selection from electron-density grids."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def integrated_electron_count(
    density: NDArray[np.float64],
    spacing: NDArray[np.float64],
) -> float:
    """Integrate rho(r) over the grid volume (electrons)."""
    dV = float(np.prod(spacing))
    return float(np.sum(density) * dV)


def isovalue_enclosing_fraction(
    density: NDArray[np.float64],
    spacing: NDArray[np.float64],
    fraction: float,
) -> tuple[float, float]:
    """Return ``(isovalue, actual_enclosed_fraction)`` for a target fraction."""
    flat = np.asarray(density, dtype=np.float64).ravel()
    dV = float(np.prod(spacing))
    total = float(np.sum(flat) * dV)
    if total <= 0 or flat.size == 0:
        return 0.0, 0.0

    target = total * min(1.0, max(0.0, fraction))
    positive = flat[flat > 0]
    if positive.size == 0:
        return 0.0, 0.0

    sorted_rho = np.sort(positive)[::-1]
    accumulated = 0.0
    isovalue = float(sorted_rho[-1])
    for rho in sorted_rho:
        accumulated += float(rho) * dV
        isovalue = float(rho)
        if accumulated >= target:
            break

    actual = accumulated / total if total > 0 else 0.0
    return isovalue, actual
