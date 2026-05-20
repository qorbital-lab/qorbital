"""Molecule definitions and geometry."""

from __future__ import annotations

from typing import Callable

MOLECULE_REGISTRY: dict[str, Callable[[float], str]] = {
    "H2": lambda r: f"H 0 0 0; H 0 0 {r}",
    "HeH+": lambda r: f"He 0 0 0; H 0 0 {r}",
    "LiH": lambda r: f"Li 0 0 0; H 0 0 {r}",
    "BeH2": lambda r: f"Be 0 0 0; H 0 0 {r}; H 0 0 {-r}",
}

DEFAULT_BOND_LENGTHS: dict[str, float] = {
    "H2": 0.735,
    "HeH+": 0.772,
    "LiH": 1.596,
    "BeH2": 1.326,
}


def resolve_atom_string(atoms: str, bond_length: float | None = None) -> str:
    """Convert a molecule name or raw PySCF atom string to a PySCF atom string."""
    if atoms not in MOLECULE_REGISTRY:
        return atoms

    if bond_length is None:
        bond_length = DEFAULT_BOND_LENGTHS[atoms]
    return MOLECULE_REGISTRY[atoms](bond_length)
