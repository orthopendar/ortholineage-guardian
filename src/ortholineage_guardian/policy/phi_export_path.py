"""PHI_EXPORT_PATH check (plan §4.1).

Violation: a column tagged `DirectIdentifier` has a column-lineage path into a dataset
marked `guardian_data_product = research_export`. Derived purely from MCP signals:
column glossary terms + dataset structured property + column lineage.
"""
from __future__ import annotations

from ..emitter import contract as C
from ..mcp_client import McpClient
from ..models import (
    CHECK_PHI_EXPORT_PATH,
    RULE_CLASS,
    CheckResult,
    Evidence,
    Finding,
)


async def _origin_of(client: McpClient, column: str, candidates: set[str]) -> str | None:
    """The furthest-upstream candidate carrying `column` tagged DirectIdentifier."""
    origin = None
    for m in sorted(candidates):
        ups = await client.column_upstream_models(m, column)
        if not (ups & candidates):  # no other candidate feeds it -> it's the source
            origin = m
            break
    return origin or (sorted(candidates)[0] if candidates else None)


async def run(client: McpClient) -> CheckResult:
    findings: list[Finding] = []

    # 1) export datasets (dataset structured property).
    export_models = []
    for model in C.MODELS:
        facts = await client.dataset_facts(model)
        if facts["structured"].get("guardian_data_product") == ["research_export"]:
            export_models.append((model, facts))

    # 2) which models carry a DirectIdentifier on which column (column glossary term).
    direct_id_carriers: dict[str, set[str]] = {}  # column -> {models}
    for model in C.MODELS:
        for col, terms in (await client.column_terms(model)).items():
            if "DirectIdentifier" in terms:
                direct_id_carriers.setdefault(col, set()).add(model)

    # 3) a DirectIdentifier column present in an export dataset = the identifier reached it.
    for export_model, facts in export_models:
        export_terms = await client.column_terms(export_model)
        for col, terms in export_terms.items():
            if "DirectIdentifier" not in terms:
                continue
            origin = await _origin_of(client, col, direct_id_carriers.get(col, {export_model}))
            path = await client.column_path(origin, col, export_model, col) if origin else []
            if not path:
                path = [f"{origin or export_model}.{col}", f"{export_model}.{col}"]
            findings.append(
                Finding(
                    check=CHECK_PHI_EXPORT_PATH,
                    namespace=client.ns.name,
                    rule_class=RULE_CLASS[CHECK_PHI_EXPORT_PATH],
                    summary=(
                        f"Direct identifier {export_model}.{col} is retained in a research "
                        f"export (must be excluded)."
                    ),
                    evidence=Evidence(
                        identifier_column=f"{export_model}.{col}",
                        export_dataset=export_model,
                        export_properties={
                            "data_product": (facts["structured"].get("guardian_data_product") or [""])[0],
                            "deidentification_required": (
                                facts["structured"].get("guardian_deidentification_required") or [""]
                            )[0],
                        },
                        path=path,
                        signals_read=[
                            "column term DirectIdentifier",
                            "dataset structuredProperty guardian_data_product",
                            "column-level lineage",
                        ],
                    ),
                )
            )
    return CheckResult(check=CHECK_PHI_EXPORT_PATH, namespace=client.ns.name, findings=findings)
