# ADR-001: Pin Qiskit to 1.x

**Status:** Accepted
**Date:** 2026-05-11
**Deciders:** Aryan, Arnav
**Related:** [GitHub issue #5](https://github.com/qorbital-lab/qorbital/issues/5)

## Context

qOrbital's quantum chemistry pipeline depends on `qiskit-nature` for
Hamiltonian construction and `qiskit-algorithms` for the VQE solver. Both
packages rely on Qiskit's V1 primitives (`Estimator`, `Sampler`), which were
removed in Qiskit 2.0.

As of May 2026 the latest `qiskit-nature` release is 0.7.2 (Feb 2024). An open
PR adds Qiskit 2.0 support, but no stable release exists yet. Additionally,
`qiskit-ionq` 1.0.x requires `qiskit>=2.0.0`, so the IonQ provider must also
be pinned to the 0.x line (`<1`) when using Qiskit 1.x.

A decision is needed now because Issue #5 pins all project dependencies and
the choice propagates into `uv.lock`, CI, and contributor environments.

## Options considered

### Option A: Pin to Qiskit 1.x (`>=1.4,<2`)

- Pros: All ecosystem packages (nature, algorithms, aer, ionq 0.x) are tested
  and stable on 1.x. No risk of runtime breakage.
- Cons: Cannot use Qiskit 2.x features (V2 primitives, new transpiler). Must
  revisit when upstream catches up.

### Option B: Use Qiskit 2.x, install qiskit-nature from git main

- Pros: Access to latest Qiskit features.
- Cons: Depends on unreleased code; may break at any commit. Not suitable for
  reproducible builds or CI.

## Decision

We chose **Option A** — pin `qiskit>=1.4,<2`. The corresponding IonQ provider
pin is `qiskit-ionq>=0.5,<1`.

## Consequences

- `uv.lock` resolves a fully stable dependency tree today.
- We cannot adopt Qiskit 2.x-only features until upstream packages release
  compatible versions.
- **Revisit trigger:** when `qiskit-nature` publishes a release with
  `qiskit>=2` support, open a new issue to bump the pin and update this ADR.
