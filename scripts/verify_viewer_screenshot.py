#!/usr/bin/env python3
"""Capture a screenshot of the qOrbital viewer for visual verification."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "qorbital" / "viz" / "web" / "fixtures" / "_verify_cloud.png"


def _ensure_playwright() -> None:
    try:
        import playwright  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "playwright"],
        )
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
        )


def capture(url: str, output: Path, wait_ms: int) -> None:
    _ensure_playwright()
    from playwright.sync_api import sync_playwright

    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(wait_ms)

        overlay = page.locator("#overlay")
        if overlay.is_visible():
            text = overlay.inner_text().strip()
            if text:
                browser.close()
                msg = f"Viewer overlay still visible: {text!r}"
                raise RuntimeError(msg)

        canvas = page.locator("#viewer-canvas")
        if canvas.count() == 0:
            browser.close()
            raise RuntimeError("Missing #viewer-canvas")

        page.screenshot(path=str(output), full_page=False)
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Screenshot the qOrbital viewer.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--wait-ms", type=int, default=1500)
    args = parser.parse_args()

    capture(args.url, args.output, args.wait_ms)
    print(f"Saved screenshot: {args.output}")


if __name__ == "__main__":
    main()
