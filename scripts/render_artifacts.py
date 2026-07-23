#!/usr/bin/env python3
"""Render PR-ready remediation artifacts into examples/ (Batch 6).

Runs the deterministic engine on a namespace, drafts remediation in TEMPLATE mode (so the
committed artifacts are deterministic and diff-reviewable — no timestamps), and writes:

    examples/remediation/remediation.patch      (git apply-able dbt patch)
    examples/reports/migration_impact_report.md
    examples/findings/findings.json

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp python scripts/render_artifacts.py --namespace faulty

Writes NOTHING when there are no findings (baseline).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ortholineage_guardian.llm import draft  # noqa: E402
from ortholineage_guardian.policy import engine  # noqa: E402
from ortholineage_guardian.remediation import render_patch, render_report  # noqa: E402

EXAMPLES = ROOT / "examples"


def write_artifacts(findings, impact, stale, namespace: str) -> list[pathlib.Path]:
    # deterministic: draft in template mode so the artifacts are golden-stable
    remediation_draft, _ = draft(findings, impact, stale, namespace, use_llm=False)
    patch = render_patch(remediation_draft, ROOT)
    report = render_report(findings, impact, stale, namespace)
    findings_json = json.dumps([f.model_dump() for f in findings], indent=2) + "\n"

    targets = {
        EXAMPLES / "remediation" / "remediation.patch": patch,
        EXAMPLES / "reports" / "migration_impact_report.md": report,
        EXAMPLES / "findings" / "findings.json": findings_json,
    }
    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return list(targets)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=["faulty", "baseline"], default="faulty")
    args = ap.parse_args()

    report = await engine.run_report(args.namespace)
    if not report.findings:
        print(f"namespace={args.namespace}: 0 findings — no artifacts written.")
        return 0

    written = write_artifacts(report.findings, report.impact, report.stale_reference, args.namespace)
    print(f"namespace={args.namespace}: {len(report.findings)} findings -> wrote:")
    for p in written:
        print(f"  {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
