"""Benchmark test isolation."""

import pytest


@pytest.fixture(autouse=True)
def _reset_streaming_registry():
    yield
    try:
        from cogscope.drift.streaming import get_streaming_registry

        get_streaming_registry().reset()
    except Exception:
        pass
