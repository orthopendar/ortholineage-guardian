"""Shared fixtures for the Batch-4 policy-engine integration tests.

These tests exercise the engine against the live dual-namespace DataHub graph
(scripts/ingest_all.sh). They require the `mcp` package and a reachable GMS; when either
is absent the tests SKIP (so the suite stays green in bare environments) — in a set-up
environment they run for real. Run with:

    uv run --with mcp pytest -q
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import urllib.request

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

# Soft-detect mcp so the Batch-1 duckdb tests still collect/run without it.
try:
    import mcp  # noqa: F401

    _HAS_MCP = True
except Exception:
    _HAS_MCP = False

GMS = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8090")


def _gms_up() -> bool:
    try:
        urllib.request.urlopen(f"{GMS}/config", timeout=5)
        return True
    except Exception:
        return False


requires_graph = pytest.mark.skipif(
    not (_HAS_MCP and _gms_up()),
    reason=(
        f"needs the mcp client + a reachable DataHub GMS at {GMS} "
        "(uv run --with mcp pytest; scripts/datahub_up.sh + scripts/ingest_all.sh)"
    ),
)


@pytest.fixture(scope="session")
def faulty_findings():
    from ortholineage_guardian.policy import engine

    return asyncio.run(engine.run("faulty"))


@pytest.fixture(scope="session")
def baseline_findings():
    from ortholineage_guardian.policy import engine

    return asyncio.run(engine.run("baseline"))
