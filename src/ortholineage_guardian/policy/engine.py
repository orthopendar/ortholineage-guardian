"""Deterministic governance policy engine (Batch 4).

Orchestrates the three checks over one namespace's DataHub metadata. DETERMINISTIC and
read-only: it decides whether a violation exists purely from MCP signals. No LLM, no
write-back, no SQL/manifest/DuckDB access.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..emitter import contract as C
from ..lineage import detect_stale_reference, impact_of_hero_field
from ..mcp_client import McpClient
from ..models import Finding, ImpactNode
from . import missingness_collapse, phi_export_path, unvalidated_ml_source

CHECKS = (phi_export_path, missingness_collapse, unvalidated_ml_source)


class EngineReport(BaseModel):
    namespace: str
    findings: list[Finding] = Field(default_factory=list)
    impact: list[ImpactNode] = Field(default_factory=list)
    stale_reference: ImpactNode | None = None


async def run_checks(client: McpClient) -> list[Finding]:
    """Run the three deterministic checks; return all findings (empty when clean)."""
    findings: list[Finding] = []
    for check in CHECKS:
        result = await check.run(client)
        findings.extend(result.findings)
    return findings


async def run(namespace: str = "faulty", gms_url: str | None = None) -> list[Finding]:
    """Open an MCP session for `namespace` and return the deterministic findings."""
    ns = C.NAMESPACES[namespace]
    async with McpClient(ns, gms_url=gms_url) as client:
        return await run_checks(client)


async def run_report(namespace: str = "faulty", gms_url: str | None = None) -> EngineReport:
    """Findings + the shared impact traversal + the STALE_REFERENCE observation."""
    ns = C.NAMESPACES[namespace]
    async with McpClient(ns, gms_url=gms_url) as client:
        findings = await run_checks(client)
        impact = await impact_of_hero_field(client)
        stale = await detect_stale_reference(client)
    return EngineReport(
        namespace=namespace, findings=findings, impact=impact, stale_reference=stale
    )
