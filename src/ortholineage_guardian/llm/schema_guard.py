"""Schema guard for LLM output (Batch 5) — written FIRST, before any prompting.

AUTHORITY SPLIT is load-bearing here: the LLM receives deterministic Findings as INPUT and
produces prose + draft-patch text as OUTPUT. It never decides whether a violation exists,
never adds/removes a finding, never changes severity, never invents an entity. Everything
it returns is validated here before use. Validation = parse + REJECT ON MISMATCH (no silent
coercion, no repair loops).

Two guards on top of Pydantic parsing:

  * ENTITY WHITELIST GUARD (the anti-hallucination property) — every dataset / column / term
    name appearing in the output must be present in the source Finding's evidence or in the
    frozen metadata contract. Any unknown entity → reject.

  * CONTRACT-KNOWLEDGE GUARD — the engine reads metadata only, so row-level facts (row/record
    counts, "found"/"observed" state values) are NOT observable and must never be asserted.
    The missingness vocabulary may be cited ONLY as contract knowledge (what the contract
    admits), never as observed rows. Any observation claim → reject (see PLAN AMENDMENT).
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from ..emitter import contract as C
from ..models import Finding


class GuardRejection(Exception):
    """Raised when LLM output fails Pydantic parsing or either guard. Never coerced away."""


# --------------------------------------------------------------------- validated LLM types
class FindingExplanation(BaseModel):
    """One deterministic Finding → one human-readable governance explanation."""

    model_config = {"extra": "forbid"}

    check: str
    namespace: str
    title: str
    what_broke: str
    why_it_matters: str
    downstream_impact: str
    remediation_summary: str
    affected_entities: list[str] = Field(default_factory=list)


class PatchHunk(BaseModel):
    model_config = {"extra": "forbid"}

    model: str            # dbt model the hunk edits (must be a known dataset)
    fixture: str          # the fixture id this hunk remediates
    description: str
    before: str
    after: str


class RemediationDraft(BaseModel):
    """Findings + impact → a DRAFT dbt patch + impact-report prose. DRAFT ONLY (Batch 6
    renders to files / writes back)."""

    model_config = {"extra": "forbid"}

    namespace: str
    summary: str
    findings_covered: list[str] = Field(default_factory=list)
    patch_hunks: list[PatchHunk] = Field(default_factory=list)
    impact_report_markdown: str


# --------------------------------------------------------------------- entity whitelist base
def _base_known_entities() -> set[str]:
    known: set[str] = set(C.MODELS)
    known |= set(C.GLOSSARY_TERMS)                 # DirectIdentifier, ExplicitMissingness, ...
    known |= set(C.STRUCTURED_PROPERTIES)          # guardian_validation_status, ...
    known |= set(C.COLUMN_TERMS)                   # governed value columns
    # paired state columns the contract guarantees for explicit-missingness fields
    known |= {f"{f}_missingness" for f, terms in C.COLUMN_TERMS.items() if "ExplicitMissingness" in terms}
    # governance rule classes + the structured-property values the contract admits
    known |= {"export_governance", "completeness", "readiness", "temporal_integrity"}
    known |= {"research_export", "validated", "unvalidated", "true", "false"}
    return known


BASE_KNOWN = _base_known_entities()

# entity-shaped tokens: bare snake_case idents and dotted dataset.column refs
_IDENT = r"[a-z][a-z0-9_]*"
_DOTTED_RE = re.compile(rf"\b({_IDENT})\.({_IDENT})\b")

# CONTRACT-KNOWLEDGE guard: assertions that imply the system inspected row data.
_ROW_COUNT_RE = re.compile(
    r"\b\d+\s+(rows?|records?|cases?|patients?|values?|nulls?|entries)\b", re.IGNORECASE
)
_MISSINGNESS_TOKENS = r"(?:NOT_DOCUMENTED|NOT_ASSESSED|NOT_APPLICABLE|PRESENT|UNKNOWN)"
_OBSERVE = r"(?:found|observed|contains?|contained|detected|counted|saw|seen|were|was|appear(?:ed|s)?)"
_OBSERVED_STATE_RE = re.compile(
    rf"\b{_OBSERVE}\b[^.]{{0,40}}\b{_MISSINGNESS_TOKENS}\b|"
    rf"\b{_MISSINGNESS_TOKENS}\b[^.]{{0,40}}\b{_OBSERVE}\b",
    re.IGNORECASE,
)


def _finding_entities(finding: Finding) -> set[str]:
    """Every dataset / column token grounded in this finding's evidence."""
    e = finding.evidence
    out: set[str] = set()
    scalar_fields = [
        e.identifier_column, e.export_dataset, e.source_column, e.paired_column,
        e.source_dataset, e.collapsed_in_dataset, e.feature_column, e.unvalidated_source,
    ]
    for val in scalar_fields + list(e.path):
        if not val:
            continue
        for part in str(val).split("."):
            part = part.strip()
            if part:
                out.add(part)
    return out


def _whitelist_for(findings: list[Finding]) -> set[str]:
    wl = set(BASE_KNOWN)
    for f in findings:
        wl |= _finding_entities(f)
    return wl


def _scan_entities(text: str) -> set[str]:
    """Extract entity-shaped tokens from prose: both sides of any dotted ref, plus any bare
    token that is a known dataset/term (so an invented bare dataset in `affected_entities`
    is caught by the field check, and invented dotted refs are caught here)."""
    found: set[str] = set()
    for m in _DOTTED_RE.finditer(text):
        found.add(m.group(1))
        found.add(m.group(2))
    return found


def _atomize(tokens: set[str]) -> set[str]:
    """Split dotted dataset.column refs into their atomic parts for whitelist checking."""
    out: set[str] = set()
    for t in tokens:
        for part in str(t).split("."):
            part = part.strip()
            if part:
                out.add(part)
    return out


def _assert_entities(tokens: set[str], whitelist: set[str], where: str) -> None:
    unknown = sorted(t for t in _atomize(tokens) if t not in whitelist)
    if unknown:
        raise GuardRejection(
            f"entity-whitelist violation in {where}: unknown entities {unknown} "
            f"(not in the finding evidence or metadata contract)"
        )


def _assert_no_observation(text: str, where: str) -> None:
    if _ROW_COUNT_RE.search(text):
        raise GuardRejection(
            f"contract-knowledge violation in {where}: asserts an observed row/record/value "
            f"count (the engine reads metadata only — row facts are not observable)"
        )
    if _OBSERVED_STATE_RE.search(text):
        raise GuardRejection(
            f"contract-knowledge violation in {where}: presents a missingness state as an "
            f"observed data value (it may be cited only as what the contract admits)"
        )


# ------------------------------------------------------------------------------- validators
def _load(raw: str | dict) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GuardRejection(f"malformed JSON from LLM: {exc}") from exc


def validate_explanation(raw: str | dict, finding: Finding) -> FindingExplanation:
    data = _load(raw)
    try:
        exp = FindingExplanation.model_validate(data)
    except ValidationError as exc:
        raise GuardRejection(f"explanation failed schema validation: {exc}") from exc

    # the LLM must not relabel the deterministic decision
    if exp.check != finding.check:
        raise GuardRejection(f"explanation.check '{exp.check}' != finding.check '{finding.check}'")
    if exp.namespace != finding.namespace:
        raise GuardRejection("explanation.namespace does not match the finding")

    whitelist = _whitelist_for([finding])
    prose = " ".join([exp.title, exp.what_broke, exp.why_it_matters,
                      exp.downstream_impact, exp.remediation_summary])
    _assert_entities(set(exp.affected_entities), whitelist, "affected_entities")
    _assert_entities(_scan_entities(prose), whitelist, "explanation prose")
    _assert_no_observation(prose, "explanation prose")
    return exp


def validate_remediation(raw: str | dict, findings: list[Finding]) -> RemediationDraft:
    data = _load(raw)
    try:
        draft = RemediationDraft.model_validate(data)
    except ValidationError as exc:
        raise GuardRejection(f"remediation failed schema validation: {exc}") from exc

    # the LLM must not invent or drop findings
    declared = {f.check for f in findings}
    covered = set(draft.findings_covered)
    if not covered <= declared:
        raise GuardRejection(f"remediation covers non-existent findings: {sorted(covered - declared)}")

    whitelist = _whitelist_for(findings)
    for hunk in draft.patch_hunks:
        if hunk.model not in whitelist:
            raise GuardRejection(f"patch hunk targets unknown model '{hunk.model}'")
        blob = " ".join([hunk.description, hunk.before, hunk.after])
        _assert_entities(_scan_entities(blob), whitelist, f"patch hunk for {hunk.model}")
        _assert_no_observation(blob, f"patch hunk for {hunk.model}")
    _assert_entities(_scan_entities(draft.summary + " " + draft.impact_report_markdown),
                     whitelist, "remediation prose")
    _assert_no_observation(draft.summary + " " + draft.impact_report_markdown, "remediation prose")
    return draft
