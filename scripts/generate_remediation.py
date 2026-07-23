#!/usr/bin/env python3
"""Explain findings + draft remediation for a namespace (Batch 5).

Runs the deterministic engine, then the LLM layer (EXPLAIN/DRAFT only). With no API key — or
with --no-llm — it renders the same validated objects from templates. It PRINTS only; writing
examples/ artifacts and any write-back are Batch 6.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp python scripts/generate_remediation.py --namespace faulty
    uv run --with mcp python scripts/generate_remediation.py --namespace faulty --no-llm

Set ANTHROPIC_API_KEY (and optionally GUARDIAN_MODEL) to use the LLM; see .env.example.
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ortholineage_guardian import config  # noqa: E402
from ortholineage_guardian.llm import draft, explain  # noqa: E402
from ortholineage_guardian.policy import engine  # noqa: E402


def _print_explanation(exp, mode: str) -> None:
    print(f"\n### {exp.check}  [{mode}]  — {exp.title}")
    print(f"  what broke      : {exp.what_broke}")
    print(f"  why it matters  : {exp.why_it_matters}")
    print(f"  downstream      : {exp.downstream_impact}")
    print(f"  remediation     : {exp.remediation_summary}")
    print(f"  affected        : {', '.join(exp.affected_entities)}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=["faulty", "baseline"], default="faulty")
    ap.add_argument("--no-llm", action="store_true", help="force deterministic template mode")
    args = ap.parse_args()
    use_llm = not args.no_llm

    report = await engine.run_report(args.namespace)
    mode_label = "LLM" if config.llm_enabled(use_llm) else "template (no key / --no-llm)"
    print(f"===== REMEDIATION — namespace={args.namespace}  mode={mode_label} =====")
    print(f"deterministic findings: {len(report.findings)}")

    if not report.findings:
        print("\nNo findings — nothing to explain or remediate.")
        return 0

    modes = set()
    for f in report.findings:
        exp, mode = explain(f, use_llm=use_llm)
        modes.add(mode)
        _print_explanation(exp, mode)

    remediation, r_mode = draft(
        report.findings, report.impact, report.stale_reference, args.namespace, use_llm=use_llm
    )
    modes.add(r_mode)
    print(f"\n### REMEDIATION DRAFT  [{r_mode}]")
    print(f"  summary          : {remediation.summary}")
    print(f"  findings_covered : {remediation.findings_covered}")
    for h in remediation.patch_hunks:
        print(f"\n  -- patch hunk: {h.model} [{h.fixture}]")
        print(f"     {h.description}")
        print("     BEFORE:")
        for line in h.before.splitlines():
            print(f"       {line}")
        print("     AFTER:")
        for line in h.after.splitlines():
            print(f"       {line}")
    print("\n  -- impact report (draft markdown) --")
    print("\n".join("  " + ln for ln in remediation.impact_report_markdown.splitlines()))

    print(f"\n[render modes used: {sorted(modes)}]  (files/write-back are Batch 6)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
