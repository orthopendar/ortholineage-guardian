"""Render a REAL, APPLICABLE dbt patch from a validated RemediationDraft (Batch 6).

The patch fixes the four planted fixtures by collapsing each faulty scenario-conditional to
its baseline behaviour: faulty-only blocks (retained patient_id, the ML bypass) are removed,
and `{% if faulty %}…{% else %}X{% endif %}` blocks (the missingness collapse, the stale
rename) keep only the clean branch X. The diff is computed from the ACTUAL model files with
`difflib`, so `git apply --check` succeeds. Deterministic (no timestamps) -> golden-stable.
"""
from __future__ import annotations

import difflib
import pathlib

# fixture id -> the single model file whose faulty conditionals it lives in
FIXTURE_FILE = {
    "PHI_EXPORT_PATH": "models/export/research_export.sql",
    "MISSINGNESS_COLLAPSE": "models/registry/trauma_registry.sql",
    "UNVALIDATED_ML_SOURCE": "models/ml/ml_feature_table.sql",
    "STALE_REFERENCE": "models/report/dashboard_report.sql",
}

_FAULTY_IF = "{% if var('scenario') == 'faulty' %}"
_ELSE = "{% else %}"
_ENDIF = "{% endif %}"


def _collapse_faulty(text: str) -> str:
    """Collapse every faulty scenario-conditional to its baseline behaviour."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == _FAULTY_IF:
            depth = 1
            j = i + 1
            else_idx: int | None = None
            while j < len(lines):
                s = lines[j].strip()
                if s.startswith("{% if"):
                    depth += 1
                elif s == _ENDIF:
                    depth -= 1
                    if depth == 0:
                        break
                elif s == _ELSE and depth == 1:
                    else_idx = j
                j += 1
            if else_idx is not None:  # keep the baseline (else) branch only
                out.extend(lines[else_idx + 1 : j])
            # else: faulty-only block -> drop entirely
            i = j + 1
            if i < len(lines) and lines[i].strip() == "":  # tidy one trailing blank line
                i += 1
        else:
            out.append(lines[i])
            i += 1
    return "".join(out)


def _file_diff(repo_root: pathlib.Path, relpath: str) -> str:
    path = repo_root / relpath
    original = path.read_text()
    remediated = _collapse_faulty(original)
    if remediated == original:
        raise ValueError(f"no faulty conditional found to remediate in {relpath}")
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        remediated.splitlines(keepends=True),
        fromfile=f"a/{relpath}",
        tofile=f"b/{relpath}",
        n=3,
    )
    return f"diff --git a/{relpath} b/{relpath}\n" + "".join(diff)


def render_patch(draft, repo_root: pathlib.Path) -> str:
    """Render the four-hunk patch, one file diff per fixture in the draft (sorted by path)."""
    fixtures = {h.fixture for h in draft.patch_hunks}
    unknown = fixtures - set(FIXTURE_FILE)
    if unknown:
        raise ValueError(f"no patch transform for fixtures {sorted(unknown)}")
    relpaths = sorted(FIXTURE_FILE[fx] for fx in fixtures)
    header = (
        "# OrthoLineage Guardian — proposed remediation for the faulty migration.\n"
        "# Generated from validated findings; apply with `git apply`.\n"
    )
    return header + "".join(_file_diff(repo_root, rp) for rp in relpaths)
