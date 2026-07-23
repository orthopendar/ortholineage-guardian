"""Controlled write-back into DataHub (Batch 6) — application code, never LLM-driven.

`contract` is pure data (markers, URNs, deterministic text) — safe to import anywhere,
including the MCP-only read-back verifier. `plan` / `apply` / `reset` need the DataHub SDK,
so they are imported lazily to keep the read path free of the write-side dependency.
"""
from . import contract
from .contract import plan  # pure — no DataHub SDK needed

__all__ = ["contract", "plan", "apply", "reset"]


def apply(*args, **kwargs):
    from .datahub_sdk import apply as _apply

    return _apply(*args, **kwargs)


def reset(*args, **kwargs):
    from .datahub_sdk import reset as _reset

    return _reset(*args, **kwargs)
