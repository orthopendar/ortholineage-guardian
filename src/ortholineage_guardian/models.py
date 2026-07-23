"""Typed models for the governance policy engine (Batch 4).

Deterministic findings only — no LLM explanation/remediation prose (that is Batch 5's
`RemediationDraft`, deliberately omitted here).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# The three deterministic checks + the migration-drift observation.
CHECK_PHI_EXPORT_PATH = "PHI_EXPORT_PATH"
CHECK_MISSINGNESS_COLLAPSE = "MISSINGNESS_COLLAPSE"
CHECK_UNVALIDATED_ML_SOURCE = "UNVALIDATED_ML_SOURCE"
OBSERVATION_STALE_REFERENCE = "STALE_REFERENCE"

# Governance rule taxonomy the checks instantiate (plan §4 texture).
RULE_CLASS = {
    CHECK_PHI_EXPORT_PATH: "export_governance",
    CHECK_MISSINGNESS_COLLAPSE: "completeness",
    CHECK_UNVALIDATED_ML_SOURCE: "readiness",
    OBSERVATION_STALE_REFERENCE: "temporal_integrity",
}


class Evidence(BaseModel):
    """Metadata-derived evidence for a finding. Every field comes from an MCP signal —
    never from SQL, the dbt manifest, or a DuckDB database."""

    # PHI_EXPORT_PATH
    identifier_column: str | None = None          # e.g. research_export.patient_id
    export_dataset: str | None = None             # e.g. research_export
    export_properties: dict[str, str] = Field(default_factory=dict)

    # MISSINGNESS_COLLAPSE
    source_column: str | None = None              # e.g. stg_ed_documentation.gcs_total
    paired_column: str | None = None              # e.g. gcs_total_missingness
    source_dataset: str | None = None             # upstream dataset that still has the pair
    collapsed_in_dataset: str | None = None       # downstream dataset missing the pair

    # UNVALIDATED_ML_SOURCE
    feature_column: str | None = None             # e.g. ml_feature_table.raw_mode_of_arrival_feature
    unvalidated_source: str | None = None         # e.g. stg_ed_documentation
    validation_status: str | None = None

    # shared: the column-level lineage path (dataset.field steps), from MCP lineage
    path: list[str] = Field(default_factory=list)
    signals_read: list[str] = Field(default_factory=list)  # which MCP signals grounded this


class Finding(BaseModel):
    check: str
    namespace: str
    rule_class: str
    severity: str = "high"
    summary: str
    evidence: Evidence


class ImpactNode(BaseModel):
    """A downstream dataset/column reached by the impact traversal from a changed field."""

    dataset: str
    column: str
    hops: int | None = None
    note: str | None = None


class CheckResult(BaseModel):
    """Per-check output: the findings it produced (empty when clean)."""

    check: str
    namespace: str
    findings: list[Finding] = Field(default_factory=list)

    @property
    def fired(self) -> bool:
        return len(self.findings) > 0
