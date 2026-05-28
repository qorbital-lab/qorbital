#!/usr/bin/env python3
"""Serve the qOrbital web viewer from the repository root."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "qorbital" / "viz" / "web"


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the qOrbital web viewer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not WEB_ROOT.is_dir():
        msg = f"viewer directory not found: {WEB_ROOT}"
        raise SystemExit(msg)

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(WEB_ROOT),
    )
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        url = f"http://{args.host}:{args.port}/"
        print(f"Serving qOrbital viewer at {url}")
        print(f"Directory: {WEB_ROOT}")
        print("Press Ctrl+C to stop.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
