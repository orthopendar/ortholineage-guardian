#!/usr/bin/env python3
"""Entry point: emit the clinical governance metadata into DataHub (Batch 3).

Promotes the governance meta keys into MCP-readable DataHub signals per
`src/ortholineage_guardian/emitter/contract.py`. Idempotent — safe to re-run.

    export DATAHUB_GMS_URL=http://localhost:8090
    uv run --with 'acryl-datahub[datahub-rest]' python scripts/emit_clinical_metadata.py

Reads DATAHUB_GMS_URL / DATAHUB_GMS_TOKEN from the environment (see .env.example).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from ortholineage_guardian.emitter import emit_all  # noqa: E402

if __name__ == "__main__":
    emit_all()
