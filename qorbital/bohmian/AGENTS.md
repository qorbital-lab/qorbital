# qorbital/bohmian

Computes Bohmian velocity fields and integrates particle trajectories from VQE-optimized wavefunctions.

## Pipeline

1. Extract 1-RDM from VQE result
2. Diagonalize → natural orbital coefficients + occupation numbers
3. Reconstruct electron density on 3D grid (NumPy)
4. Compute Bohmian velocity field: v = (ℏ/m) Im(∇ψ/ψ)
5. Integrate trajectories via adaptive Runge-Kutta (SciPy `solve_ivp`)

## Design Notes

- For multi-electron molecules, project onto natural orbitals from 1-RDM. Document this as a reduced single-particle description
- Users seed particles at different starting positions → trajectories reveal orbital structure
- Multiple hardware runs yield different velocity fields. This is intentional — trajectory variation is the visualization
- Node regions produce sensitive, divergent trajectories. This is expected and educational

## Conventions

- Grid coordinates in Bohr (atomic units) internally, convert to Angstroms at viz boundary
- Velocity field stored as 3D vector field on regular grid
- Trajectory output: list of (t, x, y, z) arrays per particle
