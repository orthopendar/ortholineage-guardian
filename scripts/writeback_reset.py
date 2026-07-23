#!/usr/bin/env python3
"""Remove everything the guardian wrote back into DataHub (Batch 6).

Removes guardian governance tags, guardian editable descriptions, and guardian incidents so
the demo can be re-recorded from a clean graph. Preserves any non-guardian tags/descriptions.
Does NOT need the engine — it sweeps the guardian-owned markers directly.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with 'acryl-datahub[datahub-rest]' python scripts/writeback_reset.py --namespace faulty
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ortholineage_guardian.emitter import contract as C  # noqa: E402
from ortholineage_guardian import writeback  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=["faulty", "baseline"], default="faulty")
    args = ap.parse_args()
    removed = writeback.reset(C.NAMESPACES[args.namespace])
    print(f"===== WRITE-BACK RESET — namespace={args.namespace} =====")
    print(f"removed: {removed['tags']} guardian tag(s), "
          f"{removed['descriptions']} guardian description(s), "
          f"{removed['incidents']} guardian incident(s)")
    print("[clean] graph restored to its ingested/emitted state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
