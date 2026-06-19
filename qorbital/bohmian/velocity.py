"""Bohmian velocity field from a complex wavefunction on a 3D grid."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from qorbital.chemistry.superposition import SuperpositionState

# Atomic units: hbar = m_e = 1
_HBAR = 1.0
_MASS = 1.0
_DENSITY_CUTOFF = 1e-8
StateGradients = tuple[
    NDArray[np.complex128],
    NDArray[np.complex128],
    NDArray[np.complex128],
]


def _bohmian_velocity_from_gradients(
    psi: NDArray[np.complex128],
    dpsi_dx: NDArray[np.complex128],
    dpsi_dy: NDArray[np.complex128],
    dpsi_dz: NDArray[np.complex128],
    *,
    hbar: float = _HBAR,
    mass: float = _MASS,
    density_cutoff: float = _DENSITY_CUTOFF,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Shared Im[grad psi / psi] velocity with density cutoff."""
    psi = np.asarray(psi, dtype=np.complex128)
    density = np.abs(psi) ** 2

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


def bohmian_velocity_at_point(
    psi: complex,
    dpsi_dx: complex,
    dpsi_dy: complex,
    dpsi_dz: complex,
    *,
    hbar: float = _HBAR,
    mass: float = _MASS,
    density_cutoff: float = _DENSITY_CUTOFF,
) -> tuple[float, float, float]:
    """Pointwise Bohmian velocity v = (hbar/m) Im[grad psi / psi]."""
    density = abs(psi) ** 2
    if density < density_cutoff:
        return (0.0, 0.0, 0.0)
    scale = hbar / mass
    with np.errstate(divide="ignore", invalid="ignore"):
        return (
            float(scale * np.imag(dpsi_dx / psi)),
            float(scale * np.imag(dpsi_dy / psi)),
            float(scale * np.imag(dpsi_dz / psi)),
        )


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
    dpsi_dx = np.gradient(psi, spacing[0], axis=0)
    dpsi_dy = np.gradient(psi, spacing[1], axis=1)
    dpsi_dz = np.gradient(psi, spacing[2], axis=2)
    return _bohmian_velocity_from_gradients(
        psi,
        dpsi_dx,
        dpsi_dy,
        dpsi_dz,
        hbar=hbar,
        mass=mass,
        density_cutoff=density_cutoff,
    )


def superposition_wavefunction(
    phi0: NDArray[np.complex128],
    phi1: NDArray[np.complex128],
    E0: float,
    E1: float,
    t: float,
    *,
    c0: float = 1.0 / math.sqrt(2.0),
    c1: float = 1.0 / math.sqrt(2.0),
    hbar: float = _HBAR,
) -> NDArray[np.complex128]:
    """Two-state superposition Psi(r,t) on a precomputed orbital grid."""
    phase0 = np.exp(-1j * E0 * t / hbar)
    phase1 = np.exp(-1j * E1 * t / hbar)
    return c0 * phi0 * phase0 + c1 * phi1 * phase1


def superposition_period(E0: float, E1: float, *, hbar: float = _HBAR) -> float:
    """Full oscillation period ``2*pi/omega`` for energies in Hartree (a.u.)."""
    delta = abs(E1 - E0)
    if delta < 1e-15:
        msg = "degenerate eigen-energies yield an undefined superposition period"
        raise ValueError(msg)
    return 2.0 * math.pi * hbar / delta


def precompute_state_gradients(
    phi: NDArray[np.complex128],
    spacing_bohr: NDArray[np.float64],
) -> StateGradients:
    """Spatial gradients of a single-particle orbital on a Bohr grid."""
    phi = np.asarray(phi, dtype=np.complex128)
    return (
        np.gradient(phi, spacing_bohr[0], axis=0),
        np.gradient(phi, spacing_bohr[1], axis=1),
        np.gradient(phi, spacing_bohr[2], axis=2),
    )


def superposition_velocity_field(
    phi0: NDArray[np.complex128],
    phi1: NDArray[np.complex128],
    grad_phi0: StateGradients,
    grad_phi1: StateGradients,
    E0: float,
    E1: float,
    t: float,
    spacing_bohr: NDArray[np.float64],
    *,
    c0: float = 1.0 / math.sqrt(2.0),
    c1: float = 1.0 / math.sqrt(2.0),
    hbar: float = _HBAR,
    mass: float = _MASS,
    density_cutoff: float = _DENSITY_CUTOFF,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Bohmian velocity of a two-state superposition at time ``t``.

    ``spacing_bohr`` must be in atomic units (Bohr), matching the B3 contract.
    """
    del spacing_bohr  # gradients already incorporate grid spacing
    phase0 = np.exp(-1j * E0 * t / hbar)
    phase1 = np.exp(-1j * E1 * t / hbar)
    psi = c0 * phi0 * phase0 + c1 * phi1 * phase1
    dpsi_dx = c0 * grad_phi0[0] * phase0 + c1 * grad_phi1[0] * phase1
    dpsi_dy = c0 * grad_phi0[1] * phase0 + c1 * grad_phi1[1] * phase1
    dpsi_dz = c0 * grad_phi0[2] * phase0 + c1 * grad_phi1[2] * phase1
    return _bohmian_velocity_from_gradients(
        psi,
        dpsi_dx,
        dpsi_dy,
        dpsi_dz,
        hbar=hbar,
        mass=mass,
        density_cutoff=density_cutoff,
    )


@dataclass(frozen=True)
class SuperpositionVelocityContext:
    """Precomputed gradients and metadata for time-dependent Bohmian velocity."""

    phi0: NDArray[np.complex128]
    phi1: NDArray[np.complex128]
    grad_phi0: StateGradients
    grad_phi1: StateGradients
    spacing_bohr: NDArray[np.float64]
    origin_bohr: NDArray[np.float64]
    E0: float
    E1: float
    c0: float
    c1: float

    @classmethod
    def from_state(cls, state: SuperpositionState) -> SuperpositionVelocityContext:
        return cls(
            phi0=state.phi0,
            phi1=state.phi1,
            grad_phi0=precompute_state_gradients(state.phi0, state.spacing),
            grad_phi1=precompute_state_gradients(state.phi1, state.spacing),
            spacing_bohr=state.spacing.copy(),
            origin_bohr=state.origin.copy(),
            E0=state.E0,
            E1=state.E1,
            c0=state.c0,
            c1=state.c1,
        )


def superposition_velocity_at_time(
    ctx: SuperpositionVelocityContext,
    t: float,
    *,
    hbar: float = _HBAR,
    mass: float = _MASS,
    density_cutoff: float = _DENSITY_CUTOFF,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Evaluate the superposition velocity field at atomic time ``t``."""
    return superposition_velocity_field(
        ctx.phi0,
        ctx.phi1,
        ctx.grad_phi0,
        ctx.grad_phi1,
        ctx.E0,
        ctx.E1,
        t,
        ctx.spacing_bohr,
        c0=ctx.c0,
        c1=ctx.c1,
        hbar=hbar,
        mass=mass,
        density_cutoff=density_cutoff,
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
