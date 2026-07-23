"""Capability matrix Row 3 — WRITE A TAG via the DataHub Python SDK.

Writes a scratch governance tag onto a dataset, reads it back to confirm, then removes
it (cleanup). Proves the write primitive the tiered write-back's Required tier depends on.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with 'acryl-datahub[datahub-rest]' python scripts/capability_spike/row3_write_tag.py
"""
from __future__ import annotations

from datahub.metadata.schema_classes import GlobalTagsClass, TagAssociationClass

from _common import SCRATCH_DATASET, SCRATCH_TAG, emit, graph


def main() -> None:
    g = graph()

    print(f"[write] adding tag {SCRATCH_TAG}\n        -> {SCRATCH_DATASET}")
    emit(g, SCRATCH_DATASET, GlobalTagsClass(tags=[TagAssociationClass(tag=SCRATCH_TAG)]))

    read = g.get_aspect(SCRATCH_DATASET, GlobalTagsClass)
    tags = [t.tag for t in read.tags] if read else []
    print(f"[read ] tags now on dataset: {tags}")
    assert SCRATCH_TAG in tags, "tag write not observed on read-back"
    print("[PROVEN] tag write + read-back succeeded")

    # cleanup: remove all scratch tags
    emit(g, SCRATCH_DATASET, GlobalTagsClass(tags=[]))
    after = g.get_aspect(SCRATCH_DATASET, GlobalTagsClass)
    print(f"[clean] tags after cleanup: {[t.tag for t in after.tags] if after else []}")


if __name__ == "__main__":
    main()
