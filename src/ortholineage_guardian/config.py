"""Runtime configuration for the LLM layer (Batch 5).

The LLM only improves prose quality; it is NEVER required for correctness. Everything works
with no API key present (deterministic template mode). No key is ever hardcoded or logged.
"""
from __future__ import annotations

import os

# Pinned Claude model id. Overridable via env; documented in .env.example / README.
DEFAULT_MODEL = "claude-opus-4-8"


def model_id() -> str:
    return os.environ.get("GUARDIAN_MODEL", DEFAULT_MODEL)


def has_api_key() -> bool:
    """True only if an Anthropic credential is present in the environment.

    We check the standard env vars the SDK resolves; if none is set we stay in template
    mode rather than prompting for a key. (An `ant auth login` profile would also work,
    but for this governance service we gate on an explicit env credential.)
    """
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def llm_enabled(requested: bool = True) -> bool:
    """Whether to attempt the LLM path: caller opted in AND a key is present."""
    return requested and has_api_key()
