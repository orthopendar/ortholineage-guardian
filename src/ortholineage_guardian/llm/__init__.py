"""LLM layer — explains deterministic findings and drafts remediation (EXPLAIN/DRAFT only).

All LLM output is schema-guarded and entity-checked before use; template mode makes the LLM
optional. The LLM never decides whether a violation exists.
"""
from .draft_remediation import draft
from .explain import explain
from .schema_guard import (
    FindingExplanation,
    GuardRejection,
    RemediationDraft,
    validate_explanation,
    validate_remediation,
)

__all__ = [
    "explain",
    "draft",
    "FindingExplanation",
    "RemediationDraft",
    "GuardRejection",
    "validate_explanation",
    "validate_remediation",
]
