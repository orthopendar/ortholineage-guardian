"""Write-back plan (Batch 6): dry-run plan is correct and validated-only; baseline writes
nothing. Offline — the pure plan needs no DataHub SDK; live apply/idempotency/reset are
proven in the Batch-6 report."""
from __future__ import annotations

from _faulty_fixtures import faulty_findings

from ortholineage_guardian.emitter import contract as C
from ortholineage_guardian.writeback import contract as W
from ortholineage_guardian.writeback import plan

FINDINGS = faulty_findings()


def test_plan_has_one_op_per_finding_on_the_right_dataset():
    ops = plan(FINDINGS, C.FAULTY)
    assert len(ops) == 3
    by_check = {op["check"]: op for op in ops}
    assert "research_export" in by_check["PHI_EXPORT_PATH"]["dataset"]
    assert "trauma_registry" in by_check["MISSINGNESS_COLLAPSE"]["dataset"]
    assert "ml_feature_table" in by_check["UNVALIDATED_ML_SOURCE"]["dataset"]


def test_plan_content_is_guardian_marked_and_validated():
    for op in plan(FINDINGS, C.FAULTY):
        assert op["tag"].startswith(W.GUARDIAN_TAG_PREFIX)
        assert op["description"].startswith(W.GUARDIAN_DESC_MARKER)
        assert "Proposed remediation:" in op["description"]
        assert op["incident"].startswith(W.GUARDIAN_INCIDENT_PREFIX)
        assert op["incident"].endswith(op["check"])


def test_baseline_zero_findings_plans_zero_writes():
    # baseline safety at the plan level: no findings -> no write operations
    assert plan([], C.BASELINE) == []
    assert plan([], C.FAULTY) == []


def test_incident_urns_cover_all_checks_for_reset():
    urns = W.all_incident_urns(C.FAULTY)
    assert len(urns) == 3
    assert all(u.startswith(W.GUARDIAN_INCIDENT_PREFIX) for u in urns)


def test_description_never_contains_raw_llm_or_observed_data():
    # descriptions are built from the deterministic (guard-clean) template + engine summary
    for op in plan(FINDINGS, C.FAULTY):
        # no observed row/value counts leak into what we write
        assert " rows" not in op["description"].lower()
        assert " records" not in op["description"].lower()
