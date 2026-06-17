#!/usr/bin/env python3
"""Prepare a static site directory for GitHub Pages deployment."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "qorbital" / "viz" / "web"
BUNDLES_ROOT = REPO_ROOT / "data" / "bundles"
DEFAULT_OUT = REPO_ROOT / "_site"


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        msg = f"Source path not found: {src}"
        raise FileNotFoundError(msg)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def prepare_site(out_dir: Path) -> Path:
    """Build the Pages artifact under *out_dir*."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    _copy_tree(WEB_ROOT, out_dir)

    for molecule_dir in sorted(BUNDLES_ROOT.iterdir()) if BUNDLES_ROOT.exists() else []:
        if not molecule_dir.is_dir():
            continue
        target = out_dir / "bundles" / molecule_dir.name
        _copy_tree(molecule_dir, target)

    (out_dir / ".nojekyll").touch()
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare GitHub Pages site artifact")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    out = prepare_site(args.out.resolve())
    print(f"Prepared GitHub Pages site at {out}")


if __name__ == "__main__":
    main()
