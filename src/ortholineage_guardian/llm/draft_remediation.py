"""LLM remediation drafting (Batch 5) — DRAFT ONLY.

Findings + impact -> a RemediationDraft (dbt patch hunks + impact-report prose). Rendering to
files and any write-back are Batch 6. A template baseline is always produced; the LLM path is
validated through the schema guard and falls back to the template on rejection.
"""
from __future__ import annotations

import logging

from .. import config
from ..models import Finding, ImpactNode
from . import templates
from .schema_guard import GuardRejection, RemediationDraft, validate_remediation

log = logging.getLogger("ortholineage_guardian.llm.draft_remediation")


def _prompt(findings: list[Finding], impact: list[ImpactNode], stale: ImpactNode | None) -> str:
    findings_json = "[\n" + ",\n".join(f.model_dump_json(indent=2) for f in findings) + "\n]"
    impact_json = "[\n" + ",\n".join(n.model_dump_json() for n in impact) + "\n]"
    stale_json = stale.model_dump_json() if stale else "null"
    return (
        "Draft a remediation for these governance findings. Produce the RemediationDraft "
        "fields (namespace, summary, findings_covered, patch_hunks, impact_report_markdown). "
        "`findings_covered` must be exactly the finding check ids. Each patch hunk targets one "
        "dbt model named in the findings/impact and shows a before/after. Fix: drop the direct "
        "identifier from the export; restore the paired missingness state column; repoint the "
        "ML feature to the validated registry; rename the stale arrival_time to "
        "ed_arrival_datetime. Reference only entities present below.\n\n"
        f"Findings:\n{findings_json}\n\nImpact nodes:\n{impact_json}\n\nStale reference:\n{stale_json}"
    )


def draft(
    findings: list[Finding],
    impact: list[ImpactNode],
    stale_reference: ImpactNode | None,
    namespace: str,
    use_llm: bool = True,
) -> tuple[RemediationDraft, str]:
    """Return (remediation_draft, mode) where mode is 'llm' or 'template'."""
    template = templates.remediation(findings, impact, stale_reference, namespace)
    if not config.llm_enabled(use_llm):
        return template, "template"

    from . import _client
    try:
        raw = _client.generate(_prompt(findings, impact, stale_reference), RemediationDraft)
        validated = validate_remediation(raw, findings)
        return validated, "llm"
    except (GuardRejection, Exception) as exc:  # noqa: BLE001 - any failure -> safe fallback
        log.warning("LLM remediation rejected/failed (%s); falling back to template", exc)
        return template, "template"
