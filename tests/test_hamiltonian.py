"""Validate Hamiltonian construction across fermion-to-qubit mappings."""

import numpy as np
import pytest
from qiskit.quantum_info import SparsePauliOp

from qorbital.chemistry.hamiltonian import (
    QubitHamiltonian,
    QubitMapping,
    build_hamiltonian,
    map_integrals_to_qubit_op,
)
from qorbital.chemistry.integrals import compute_integrals

H2_REF_NUCLEAR_REPULSION = 0.719968994449
H2_REF_ELECTRONIC_GROUND_STATE = -1.8572750302023797


def _eigenvalues(qh: QubitHamiltonian) -> np.ndarray:
    """Diagonalise the qubit operator and return sorted eigenvalues."""
    return np.sort(np.linalg.eigvalsh(qh.qubit_op.to_matrix()).real)


@pytest.fixture(scope="module")
def h2_jw() -> QubitHamiltonian:
    return build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")


@pytest.fixture(scope="module")
def h2_parity() -> QubitHamiltonian:
    return build_hamiltonian("H2", bond_length=0.735, mapping="parity")


@pytest.fixture(scope="module")
def h2_parity_2qr() -> QubitHamiltonian:
    return build_hamiltonian(
        "H2", bond_length=0.735, mapping="parity", two_qubit_reduction=True
    )


class TestH2JordanWigner:
    """Validate JW mapping for H2/STO-3G."""

    def test_returns_sparse_pauli_op(self, h2_jw):
        assert isinstance(h2_jw.qubit_op, SparsePauliOp)

    def test_num_qubits(self, h2_jw):
        assert h2_jw.num_qubits == 4

    def test_metadata(self, h2_jw):
        assert h2_jw.mapping == QubitMapping.JORDAN_WIGNER
        assert h2_jw.num_particles == (1, 1)
        assert h2_jw.num_spatial_orbitals == 2
        assert h2_jw.two_qubit_reduction is False

    def test_ground_state_eigenvalue(self, h2_jw):
        ground = _eigenvalues(h2_jw)[0]
        np.testing.assert_allclose(ground, H2_REF_ELECTRONIC_GROUND_STATE, atol=1e-10)


class TestH2Parity:
    """Validate parity mapping for H2/STO-3G."""

    def test_num_qubits(self, h2_parity):
        assert h2_parity.num_qubits == 4

    def test_2qr_num_qubits(self, h2_parity_2qr):
        assert h2_parity_2qr.num_qubits == 2

    def test_parity_metadata(self, h2_parity):
        assert h2_parity.mapping == QubitMapping.PARITY
        assert h2_parity.two_qubit_reduction is False

    def test_2qr_metadata(self, h2_parity_2qr):
        assert h2_parity_2qr.mapping == QubitMapping.PARITY
        assert h2_parity_2qr.two_qubit_reduction is True


class TestEigenvalueEquivalence:
    """JW, parity, and parity+2qr must produce consistent spectra."""

    def test_jw_parity_eigenvalues_match(self, h2_jw, h2_parity):
        np.testing.assert_allclose(
            _eigenvalues(h2_jw), _eigenvalues(h2_parity), atol=1e-10
        )

    def test_2qr_ground_state_matches(self, h2_jw, h2_parity_2qr):
        jw_ground = _eigenvalues(h2_jw)[0]
        p2qr_ground = _eigenvalues(h2_parity_2qr)[0]
        np.testing.assert_allclose(jw_ground, p2qr_ground, atol=1e-10)

    def test_2qr_spectrum_smaller(self, h2_parity, h2_parity_2qr):
        assert len(_eigenvalues(h2_parity)) == 16
        assert len(_eigenvalues(h2_parity_2qr)) == 4


class TestInterfaceValidation:
    """Argument handling, string coercion, and error paths."""

    def test_string_mapping_arg(self, h2_jw):
        assert h2_jw.mapping == QubitMapping.JORDAN_WIGNER

    def test_enum_mapping_arg(self):
        result = build_hamiltonian("H2", bond_length=0.735, mapping=QubitMapping.PARITY)
        assert result.mapping == QubitMapping.PARITY

    def test_two_qubit_reduction_requires_parity(self):
        with pytest.raises(ValueError, match="parity"):
            build_hamiltonian(
                "H2",
                bond_length=0.735,
                mapping="jordan_wigner",
                two_qubit_reduction=True,
            )

    def test_raw_atom_string(self):
        result = build_hamiltonian("H 0 0 0; H 0 0 0.735")
        assert result.num_particles == (1, 1)

    def test_nuclear_repulsion_passed_through(self, h2_jw):
        assert h2_jw.nuclear_repulsion_energy == pytest.approx(
            H2_REF_NUCLEAR_REPULSION, abs=1e-10
        )


class TestMapIntegralsToQubitOp:
    """Validate the lower-level entry point."""

    def test_matches_build_hamiltonian(self):
        integrals = compute_integrals("H2", bond_length=0.735)
        from_map = map_integrals_to_qubit_op(integrals, mapping="jordan_wigner")
        from_build = build_hamiltonian("H2", bond_length=0.735, mapping="jordan_wigner")
        np.testing.assert_allclose(
            np.sort(np.linalg.eigvalsh(from_map.qubit_op.to_matrix()).real),
            np.sort(np.linalg.eigvalsh(from_build.qubit_op.to_matrix()).real),
            atol=1e-10,
        )

    def test_two_qubit_reduction_requires_parity(self):
        integrals = compute_integrals("H2", bond_length=0.735)
        with pytest.raises(ValueError, match="parity"):
            map_integrals_to_qubit_op(
                integrals, mapping="jordan_wigner", two_qubit_reduction=True
            )


class TestLiHSmoke:
    """Smoke tests for a larger molecule."""

    def test_jw_qubit_count(self):
        result = build_hamiltonian("LiH", bond_length=1.596, mapping="jordan_wigner")
        assert result.num_qubits == 12

    def test_parity_2qr_qubit_count(self):
        result = build_hamiltonian(
            "LiH", bond_length=1.596, mapping="parity", two_qubit_reduction=True
        )
        assert result.num_qubits == 10
