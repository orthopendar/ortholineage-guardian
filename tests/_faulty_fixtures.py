"""Deterministic reconstruction of the three faulty findings + impact the Batch-4 engine
produces, so the Batch-5 LLM/template tests and goldens run with no DataHub and no API key.

These mirror the live `engine.run_report("faulty")` output verbatim (verified in the Batch-5
live run). Keeping them here lets the golden and fallback tests stay fully offline.
"""
from __future__ import annotations

from ortholineage_guardian.models import (
    CHECK_MISSINGNESS_COLLAPSE,
    CHECK_PHI_EXPORT_PATH,
    CHECK_UNVALIDATED_ML_SOURCE,
    Evidence,
    Finding,
    ImpactNode,
)


def faulty_findings() -> list[Finding]:
    return [
        Finding(
            check=CHECK_PHI_EXPORT_PATH,
            namespace="faulty",
            rule_class="export_governance",
            summary=(
                "Direct identifier research_export.patient_id is retained in a research "
                "export (must be excluded)."
            ),
            evidence=Evidence(
                identifier_column="research_export.patient_id",
                export_dataset="research_export",
                export_properties={"data_product": "research_export", "deidentification_required": "true"},
                path=[
                    "stg_ed_documentation.patient_id",
                    "trauma_registry.patient_id",
                    "research_export.patient_id",
                ],
                signals_read=[
                    "column term DirectIdentifier",
                    "dataset structuredProperty guardian_data_product",
                    "column-level lineage",
                ],
            ),
        ),
        Finding(
            check=CHECK_MISSINGNESS_COLLAPSE,
            namespace="faulty",
            rule_class="completeness",
            summary=(
                "Explicit-missingness contract on gcs_total collapsed: trauma_registry keeps "
                "gcs_total but dropped the paired gcs_total_missingness carried by "
                "stg_ed_documentation."
            ),
            evidence=Evidence(
                source_column="stg_ed_documentation.gcs_total",
                paired_column="gcs_total_missingness",
                source_dataset="stg_ed_documentation",
                collapsed_in_dataset="trauma_registry",
                path=["stg_ed_documentation.gcs_total", "trauma_registry.gcs_total"],
                signals_read=[
                    "column term ExplicitMissingness",
                    "schema shape (paired column presence/absence)",
                    "column-level lineage",
                ],
            ),
        ),
        Finding(
            check=CHECK_UNVALIDATED_ML_SOURCE,
            namespace="faulty",
            rule_class="readiness",
            summary=(
                "ML feature ml_feature_table.raw_mode_of_arrival_feature is derived directly "
                "from the unvalidated source stg_ed_documentation, bypassing the validated "
                "registry."
            ),
            evidence=Evidence(
                feature_column="ml_feature_table.raw_mode_of_arrival_feature",
                unvalidated_source="stg_ed_documentation",
                validation_status="unvalidated",
                path=["stg_ed_documentation", "ml_feature_table.raw_mode_of_arrival_feature"],
                signals_read=[
                    "dataset structuredProperty guardian_validation_status",
                    "column-level lineage (direct upstream, registry not mediating)",
                ],
            ),
        ),
    ]


def faulty_impact() -> list[ImpactNode]:
    note = "carries the renamed encounter timestamp"
    return [
        ImpactNode(dataset="dashboard_report", column="arrival_time", note=note),
        ImpactNode(dataset="dq_metrics", column="ed_arrival_datetime", note=note),
        ImpactNode(dataset="ml_feature_table", column="ed_arrival_datetime", note=note),
        ImpactNode(dataset="research_export", column="ed_arrival_datetime", note=note),
    ]


def faulty_stale_reference() -> ImpactNode:
    return ImpactNode(
        dataset="dashboard_report",
        column="arrival_time",
        note=(
            "stale reference: dashboard_report.arrival_time persists after trauma_registry "
            "renamed it to ed_arrival_datetime"
        ),
    )
