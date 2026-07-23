#!/usr/bin/env python3
"""Read the guardian's write-back back THROUGH MCP (Batch 6) — the same path the engine uses.

Reads each affected dataset via the official MCP server's get_entities and reports whether
the governance tag, the guardian editable description, and an active incident are present.
Use --expect present (after --apply) or --expect clean (after reset) to assert + exit-code.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp python scripts/writeback_verify.py --namespace faulty --expect present
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from ortholineage_guardian.emitter import contract as C  # noqa: E402
from ortholineage_guardian.writeback import contract as W  # noqa: E402

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090")
# datasets the guardian writes to on faulty
AFFECTED = ["research_export", "trauma_registry", "ml_feature_table"]


def _text(result) -> str:
    return "\n".join(getattr(b, "text", str(b)) for b in result.content)


def _read_state(entity: dict) -> dict:
    tags = [t["tag"]["urn"] for t in entity.get("tags", {}).get("tags", [])]
    desc = (entity.get("editableProperties") or {}).get("description") or ""
    active_incident = any(
        h.get("type") == "INCIDENTS" and "ACTIVE_INCIDENTS" in (h.get("causes") or [])
        for h in entity.get("health", [])
    )
    return {
        "guardian_tag": any(t.startswith(W.GUARDIAN_TAG_PREFIX) for t in tags),
        "guardian_desc": desc.startswith(W.GUARDIAN_DESC_MARKER),
        "active_incident": active_incident,
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=["faulty", "baseline"], default="faulty")
    ap.add_argument("--expect", choices=["present", "clean"], default=None)
    args = ap.parse_args()
    ns = C.NAMESPACES[args.namespace]

    env = dict(os.environ)
    env["DATAHUB_GMS_URL"] = GMS
    env.setdefault("DATAHUB_GMS_TOKEN", "")
    params = StdioServerParameters(command="uvx", args=["mcp-server-datahub@latest"], env=env)

    ok = True
    async with stdio_client(params, errlog=open(os.devnull, "w")) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print(f"# MCP read-back  namespace={ns.name}  (via get_entities)\n")
            for model in AFFECTED:
                ent = json.loads(_text(await s.call_tool(
                    "get_entities", {"urns": C.dataset_urn(model, ns)})))
                st = _read_state(ent)
                print(f"  {model:18} tag={st['guardian_tag']!s:5} "
                      f"description={st['guardian_desc']!s:5} "
                      f"active_incident={st['active_incident']!s:5}")
                if args.expect == "present" and not all(st.values()):
                    ok = False
                if args.expect == "clean" and any(st.values()):
                    ok = False

    if args.expect:
        print(f"\n{'PASS' if ok else 'FAIL'}: state matches --expect {args.expect}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
