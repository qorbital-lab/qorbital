"""Spatial uncertainty cloud from Bohmian trajectory ensembles."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class UncertaintyCloud:
    """Histogram-based spatial probability and per-voxel standard deviation."""

    density: NDArray[np.float64]
    std: NDArray[np.float64]
    origin: NDArray[np.float64]
    spacing: NDArray[np.float64]
    grid_shape: tuple[int, int, int]


def compute_uncertainty_cloud(
    trajectory_ensembles: list[NDArray[np.float64]],
    origin: NDArray[np.float64],
    spacing: NDArray[np.float64],
    grid_shape: tuple[int, int, int],
) -> UncertaintyCloud:
    """Histogram N trajectory ensembles into a 3D probability density.

    Parameters
    ----------
    trajectory_ensembles
        List of arrays, each shape ``(n_particles, n_steps, 3)``.
    origin, spacing, grid_shape
        Target grid specification (Angstrom).

    Returns
    -------
    UncertaintyCloud
        Normalised spatial density plus per-voxel position std.
    """
    nx, ny, nz = grid_shape
    counts = np.zeros((nx, ny, nz), dtype=np.float64)
    sum_x = np.zeros((nx, ny, nz), dtype=np.float64)
    sum_y = np.zeros((nx, ny, nz), dtype=np.float64)
    sum_z = np.zeros((nx, ny, nz), dtype=np.float64)
    sum_sq = np.zeros((nx, ny, nz), dtype=np.float64)

    for ensemble in trajectory_ensembles:
        flat = ensemble.reshape(-1, 3)
        for pos in flat:
            idx = np.round((pos - origin) / spacing).astype(int)
            if np.any(idx < 0) or idx[0] >= nx or idx[1] >= ny or idx[2] >= nz:
                continue
            i, j, k = idx
            counts[i, j, k] += 1.0
            sum_x[i, j, k] += pos[0]
            sum_y[i, j, k] += pos[1]
            sum_z[i, j, k] += pos[2]
            sum_sq[i, j, k] += np.sum(pos**2)

    total = counts.sum()
    density = counts / total if total > 0 else counts

    with np.errstate(divide="ignore", invalid="ignore"):
        mean_x = np.where(counts > 0, sum_x / counts, 0.0)
        mean_y = np.where(counts > 0, sum_y / counts, 0.0)
        mean_z = np.where(counts > 0, sum_z / counts, 0.0)
        mean_sq = np.where(counts > 0, sum_sq / counts, 0.0)
        var = mean_sq - (mean_x**2 + mean_y**2 + mean_z**2)
        var = np.maximum(var, 0.0)
        std = np.sqrt(var)

    return UncertaintyCloud(
        density=density,
        std=std,
        origin=origin.copy(),
        spacing=spacing.copy(),
        grid_shape=grid_shape,
    )
