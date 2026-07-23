"""Thin Anthropic wrapper (Batch 5). Imported lazily so the template path and the tests
never require the SDK or a network. No key is hardcoded; the SDK resolves it from the env.
"""
from __future__ import annotations

from pydantic import BaseModel

from .. import config

# The LLM EXPLAINS/DRAFTS only; it never decides. These guardrails are restated in-prompt.
_SYSTEM = (
    "You are a data-governance writing assistant for OrthoLineage Guardian. A deterministic "
    "policy engine has already decided that a violation exists and produced a structured "
    "finding. Your ONLY job is to turn that finding into clear governance prose (and, when "
    "asked, a draft dbt patch). Hard rules:\n"
    "- Never change the decision, the check id, the severity, or the namespace.\n"
    "- Never add or remove findings.\n"
    "- Reference ONLY dataset/column/term names that appear in the finding you are given. "
    "Never invent an entity.\n"
    "- The engine reads DataHub metadata only. NEVER assert observed row data: no row/record/"
    "value counts, and never state that a missingness value was 'found' or 'observed'. The "
    "missingness vocabulary (PRESENT, NOT_DOCUMENTED, NOT_ASSESSED, NOT_APPLICABLE, UNKNOWN) "
    "may be mentioned only as what the contract admits, never as data you saw.\n"
    "- This is data governance, never clinical advice.\n"
    "Return only the requested structured fields."
)


class TruncationError(RuntimeError):
    """Raised when the model hit max_tokens mid-JSON. Distinct from a schema/JSON error so
    the log says 'truncated — raise max_tokens' rather than a misleading validation failure."""


def generate(user_prompt: str, output_model: type[BaseModel], max_tokens: int = 8192) -> dict:
    """Call Claude with structured output; return the parsed object as a plain dict.

    Checks stop_reason FIRST: a refusal or a max_tokens truncation raises a distinct, explicit
    error. Raises on any SDK/parse error so the caller can fall back to template mode.
    """
    import anthropic  # lazy: only when a key is present and the LLM path is taken

    client = anthropic.Anthropic()
    message = client.messages.parse(
        model=config.model_id(),
        max_tokens=max_tokens,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=output_model,
    )
    if message.stop_reason == "refusal":
        raise RuntimeError("LLM refused the request")
    if message.stop_reason == "max_tokens":
        raise TruncationError(
            f"model output truncated — raise max_tokens (was {max_tokens})"
        )
    parsed = message.parsed_output
    if parsed is None:
        raise RuntimeError("LLM returned no parseable structured output")
    return parsed.model_dump()
