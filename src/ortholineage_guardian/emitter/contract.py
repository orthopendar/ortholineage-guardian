"""The FROZEN clinical-metadata contract (Batch 3).

This module is the single source of truth for what governance signals the emitter writes
into DataHub, at what granularity, and in what representation. Batch 4's policy engine
reads ONLY what this contract promises (via MCP) — it never reads dbt SQL.

Representation decision (proven in the Batch-2/3 capability spike, rows 6-7):

  * COLUMN-level signals are emitted as GLOSSARY TERMS attached through the dataset's
    `editableSchemaMetadata` aspect. This is the ONLY column-level representation the MCP
    server surfaces (via `list_schema_fields` -> per-field `editedGlossaryTerms: [name]`).
    Structured properties and tags written to schemaField entities do NOT come back
    through the MCP field view, so they are unusable for the checks.

  * DATASET-level facts are emitted as STRUCTURED PROPERTIES (MCP-readable via
    `get_entities` -> `structuredProperties`), plus a DATASET GLOSSARY TERM for the
    semantic class (MCP-readable via `get_entities` -> `glossaryTerms`).

Deliberate additions beyond plan §3.2 (recorded here per the DETECTION-PROVENANCE rule
"if a check needs a signal not in §3.2, add it deliberately and record it"):
  * `EncounterTimestamp` glossary term represents `clinical_semantic: encounter_timestamp`.
    §3.2 mapped clinical_semantic to a column structured property, but column structured
    properties are not MCP-readable, so it is represented as a glossary term instead.
  * `ValidatedSource` glossary term + `validation_status=validated` on trauma_registry —
    the counterpart of UnvalidatedSource, so the ML-source check can positively confirm a
    governed source, not merely the absence of the unvalidated marker.

STANDING PLAN AMENDMENT (binding): `ExplicitMissingness` is emitted for `gcs_total` and
`mechanism_category` ONLY — NEVER for `arrival_time` / `ed_arrival_datetime` (no paired
`_missingness` column; tagging it would manufacture a guaranteed Batch-4 false positive).
`assert_amendment()` enforces this.
"""
from __future__ import annotations

# Deterministic audit-stamp time (fixed so re-runs are byte-identical -> idempotent).
FIXED_AUDIT_TIME_MS = 1704067200000  # 2024-01-01T00:00:00Z
SYSTEM_ACTOR = "urn:li:corpuser:datahub"

DATA_PLATFORM_DBT = "urn:li:dataPlatform:dbt"
DATASET_PREFIX = "ortholineage_guardian.faulty.main"

MODELS = [
    "stg_ed_documentation",
    "trauma_registry",
    "dq_metrics",
    "research_export",
    "ml_feature_table",
    "dashboard_report",
]


def dataset_urn(model: str) -> str:
    return f"urn:li:dataset:({DATA_PLATFORM_DBT},{DATASET_PREFIX}.{model},PROD)"


def term_urn(name: str) -> str:
    # hierarchicalName = guardian.<Name>; MCP returns the short `name` in editedGlossaryTerms.
    return f"urn:li:glossaryTerm:guardian.{name}"


def structured_property_urn(qualified_name: str) -> str:
    return f"urn:li:structuredProperty:{qualified_name}"


# ---------------------------------------------------------------- glossary term catalog
# name -> human definition. The `name` is what MCP returns per column/dataset, so the
# checks match on these exact strings.
GLOSSARY_TERMS: dict[str, str] = {
    "DirectIdentifier": (
        "A direct identifier (e.g. patient_id, medical_record_number). Must never enter a "
        "research export."
    ),
    "QuasiIdentifier": (
        "A quasi-identifier (e.g. an encounter or injury timestamp) — re-identifying in "
        "combination, not alone."
    ),
    "EncounterTimestamp": (
        "Clinical semantic: the emergency-department encounter/arrival timestamp "
        "(clinical_semantic=encounter_timestamp)."
    ),
    "ExplicitMissingness": (
        "Column governed by an explicit missingness contract: absence is recorded in a "
        "paired <field>_missingness state column, not as a bare NULL."
    ),
    "UnvalidatedSource": "Dataset whose validation status is unvalidated.",
    "ValidatedSource": "Dataset whose validation status is validated.",
    "ResearchExport": (
        "De-identified research-export data product; must contain no direct identifiers."
    ),
}

# ------------------------------------------------------- structured-property definitions
# qualifiedName -> (displayName, allowed string values)
STRUCTURED_PROPERTIES: dict[str, tuple[str, list[str]]] = {
    "guardian_validation_status": ("Guardian: validation status", ["validated", "unvalidated"]),
    "guardian_data_product": ("Guardian: data product", ["research_export"]),
    "guardian_deidentification_required": ("Guardian: de-identification required", ["true", "false"]),
}

# ---------------------------------------------------- COLUMN rule: fieldPath -> term names
# Applied to a column wherever it exists in a dataset's schema.
COLUMN_TERMS: dict[str, list[str]] = {
    "patient_id": ["DirectIdentifier"],
    "medical_record_number": ["DirectIdentifier"],
    "arrival_time": ["QuasiIdentifier", "EncounterTimestamp"],        # pre-rename name (stg, stale dashboard_report)
    "ed_arrival_datetime": ["QuasiIdentifier", "EncounterTimestamp"],  # post-rename name
    "injury_datetime": ["QuasiIdentifier"],
    "gcs_total": ["ExplicitMissingness"],
    "mechanism_category": ["ExplicitMissingness"],
}

# --------------------------------------------------- DATASET-level assignments (by model)
# model -> {"properties": {qualifiedName: value}, "terms": [term names]}
DATASET_SIGNALS: dict[str, dict] = {
    "stg_ed_documentation": {
        "properties": {"guardian_validation_status": "unvalidated"},
        "terms": ["UnvalidatedSource"],
    },
    "trauma_registry": {
        "properties": {"guardian_validation_status": "validated"},
        "terms": ["ValidatedSource"],
    },
    "research_export": {
        "properties": {
            "guardian_data_product": "research_export",
            "guardian_deidentification_required": "true",
        },
        "terms": ["ResearchExport"],
    },
}

# Fields for which emitting ExplicitMissingness is FORBIDDEN (standing plan amendment).
_MISSINGNESS_FORBIDDEN = {"arrival_time", "ed_arrival_datetime", "injury_datetime"}


def assert_amendment() -> None:
    """Fail loudly if the contract ever tries to mark a timestamp with ExplicitMissingness."""
    for field, terms in COLUMN_TERMS.items():
        if field in _MISSINGNESS_FORBIDDEN:
            assert "ExplicitMissingness" not in terms, (
                f"AMENDMENT VIOLATION: {field} must never carry ExplicitMissingness"
            )
    # ExplicitMissingness may only be on gcs_total / mechanism_category.
    carriers = {f for f, ts in COLUMN_TERMS.items() if "ExplicitMissingness" in ts}
    assert carriers == {"gcs_total", "mechanism_category"}, (
        f"ExplicitMissingness carriers drifted: {carriers}"
    )
