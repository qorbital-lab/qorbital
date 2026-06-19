"""Validate electron density extraction against PySCF/exact-diag references."""

import numpy as np
import pytest

from qorbital.chemistry.density import (
    ElectronDensityGrid,
    _extract_rdm1,
    compute_density,
    density_from_rdm1,
)
from qorbital.chemistry.hamiltonian import build_hamiltonian, make_mapper
from qorbital.chemistry.integrals import MolecularIntegrals, compute_integrals


@pytest.fixture(scope="module")
def h2_integrals() -> MolecularIntegrals:
    return compute_integrals("H2", bond_length=0.735, basis="sto-3g")


@pytest.fixture(scope="module")
def h2_statevector(h2_integrals: MolecularIntegrals) -> np.ndarray:
    qh = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
    matrix = qh.qubit_op.to_matrix()
    _, eigvecs = np.linalg.eigh(matrix)
    return eigvecs[:, 0]


@pytest.fixture(scope="module")
def h2_density(
    h2_statevector: np.ndarray, h2_integrals: MolecularIntegrals
) -> ElectronDensityGrid:
    return compute_density(
        h2_statevector, h2_integrals, grid_points=50, atom_string="H2"
    )


class TestDensityH2:
    """Acceptance criteria for H2/STO-3G with exact ground state."""

    def test_returns_dataclass(self, h2_density: ElectronDensityGrid):
        assert isinstance(h2_density, ElectronDensityGrid)

    def test_rdm1_trace_matches_electron_count(
        self, h2_density: ElectronDensityGrid, h2_integrals: MolecularIntegrals
    ):
        n_electrons = sum(h2_integrals.num_particles)
        assert h2_density.total_electrons == pytest.approx(n_electrons, abs=1e-6)

    def test_rdm1_mo_is_hermitian(self, h2_density: ElectronDensityGrid):
        np.testing.assert_allclose(h2_density.rdm1_mo, h2_density.rdm1_mo.T, atol=1e-10)

    def test_rdm1_ao_is_hermitian(self, h2_density: ElectronDensityGrid):
        np.testing.assert_allclose(h2_density.rdm1_ao, h2_density.rdm1_ao.T, atol=1e-10)

    def test_density_integrates_to_electron_count(
        self, h2_density: ElectronDensityGrid, h2_integrals: MolecularIntegrals
    ):
        n_electrons = sum(h2_integrals.num_particles)
        assert h2_density.integrated_density == pytest.approx(n_electrons, abs=1e-3)

    def test_density_non_negative(self, h2_density: ElectronDensityGrid):
        assert np.all(h2_density.density >= -1e-10)

    def test_density_peaks_above_threshold(self, h2_density: ElectronDensityGrid):
        assert np.max(h2_density.density) > 0.1

    def test_density_peaks_near_nuclei(self, h2_density: ElectronDensityGrid):
        flat = h2_density.density.ravel()
        peak_idx = np.argmax(flat)
        peak_coord = h2_density.grid_points[peak_idx]

        nucleus_a = np.array([0.0, 0.0, 0.0])
        nucleus_b = np.array([0.0, 0.0, 0.735])
        dist_a = np.linalg.norm(peak_coord - nucleus_a)
        dist_b = np.linalg.norm(peak_coord - nucleus_b)
        assert min(dist_a, dist_b) < 0.5

    def test_grid_shape_consistency(self, h2_density: ElectronDensityGrid):
        assert h2_density.density.shape == h2_density.grid_shape
        nx, ny, nz = h2_density.grid_shape
        assert h2_density.grid_points.shape == (nx * ny * nz, 3)

    def test_natural_occupations_sum_to_electrons(
        self, h2_density: ElectronDensityGrid, h2_integrals: MolecularIntegrals
    ):
        n_electrons = sum(h2_integrals.num_particles)
        assert np.sum(h2_density.natural_occupations) == pytest.approx(
            n_electrons, abs=1e-6
        )

    def test_natural_occupations_bounded(self, h2_density: ElectronDensityGrid):
        assert np.all(h2_density.natural_occupations >= -1e-10)
        assert np.all(h2_density.natural_occupations <= 2.0 + 1e-10)

    def test_natural_occupations_sorted_descending(
        self, h2_density: ElectronDensityGrid
    ):
        occs = h2_density.natural_occupations
        assert np.all(np.diff(occs) <= 1e-12)


class TestDensityFromRDM1:
    """The factored-out RDM->grid path reproduces compute_density exactly."""

    def test_matches_compute_density(
        self, h2_statevector: np.ndarray, h2_integrals: MolecularIntegrals
    ):
        full = compute_density(
            h2_statevector, h2_integrals, grid_points=20, atom_string="H2"
        )
        mapper = make_mapper("jordan_wigner", h2_integrals.num_particles, False)
        rdm1 = _extract_rdm1(h2_statevector, h2_integrals.num_spatial_orbitals, mapper)
        direct = density_from_rdm1(rdm1, h2_integrals, "H2", grid_points=20)
        np.testing.assert_allclose(direct.density, full.density, atol=1e-10)
        np.testing.assert_allclose(
            direct.natural_occupations, full.natural_occupations, atol=1e-10
        )


class TestInterfaceVariants:
    """Verify compute_density handles different argument forms."""

    def test_custom_grid_resolution(
        self, h2_statevector: np.ndarray, h2_integrals: MolecularIntegrals
    ):
        result = compute_density(
            h2_statevector, h2_integrals, grid_points=20, atom_string="H2"
        )
        assert result.grid_shape == (20, 20, 20)

    def test_custom_padding(
        self, h2_statevector: np.ndarray, h2_integrals: MolecularIntegrals
    ):
        result = compute_density(
            h2_statevector,
            h2_integrals,
            grid_points=20,
            padding=5.0,
            atom_string="H2",
        )
        extent_range = result.extent[:, 1] - result.extent[:, 0]
        assert np.all(extent_range > 9.0)

    def test_raw_atom_string_accepted(
        self, h2_statevector: np.ndarray, h2_integrals: MolecularIntegrals
    ):
        result = compute_density(
            h2_statevector,
            h2_integrals,
            grid_points=20,
            atom_string="H 0 0 0; H 0 0 0.735",
        )
        assert isinstance(result, ElectronDensityGrid)

    def test_missing_atom_string_raises(
        self, h2_statevector: np.ndarray, h2_integrals: MolecularIntegrals
    ):
        with pytest.raises(ValueError, match="atom_string is required"):
            compute_density(h2_statevector, h2_integrals, grid_points=10)


class TestLiHSmoke:
    """LiH (4 electrons, 12 qubits) -- needs a fine grid to resolve Li's 1s cusp."""

    @pytest.mark.slow
    def test_lih_density_integrates(self):
        integrals = compute_integrals("LiH", bond_length=1.596, basis="sto-3g")
        qh = build_hamiltonian("LiH", bond_length=1.596, mapping="jordan_wigner")
        matrix = qh.qubit_op.to_matrix()
        _, eigvecs = np.linalg.eigh(matrix)
        sv = eigvecs[:, 0]
        # 80**3 grid (~0.1 A spacing) is needed to resolve Li's sharp 1s cusp;
        # coarser grids systematically under-integrate by losing density at the nucleus.
        result = compute_density(sv, integrals, grid_points=80, atom_string="LiH")
        assert result.total_electrons == pytest.approx(4.0, abs=1e-6)
        assert result.integrated_density == pytest.approx(4.0, abs=5e-2)
