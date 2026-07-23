"""UNVALIDATED_ML_SOURCE check (plan §4.3).

Violation: an `ml_feature_table` column whose column-lineage reaches an `unvalidated`
dataset DIRECTLY — i.e. the unvalidated source is in the column's upstream set while the
`validated` registry that should mediate it is NOT. This distinguishes the planted bypass
(a feature read straight from stg_ed_documentation) from every column's legitimate,
registry-mediated descent from the same raw source. Derived from dataset validation-status
property + column lineage.
"""
from __future__ import annotations

from ..mcp_client import McpClient
from ..models import (
    CHECK_UNVALIDATED_ML_SOURCE,
    RULE_CLASS,
    CheckResult,
    Evidence,
    Finding,
)
from ..emitter import contract as C

ML_MODEL = "ml_feature_table"


async def run(client: McpClient) -> CheckResult:
    findings: list[Finding] = []

    unvalidated: set[str] = set()
    validated: set[str] = set()
    for model in C.MODELS:
        vs = (await client.dataset_facts(model))["structured"].get("guardian_validation_status")
        if vs == ["unvalidated"]:
            unvalidated.add(model)
        elif vs == ["validated"]:
            validated.add(model)

    for col in sorted(await client.column_names(ML_MODEL)):
        ups = await client.column_upstream_models(ML_MODEL, col)
        u_hits = ups & unvalidated
        v_hits = ups & validated
        if u_hits and not v_hits:
            source = sorted(u_hits)[0]
            findings.append(
                Finding(
                    check=CHECK_UNVALIDATED_ML_SOURCE,
                    namespace=client.ns.name,
                    rule_class=RULE_CLASS[CHECK_UNVALIDATED_ML_SOURCE],
                    summary=(
                        f"ML feature {ML_MODEL}.{col} is derived directly from the "
                        f"unvalidated source {source}, bypassing the validated registry."
                    ),
                    evidence=Evidence(
                        feature_column=f"{ML_MODEL}.{col}",
                        unvalidated_source=source,
                        validation_status="unvalidated",
                        path=[source, f"{ML_MODEL}.{col}"],
                        signals_read=[
                            "dataset structuredProperty guardian_validation_status",
                            "column-level lineage (direct upstream, registry not mediating)",
                        ],
                    ),
                )
            )
    return CheckResult(
        check=CHECK_UNVALIDATED_ML_SOURCE, namespace=client.ns.name, findings=findings
    )
