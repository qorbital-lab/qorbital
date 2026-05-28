# qorbital/chemistry

Computes molecular integrals via PySCF and wraps them for the VQE pipeline.

## API

`compute_integrals(atoms, bond_length, basis="sto-3g")` → `MolecularIntegrals` dataclass containing one-body integrals, two-body integrals, nuclear repulsion energy, HF energy, MO coefficients, and the `ElectronicStructureProblem` for VQE.

## Qiskit Nature 0.7 Patterns

```python
from qiskit_nature.second_q.drivers import PySCFDriver
from qiskit_nature.units import DistanceUnit

driver = PySCFDriver(atom="H 0 0 0; H 0 0 0.735", basis="sto3g", unit=DistanceUnit.ANGSTROM)
problem = driver.run()
hamiltonian = problem.hamiltonian
one_body = hamiltonian.electronic_integrals.alpha["+-"]
two_body = hamiltonian.electronic_integrals.alpha["++--"]
nuclear_repulsion = hamiltonian.nuclear_repulsion_energy
```

## Molecule Registry

Four target molecules with default bond lengths:
- H₂ (0.735 Å) — 2 spatial orbitals in STO-3G, tutorial baseline
- HeH⁺ (0.772 Å) — polar asymmetry demo
- LiH (1.596 Å) — 6 spatial orbitals, main showcase
- BeH₂ (1.326 Å) — stretch goal, linear geometry (H–Be–H)

## Conventions

- Two-body integrals in chemist's notation `(ij|kl)`, matching PySCF default
- All geometries in Angstroms
- Basis defaults to STO-3G; support arbitrary basis strings
- Don't expose raw PySCF `Mole` or `SCF` objects outside this package — wrap in `MolecularIntegrals`
