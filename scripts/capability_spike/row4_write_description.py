"""Capability matrix Row 4 — WRITE A DESCRIPTION via the DataHub Python SDK.

Sets the dataset's EDITABLE description (the UI-editable layer, separate from the
dbt-ingested description, so the ingested docs are never clobbered), reads it back, then
clears it (cleanup). Also demonstrates attaching a remediation summary as the editable
description — the Required tier's "attach a remediation summary" action.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with 'acryl-datahub[datahub-rest]' python scripts/capability_spike/row4_write_description.py
"""
from __future__ import annotations

from datahub.metadata.schema_classes import EditableDatasetPropertiesClass

from _common import SCRATCH_DATASET, emit, graph, now_ms

REMEDIATION_SUMMARY = (
    "[OrthoLineage Guardian scratch] Governance finding STALE_REFERENCE: this report "
    "still exposes the pre-rename column `arrival_time`. Proposed remediation: rename to "
    "`ed_arrival_datetime`. (Batch-2 capability probe; safe to ignore.)"
)


def main() -> None:
    g = graph()

    print("[write] setting editable description (remediation summary)")
    emit(
        g,
        SCRATCH_DATASET,
        EditableDatasetPropertiesClass(
            description=REMEDIATION_SUMMARY, lastModified=None, created=None
        ),
    )

    read = g.get_aspect(SCRATCH_DATASET, EditableDatasetPropertiesClass)
    desc = read.description if read else None
    print(f"[read ] editable description now: {desc!r}")
    assert desc == REMEDIATION_SUMMARY, "description write not observed on read-back"
    print("[PROVEN] description write + read-back succeeded")

    # cleanup: clear the editable description
    emit(g, SCRATCH_DATASET, EditableDatasetPropertiesClass(description=""))
    after = g.get_aspect(SCRATCH_DATASET, EditableDatasetPropertiesClass)
    print(f"[clean] editable description after cleanup: {after.description!r}")


if __name__ == "__main__":
    main()
