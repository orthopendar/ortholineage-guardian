"""Render the migration-impact report (Batch 6). Deterministic markdown — no timestamps."""
from __future__ import annotations

from ..models import Finding, ImpactNode

_RULE_LABEL = {
    "export_governance": "export governance",
    "completeness": "completeness",
    "readiness": "readiness",
    "temporal_integrity": "temporal integrity / migration drift",
}


def _evidence_block(f: Finding) -> list[str]:
    e = f.evidence
    lines = [f"### {f.check}  ({_RULE_LABEL.get(f.rule_class, f.rule_class)})", "", f.summary, ""]
    if e.identifier_column:
        lines.append(f"- identifier column: `{e.identifier_column}`")
        lines.append(f"- export dataset: `{e.export_dataset}`  {e.export_properties}")
    if e.source_column:
        lines.append(f"- source column: `{e.source_column}`  (paired: `{e.paired_column}`)")
        lines.append(f"- collapsed in: `{e.collapsed_in_dataset}`  (source: `{e.source_dataset}`)")
    if e.feature_column:
        lines.append(f"- feature column: `{e.feature_column}`")
        lines.append(f"- unvalidated source: `{e.unvalidated_source}` (validation_status={e.validation_status})")
    if e.path:
        lines.append(f"- lineage path: {' -> '.join(f'`{s}`' for s in e.path)}")
    lines.append(f"- signals read (metadata only): {', '.join(e.signals_read)}")
    lines.append("")
    return lines


def render_report(
    findings: list[Finding], impact: list[ImpactNode], stale_reference: ImpactNode | None,
    namespace: str,
) -> str:
    out = [
        "# Migration impact report",
        "",
        "**Change:** the encounter timestamp `arrival_time` was renamed to "
        "`ed_arrival_datetime` in `trauma_registry`.",
        "",
        f"**Namespace analysed:** `{namespace}`  ·  **deterministic findings:** {len(findings)}",
        "",
        "This report is produced by the governance agent from DataHub metadata alone "
        "(lineage, schema aspects, glossary terms, structured properties) — never by reading "
        "the dbt SQL.",
        "",
        "## Affected downstream datasets / columns",
        "",
        "Reached by column-level lineage traversal from the renamed field:",
        "",
    ]
    for n in impact:
        out.append(f"- `{n.dataset}.{n.column}` — {n.note}")
    out += ["", "## Governance findings", ""]
    for f in findings:
        out += _evidence_block(f)
    out += ["## Migration-drift observation (reported alongside, not a check)", ""]
    if stale_reference is not None:
        out.append(f"- {stale_reference.note}")
    else:
        out.append("- none")
    out += [
        "",
        "## Proposed remediation",
        "",
        "See `examples/remediation/remediation.patch` — a `git apply`-able dbt patch that "
        "drops the direct identifier from the export, restores the paired missingness state "
        "column, repoints the ML feature to the validated registry, and renames the stale "
        "`arrival_time` reference to `ed_arrival_datetime`.",
        "",
    ]
    return "\n".join(out)
