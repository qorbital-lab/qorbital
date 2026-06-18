"""Bohmian velocity field from a complex wavefunction on a 3D grid."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Atomic units: hbar = m_e = 1
_HBAR = 1.0
_MASS = 1.0
_DENSITY_CUTOFF = 1e-8


def velocity_field(
    psi: NDArray[np.complex128],
    spacing: NDArray[np.float64],
    *,
    hbar: float = _HBAR,
    mass: float = _MASS,
    density_cutoff: float = _DENSITY_CUTOFF,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Compute Bohmian velocity v(r) = (hbar/m) Im[grad psi / psi] on a grid.

    Parameters
    ----------
    psi
        Complex wavefunction array, shape ``(nx, ny, nz)``.
    spacing
        Grid spacing ``[dx, dy, dz]`` in Angstrom (same units as the grid).
    density_cutoff
        Where ``|psi|^2 < cutoff``, velocity is set to zero to avoid
        division by zero near nodes.

    Returns
    -------
    vx, vy, vz
        Velocity component arrays, each shape ``(nx, ny, nz)``.

    Notes
    -----
    For a **real** stationary ground state, ``Im[grad psi / psi] = 0`` everywhere
    and trajectories remain fixed.  Inject phase into ``psi`` before calling
    this function to obtain non-trivial motion for visualisation.
    """
    psi = np.asarray(psi, dtype=np.complex128)
    density = np.abs(psi) ** 2

    dpsi_dx = np.gradient(psi, spacing[0], axis=0)
    dpsi_dy = np.gradient(psi, spacing[1], axis=1)
    dpsi_dz = np.gradient(psi, spacing[2], axis=2)

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_x = dpsi_dx / psi
        ratio_y = dpsi_dy / psi
        ratio_z = dpsi_dz / psi

    vx = (hbar / mass) * np.imag(ratio_x)
    vy = (hbar / mass) * np.imag(ratio_y)
    vz = (hbar / mass) * np.imag(ratio_z)

    mask = density < density_cutoff
    vx = np.where(mask, 0.0, vx)
    vy = np.where(mask, 0.0, vy)
    vz = np.where(mask, 0.0, vz)

    return (
        vx.astype(np.float64),
        vy.astype(np.float64),
        vz.astype(np.float64),
    )


def add_azimuthal_phase(
    psi: NDArray[np.complex128],
    origin: NDArray[np.float64],
    spacing: NDArray[np.float64],
    *,
    strength: float = 1.0,
) -> NDArray[np.complex128]:
    """Multiply a real psi by exp(i * strength * phi) for azimuthal phase.

    Useful for generating non-stationary Bohmian trajectories from a real
    natural orbital when the ground-state velocity field would otherwise
    vanish identically.
    """
    nx, ny, nz = psi.shape
    axes = [origin[i] + np.arange(n) * spacing[i] for i, n in enumerate((nx, ny, nz))]
    xv, yv, zv = np.meshgrid(*axes, indexing="ij")
    phi = np.arctan2(yv, xv)
    return psi * np.exp(1j * strength * phi)
