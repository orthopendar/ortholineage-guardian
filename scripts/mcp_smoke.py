#!/usr/bin/env python3
"""MCP read-path smoke test for OrthoLineage Guardian (Batch 2).

Drives the OFFICIAL DataHub MCP server (`uvx mcp-server-datahub@latest`, stdio) as a
plain MCP client and exercises the two reads the policy engine depends on:

  (a) lineage for trauma_registry (incl. the ed_arrival_datetime column path), and
  (b) schema + tags/properties for research_export.

This proves capability-matrix Rows 1 (read lineage) and 2 (read schema/tags/properties)
over the MCP Server path — no DataHub SQL is read.

Run (DataHub must be up; see scripts/datahub_up.sh):
    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with mcp python scripts/mcp_smoke.py

On the local quickstart, metadata-service auth is disabled, so DATAHUB_GMS_TOKEN may be
empty. For a secured instance, export a DATAHUB_GMS_TOKEN (see .env.example).
"""
from __future__ import annotations

import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090")
# The dbt-platform model nodes carry schema + lineage + column-lineage (the duckdb
# datasets are thin physical siblings). The policy engine reads these dbt URNs.
DBT = "urn:li:dataPlatform:dbt"


def durn(model: str) -> str:
    return f"urn:li:dataset:({DBT},ortholineage_guardian.faulty.main.{model},PROD)"


def _text(result) -> str:
    """Flatten an MCP tool result's content blocks to text."""
    out = []
    for block in result.content:
        out.append(getattr(block, "text", str(block)))
    return "\n".join(out)


async def main() -> None:
    env = dict(os.environ)
    env["DATAHUB_GMS_URL"] = GMS
    env.setdefault("DATAHUB_GMS_TOKEN", "")
    params = StdioServerParameters(
        command="uvx", args=["mcp-server-datahub@latest"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            print(f"# MCP server connected to {GMS}")
            print(f"# tools exposed: {tools}\n")

            print("=" * 78)
            print("(a) ROW 1 — read lineage for trauma_registry (get_lineage)")
            print("=" * 78)
            lineage = await session.call_tool(
                "get_lineage", {"urn": durn("trauma_registry")}
            )
            print(_text(lineage)[:2500])

            print("\n" + "=" * 78)
            print("(b) ROW 2 — read schema + tags/properties for research_export")
            print("=" * 78)
            schema = await session.call_tool(
                "list_schema_fields", {"urn": durn("research_export")}
            )
            print(_text(schema)[:2500])

            print("\n" + "-" * 78)
            print("get_entities(research_export) — dataset-level properties/tags")
            print("-" * 78)
            ent = await session.call_tool(
                "get_entities", {"urns": durn("research_export")}
            )
            print(_text(ent)[:2000])


if __name__ == "__main__":
    asyncio.run(main())
