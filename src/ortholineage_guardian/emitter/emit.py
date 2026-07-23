"""Clinical-metadata emitter (Batch 3).

Promotes the governance meta keys into first-class, MCP-readable DataHub signals at the
correct granularity, per `contract.py`. Idempotent: every write is a whole-aspect replace
computed deterministically (fixed audit stamps), so re-running produces byte-identical
aspects and never duplicates or drifts.

No LLM. No check logic. Emit only. Writes via the validated DataHub Python SDK against the
dbt-platform dataset URNs (AUTHORITY SPLIT).
"""
from __future__ import annotations

import os

from datahub.emitter.mcp import MetadataChangeProposalWrapper as MCP
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.schema_classes import (
    AuditStampClass,
    EditableSchemaFieldInfoClass,
    EditableSchemaMetadataClass,
    GlossaryTermAssociationClass,
    GlossaryTermInfoClass,
    GlossaryTermsClass,
    PropertyValueClass,
    SchemaMetadataClass,
    StructuredPropertiesClass,
    StructuredPropertyDefinitionClass,
    StructuredPropertyValueAssignmentClass,
)

from . import contract as C


def _graph(server: str | None = None) -> DataHubGraph:
    return DataHubGraph(
        DatahubClientConfig(
            server=server or os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090"),
            token=os.environ.get("DATAHUB_GMS_TOKEN") or None,
        )
    )


def _stamp() -> AuditStampClass:
    return AuditStampClass(time=C.FIXED_AUDIT_TIME_MS, actor=C.SYSTEM_ACTOR)


def _define_glossary_terms(g: DataHubGraph) -> int:
    for name, definition in C.GLOSSARY_TERMS.items():
        g.emit(
            MCP(
                entityUrn=C.term_urn(name),
                aspect=GlossaryTermInfoClass(
                    name=name, definition=definition, termSource="INTERNAL"
                ),
            )
        )
    return len(C.GLOSSARY_TERMS)


def _define_structured_properties(g: DataHubGraph) -> int:
    for qn, (display, allowed) in C.STRUCTURED_PROPERTIES.items():
        g.emit(
            MCP(
                entityUrn=C.structured_property_urn(qn),
                aspect=StructuredPropertyDefinitionClass(
                    qualifiedName=qn,
                    displayName=display,
                    valueType="urn:li:dataType:datahub.string",
                    cardinality="SINGLE",
                    entityTypes=["urn:li:entityType:datahub.dataset"],
                    allowedValues=[
                        PropertyValueClass(value=v, description=v) for v in allowed
                    ],
                ),
            )
        )
    return len(C.STRUCTURED_PROPERTIES)


def _schema_field_paths(g: DataHubGraph, dataset_urn: str) -> list[str]:
    sm = g.get_aspect(dataset_urn, SchemaMetadataClass)
    return [f.fieldPath for f in sm.fields] if sm else []


def _emit_column_terms(g: DataHubGraph, model: str) -> dict[str, list[str]]:
    """Attach column glossary terms via editableSchemaMetadata (the MCP-readable path)."""
    dataset_urn = C.dataset_urn(model)
    fields = _schema_field_paths(g, dataset_urn)
    applied: dict[str, list[str]] = {}
    field_infos = []
    for field_path in fields:
        term_names = C.COLUMN_TERMS.get(field_path)
        if not term_names:
            continue
        applied[field_path] = term_names
        field_infos.append(
            EditableSchemaFieldInfoClass(
                fieldPath=field_path,
                glossaryTerms=GlossaryTermsClass(
                    terms=[
                        GlossaryTermAssociationClass(urn=C.term_urn(n)) for n in term_names
                    ],
                    auditStamp=_stamp(),
                ),
            )
        )
    # Whole-aspect replace (the emitter owns editableSchemaMetadata) -> idempotent.
    g.emit(
        MCP(
            entityUrn=dataset_urn,
            aspect=EditableSchemaMetadataClass(
                created=_stamp(),
                lastModified=_stamp(),
                editableSchemaFieldInfo=field_infos,
            ),
        )
    )
    return applied


def _emit_dataset_signals(g: DataHubGraph, model: str) -> dict:
    signals = C.DATASET_SIGNALS.get(model)
    if not signals:
        return {}
    dataset_urn = C.dataset_urn(model)
    props = signals.get("properties", {})
    if props:
        g.emit(
            MCP(
                entityUrn=dataset_urn,
                aspect=StructuredPropertiesClass(
                    properties=[
                        StructuredPropertyValueAssignmentClass(
                            propertyUrn=C.structured_property_urn(qn), values=[value]
                        )
                        for qn, value in props.items()
                    ]
                ),
            )
        )
    terms = signals.get("terms", [])
    if terms:
        g.emit(
            MCP(
                entityUrn=dataset_urn,
                aspect=GlossaryTermsClass(
                    terms=[GlossaryTermAssociationClass(urn=C.term_urn(n)) for n in terms],
                    auditStamp=_stamp(),
                ),
            )
        )
    return signals


def emit_all(server: str | None = None) -> None:
    """Define the vocabulary, then apply column + dataset signals. Idempotent."""
    C.assert_amendment()
    g = _graph(server)

    n_terms = _define_glossary_terms(g)
    n_props = _define_structured_properties(g)
    print(f"[define] {n_terms} glossary terms, {n_props} structured properties")

    for model in C.MODELS:
        col = _emit_column_terms(g, model)
        ds = _emit_dataset_signals(g, model)
        col_desc = ", ".join(f"{k}={v}" for k, v in col.items()) or "-"
        ds_props = ds.get("properties", {})
        ds_terms = ds.get("terms", [])
        print(f"[emit ] {model}")
        print(f"          columns : {col_desc}")
        if ds_props or ds_terms:
            print(f"          dataset : props={ds_props} terms={ds_terms}")

    print("[done ] clinical metadata emitted (idempotent).")


def main() -> None:
    emit_all()


if __name__ == "__main__":
    main()
