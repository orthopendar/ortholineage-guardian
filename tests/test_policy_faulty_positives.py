"""FAULTY namespace: all three deterministic checks fire, each with correct, populated
evidence (not merely a boolean)."""
from __future__ import annotations

from conftest import requires_graph

from ortholineage_guardian.models import (
    CHECK_MISSINGNESS_COLLAPSE,
    CHECK_PHI_EXPORT_PATH,
    CHECK_UNVALIDATED_ML_SOURCE,
)


@requires_graph
def test_exactly_the_three_checks_fire(faulty_findings):
    fired = sorted({f.check for f in faulty_findings})
    assert fired == sorted(
        [CHECK_PHI_EXPORT_PATH, CHECK_MISSINGNESS_COLLAPSE, CHECK_UNVALIDATED_ML_SOURCE]
    ), f"expected the three checks to fire; got {fired}"


@requires_graph
def test_phi_export_path_evidence(faulty_findings):
    f = next(f for f in faulty_findings if f.check == CHECK_PHI_EXPORT_PATH)
    e = f.evidence
    assert e.identifier_column == "research_export.patient_id"
    assert e.export_dataset == "research_export"
    assert e.export_properties.get("data_product") == "research_export"
    assert e.export_properties.get("deidentification_required") == "true"
    # the column-level path is populated and terminates at the export
    assert e.path and e.path[-1] == "research_export.patient_id"
    assert e.path[0] == "stg_ed_documentation.patient_id"


@requires_graph
def test_missingness_collapse_evidence(faulty_findings):
    f = next(f for f in faulty_findings if f.check == CHECK_MISSINGNESS_COLLAPSE)
    e = f.evidence
    assert e.source_column == "stg_ed_documentation.gcs_total"
    assert e.paired_column == "gcs_total_missingness"
    assert e.collapsed_in_dataset == "trauma_registry"
    assert e.source_dataset == "stg_ed_documentation"
    assert e.path[0] == "stg_ed_documentation.gcs_total"


@requires_graph
def test_unvalidated_ml_source_evidence(faulty_findings):
    f = next(f for f in faulty_findings if f.check == CHECK_UNVALIDATED_ML_SOURCE)
    e = f.evidence
    assert e.feature_column == "ml_feature_table.raw_mode_of_arrival_feature"
    assert e.unvalidated_source == "stg_ed_documentation"
    assert e.validation_status == "unvalidated"


@requires_graph
def test_every_finding_has_grounding_signals(faulty_findings):
    # evidence must name the MCP signals that grounded it (DETECTION PROVENANCE).
    for f in faulty_findings:
        assert f.evidence.signals_read, f"{f.check} has no signals_read"
        assert f.namespace == "faulty"
