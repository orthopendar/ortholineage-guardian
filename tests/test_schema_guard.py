"""Schema-guard rejections (Batch 5). No network, no API key — LLM output is MOCKED as dicts.

Proves the three failure modes are rejected:
  1. malformed JSON,
  2. output naming a non-existent entity (entity whitelist / anti-hallucination),
  3. output asserting observed row data (contract-knowledge guard).
"""
from __future__ import annotations

import pytest
from _faulty_fixtures import faulty_findings

from ortholineage_guardian.llm.schema_guard import (
    GuardRejection,
    validate_explanation,
    validate_remediation,
)

FINDINGS = faulty_findings()
PHI = FINDINGS[0]


def _valid_explanation_dict() -> dict:
    return {
        "check": "PHI_EXPORT_PATH",
        "namespace": "faulty",
        "title": "Direct identifier reaches a research export",
        "what_broke": "research_export.patient_id has DirectIdentifier and reaches research_export.",
        "why_it_matters": "A research export must not carry a direct identifier.",
        "downstream_impact": "Consumers of research_export inherit the identifier.",
        "remediation_summary": "Drop research_export.patient_id from research_export.",
        "affected_entities": ["research_export.patient_id", "research_export"],
    }


def test_valid_explanation_passes():
    exp = validate_explanation(_valid_explanation_dict(), PHI)
    assert exp.check == "PHI_EXPORT_PATH"


def test_malformed_json_rejected():
    with pytest.raises(GuardRejection, match="malformed JSON"):
        validate_explanation('{"check": "PHI_EXPORT_PATH", not valid json', PHI)


def test_hallucinated_entity_rejected():
    bad = _valid_explanation_dict()
    # invent a table that exists nowhere in the finding evidence or the contract
    bad["what_broke"] = "The identifier flows into phantom_export.patient_ssn downstream."
    with pytest.raises(GuardRejection, match="entity-whitelist violation"):
        validate_explanation(bad, PHI)


def test_hallucinated_entity_in_affected_list_rejected():
    bad = _valid_explanation_dict()
    bad["affected_entities"] = ["research_export", "billing_warehouse"]
    with pytest.raises(GuardRejection, match="entity-whitelist violation"):
        validate_explanation(bad, PHI)


def test_observed_row_count_rejected():
    bad = _valid_explanation_dict()
    bad["downstream_impact"] = "The export leaks 27 patient records to consumers."
    with pytest.raises(GuardRejection, match="contract-knowledge violation"):
        validate_explanation(bad, PHI)


def test_observed_missingness_state_rejected():
    # a MISSINGNESS finding whose prose claims it observed specific state values
    collapse = FINDINGS[1]
    bad = {
        "check": "MISSINGNESS_COLLAPSE",
        "namespace": "faulty",
        "title": "Collapse",
        "what_broke": "stg_ed_documentation.gcs_total lost its paired gcs_total_missingness in trauma_registry.",
        "why_it_matters": "We found NOT_DOCUMENTED and NOT_ASSESSED values collapsed to NULL.",
        "downstream_impact": "trauma_registry consumers cannot tell them apart.",
        "remediation_summary": "Restore gcs_total_missingness.",
        "affected_entities": ["stg_ed_documentation.gcs_total"],
    }
    with pytest.raises(GuardRejection, match="contract-knowledge violation"):
        validate_explanation(bad, collapse)


def test_relabelled_decision_rejected():
    bad = _valid_explanation_dict()
    bad["check"] = "MISSINGNESS_COLLAPSE"  # LLM must not relabel the deterministic decision
    with pytest.raises(GuardRejection, match="does not|!="):
        validate_explanation(bad, PHI)


def test_remediation_unknown_model_rejected():
    draft = {
        "namespace": "faulty",
        "summary": "draft",
        "findings_covered": ["PHI_EXPORT_PATH"],
        "patch_hunks": [
            {"model": "shadow_table", "fixture": "PHI_EXPORT_PATH",
             "description": "x", "before": "y", "after": "z"}
        ],
        "impact_report_markdown": "# report",
    }
    with pytest.raises(GuardRejection, match="unknown model"):
        validate_remediation(draft, FINDINGS)


def test_remediation_invented_finding_rejected():
    draft = {
        "namespace": "faulty",
        "summary": "draft",
        "findings_covered": ["PHI_EXPORT_PATH", "SECRET_LEAK"],
        "patch_hunks": [],
        "impact_report_markdown": "# report",
    }
    with pytest.raises(GuardRejection, match="non-existent findings"):
        validate_remediation(draft, FINDINGS)
