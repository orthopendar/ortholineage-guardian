"""READ-only DataHub MCP client for the policy engine (Batch 4).

DETECTION PROVENANCE: this is the engine's ONLY door to metadata. It talks exclusively to
the official DataHub MCP server (`uvx mcp-server-datahub`, stdio). It never opens a `.sql`
file, the dbt manifest, `catalog.json`, or a DuckDB database — the whole point is that the
checks decide from the metadata graph alone.

Parses the exact MCP shapes documented in docs/METADATA_CONTRACT.md:
  * list_schema_fields -> fields[].editedGlossaryTerms (column glossary terms)
  * get_entities -> structuredProperties / glossaryTerms (dataset facts + classes)
  * get_lineage(column=...) -> column-scoped upstream datasets
  * get_lineage_paths_between -> column-level path (for evidence)
"""
from __future__ import annotations

import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .emitter import contract as C


def _text(result) -> str:
    return "\n".join(getattr(b, "text", str(b)) for b in result.content)


class McpClient:
    """Async context manager wrapping one MCP session for a single namespace."""

    def __init__(self, ns: C.Namespace, gms_url: str | None = None, token: str | None = None):
        self.ns = ns
        self.gms_url = gms_url or os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090")
        self.token = token if token is not None else (os.environ.get("DATAHUB_GMS_TOKEN") or "")
        self._session: ClientSession | None = None
        self._stdio_cm = None
        self._session_cm = None

    # -- lifecycle ---------------------------------------------------------------------
    async def __aenter__(self) -> "McpClient":
        env = dict(os.environ)
        env["DATAHUB_GMS_URL"] = self.gms_url
        env["DATAHUB_GMS_TOKEN"] = self.token
        params = StdioServerParameters(
            command="uvx", args=["mcp-server-datahub@latest"], env=env
        )
        # The MCP server logs its GraphQL queries to stderr. Keep the demo terminal clean by
        # routing that to devnull unless GUARDIAN_MCP_DEBUG is set (then it goes to stderr).
        self._errlog = (
            sys.stderr if os.environ.get("GUARDIAN_MCP_DEBUG") else open(os.devnull, "w")
        )
        self._stdio_cm = stdio_client(params, errlog=self._errlog)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(*exc)
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(*exc)
        if getattr(self, "_errlog", None) is not None and self._errlog is not sys.stderr:
            self._errlog.close()

    async def _call(self, name: str, args: dict) -> dict:
        result = await self._session.call_tool(name, args)
        return json.loads(_text(result))

    # -- URN helpers -------------------------------------------------------------------
    def dataset_urn(self, model: str) -> str:
        return C.dataset_urn(model, self.ns)

    def _ns_prefix(self) -> str:
        return f"{self.ns.platform_instance}.{self.ns.database}.main."

    def _model_if_in_ns(self, entity: dict) -> str | None:
        """Return the model short-name if `entity` is one of the 6 dbt models in THIS
        namespace. MCP returns `entity.name` as the short name, so the namespace is
        derived from the URN (which carries the full name + env)."""
        if entity.get("platform", {}).get("name") != "dbt":
            return None
        urn = entity.get("urn", "")
        if not urn.endswith(f",{self.ns.env})"):
            return None
        full = _name_from_dataset_urn(urn)  # ortholineage_guardian.<db>.main.<model>
        if not full.startswith(self._ns_prefix()):
            return None
        model = full.split(".")[-1]
        return model if model in C.MODELS else None  # exclude the seed / non-models

    # -- reads -------------------------------------------------------------------------
    async def schema_fields(self, model: str) -> list[dict]:
        """[{fieldPath, editedGlossaryTerms:[...]}] for the model's columns."""
        data = await self._call("list_schema_fields", {"urn": self.dataset_urn(model)})
        return [
            {"fieldPath": f["fieldPath"], "terms": f.get("editedGlossaryTerms", [])}
            for f in data.get("fields", [])
        ]

    async def column_terms(self, model: str) -> dict[str, list[str]]:
        return {f["fieldPath"]: f["terms"] for f in await self.schema_fields(model)}

    async def column_names(self, model: str) -> set[str]:
        return {f["fieldPath"] for f in await self.schema_fields(model)}

    async def dataset_facts(self, model: str) -> dict:
        """{'structured': {qualifiedName: [values]}, 'terms': [names]} for a dataset."""
        ent = await self._call("get_entities", {"urns": self.dataset_urn(model)})
        structured = {
            p["structuredProperty"]["definition"]["qualifiedName"]: [
                v.get("stringValue") for v in p.get("values", [])
            ]
            for p in ent.get("structuredProperties", {}).get("properties", [])
        }
        terms = [
            t["term"]["properties"]["name"]
            for t in ent.get("glossaryTerms", {}).get("terms", [])
            if t.get("term", {}).get("properties")
        ]
        return {"structured": structured, "terms": terms}

    async def _column_related_models(self, model: str, column: str, upstream: bool) -> set[str]:
        data = await self._call(
            "get_lineage",
            {"urn": self.dataset_urn(model), "column": column, "upstream": upstream, "max_hops": 20},
        )
        key = "upstreams" if upstream else "downstreams"
        out: set[str] = set()
        for sr in data.get(key, {}).get("searchResults", []):
            m = self._model_if_in_ns(sr.get("entity", {}))
            if m and m != model:
                out.add(m)
        return out

    async def column_upstream_models(self, model: str, column: str) -> set[str]:
        """Set of model short-names (this namespace) upstream of model.column."""
        return await self._column_related_models(model, column, upstream=True)

    async def column_downstream_models(self, model: str, column: str) -> set[str]:
        """Set of model short-names (this namespace) downstream of model.column."""
        return await self._column_related_models(model, column, upstream=False)

    async def column_path(self, src_model: str, src_col: str, tgt_model: str, tgt_col: str) -> list[str]:
        """Column-level path 'model.field -> ...' from source to target (dbt nodes only)."""
        try:
            data = await self._call(
                "get_lineage_paths_between",
                {
                    "source_urn": self.dataset_urn(src_model),
                    "source_column": src_col,
                    "target_urn": self.dataset_urn(tgt_model),
                    "target_column": tgt_col,
                    "direction": "downstream",
                },
            )
        except Exception:
            return []
        paths = data.get("paths", [])
        if not paths:
            return []
        steps: list[str] = []
        for node in paths[0].get("path", []):
            if node.get("type") != "SCHEMA_FIELD":
                continue
            parent_urn = node.get("parent", {}).get("urn", "")
            platform = "dbt" if "dataPlatform:dbt" in parent_urn else "duckdb"
            model = self._model_if_in_ns({"platform": {"name": platform}, "urn": parent_urn})
            if model:
                step = f"{model}.{node.get('fieldPath')}"
                if not steps or steps[-1] != step:
                    steps.append(step)
        return steps


def _name_from_dataset_urn(urn: str) -> str:
    # urn:li:dataset:(urn:li:dataPlatform:dbt,<name>,<env>) -> <name>
    try:
        inner = urn.split("(", 1)[1].rsplit(")", 1)[0]
        return inner.split(",")[1]
    except Exception:
        return ""
