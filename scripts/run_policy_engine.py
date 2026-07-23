#!/usr/bin/env python3
"""Run the deterministic governance policy engine against a namespace (Batch 4).

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp python scripts/run_policy_engine.py --namespace faulty
    uv run --with mcp python scripts/run_policy_engine.py --namespace baseline

Reads ONLY DataHub MCP metadata signals. No LLM, no write-back, no SQL/manifest/DuckDB.
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ortholineage_guardian.policy import engine  # noqa: E402


def _print_finding(i: int, f) -> None:
    e = f.evidence
    print(f"\nfinding {i}: {f.check}   [{f.rule_class}, severity={f.severity}]")
    print(f"  summary: {f.summary}")
    if e.identifier_column:
        print(f"  identifier_column: {e.identifier_column}")
        print(f"  export_dataset: {e.export_dataset}  {e.export_properties}")
    if e.source_column:
        print(f"  source_column: {e.source_column}  paired_column: {e.paired_column}")
        print(f"  collapsed_in_dataset: {e.collapsed_in_dataset}  (source: {e.source_dataset})")
    if e.feature_column:
        print(f"  feature_column: {e.feature_column}")
        print(f"  unvalidated_source: {e.unvalidated_source} (validation_status={e.validation_status})")
    print(f"  path: {' -> '.join(e.path)}")
    print(f"  signals_read: {e.signals_read}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=["faulty", "baseline"], default="faulty")
    args = ap.parse_args()

    report = await engine.run_report(args.namespace)
    print(f"===== POLICY ENGINE — namespace={report.namespace} =====")
    print(f"deterministic findings: {len(report.findings)}")
    for i, f in enumerate(report.findings, 1):
        _print_finding(i, f)

    print("\n--- impact traversal (shared substrate, not a check) ---")
    for n in report.impact:
        print(f"  {n.dataset}.{n.column}  — {n.note}")
    print("--- STALE_REFERENCE observation (reported alongside, not a check) ---")
    if report.stale_reference:
        print(f"  {report.stale_reference.note}")
    else:
        print("  none")

    if not report.findings:
        print("\nZERO deterministic findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
