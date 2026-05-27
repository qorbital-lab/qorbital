"""PyVista renderer skeleton for ADR-004 visualization bundles.

Implements:
- render_isosurface: draw a single isosurface from a mock grid or mesh
- render_trajectories: draw simple mock trajectories as 3D lines
- render_combined: draw orbital, trajectories, and atoms from a VisualizationBundle

Designed to satisfy GitHub issue #16 and align with ADR-004 and the Three.js
viewer skeleton. This module intentionally keeps a small, testable surface
area and uses mock data until the full chemistry and Bohmian stacks land.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pyvista as pv

from qorbital.viz.fixtures import grid_mock_bundle, h2_mock_bundle
from qorbital.viz.schema import DensityGrid, MeshSurface, VisualizationBundle


@dataclass
class MockTrajectory:
    """Simple in-memory trajectory used before Bohmian engine is available."""

    points: np.ndarray  # shape (N, 3)


def _ensure_jupyter_backend(jupyter_backend: str | None) -> None:
    """Configure PyVista for Jupyter when requested."""

    if jupyter_backend is None:
        return
    try:
        pv.set_jupyter_backend(jupyter_backend)
    except Exception:  # pragma: no cover - backend availability is environment-specific
        # If the backend is unavailable, continue with the default one.
        return


def _grid_to_mock_polydata(grid: DensityGrid) -> pv.PolyData:
    """Convert a tiny DensityGrid into a mock isosurface PolyData.

    This avoids relying on backends that may not be available in all
    environments while still exercising the rendering path.
    """

    nx, ny, nz = grid.shape
    dx, dy, dz = grid.spacing
    ox, oy, oz = grid.origin

    xs = np.linspace(ox, ox + dx * (nx - 1), nx)
    ys = np.linspace(oy, oy + dy * (ny - 1), ny)
    zs = np.linspace(oz, oz + dz * (nz - 1), nz)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")

    r2 = X**2 + Y**2 + Z**2
    values = np.exp(-r2) - 0.5 * np.exp(-4.0 * r2)

    # Take an isosurface-like band and sample points from it to form a cloud.
    iso = float(grid.default_isovalue or 0.02)
    mask = np.logical_and(values > iso * 0.9, values < iso * 1.1)
    pts = np.stack([X[mask], Y[mask], Z[mask]], axis=1)
    if pts.size == 0:
        pts = np.zeros((1, 3), dtype=float)

    poly = pv.PolyData(pts)
    poly["density"] = values[mask] if values[mask].size > 0 else np.array([iso])
    return poly


def _mesh_surface_to_polydata(surface: MeshSurface) -> pv.PolyData:
    """Convert a MeshSurface into PyVista PolyData."""

    vertices = np.asarray(surface.vertices, dtype=float)
    faces = np.asarray(surface.faces, dtype=int)

    if faces.size == 0:
        return pv.PolyData(vertices)

    # PyVista expects a flat array of [3, i, j, k, 3, ...]
    n_faces = faces.shape[0]
    flat_faces = np.hstack(
        [np.full((n_faces, 1), 3, dtype=int), faces],
    ).ravel()

    poly = pv.PolyData(vertices, flat_faces)
    if surface.vertex_scalars is not None:
        scalars = np.asarray(surface.vertex_scalars, dtype=float)
        if scalars.shape[0] == vertices.shape[0]:
            poly["phase"] = scalars
    return poly


def render_isosurface(
    grid_or_mesh: DensityGrid | MeshSurface,
    *,
    isovalue: float | None = None,
    show: bool = True,
    jupyter_backend: str | None = "panel",
) -> pv.Plotter:
    """Render a single isosurface from a DensityGrid or MeshSurface.

    Returns the Plotter so callers can further customise or embed it in Jupyter.
    """

    _ensure_jupyter_backend(jupyter_backend)
    plotter = pv.Plotter()

    if isinstance(grid_or_mesh, DensityGrid):
        contour = _grid_to_mock_polydata(grid_or_mesh)
        plotter.add_mesh(
            contour,
            cmap="viridis",
            opacity=0.8,
            lighting=True,
        )
    else:
        poly = _mesh_surface_to_polydata(grid_or_mesh)
        scalars = "phase" if "phase" in poly.point_data else None
        plotter.add_mesh(
            poly,
            scalars=scalars,
            cmap="coolwarm" if scalars else None,
            opacity=0.85,
            lighting=True,
        )

    plotter.set_background("black")

    if show:
        plotter.show()
    return plotter


def render_trajectories(
    trajectories: Iterable[MockTrajectory],
    *,
    show: bool = True,
    jupyter_backend: str | None = "panel",
) -> pv.Plotter:
    """Render a list of mock trajectories as 3D line objects."""

    _ensure_jupyter_backend(jupyter_backend)
    plotter = pv.Plotter()
    for traj in trajectories:
        if traj.points.size == 0:
            continue
        spline = pv.Spline(traj.points, n_points=len(traj.points) * 5)
        plotter.add_mesh(
            spline,
            color="cyan",
            line_width=2.0,
            opacity=0.9,
        )
    plotter.set_background("black")
    if show:
        plotter.show()
    return plotter


def _mock_spiral_trajectories(count: int = 8) -> list[MockTrajectory]:
    """Generate simple spiral-like trajectories around the origin."""

    trajectories: list[MockTrajectory] = []
    thetas = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    for theta0 in thetas:
        t = np.linspace(0.0, 6.0 * np.pi, 80)
        r = 0.3 + 0.02 * t
        x = r * np.cos(t + theta0)
        y = r * np.sin(t + theta0)
        z = 0.05 * t - 0.5
        points = np.stack([x, y, z], axis=1)
        trajectories.append(MockTrajectory(points=points))
    return trajectories


def _add_atoms_from_bundle(bundle: VisualizationBundle, plotter: pv.Plotter) -> None:
    """Add simple atom glyphs for the molecule in a bundle."""

    for atom in bundle.molecule.atoms:
        center = np.asarray(atom.position, dtype=float)
        radius = 0.3
        sphere = pv.Sphere(radius=radius, center=center)
        plotter.add_mesh(
            sphere,
            color="white",
            specular=0.2,
            smooth_shading=True,
        )


def render_combined(
    bundle: VisualizationBundle,
    *,
    show: bool = True,
    jupyter_backend: str | None = "panel",
) -> pv.Plotter:
    """Render density, trajectories, and atoms from a VisualizationBundle."""

    _ensure_jupyter_backend(jupyter_backend)
    plotter = pv.Plotter()

    # Density / isosurface
    if isinstance(bundle.density, DensityGrid):
        contour = _grid_to_mock_polydata(bundle.density)
        plotter.add_mesh(
            contour,
            cmap="viridis",
            opacity=0.8,
            lighting=True,
        )
    else:
        poly = _mesh_surface_to_polydata(bundle.density)
        scalars = "phase" if "phase" in poly.point_data else None
        plotter.add_mesh(
            poly,
            scalars=scalars,
            cmap="coolwarm" if scalars else None,
            opacity=0.85,
            lighting=True,
        )

    # Atoms
    _add_atoms_from_bundle(bundle, plotter)

    # Trajectories (mock for now)
    for traj in _mock_spiral_trajectories():
        spline = pv.Spline(traj.points, n_points=len(traj.points) * 4)
        plotter.add_mesh(
            spline,
            color="cyan",
            line_width=2.0,
            opacity=0.9,
        )

    plotter.set_background("black")

    if show:
        plotter.show()
    return plotter


def show_h2_mock(
    *,
    show: bool = True,
    jupyter_backend: str | None = "panel",
) -> pv.Plotter:
    """Convenience helper: render the mock H₂ bundle in a single call."""

    bundle = h2_mock_bundle()
    return render_combined(bundle, show=show, jupyter_backend=jupyter_backend)


def show_grid_mock(
    *,
    show: bool = True,
    jupyter_backend: str | None = "panel",
) -> pv.Plotter:
    """Convenience helper: render a tiny grid-based mock bundle."""

    bundle = grid_mock_bundle()
    return render_combined(bundle, show=show, jupyter_backend=jupyter_backend)
