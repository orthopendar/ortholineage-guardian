"""Deterministic template renderers (Batch 5) — the required --no-llm fallback.

These build the SAME validated Pydantic objects the LLM path returns, using ONLY the
deterministic Finding fields (never row data). `guardian` must produce a complete, useful
artifact with NO API key present — judges may have none. The LLM only improves prose; it is
never required for correctness.

Prose here is written to satisfy the schema guard: it names only whitelisted entities and
cites the missingness vocabulary strictly as contract knowledge (what the contract admits),
never as observed rows.
"""
from __future__ import annotations

from ..models import (
    CHECK_MISSINGNESS_COLLAPSE,
    CHECK_PHI_EXPORT_PATH,
    CHECK_UNVALIDATED_ML_SOURCE,
    Finding,
    ImpactNode,
)
from .schema_guard import FindingExplanation, PatchHunk, RemediationDraft

# fixture id per check, for the remediation hunks
_FIXTURE = {
    CHECK_PHI_EXPORT_PATH: "PHI_EXPORT_PATH",
    CHECK_MISSINGNESS_COLLAPSE: "MISSINGNESS_COLLAPSE",
    CHECK_UNVALIDATED_ML_SOURCE: "UNVALIDATED_ML_SOURCE",
}


def _entities(finding: Finding) -> list[str]:
    e = finding.evidence
    vals = [
        e.identifier_column, e.export_dataset, e.source_column, e.paired_column,
        e.source_dataset, e.collapsed_in_dataset, e.feature_column, e.unvalidated_source,
    ]
    return sorted({v for v in vals if v})


def _path(finding: Finding) -> str:
    return " -> ".join(finding.evidence.path) if finding.evidence.path else "(direct)"


def explanation(finding: Finding) -> FindingExplanation:
    e = finding.evidence
    check = finding.check

    if check == CHECK_PHI_EXPORT_PATH:
        title = "Direct identifier reaches a research export"
        what = (
            f"The column {e.identifier_column} carries the DirectIdentifier class, and its "
            f"column-level lineage reaches {e.export_dataset}, a dataset whose "
            f"guardian_data_product property is research_export. Lineage path: {_path(finding)}."
        )
        why = (
            "A de-identified research export must never carry a direct identifier: the "
            "export's deidentification_required contract forbids it. This is an "
            "export-governance violation, not a clinical judgement."
        )
        downstream = (
            f"Any consumer of {e.export_dataset} inherits the identifier, so the "
            "de-identification guarantee is broken for everything downstream of the export."
        )
        summary = f"Drop {e.identifier_column} from {e.export_dataset}."

    elif check == CHECK_MISSINGNESS_COLLAPSE:
        title = "Explicit-missingness contract collapsed downstream"
        what = (
            f"The value column {e.source_column} carries the ExplicitMissingness class and is "
            f"paired in {e.source_dataset} with the state column {e.paired_column}. Downstream, "
            f"{e.collapsed_in_dataset} keeps the value column but drops the paired state column."
        )
        why = (
            "An explicit-missingness contract distinguishes governed reasons such as "
            "NOT_DOCUMENTED and NOT_ASSESSED from a bare SQL NULL; the contract admits those "
            "as dispositioned states while a null on an expected field is the blocking state. "
            "Dropping the paired state column erases that distinction, which is a completeness "
            "violation."
        )
        downstream = (
            f"Consumers reading {e.source_column} from {e.collapsed_in_dataset} can no longer "
            "tell a governed absence from a bare null."
        )
        summary = (
            f"Restore the paired {e.paired_column} column alongside {e.source_column} in "
            f"{e.collapsed_in_dataset}."
        )

    elif check == CHECK_UNVALIDATED_ML_SOURCE:
        title = "ML feature sourced from an unvalidated dataset"
        what = (
            f"The feature {e.feature_column} draws directly from {e.unvalidated_source}, whose "
            "guardian_validation_status property is unvalidated, bypassing the validated "
            "registry that should mediate it."
        )
        why = (
            "A feature grounded in an unvalidated source inherits its readiness gap: the "
            "governed registry exists precisely so ML consumers read validated data. This is a "
            "readiness violation."
        )
        downstream = (
            f"Every model trained on {e.feature_column} inherits the unvalidated provenance of "
            f"{e.unvalidated_source}."
        )
        summary = f"Repoint {e.feature_column} to derive from the validated registry."

    else:  # pragma: no cover - defensive; engine only emits the three checks
        title = "Governance finding"
        what = finding.summary
        why = "See the metadata contract for the governance rule this instantiates."
        downstream = "See the impact traversal."
        summary = "Review the finding."

    return FindingExplanation(
        check=check,
        namespace=finding.namespace,
        title=title,
        what_broke=what,
        why_it_matters=why,
        downstream_impact=downstream,
        remediation_summary=summary,
        affected_entities=_entities(finding),
    )


# ------------------------------------------------------------------------- remediation draft
def _hunk_for(finding: Finding) -> PatchHunk:
    e = finding.evidence
    check = finding.check
    if check == CHECK_PHI_EXPORT_PATH:
        return PatchHunk(
            model=e.export_dataset or "research_export",
            fixture=_FIXTURE[check],
            description=f"Remove the direct identifier {e.identifier_column} from the export select list.",
            before="select\n    registry_case_id,\n    patient_id,   -- direct identifier retained\n    ed_arrival_datetime,\n    ...",
            after="select\n    registry_case_id,\n    ed_arrival_datetime,\n    ...",
        )
    if check == CHECK_MISSINGNESS_COLLAPSE:
        return PatchHunk(
            model=e.collapsed_in_dataset or "trauma_registry",
            fixture=_FIXTURE[check],
            description=f"Carry the paired {e.paired_column} state column through instead of dropping it.",
            before="case when gcs_total_missingness in (...) then null else gcs_total end as gcs_total,\n-- gcs_total_missingness not selected",
            after="gcs_total,\ngcs_total_missingness,",
        )
    if check == CHECK_UNVALIDATED_ML_SOURCE:
        return PatchHunk(
            model="ml_feature_table",
            fixture=_FIXTURE[check],
            description=f"Derive {e.feature_column} from the validated registry rather than the raw source.",
            before="..., raw_mode_of_arrival_feature\n-- left join stg_ed_documentation (unvalidated) as the feature source",
            after="-- feature dropped, or re-derived via trauma_registry",
        )
    raise ValueError(f"no hunk template for {check}")  # pragma: no cover


def _stale_hunk(node: ImpactNode) -> PatchHunk:
    return PatchHunk(
        model=node.dataset,
        fixture="STALE_REFERENCE",
        description="Use the post-rename ed_arrival_datetime name instead of the stale arrival_time.",
        before="max(ed_arrival_datetime) as arrival_time",
        after="max(ed_arrival_datetime) as ed_arrival_datetime",
    )


def remediation(
    findings: list[Finding], impact: list[ImpactNode], stale_reference: ImpactNode | None,
    namespace: str,
) -> RemediationDraft:
    hunks = [_hunk_for(f) for f in findings]
    if stale_reference is not None:
        hunks.append(_stale_hunk(stale_reference))

    lines = [
        "# Migration impact report (draft)",
        "",
        "The migration renamed the encounter timestamp arrival_time -> ed_arrival_datetime "
        "in trauma_registry. The faulty state carries the governance findings below.",
        "",
        "## Affected downstream datasets/columns",
    ]
    for n in impact:
        lines.append(f"- {n.dataset}.{n.column} — {n.note}")
    if stale_reference is not None:
        lines.append(f"- {stale_reference.dataset}.{stale_reference.column} — {stale_reference.note}")
    lines += ["", "## Findings", ""]
    for f in findings:
        lines.append(f"- **{f.check}** ({f.rule_class}): {f.summary}")
    lines += ["", "## Proposed remediation", ""]
    for h in hunks:
        lines.append(f"- {h.model} [{h.fixture}]: {h.description}")

    summary = (
        f"Draft remediation for {len(findings)} governance findings plus the stale-reference "
        "observation, in namespace " + namespace + "."
    )
    return RemediationDraft(
        namespace=namespace,
        summary=summary,
        findings_covered=[f.check for f in findings],
        patch_hunks=hunks,
        impact_report_markdown="\n".join(lines),
    )
