# ADR-004: Visualization data schema

**Status:** Accepted
**Date:** 2026-05-27
**Deciders:** Aryan, Arnav
**Related:** [GitHub issue #18](https://github.com/qorbital-lab/qorbital/issues/18), [#17](https://github.com/qorbital-lab/qorbital/issues/17)

## Context

The chemistry, VQE, Bohmian, PyVista, and Three.js layers all need a single,
versioned format for passing molecular geometry, electron density, and (later)
trajectories to renderers. Without a contract, the web viewer and notebook
renderer will diverge.

Constraints:

- Large density grids must not be inlined in JSON (use sidecar binary files).
- H₂ mock data must be loadable before the full VQE pipeline lands.
- Browser and Python must validate the same `schema_version`.

## Options considered

### Option A: Mesh-only JSON (precomputed vertices/faces)

- Pros: Fast in the browser; no marching cubes on the client for large systems.
- Cons: Large payloads for high-resolution surfaces; must re-export per isovalue
  unless the client recomputes.

### Option B: Grid-only (origin, spacing, shape + binary values)

- Pros: One export supports many isovalues (client-side marching cubes).
- Cons: Heavier in the browser; needs Web Workers for LiH-scale grids.

### Option C: Dual format (`kind: "mesh"` | `kind: "grid"`)

- Pros: H₂ and demos use grids or meshes; LiH/BeH₂ can ship precomputed meshes.
- Cons: Two code paths in loaders (accepted).

## Decision

We chose **Option C** — a `VisualizationBundle` with `schema_version`, molecule
metadata, and a `density` object that is either `MeshSurface` or `DensityGrid`.
Trajectories and HF comparison payloads are optional extensions in the same bundle.

Canonical Python types live in `qorbital.viz.schema`. The web viewer validates
`schema_version` and loads sidecars relative to the bundle JSON path.

## Schema summary

| Object | Purpose |
|--------|---------|
| `VisualizationBundle` | Top-level payload for one geometry + method |
| `MoleculeSpec` | Atoms, bond length, basis, id |
| `MeshSurface` | Precomputed isosurface (`vertices`, `faces`, optional `vertex_scalars`) |
| `DensityGrid` | 3D grid metadata + `values` sidecar path |
| `TrajectorySet` | Bohmian paths (Phase 3) |
| `PESManifest` | Bond-length sweep index (Phase 4) |

See `qorbital/viz/schema.py` for field definitions and `qorbital/viz/web/fixtures/h2_mesh_v0.json` for an example.

## Consequences

- Three.js skeleton (#17) loads `MeshSurface` mock fixtures immediately.
- PyVista renderer (#16) should consume the same bundle type.
- Bump `schema_version` on breaking changes; loaders reject unknown major versions.
- Revisit when #10 (density from VQE) lands: default export may be `DensityGrid`
  with optional cached `MeshSurface` for performance.
