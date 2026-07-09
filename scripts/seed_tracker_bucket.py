#!/usr/bin/env python3
"""Upload git-tracked community records to the public tracker S3 bucket."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMUNITY_DIR = REPO_ROOT / "tracker" / "data" / "community"
PREFIX = "community"


def load_records() -> list[dict]:
    records: list[dict] = []
    if not COMMUNITY_DIR.is_dir():
        return records
    for path in sorted(COMMUNITY_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("schema_version"):
            records.append(data)
    return records


def main() -> int:
    bucket = sys.argv[1] if len(sys.argv) > 1 else None
    if not bucket:
        print("Usage: python scripts/seed_tracker_bucket.py <bucket-name>", file=sys.stderr)
        return 1

    records = load_records()
    s3 = boto3.client("s3")

    by_model: dict[str, list] = defaultdict(list)
    for record in records:
        key = f"{PREFIX}/{record['record_id']}.json"
        body = json.dumps(record, indent=2) + "\n"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
            CacheControl="public, max-age=300",
        )
        by_model[record["model"]].append(record)
        print(f"uploaded {key}")

    for model in by_model:
        by_model[model].sort(key=lambda r: r.get("timestamp", ""))

    index = {
        "schema_version": 1,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "by_model": dict(by_model),
        "record_count": len(records),
    }
    index_body = json.dumps(index, indent=2) + "\n"
    s3.put_object(
        Bucket=bucket,
        Key=f"{PREFIX}/index.json",
        Body=index_body.encode("utf-8"),
        ContentType="application/json",
        CacheControl="public, max-age=120",
    )
    print(f"uploaded {PREFIX}/index.json ({len(records)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
