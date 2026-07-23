# Migration impact report

**Change:** the encounter timestamp `arrival_time` was renamed to `ed_arrival_datetime` in `trauma_registry`.

**Namespace analysed:** `faulty`  ·  **deterministic findings:** 3

This report is produced by the governance agent from DataHub metadata alone (lineage, schema aspects, glossary terms, structured properties) — never by reading the dbt SQL.

## Affected downstream datasets / columns

Reached by column-level lineage traversal from the renamed field:

- `dashboard_report.arrival_time` — carries the renamed encounter timestamp
- `dq_metrics.ed_arrival_datetime` — carries the renamed encounter timestamp
- `ml_feature_table.ed_arrival_datetime` — carries the renamed encounter timestamp
- `research_export.ed_arrival_datetime` — carries the renamed encounter timestamp

## Governance findings

### PHI_EXPORT_PATH  (export governance)

Direct identifier research_export.patient_id is retained in a research export (must be excluded).

- identifier column: `research_export.patient_id`
- export dataset: `research_export`  {'data_product': 'research_export', 'deidentification_required': 'true'}
- lineage path: `stg_ed_documentation.patient_id` -> `trauma_registry.patient_id` -> `research_export.patient_id`
- signals read (metadata only): column term DirectIdentifier, dataset structuredProperty guardian_data_product, column-level lineage

### MISSINGNESS_COLLAPSE  (completeness)

Explicit-missingness contract on gcs_total collapsed: trauma_registry keeps gcs_total but dropped the paired gcs_total_missingness carried by stg_ed_documentation.

- source column: `stg_ed_documentation.gcs_total`  (paired: `gcs_total_missingness`)
- collapsed in: `trauma_registry`  (source: `stg_ed_documentation`)
- lineage path: `stg_ed_documentation.gcs_total` -> `trauma_registry.gcs_total`
- signals read (metadata only): column term ExplicitMissingness, schema shape (paired column presence/absence), column-level lineage

### UNVALIDATED_ML_SOURCE  (readiness)

ML feature ml_feature_table.raw_mode_of_arrival_feature is derived directly from the unvalidated source stg_ed_documentation, bypassing the validated registry.

- feature column: `ml_feature_table.raw_mode_of_arrival_feature`
- unvalidated source: `stg_ed_documentation` (validation_status=unvalidated)
- lineage path: `stg_ed_documentation` -> `ml_feature_table.raw_mode_of_arrival_feature`
- signals read (metadata only): dataset structuredProperty guardian_validation_status, column-level lineage (direct upstream, registry not mediating)

## Migration-drift observation (reported alongside, not a check)

- stale reference: dashboard_report.arrival_time persists after trauma_registry renamed it to ed_arrival_datetime

## Proposed remediation

See `examples/remediation/remediation.patch` — a `git apply`-able dbt patch that drops the direct identifier from the export, restores the paired missingness state column, repoints the ML feature to the validated registry, and renames the stale `arrival_time` reference to `ed_arrival_datetime`.
