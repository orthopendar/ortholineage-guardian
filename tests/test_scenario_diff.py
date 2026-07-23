"""Scenario-difference proofs for the OrthoLineage Guardian synthetic pipeline.

Proves, against the built DuckDB files (and the per-scenario dbt manifests when
available), that:

  * BASELINE carries ZERO of the four planted defects, and
  * FAULTY carries EXACTLY the four planted defects.

These tests read the *built artifacts* (schema + data + lineage), not the model SQL,
so they mirror how the later metadata-only policy engine will detect the same defects.

Run standalone after `bash scripts/build.sh`, or as part of it:
    uv run pytest -q
"""
from __future__ import annotations

import json
import pathlib
import re

import duckdb
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
BASELINE_DB = REPO / "baseline.duckdb"
FAULTY_DB = REPO / "faulty.duckdb"
MANIFEST_BASELINE = REPO / "target" / "manifest.baseline.json"
MANIFEST_FAULTY = REPO / "target" / "manifest.faulty.json"
MODELS_DIR = REPO / "models"

DIRECT_IDENTIFIERS = ("patient_id", "medical_record_number")
COLLAPSED_STATES = ("NOT_DOCUMENTED", "NOT_ASSESSED")


# --------------------------------------------------------------------------- helpers
def _require(db: pathlib.Path) -> duckdb.DuckDBPyConnection:
    if not db.exists():
        pytest.fail(f"{db.name} not found — run `bash scripts/build.sh` first.")
    return duckdb.connect(str(db), read_only=True)


def columns(db: pathlib.Path, table: str) -> list[str]:
    con = _require(db)
    try:
        rows = con.execute(
            "select column_name from information_schema.columns "
            "where table_name = ? order by ordinal_position",
            [table],
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def scalar(db: pathlib.Path, sql: str):
    con = _require(db)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


def distinct_states(db: pathlib.Path, table: str, col: str) -> set[str]:
    con = _require(db)
    try:
        rows = con.execute(
            f"select distinct {col} from {table} where {col} is not null"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def manifest_parents(manifest: pathlib.Path, model: str) -> set[str]:
    """Set of parent model short-names that `model` depends on, per the dbt manifest."""
    data = json.loads(manifest.read_text())
    node_key = f"model.ortholineage_guardian.{model}"
    node = data["nodes"][node_key]
    parents = node["depends_on"]["nodes"]
    return {p.split(".")[-1] for p in parents}


# ----------------------------------------------------------------- baseline: zero defects
def test_baseline_no_direct_identifiers_in_research_export():
    """PHI_EXPORT_PATH is absent in baseline: no direct identifier reaches the export."""
    export_cols = columns(BASELINE_DB, "research_export")
    leaked = [c for c in DIRECT_IDENTIFIERS if c in export_cols]
    assert leaked == [], f"baseline research_export leaked direct identifiers: {leaked}"


def test_baseline_paired_state_column_present_and_states_distinct():
    """MISSINGNESS_COLLAPSE is absent in baseline: the paired state column survives
    downstream in trauma_registry AND the distinct explicit states are preserved."""
    reg_cols = columns(BASELINE_DB, "trauma_registry")
    assert "gcs_total_missingness" in reg_cols, (
        "baseline trauma_registry must carry the paired gcs_total_missingness column"
    )
    states = distinct_states(BASELINE_DB, "trauma_registry", "gcs_total_missingness")
    # Both collapse-target states must remain distinguishable downstream.
    for st in COLLAPSED_STATES:
        assert st in states, f"baseline lost distinct state {st}; states={sorted(states)}"
    assert len(states) >= 2, f"expected >=2 distinct states, got {sorted(states)}"


def test_baseline_ml_features_from_registry_only():
    """UNVALIDATED_ML_SOURCE is absent in baseline: no feature is sourced directly from
    the raw stg_ed_documentation; the ML table draws only from trauma_registry."""
    ml_cols = columns(BASELINE_DB, "ml_feature_table")
    assert "raw_mode_of_arrival_feature" not in ml_cols, (
        "baseline ml_feature_table must not carry a raw stg-sourced feature"
    )
    if MANIFEST_BASELINE.exists():
        parents = manifest_parents(MANIFEST_BASELINE, "ml_feature_table")
        assert "stg_ed_documentation" not in parents, (
            f"baseline ml_feature_table must not depend on stg directly; parents={parents}"
        )
        assert "trauma_registry" in parents


def test_baseline_no_stale_arrival_time_reference():
    """STALE_REFERENCE is absent in baseline: the post-rename ed_arrival_datetime is used
    downstream and the pre-rename `arrival_time` name does NOT reappear."""
    report_cols = columns(BASELINE_DB, "dashboard_report")
    assert "ed_arrival_datetime" in report_cols
    assert "arrival_time" not in report_cols, (
        "baseline dashboard_report must not expose the stale `arrival_time` name"
    )
    # No model downstream of the rename should re-introduce the pre-rename name.
    for table in ("trauma_registry", "dq_metrics", "research_export",
                  "ml_feature_table", "dashboard_report"):
        assert "arrival_time" not in columns(BASELINE_DB, table), (
            f"baseline {table} unexpectedly exposes stale `arrival_time`"
        )


# ------------------------------------------------------------------ faulty: exactly four
def test_faulty_phi_export_path():
    """Fixture 1: a direct identifier (patient_id) is retained in research_export."""
    export_cols = columns(FAULTY_DB, "research_export")
    assert "patient_id" in export_cols, "faulty research_export must retain patient_id"
    # And the value actually flows through (not an all-null artifact).
    non_null = scalar(FAULTY_DB, "select count(*) from research_export where patient_id is not null")
    assert non_null > 0


def test_faulty_missingness_collapse():
    """Fixture 2: >=2 distinct explicit states collapse to a single NULL and the paired
    state column is dropped from trauma_registry."""
    reg_cols = columns(FAULTY_DB, "trauma_registry")
    assert "gcs_total_missingness" not in reg_cols, (
        "faulty trauma_registry must drop the paired gcs_total_missingness column"
    )
    # The rows that were NOT_DOCUMENTED and NOT_ASSESSED in the raw source must now be
    # indistinguishable NULLs in the registry's gcs_total.
    con = _require(FAULTY_DB)
    try:
        bad = con.execute(
            """
            select s.gcs_total_missingness, count(*) as n, count(r.gcs_total) as non_null
            from stg_ed_documentation s
            join trauma_registry r on r.registry_case_id = s.registry_case_id
            where s.gcs_total_missingness in ('NOT_DOCUMENTED', 'NOT_ASSESSED')
            group by 1
            """
        ).fetchall()
    finally:
        con.close()
    # Both collapse-target states must be present in the source sample and fully nulled.
    seen = {row[0]: row[2] for row in bad}
    for st in COLLAPSED_STATES:
        assert st in seen, f"expected source rows in state {st}; got {seen}"
        assert seen[st] == 0, f"state {st} should collapse to NULL gcs_total, got {seen[st]} non-null"


def test_faulty_unvalidated_ml_source():
    """Fixture 3: at least one ML feature is read directly from stg_ed_documentation."""
    ml_cols = columns(FAULTY_DB, "ml_feature_table")
    assert "raw_mode_of_arrival_feature" in ml_cols, (
        "faulty ml_feature_table must carry a feature sourced from raw stg"
    )
    if MANIFEST_FAULTY.exists():
        parents = manifest_parents(MANIFEST_FAULTY, "ml_feature_table")
        assert "stg_ed_documentation" in parents, (
            f"faulty ml_feature_table must depend on stg directly; parents={parents}"
        )


def test_faulty_stale_reference():
    """Fixture 4: the pre-rename `arrival_time` name reappears downstream."""
    report_cols = columns(FAULTY_DB, "dashboard_report")
    assert "arrival_time" in report_cols, (
        "faulty dashboard_report must expose the stale `arrival_time` name"
    )
    assert "ed_arrival_datetime" not in report_cols, (
        "faulty dashboard_report should have renamed the output back to the stale name"
    )


# ------------------------------------------------------- structural: exactly four defects
def test_exactly_four_planted_defect_annotations():
    """Every planted defect is annotated in-code and there are exactly four of them."""
    hits = []
    for sql in sorted(MODELS_DIR.rglob("*.sql")):
        for i, line in enumerate(sql.read_text().splitlines(), start=1):
            if "PLANTED DEFECT" in line:
                hits.append((sql.relative_to(REPO).as_posix(), i, line.strip()))
    ids = sorted(re.search(r"PLANTED DEFECT:\s*(\w+)", h[2]).group(1) for h in hits)
    assert len(hits) == 4, f"expected exactly 4 planted-defect annotations, found: {hits}"
    assert ids == ["MISSINGNESS_COLLAPSE", "PHI_EXPORT_PATH",
                   "STALE_REFERENCE", "UNVALIDATED_ML_SOURCE"], ids


def test_baseline_and_faulty_are_separate_databases():
    """The two scenarios build into their own DuckDB files."""
    assert BASELINE_DB.exists() and FAULTY_DB.exists()
    assert BASELINE_DB.resolve() != FAULTY_DB.resolve()
