"""The --no-llm / no-key path (Batch 5): a complete, valid artifact with NO API key.

Even when the caller opts into the LLM (use_llm=True), with no credential present the layer
must deterministically produce valid, complete Pydantic objects for all three findings — the
LLM is never required for correctness.
"""
from __future__ import annotations

import pytest
from _faulty_fixtures import faulty_findings, faulty_impact, faulty_stale_reference

from ortholineage_guardian.llm import draft, explain
from ortholineage_guardian.llm.schema_guard import validate_explanation, validate_remediation


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


def test_explain_all_three_fall_back_to_template():
    for finding in faulty_findings():
        exp, mode = explain(finding, use_llm=True)  # opted in, but no key
        assert mode == "template"
        assert exp.check == finding.check
        assert exp.namespace == finding.namespace
        # complete: every prose field populated
        assert exp.title and exp.what_broke and exp.why_it_matters
        assert exp.downstream_impact and exp.remediation_summary
        assert exp.affected_entities
        # and still guard-clean
        validate_explanation(exp.model_dump(), finding)


def test_remediation_falls_back_and_is_complete():
    findings = faulty_findings()
    d, mode = draft(findings, faulty_impact(), faulty_stale_reference(), "faulty", use_llm=True)
    assert mode == "template"
    assert d.namespace == "faulty"
    assert sorted(d.findings_covered) == sorted(f.check for f in findings)
    # a hunk per finding + the stale-reference hunk
    assert len(d.patch_hunks) == len(findings) + 1
    fixtures = {h.fixture for h in d.patch_hunks}
    assert {"PHI_EXPORT_PATH", "MISSINGNESS_COLLAPSE", "UNVALIDATED_ML_SOURCE", "STALE_REFERENCE"} <= fixtures
    assert d.impact_report_markdown.startswith("# Migration impact report")
    validate_remediation(d.model_dump(), findings)


def test_no_finding_is_added_or_dropped():
    findings = faulty_findings()
    d, _ = draft(findings, faulty_impact(), faulty_stale_reference(), "faulty", use_llm=True)
    # remediation covers exactly the deterministic findings — the LLM layer never invents one
    assert set(d.findings_covered) == {f.check for f in findings}
