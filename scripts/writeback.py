#!/usr/bin/env python3
"""Controlled write-back of governance findings into DataHub (Batch 6).

DRY-RUN BY DEFAULT — prints exactly what would be written and writes NOTHING. Writing
requires explicit --apply. Never writes when there are no findings (baseline safety).

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp --with 'acryl-datahub[datahub-rest]' python scripts/writeback.py --namespace faulty
    uv run --with mcp --with 'acryl-datahub[datahub-rest]' python scripts/writeback.py --namespace faulty --apply

The engine (deterministic decision) runs first; write-back is validated application code —
the LLM never performs or triggers a write.
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ortholineage_guardian.emitter import contract as C  # noqa: E402
from ortholineage_guardian.policy import engine  # noqa: E402
from ortholineage_guardian import writeback  # noqa: E402


def _print_plan(ops: list[dict], applied: bool) -> None:
    verb = "WROTE" if applied else "WOULD WRITE (dry-run — nothing written)"
    print(f"\n{verb} {len(ops)} finding write-back(s):")
    for op in ops:
        print(f"\n  [{op['check']}] -> {op['dataset']}")
        print(f"    tag         : {op['tag']}")
        print(f"    description : {op['description']}")
        print(f"    incident    : {op['incident']}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=["faulty", "baseline"], default="faulty")
    ap.add_argument("--apply", action="store_true", help="perform the writes (default: dry-run)")
    args = ap.parse_args()
    ns = C.NAMESPACES[args.namespace]

    report = await engine.run_report(args.namespace)
    print(f"===== WRITE-BACK — namespace={args.namespace}  "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'} =====")
    print(f"deterministic findings: {len(report.findings)}")

    if not report.findings:
        print("0 findings — writing nothing (baseline safety).")
        return 0

    if args.apply:
        ops = writeback.apply(report.findings, ns)
        _print_plan(ops, applied=True)
        print("\n[applied]  re-run with --apply again for idempotency; "
              "run scripts/writeback_reset.py to clean up.")
    else:
        ops = writeback.plan(report.findings, ns)
        _print_plan(ops, applied=False)
        print("\n[dry-run]  pass --apply to write these into DataHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
