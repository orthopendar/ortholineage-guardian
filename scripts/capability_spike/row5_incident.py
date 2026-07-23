"""Capability matrix Row 5 (Preferred tier) — CREATE AN INCIDENT via the Python SDK.

Attempts to create a DataHub incident entity attached to a dataset, read it back, then
resolve + soft-delete it (cleanup). If incident creation is unsupported on this OSS
build, the failure is captured verbatim for the matrix — Row 5 is Preferred, never a
dependency of the Required tier.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with 'acryl-datahub[datahub-rest]' python scripts/capability_spike/row5_incident.py
"""
from __future__ import annotations

import traceback

from datahub.metadata.schema_classes import (
    AuditStampClass,
    IncidentInfoClass,
    IncidentSourceClass,
    IncidentSourceTypeClass,
    IncidentStateClass,
    IncidentStatusClass,
    IncidentTypeClass,
)

from _common import SCRATCH_DATASET, emit, graph, now_ms

INCIDENT_URN = "urn:li:incident:guardian-scratch-batch2"
ACTOR = "urn:li:corpuser:datahub"


def main() -> None:
    g = graph()
    try:
        stamp = AuditStampClass(time=now_ms(), actor=ACTOR)
        print(f"[write] creating incident {INCIDENT_URN}\n        on {SCRATCH_DATASET}")
        emit(
            g,
            INCIDENT_URN,
            IncidentInfoClass(
                type=IncidentTypeClass.CUSTOM,
                customType="GOVERNANCE_FINDING",
                title="[scratch] STALE_REFERENCE on dashboard_report",
                description="Batch-2 capability probe: incident creation test.",
                entities=[SCRATCH_DATASET],
                source=IncidentSourceClass(type=IncidentSourceTypeClass.MANUAL),
                created=stamp,
                status=IncidentStatusClass(
                    state=IncidentStateClass.ACTIVE, lastUpdated=stamp,
                    message="opened by capability spike",
                ),
            ),
        )
        read = g.get_aspect(INCIDENT_URN, IncidentInfoClass)
        print(f"[read ] incident state={read.status.state!r} entities={read.entities}")
        assert read and read.status.state == IncidentStateClass.ACTIVE
        print("[PROVEN] incident creation + read-back succeeded")

        # cleanup: hard-delete the scratch incident entity. (The incident entity does
        # not accept a standalone `status` aspect, so soft-delete-by-status returns 422;
        # hard_delete_entity removes it cleanly.)
        g.hard_delete_entity(INCIDENT_URN)
        print(f"[clean] incident hard-deleted; exists={g.exists(INCIDENT_URN)}")
    except Exception:
        print("[FAILED] incident creation raised:")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
