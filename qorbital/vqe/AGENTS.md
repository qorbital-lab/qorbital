# qorbital/vqe

Runs VQE to find ground-state energy and wavefunction. Consumes `ElectronicStructureProblem` from `chemistry/`.

## Backends (priority order)

1. IonQ Aria/Forte QPU via `qiskit-ionq` — primary, uses Qollab compute credits
2. IonQ simulator — interactive/development
3. `qiskit.primitives.StatevectorEstimator` — exact statevector sim, used in tests today
4. Qiskit Aer — optional offline fallback (dependency pinned; not wired in solver yet)

## Ansatz

UCCSD with HartreeFock initial state. Optimizer: SLSQP or COBYLA.

## Key Behaviors

- Emit parameter snapshots at each VQE iteration for the convergence dashboard
- Return optimized parameters + final `StatevectorResult` or measurement counts
- IonQ credentials via environment variables only — never in code
- Tests use `StatevectorEstimator`, never real hardware

## Qubit Mapping

```python
from qiskit_nature.second_q.mappers import JordanWignerMapper, ParityMapper
mapper = ParityMapper(num_particles=problem.num_particles)  # with 2-qubit reduction
```

Do NOT use `QubitConverter` — removed in Qiskit Nature 0.6.
