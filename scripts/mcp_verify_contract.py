#!/usr/bin/env python3
"""Verify the clinical metadata contract THROUGH THE MCP READ PATH (Batch 3).

Batch 4's policy engine reads via MCP, so a signal that is SDK-writable but not
MCP-readable is useless. This script reads back EVERY signal promised by
`emitter/contract.py` through the official DataHub MCP server and asserts it is present at
the correct granularity, printing the exact shape MCP returns (which Batch 4 parses).

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp python scripts/mcp_verify_contract.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import pathlib
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load the pure-data contract module directly by path, so this verifier does NOT pull in
# the emitter package __init__ (which imports the datahub SDK). The verifier only needs
# the MCP client + the contract's expectations.
_contract_path = (
    pathlib.Path(__file__).resolve().parents[1]
    / "src" / "ortholineage_guardian" / "emitter" / "contract.py"
)
_spec = importlib.util.spec_from_file_location("guardian_contract", _contract_path)
C = importlib.util.module_from_spec(_spec)
sys.modules["guardian_contract"] = C  # needed for @dataclass annotation resolution
_spec.loader.exec_module(C)

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090")
_failures: list[str] = []
NS = C.FAULTY  # set from --namespace in __main__


def _text(result) -> str:
    return "\n".join(getattr(b, "text", str(b)) for b in result.content)


def _check(ok: bool, label: str) -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        _failures.append(label)


async def _column_terms(session, model: str) -> dict[str, list[str]]:
    """MCP list_schema_fields -> {fieldPath: editedGlossaryTerms}."""
    res = await session.call_tool("list_schema_fields", {"urn": C.dataset_urn(model, NS)})
    data = json.loads(_text(res))
    return {
        f["fieldPath"]: f.get("editedGlossaryTerms", []) for f in data.get("fields", [])
    }


async def _dataset_entity(session, model: str) -> dict:
    res = await session.call_tool("get_entities", {"urns": C.dataset_urn(model, NS)})
    return json.loads(_text(res))


async def main() -> None:
    env = dict(os.environ)
    env["DATAHUB_GMS_URL"] = GMS
    env.setdefault("DATAHUB_GMS_TOKEN", "")
    params = StdioServerParameters(command="uvx", args=["mcp-server-datahub@latest"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"# MCP connected to {GMS}  namespace={NS.name} (db={NS.database}, env={NS.env})\n")

            # ---- COLUMN-level glossary terms (the checks' column signals) ----
            print("== COLUMN-level signals (MCP list_schema_fields -> editedGlossaryTerms) ==")
            for model in C.MODELS:
                got = await _column_terms(session, model)
                for field_path, expected in C.COLUMN_TERMS.items():
                    if field_path not in got:
                        continue  # column not in this dataset's schema
                    have = set(got[field_path])
                    _check(
                        set(expected) <= have,
                        f"{model}.{field_path}: editedGlossaryTerms={sorted(have)} ⊇ {expected}",
                    )

            # ---- exact column shape MCP returns (Batch 4 parses this) ----
            print("\n== Exact MCP column shape for the load-bearing columns ==")
            res = await session.call_tool(
                "list_schema_fields", {"urn": C.dataset_urn("research_export", NS)}
            )
            for f in json.loads(_text(res)).get("fields", []):
                if f["fieldPath"] == "patient_id":
                    print("  research_export.patient_id (sensitivity):")
                    print("   ", json.dumps(f))
            res = await session.call_tool(
                "list_schema_fields", {"urn": C.dataset_urn("stg_ed_documentation", NS)}
            )
            for f in json.loads(_text(res)).get("fields", []):
                if f["fieldPath"] == "gcs_total":
                    print("  stg_ed_documentation.gcs_total (missingness_contract):")
                    print("   ", json.dumps(f))

            # ---- DATASET-level structured properties + glossary terms ----
            print("\n== DATASET-level signals (MCP get_entities) ==")
            for model, signals in C.DATASET_SIGNALS.items():
                ent = await _dataset_entity(session, model)
                sp = ent.get("structuredProperties", {}).get("properties", [])
                sp_map = {
                    p["structuredProperty"]["definition"]["qualifiedName"]: [
                        v.get("stringValue") for v in p.get("values", [])
                    ]
                    for p in sp
                }
                for qn, value in signals.get("properties", {}).items():
                    _check(
                        value in sp_map.get(qn, []),
                        f"{model}: structuredProperty {qn}={value} (MCP={sp_map.get(qn)})",
                    )
                terms = {
                    t["term"]["properties"]["name"]
                    for t in ent.get("glossaryTerms", {}).get("terms", [])
                    if t.get("term", {}).get("properties")
                }
                for term in signals.get("terms", []):
                    _check(term in terms, f"{model}: dataset glossaryTerm {term} (MCP={sorted(terms)})")

    print("\n" + ("ALL SIGNALS MCP-READABLE ✔" if not _failures else f"FAILURES: {_failures}"))
    sys.exit(1 if _failures else 0)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", choices=list(C.NAMESPACES), default="faulty")
    NS = C.NAMESPACES[ap.parse_args().namespace]
    asyncio.run(main())
