"""Clinical metadata emitter — promotes governance meta keys into MCP-readable DataHub signals.

`contract` is pure data (safe to import anywhere, including the read-only policy engine).
`emit_all` needs the DataHub SDK, so it is imported lazily to keep the engine's import
graph free of the write-side dependency.
"""
from . import contract

__all__ = ["contract", "emit_all"]


def emit_all(*args, **kwargs):
    from .emit import emit_all as _emit_all

    return _emit_all(*args, **kwargs)
