"""DETECTION PROVENANCE guard.

Proves the engine decides from DataHub metadata ALONE: while it runs, it must open no dbt
SQL, no dbt manifest/catalog JSON, and no DuckDB database. We install a CPython audit hook
(`sys.addaudithook`) that records every `open` / `os.open` in THIS process during an engine
run, then assert none of the recorded paths is a forbidden artifact.

Note the MCP server runs as a SEPARATE process (`uvx mcp-server-datahub`); its file access
is irrelevant — the point is that OUR engine process reaches the verdict purely over the
MCP wire. The engine actually producing findings confirms the hook was active during real
metadata reads, not a no-op.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

from conftest import requires_graph

# path patterns the engine must NEVER open
_FORBIDDEN_BASENAME = re.compile(r"^(manifest|catalog)(\.(baseline|faulty))?\.json$")
_FORBIDDEN_SUFFIX = re.compile(r"\.sql$|\.duckdb($|\.)")

_opened: list[str] = []
_recording = {"on": False}


def _audit(event: str, args) -> None:
    if not _recording["on"]:
        return
    if event in ("open", "os.open") and args:
        target = args[0]
        if isinstance(target, (str, bytes, os.PathLike)):
            _opened.append(os.fspath(target) if not isinstance(target, bytes) else target.decode("utf-8", "replace"))


sys.addaudithook(_audit)  # permanent; gated by _recording["on"]


def _forbidden(path: str) -> bool:
    return bool(_FORBIDDEN_SUFFIX.search(path) or _FORBIDDEN_BASENAME.match(os.path.basename(path)))


@requires_graph
def test_engine_opens_no_sql_manifest_or_duckdb():
    from ortholineage_guardian.policy import engine

    _opened.clear()
    _recording["on"] = True
    try:
        findings = asyncio.run(engine.run("faulty"))
    finally:
        _recording["on"] = False

    # the engine genuinely ran and reached a verdict over MCP
    assert findings, "engine produced no findings — guard would be vacuous"

    offenders = sorted({p for p in _opened if _forbidden(p)})
    assert not offenders, (
        "engine violated DETECTION PROVENANCE by opening forbidden artifacts:\n  "
        + "\n  ".join(offenders)
    )


def test_guard_matcher_recognises_forbidden_paths():
    # unit-level sanity that the matcher forbids the right things and allows code files
    assert _forbidden("/repo/target/manifest.json")
    assert _forbidden("/repo/target/catalog.json")
    assert _forbidden("/repo/models/registry/trauma_registry.sql")
    assert _forbidden("/repo/faulty.duckdb")
    assert not _forbidden("/repo/src/ortholineage_guardian/policy/engine.py")
    assert not _forbidden("/repo/src/ortholineage_guardian/models.py")
