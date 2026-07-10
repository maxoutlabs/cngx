"""Stdio helpers for CLI reliability across platforms."""

from __future__ import annotations

import sys


def configure_cli_stdio() -> None:
    """Prefer UTF-8 on Windows so Rich tables with arrows do not crash cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
