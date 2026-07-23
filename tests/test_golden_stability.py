"""Golden stability (Batch 5): template-mode output matches the committed goldens.

Keeps the deterministic artifacts inspectable and stable without a running stack or a key.
Regenerate intentionally with `uv run python scripts/generate_goldens.py`.
"""
from __future__ import annotations

import json
import pathlib

from _faulty_fixtures import faulty_findings, faulty_impact, faulty_stale_reference

from ortholineage_guardian.llm import templates

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden"


def test_explanations_match_golden():
    expected = json.loads((GOLDEN / "explanations.json").read_text())
    actual = [templates.explanation(f).model_dump() for f in faulty_findings()]
    assert actual == expected


def test_remediation_matches_golden():
    expected = json.loads((GOLDEN / "remediation.json").read_text())
    actual = templates.remediation(
        faulty_findings(), faulty_impact(), faulty_stale_reference(), namespace="faulty"
    ).model_dump()
    assert actual == expected
