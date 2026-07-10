"""Claude adapter request shaping."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_claude_request_sends_temperature_not_both() -> None:
    with patch.dict("sys.modules", {"anthropic": MagicMock()}):
        from cngx.capture.adapters.claude import ClaudeAdapter

        adapter = ClaudeAdapter(model="claude-haiku-4-5-20251001", api_key="sk-test")
        kwargs = adapter._build_request_kwargs(
            messages=[{"role": "user", "content": "hi"}],
            system_message=None,
            tools=None,
        )
        assert "temperature" in kwargs
        assert "top_p" not in kwargs


def test_claude_request_top_p_only_when_temperature_none() -> None:
    with patch.dict("sys.modules", {"anthropic": MagicMock()}):
        from cngx.capture.adapters.claude import ClaudeAdapter

        adapter = ClaudeAdapter(model="claude-haiku-4-5-20251001", api_key="sk-test")
        adapter.config.temperature = None  # type: ignore[assignment]
        adapter.config.top_p = 0.9
        kwargs = adapter._build_request_kwargs(
            messages=[{"role": "user", "content": "hi"}],
            system_message=None,
            tools=None,
        )
        assert "temperature" not in kwargs
        assert kwargs.get("top_p") == 0.9
