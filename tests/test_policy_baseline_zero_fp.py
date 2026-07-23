"""BASELINE namespace: ZERO false positives. This is the headline claim.

The baseline graph carries the full clinical contract (same terms/properties emitted) but a
CLEAN schema/lineage: research_export has no patient_id, trauma_registry keeps the paired
gcs_total_missingness, and ml_feature_table has no direct stg edge. The deterministic engine
must therefore produce exactly zero findings.
"""
from __future__ import annotations

from conftest import requires_graph


@requires_graph
def test_baseline_has_zero_findings(baseline_findings):
    assert baseline_findings == [], (
        "baseline must produce ZERO findings (false-positive test bed); got: "
        + ", ".join(f"{f.check}:{f.summary}" for f in baseline_findings)
    )


@requires_graph
def test_baseline_count_is_zero(baseline_findings):
    assert len(baseline_findings) == 0
