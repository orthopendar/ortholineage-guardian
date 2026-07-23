"""Remediation artifacts (Batch 6): the generated dbt patch is REAL and APPLICABLE, and the
committed artifacts are golden-stable (re-rendered from fixtures match). Offline — no stack."""
from __future__ import annotations

import json
import pathlib
import subprocess

from _faulty_fixtures import faulty_findings, faulty_impact, faulty_stale_reference

from ortholineage_guardian.llm import templates
from ortholineage_guardian.remediation import render_patch, render_report

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _draft():
    return templates.remediation(
        faulty_findings(), faulty_impact(), faulty_stale_reference(), namespace="faulty"
    )


def test_generated_patch_applies_cleanly(tmp_path):
    patch = render_patch(_draft(), ROOT)
    patch_file = tmp_path / "remediation.patch"
    patch_file.write_text(patch)
    result = subprocess.run(
        ["git", "apply", "--check", "-p1", str(patch_file)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"git apply --check failed:\n{result.stderr}"


def test_patch_matches_committed_golden():
    assert render_patch(_draft(), ROOT) == (EXAMPLES / "remediation" / "remediation.patch").read_text()


def test_impact_report_matches_committed_golden():
    report = render_report(faulty_findings(), faulty_impact(), faulty_stale_reference(), "faulty")
    assert report == (EXAMPLES / "reports" / "migration_impact_report.md").read_text()


def test_findings_json_matches_committed_golden():
    expected = json.loads((EXAMPLES / "findings" / "findings.json").read_text())
    actual = [f.model_dump() for f in faulty_findings()]
    assert actual == expected


def test_patch_removes_every_planted_defect():
    patch = render_patch(_draft(), ROOT)
    # each fixture's defect marker appears only on removed (-) lines
    for marker in ("PHI_EXPORT_PATH", "MISSINGNESS_COLLAPSE", "UNVALIDATED_ML_SOURCE",
                   "STALE_REFERENCE"):
        removed = [ln for ln in patch.splitlines() if ln.startswith("-") and f"PLANTED DEFECT: {marker}" in ln]
        assert removed, f"{marker} defect not removed by the patch"
