"""Controlled write-back via the DataHub Python SDK (Batch 6) — application code, never LLM.

DRY-RUN BY DEFAULT: `plan()` computes exactly what would be written and returns it for
printing; nothing is emitted. `apply()` performs the writes; `reset()` removes everything the
guardian wrote. Idempotent: whole-aspect replaces + fixed incident timestamps, so re-running
`apply()` yields identical graph state with no duplicates. Non-guardian tags/descriptions on
the same datasets are preserved (merge on write, marker-scoped removal on reset).
"""
from __future__ import annotations

import os

from datahub.emitter.mcp import MetadataChangeProposalWrapper as MCP
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.schema_classes import (
    AuditStampClass,
    EditableDatasetPropertiesClass,
    GlobalTagsClass,
    IncidentInfoClass,
    IncidentSourceClass,
    IncidentSourceTypeClass,
    IncidentStateClass,
    IncidentStatusClass,
    IncidentTypeClass,
)

from ..emitter import contract as C
from ..models import Finding
from . import contract as W


def _graph(server: str | None = None) -> DataHubGraph:
    return DataHubGraph(
        DatahubClientConfig(
            server=server or os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090"),
            token=os.environ.get("DATAHUB_GMS_TOKEN") or None,
        )
    )


def _stamp() -> AuditStampClass:
    return AuditStampClass(time=W.FIXED_AUDIT_TIME_MS, actor=W.SYSTEM_ACTOR)


plan = W.plan  # dry-run plan is pure; defined in contract.py so it needs no DataHub SDK


def _merge_tags(g: DataHubGraph, dataset_urn: str, add_tag: str) -> None:
    from datahub.metadata.schema_classes import TagAssociationClass

    existing = g.get_aspect(dataset_urn, GlobalTagsClass)
    tags = [t.tag for t in existing.tags] if existing and existing.tags else []
    if add_tag not in tags:
        tags.append(add_tag)
    g.emit(MCP(entityUrn=dataset_urn, aspect=GlobalTagsClass(
        tags=[TagAssociationClass(tag=t) for t in sorted(tags)])))


def _write_incident(g: DataHubGraph, finding: Finding, ns: C.Namespace,
                    state: str = IncidentStateClass.ACTIVE) -> None:
    urn = W.incident_urn(finding, ns)
    g.emit(MCP(entityUrn=urn, aspect=IncidentInfoClass(
        type=IncidentTypeClass.CUSTOM,
        customType="GOVERNANCE_FINDING",
        title=f"{finding.check} on {W.affected_model(finding)}",
        description=W.description_text(finding),
        entities=[W.dataset_urn(finding, ns)],
        source=IncidentSourceClass(type=IncidentSourceTypeClass.MANUAL),
        created=_stamp(),
        status=IncidentStatusClass(state=state, lastUpdated=_stamp(),
                                   message="opened by OrthoLineage Guardian"),
    )))


def apply(findings: list[Finding], ns: C.Namespace, server: str | None = None) -> list[dict]:
    """Write the Required tier (tag + editable description) + Preferred tier (incident)."""
    if not findings:
        return []  # never write when there are no findings
    g = _graph(server)
    for f in findings:
        urn = W.dataset_urn(f, ns)
        _merge_tags(g, urn, W.governance_tag(f))                                   # Required: tag
        g.emit(MCP(entityUrn=urn, aspect=EditableDatasetPropertiesClass(           # Required: description
            description=W.description_text(f))))
        _write_incident(g, f, ns)                                                  # Preferred: incident
    return plan(findings, ns)


def reset(ns: C.Namespace, server: str | None = None) -> dict:
    """Remove everything the guardian wrote: guardian tags, guardian editable descriptions,
    and guardian incidents. Preserves any non-guardian tags/descriptions."""
    from datahub.metadata.schema_classes import TagAssociationClass

    g = _graph(server)
    removed = {"tags": 0, "descriptions": 0, "incidents": 0}
    for model in C.MODELS:  # sweep all datasets guardian could have touched
        urn = C.dataset_urn(model, ns)
        gt = g.get_aspect(urn, GlobalTagsClass)
        if gt and gt.tags:
            kept = [t for t in gt.tags if not t.tag.startswith(W.GUARDIAN_TAG_PREFIX)]
            if len(kept) != len(gt.tags):
                removed["tags"] += len(gt.tags) - len(kept)
                g.emit(MCP(entityUrn=urn, aspect=GlobalTagsClass(
                    tags=[TagAssociationClass(tag=t.tag) for t in kept])))
        ed = g.get_aspect(urn, EditableDatasetPropertiesClass)
        if ed and (ed.description or "").startswith(W.GUARDIAN_DESC_MARKER):
            removed["descriptions"] += 1
            g.emit(MCP(entityUrn=urn, aspect=EditableDatasetPropertiesClass(description="")))
    for incident_urn in W.all_incident_urns(ns):
        if g.exists(incident_urn):
            g.hard_delete_entity(incident_urn)
            removed["incidents"] += 1
    return removed
