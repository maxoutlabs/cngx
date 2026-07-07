#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
pip install -q -e .
vhs scripts/demo/quickstart.tape
ls -lh docs/assets/quickstart.gif
