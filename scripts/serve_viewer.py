#!/usr/bin/env python3
"""Serve the qOrbital web viewer with bundles and PES data."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "qorbital" / "viz" / "web"
BUNDLES_ROOT = REPO_ROOT / "data" / "bundles"
PES_ROOT = REPO_ROOT / "data" / "pes"
RUNS_ROOT = REPO_ROOT / "data" / "runs"
SITE_ROOT = REPO_ROOT / "_site"


class ViewerRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve web assets plus /bundles/, /pes/, and /runs/ from data/."""

    def __init__(
        self,
        *args,
        web_root: Path,
        bundles_root: Path,
        pes_root: Path,
        runs_root: Path,
        **kwargs,
    ) -> None:
        self._web_root = web_root
        self._bundles_root = bundles_root
        self._pes_root = pes_root
        self._runs_root = runs_root
        super().__init__(*args, directory=str(web_root), **kwargs)

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/bundles/"):
            rel = clean.removeprefix("/bundles/")
            return str(self._bundles_root / rel)
        if clean.startswith("/pes/"):
            rel = clean.removeprefix("/pes/")
            return str(self._pes_root / rel)
        if clean.startswith("/runs/"):
            rel = clean.removeprefix("/runs/")
            return str(self._runs_root / rel)
        return super().translate_path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the qOrbital web viewer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--site",
        action="store_true",
        help="Serve the prepared _site/ artifact (GitHub Pages layout)",
    )
    args = parser.parse_args()

    if args.site:
        if not SITE_ROOT.is_dir():
            msg = f"{SITE_ROOT} not found. Run: python scripts/prepare_pages_site.py"
            raise SystemExit(msg)
        serve_root = SITE_ROOT
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler,
            directory=str(serve_root),
        )
        print(f"Directory: {serve_root}")
    else:
        if not WEB_ROOT.is_dir():
            msg = f"viewer directory not found: {WEB_ROOT}"
            raise SystemExit(msg)
        if not BUNDLES_ROOT.is_dir():
            msg = f"bundles directory not found: {BUNDLES_ROOT}"
            raise SystemExit(msg)
        if not PES_ROOT.is_dir():
            msg = f"PES directory not found: {PES_ROOT}"
            raise SystemExit(msg)
        if not RUNS_ROOT.is_dir():
            msg = f"runs directory not found: {RUNS_ROOT}"
            raise SystemExit(msg)
        handler = functools.partial(
            ViewerRequestHandler,
            web_root=WEB_ROOT,
            bundles_root=BUNDLES_ROOT,
            pes_root=PES_ROOT,
            runs_root=RUNS_ROOT,
        )
        print(f"Directory: {WEB_ROOT}")
        print(f"Bundles: {BUNDLES_ROOT}")
        print(f"PES: {PES_ROOT}")
        print(f"Runs: {RUNS_ROOT}")

    url = f"http://{args.host}:{args.port}/"
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"Serving qOrbital viewer at {url}")
        print("Press Ctrl+C to stop.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
