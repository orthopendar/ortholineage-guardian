"""Shared helpers for the Batch-2 write-back capability spike (Python SDK path).

All spikes operate on a SCRATCH target and clean up after themselves so the metadata
graph is left as it was ingested. Nothing here is part of the shipped agent — these are
capability probes whose evidence fills docs/BATCH2_CAPABILITY_MATRIX.md.
"""
from __future__ import annotations

import os
import time

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph

# Scratch target: the least-central model node. Writes here are reverted at the end.
SCRATCH_DATASET = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "ortholineage_guardian.faulty.main.dashboard_report,PROD)"
)
SCRATCH_TAG = "urn:li:tag:guardian_scratch_batch2"


def graph() -> DataHubGraph:
    return DataHubGraph(
        DatahubClientConfig(
            server=os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090"),
            token=os.environ.get("DATAHUB_GMS_TOKEN") or None,
        )
    )


def emit(g: DataHubGraph, entity_urn: str, aspect) -> None:
    g.emit(MetadataChangeProposalWrapper(entityUrn=entity_urn, aspect=aspect))


def now_ms() -> int:
    return int(time.time() * 1000)
