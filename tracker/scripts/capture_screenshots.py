#!/usr/bin/env python3
"""Capture tracker site screenshots for visual verification (Prompt 14)."""

from __future__ import annotations

import http.server
import socket
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
OUT_DIR = Path(__file__).resolve().parent.parent / "screenshots"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    port = _free_port()

    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(
        target=httpd.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
    )
    thread.start()

    import os

    os.chdir(SITE_DIR)
    url = f"http://127.0.0.1:{port}/index.html"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, width, height in (
            ("desktop", 1280, 900),
            ("mobile", 390, 844),
        ):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(800)
            out = OUT_DIR / f"tracker-{name}.png"
            page.screenshot(path=str(out), full_page=True)
            print(f"Wrote {out}")
        browser.close()

    httpd.shutdown()


if __name__ == "__main__":
    main()
