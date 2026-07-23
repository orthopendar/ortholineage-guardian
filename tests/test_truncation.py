"""Truncation surfaces as a distinct TruncationError (Batch 6, Task 0b) — offline, stubbed.

When the model hits max_tokens mid-JSON, the client must raise a clear TruncationError
("truncated — raise max_tokens") rather than a misleading JSON/schema validation error.
"""
from __future__ import annotations

import pytest

from ortholineage_guardian.llm import _client
from ortholineage_guardian.llm.schema_guard import FindingExplanation


class _FakeMessage:
    def __init__(self, stop_reason: str):
        self.stop_reason = stop_reason
        self.parsed_output = None


class _FakeMessages:
    def __init__(self, stop_reason: str):
        self._stop = stop_reason

    def parse(self, **_kwargs):
        return _FakeMessage(self._stop)


class _FakeClient:
    def __init__(self, stop_reason: str):
        self.messages = _FakeMessages(stop_reason)


def test_max_tokens_raises_truncation_error(monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda: _FakeClient("max_tokens"))
    with pytest.raises(_client.TruncationError, match="truncated"):
        _client.generate("prompt", FindingExplanation, max_tokens=16)


def test_refusal_raises_runtime_error(monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda: _FakeClient("refusal"))
    with pytest.raises(RuntimeError, match="refused"):
        _client.generate("prompt", FindingExplanation)
