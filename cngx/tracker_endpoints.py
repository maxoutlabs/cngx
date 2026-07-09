"""Public tracker API endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path

_ENDPOINTS_FILE = Path(__file__).resolve().parents[1] / "tracker" / "public_endpoints.json"


def _load_file_endpoints() -> dict[str, str]:
    if not _ENDPOINTS_FILE.is_file():
        return {}
    with open(_ENDPOINTS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def submit_url() -> str:
    return os.environ.get(
        "CNGX_SUBMIT_URL",
        _load_file_endpoints().get(
            "submit_url",
            "https://d2m4128rn1m95q.cloudfront.net/submit",
        ),
    )


def tracker_index_url() -> str:
    return os.environ.get(
        "CNGX_TRACKER_INDEX_URL",
        _load_file_endpoints().get(
            "tracker_index_url",
            "https://cngx-tracker-239143557891-us-east-1.s3.us-east-1.amazonaws.com/community/index.json",
        ),
    )
