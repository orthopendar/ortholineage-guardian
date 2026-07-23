"""Remediation artifact renderers (Batch 6) — deterministic, PR-ready outputs for examples/."""
from .dbt_patch import render_patch
from .impact_report import render_report

__all__ = ["render_patch", "render_report"]
