"""The tiered write-back contract (Batch 6) — what the guardian writes per finding.

Frozen in docs/BATCH2_CAPABILITY_MATRIX.md:
  * Required tier: a governance-finding TAG + an editable DESCRIPTION (finding + remediation
    summary) on each affected dataset.
  * Preferred tier: a DataHub INCIDENT per finding.

All content is derived deterministically from VALIDATED findings + the guard-clean template
explanation — never raw LLM text. A fixed audit timestamp keeps writes idempotent.
"""
from __future__ import annotations

from ..emitter import contract as C
from ..llm import templates
from ..models import (
    CHECK_MISSINGNESS_COLLAPSE,
    CHECK_PHI_EXPORT_PATH,
    CHECK_UNVALIDATED_ML_SOURCE,
    Finding,
)

# markers so reset can find/remove exactly what the guardian wrote (and nothing else)
GUARDIAN_TAG_PREFIX = "urn:li:tag:guardian_finding_"
GUARDIAN_DESC_MARKER = "[OrthoLineage Guardian]"
GUARDIAN_INCIDENT_PREFIX = "urn:li:incident:guardian-"

FIXED_AUDIT_TIME_MS = 1704067200000  # 2024-01-01 — fixed so incident writes are idempotent
SYSTEM_ACTOR = "urn:li:corpuser:datahub"

# every check the guardian can emit — reset sweeps all of these regardless of live findings
ALL_CHECKS = [CHECK_PHI_EXPORT_PATH, CHECK_MISSINGNESS_COLLAPSE, CHECK_UNVALIDATED_ML_SOURCE]


def affected_model(finding: Finding) -> str:
    """The single dataset the finding's write-back lands on (short model name)."""
    e = finding.evidence
    if finding.check == CHECK_PHI_EXPORT_PATH:
        return e.export_dataset or "research_export"
    if finding.check == CHECK_MISSINGNESS_COLLAPSE:
        return e.collapsed_in_dataset or "trauma_registry"
    if finding.check == CHECK_UNVALIDATED_ML_SOURCE:
        return (e.feature_column or "ml_feature_table.x").split(".")[0]
    raise ValueError(f"no affected model mapping for {finding.check}")


def dataset_urn(finding: Finding, ns: C.Namespace) -> str:
    return C.dataset_urn(affected_model(finding), ns)


def governance_tag(finding: Finding) -> str:
    return f"{GUARDIAN_TAG_PREFIX}{finding.check.lower()}"


def description_text(finding: Finding) -> str:
    """Editable-description block: finding + guard-clean remediation summary."""
    remediation = templates.explanation(finding).remediation_summary  # guard-clean
    return (
        f"{GUARDIAN_DESC_MARKER} Governance finding {finding.check} "
        f"[{finding.rule_class}]: {finding.summary} "
        f"Proposed remediation: {remediation}"
    )


def incident_urn(finding: Finding, ns: C.Namespace) -> str:
    return f"{GUARDIAN_INCIDENT_PREFIX}{ns.name}-{finding.check}"


def all_incident_urns(ns: C.Namespace) -> list[str]:
    return [f"{GUARDIAN_INCIDENT_PREFIX}{ns.name}-{check}" for check in ALL_CHECKS]


def plan(findings: list[Finding], ns: C.Namespace) -> list[dict]:
    """What apply() WOULD write, per finding — pure, no graph access, nothing emitted.

    Lives here (not datahub_sdk) so the dry-run plan can be computed and tested without the
    DataHub SDK installed."""
    return [
        {
            "check": f.check,
            "dataset": dataset_urn(f, ns),
            "tag": governance_tag(f),
            "description": description_text(f),
            "incident": incident_urn(f, ns),
        }
        for f in findings
    ]
