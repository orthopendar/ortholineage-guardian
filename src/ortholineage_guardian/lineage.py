"""Impact-graph traversal over MCP column-level lineage (Batch 4).

Shared substrate, not a check: from the changed hero field (ed_arrival_datetime), walk
column-level lineage to name every downstream dataset/column affected. Also surfaces the
STALE_REFERENCE migration-drift observation — reported ALONGSIDE the three checks, not as
one of them.

Reads only MCP lineage + schema signals (DETECTION PROVENANCE).
"""
from __future__ import annotations

from .mcp_client import McpClient
from .models import ImpactNode

HERO_MODEL = "trauma_registry"
HERO_COLUMN = "ed_arrival_datetime"
PRE_RENAME_COLUMN = "arrival_time"


async def impact_of_hero_field(client: McpClient) -> list[ImpactNode]:
    """Downstream datasets/columns reached from trauma_registry.ed_arrival_datetime."""
    nodes: list[ImpactNode] = []
    downstream = await client.column_downstream_models(HERO_MODEL, HERO_COLUMN)
    for model in sorted(downstream):
        cols = await client.column_names(model)
        # the affected column is the encounter timestamp under either name
        for cand in (HERO_COLUMN, PRE_RENAME_COLUMN):
            if cand in cols:
                nodes.append(ImpactNode(dataset=model, column=cand,
                                        note="carries the renamed encounter timestamp"))
    return nodes


async def detect_stale_reference(client: McpClient) -> ImpactNode | None:
    """Migration-drift observation: the registry exposes the post-rename
    `ed_arrival_datetime`, yet a downstream dataset still exposes the pre-rename
    `arrival_time`. Purely schema-derived (a naming inconsistency in the graph)."""
    registry_cols = await client.column_names(HERO_MODEL)
    if HERO_COLUMN not in registry_cols or PRE_RENAME_COLUMN in registry_cols:
        return None  # registry hasn't performed the rename; nothing to lag behind
    # look for any downstream model still exposing the stale name
    for model in ("dashboard_report", "dq_metrics", "research_export", "ml_feature_table"):
        cols = await client.column_names(model)
        if PRE_RENAME_COLUMN in cols:
            return ImpactNode(
                dataset=model,
                column=PRE_RENAME_COLUMN,
                note=(
                    f"stale reference: {model}.{PRE_RENAME_COLUMN} persists after "
                    f"{HERO_MODEL} renamed it to {HERO_COLUMN}"
                ),
            )
    return None
