"""Smoke tests for the PyVista renderer skeleton (issue #16).

These tests avoid opening interactive windows by always using show=False.
"""

from __future__ import annotations

from typing import Iterable

import pyvista as pv

from qorbital.viz.fixtures import grid_mock_bundle, h2_mock_bundle
from qorbital.viz.pyvista_renderer import (
    MockTrajectory,
    render_combined,
    render_isosurface,
    render_trajectories,
)
from qorbital.viz.schema import DensityGrid, MeshSurface


def _count_actors(plotter: pv.Plotter) -> int:
    """Return number of actors in the plotter."""

    return len(list(plotter.renderer.actors.values()))


def _mock_trajectories() -> Iterable[MockTrajectory]:
    import numpy as np

    points = np.array(
        [
            [-0.5, 0.0, 0.0],
            [0.0, 0.5, 0.0],
            [0.5, 0.0, 0.0],
        ],
        dtype=float,
    )
    return [MockTrajectory(points=points)]


def test_render_isosurface_from_mesh_returns_plotter() -> None:
    bundle = h2_mock_bundle()
    assert isinstance(bundle.density, MeshSurface)
    plotter = render_isosurface(bundle.density, show=False, jupyter_backend=None)
    assert isinstance(plotter, pv.Plotter)
    assert _count_actors(plotter) >= 1


def test_render_isosurface_from_grid_returns_plotter() -> None:
    bundle = grid_mock_bundle()
    assert isinstance(bundle.density, DensityGrid)
    plotter = render_isosurface(bundle.density, show=False, jupyter_backend=None)
    assert isinstance(plotter, pv.Plotter)
    assert _count_actors(plotter) >= 1


def test_render_trajectories_returns_plotter() -> None:
    plotter = render_trajectories(
        _mock_trajectories(),
        show=False,
        jupyter_backend=None,
    )
    assert isinstance(plotter, pv.Plotter)
    assert _count_actors(plotter) >= 1


def test_render_combined_from_mesh_bundle() -> None:
    bundle = h2_mock_bundle()
    plotter = render_combined(bundle, show=False, jupyter_backend=None)
    assert isinstance(plotter, pv.Plotter)
    # Surface + atoms + trajectories should produce multiple actors.
    assert _count_actors(plotter) >= 3


def test_render_combined_from_grid_bundle() -> None:
    bundle = grid_mock_bundle()
    plotter = render_combined(bundle, show=False, jupyter_backend=None)
    assert isinstance(plotter, pv.Plotter)
    assert _count_actors(plotter) >= 3

