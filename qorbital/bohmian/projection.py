"""Multi-electron to single-particle projection for Bohmian visualisation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from qorbital.chemistry.density import (
    ElectronDensityGrid,
    WavefunctionGrid,
    wavefunction_grid,
)
from qorbital.chemistry.integrals import MolecularIntegrals


def project_natural_orbital(
    density_grid: ElectronDensityGrid,
    integrals: MolecularIntegrals,
    atom_string: str,
    basis: str = "sto-3g",
    orbital_index: int = 0,
    phase: NDArray[np.complex128] | complex | None = None,
) -> WavefunctionGrid:
    """Project multi-electron state onto the highest-occupation natural orbital.

    Diagonalises the 1-RDM (already done in :func:`compute_density`) and uses
    the natural orbital with the largest occupation as an effective
    single-particle wavefunction for Bohmian trajectory visualisation.

    This is a visualization approximation, not an exact N-body Bohmian
    treatment.  See Wyatt (2005) for the theoretical context of using
    natural orbitals in quantum trajectory methods.

    Parameters
    ----------
    orbital_index
        Which natural orbital to project (0 = highest occupation).
    phase
        Optional phase injection for non-stationary Bohmian motion.
    """
    return wavefunction_grid(
        density_grid,
        integrals,
        atom_string=atom_string,
        basis=basis,
        orbital_index=orbital_index,
        phase=phase,
    )


def project_homo_orbital(
    density_grid: ElectronDensityGrid,
    integrals: MolecularIntegrals,
    atom_string: str,
    basis: str = "sto-3g",
    phase: NDArray[np.complex128] | complex | None = None,
) -> WavefunctionGrid:
    """Fallback: use the Hartree-Fock HOMO as the single-particle psi.

    Simpler than natural-orbital projection; visually similar for many
    closed-shell molecules when NO projection produces poor results.
    """
    from pyscf import gto

    from qorbital.chemistry.density import _ANGSTROM_TO_BOHR, _molecule_meta
    from qorbital.chemistry.density import WavefunctionGrid as WFG

    resolved, charge, spin = _molecule_meta(atom_string)
    mo_coeff = integrals.mo_coefficients
    n_occ = integrals.num_particles[0]
    homo_ao = mo_coeff[:, n_occ - 1]

    mol = gto.M(atom=resolved, basis=basis, charge=charge, spin=spin, unit="Angstrom")
    grid_bohr = density_grid.grid_points * _ANGSTROM_TO_BOHR
    ao_vals = mol.eval_gto("GTOval_sph", grid_bohr)
    psi_flat = ao_vals @ homo_ao.astype(np.complex128)

    if phase is not None:
        if np.isscalar(phase) or isinstance(phase, (complex, float, int)):
            psi_flat = psi_flat * np.exp(1j * float(phase))
        else:
            psi_flat = psi_flat * np.exp(1j * np.asarray(phase, dtype=np.float64))

    return WFG(
        psi=psi_flat.reshape(density_grid.grid_shape),
        grid_shape=density_grid.grid_shape,
        origin=density_grid.origin.copy(),
        spacing=density_grid.spacing.copy(),
        occupation=2.0,
        orbital_index=n_occ - 1,
    )
