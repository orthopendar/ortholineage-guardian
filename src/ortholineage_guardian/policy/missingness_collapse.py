"""MISSINGNESS_COLLAPSE check (plan §4.2).

Violation: a value column tagged `ExplicitMissingness` survives into a downstream dataset
that LACKS its paired `<field>_missingness` state column, while an upstream dataset (per
column lineage) still carried BOTH. The explicit governed missingness states have been
collapsed into an indistinguishable bare value. Derived from schema shape + column term +
column lineage — never from row data.
"""
from __future__ import annotations

from ..emitter import contract as C
from ..mcp_client import McpClient
from ..models import (
    CHECK_MISSINGNESS_COLLAPSE,
    RULE_CLASS,
    CheckResult,
    Evidence,
    Finding,
)


async def run(client: McpClient) -> CheckResult:
    findings: list[Finding] = []

    for model in C.MODELS:
        terms = await client.column_terms(model)
        cols = set(terms)
        for field, field_terms in terms.items():
            if "ExplicitMissingness" not in field_terms:
                continue
            paired = f"{field}_missingness"
            if paired in cols:
                continue  # this dataset preserves the pair -> healthy carrier

            # value column present, paired state column absent: confirm an upstream had both.
            source = None
            for upstream in sorted(await client.column_upstream_models(model, field)):
                ucols = await client.column_names(upstream)
                if field in ucols and paired in ucols:
                    source = upstream
                    break
            if source is None:
                continue  # no governed upstream pair -> not a collapse we can attribute

            path = await client.column_path(source, field, model, field)
            if not path:
                path = [f"{source}.{field}", f"{model}.{field}"]
            findings.append(
                Finding(
                    check=CHECK_MISSINGNESS_COLLAPSE,
                    namespace=client.ns.name,
                    rule_class=RULE_CLASS[CHECK_MISSINGNESS_COLLAPSE],
                    summary=(
                        f"Explicit-missingness contract on {field} collapsed: {model} keeps "
                        f"{field} but dropped the paired {paired} carried by {source}."
                    ),
                    evidence=Evidence(
                        source_column=f"{source}.{field}",
                        paired_column=paired,
                        source_dataset=source,
                        collapsed_in_dataset=model,
                        path=path,
                        signals_read=[
                            "column term ExplicitMissingness",
                            "schema shape (paired column presence/absence)",
                            "column-level lineage",
                        ],
                    ),
                )
            )
    return CheckResult(
        check=CHECK_MISSINGNESS_COLLAPSE, namespace=client.ns.name, findings=findings
    )
