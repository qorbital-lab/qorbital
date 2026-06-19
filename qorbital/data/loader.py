"""Load persisted VQE run logs from disk."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def load_runs(
    molecule: str,
    filter_fn: Callable[[dict[str, Any]], bool] | None = None,
    runs_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Load run logs from ``data/runs/<molecule>/``.

    Parameters
    ----------
    molecule
        Registry name (e.g. ``"H2"``, ``"LiH"``).
    filter_fn
        Optional predicate applied to each log dict before inclusion.
    runs_dir
        Override the base runs directory (default ``data/runs``).

    Returns
    -------
    list[dict]
        Parsed run log JSON objects, sorted by timestamp.
    """
    if runs_dir is None:
        runs_dir = Path("data/runs")
    mol_dir = runs_dir / molecule.lower()
    if not mol_dir.exists():
        return []

    logs: list[dict[str, Any]] = []
    for path in sorted(mol_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if filter_fn is None or filter_fn(data):
            logs.append(data)

    logs.sort(key=lambda d: d.get("timestamp", ""))
    return logs
