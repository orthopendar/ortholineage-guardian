"""LLM explanation of a deterministic finding (Batch 5) — EXPLAIN ONLY.

Input is the Finding only (never the SQL or the manifest). A template baseline is always
produced; when the LLM path is enabled the model's prose is validated through the schema
guard, and any rejection falls back to the template — recorded, never silently dropped.
"""
from __future__ import annotations

import logging

from .. import config
from ..models import Finding
from . import templates
from .schema_guard import FindingExplanation, GuardRejection, validate_explanation

log = logging.getLogger("ortholineage_guardian.llm.explain")


def _prompt(finding: Finding) -> str:
    return (
        "Explain this governance finding for a data steward. Produce the FindingExplanation "
        "fields (check, namespace, title, what_broke, why_it_matters, downstream_impact, "
        "remediation_summary, affected_entities). Keep `check` and `namespace` exactly as "
        "given. `affected_entities` must be dataset/column names taken from the finding.\n\n"
        f"Finding JSON:\n{finding.model_dump_json(indent=2)}"
    )


def explain(finding: Finding, use_llm: bool = True) -> tuple[FindingExplanation, str]:
    """Return (explanation, mode) where mode is 'llm' or 'template'."""
    template = templates.explanation(finding)
    if not config.llm_enabled(use_llm):
        return template, "template"

    from . import _client  # lazy import of the SDK wrapper
    try:
        raw = _client.generate(_prompt(finding), FindingExplanation)
        validated = validate_explanation(raw, finding)
        return validated, "llm"
    except (GuardRejection, Exception) as exc:  # noqa: BLE001 - any failure -> safe fallback
        log.warning("LLM explanation rejected/failed (%s); falling back to template", exc)
        return template, "template"
