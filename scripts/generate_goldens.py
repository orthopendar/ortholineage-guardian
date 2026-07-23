#!/usr/bin/env python3
"""Regenerate the committed golden artifacts (Batch 5).

Builds the template-mode explanation + remediation for the three faulty findings, validates
each through the schema guard (proving the deterministic output is itself guard-clean), and
writes tests/golden/*.json. Fully offline — no DataHub, no API key.

    uv run python scripts/generate_goldens.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from _faulty_fixtures import faulty_findings, faulty_impact, faulty_stale_reference  # noqa: E402
from ortholineage_guardian.llm import templates  # noqa: E402
from ortholineage_guardian.llm.schema_guard import (  # noqa: E402
    validate_explanation,
    validate_remediation,
)

GOLDEN = ROOT / "tests" / "golden"


def main() -> None:
    findings = faulty_findings()
    impact = faulty_impact()
    stale = faulty_stale_reference()

    explanations = []
    for f in findings:
        exp = templates.explanation(f)
        validate_explanation(exp.model_dump(), f)  # guard-clean assertion
        explanations.append(exp.model_dump())

    draft = templates.remediation(findings, impact, stale, namespace="faulty")
    validate_remediation(draft.model_dump(), findings)  # guard-clean assertion

    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / "explanations.json").write_text(json.dumps(explanations, indent=2) + "\n")
    (GOLDEN / "remediation.json").write_text(json.dumps(draft.model_dump(), indent=2) + "\n")
    print(f"wrote {len(explanations)} explanations + 1 remediation draft to {GOLDEN} (guard-clean)")


if __name__ == "__main__":
    main()
