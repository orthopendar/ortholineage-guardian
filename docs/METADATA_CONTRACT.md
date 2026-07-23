# Metadata Contract (FROZEN) — Batch 3

This is **Batch 4's input contract.** The policy engine reads ONLY what this file
promises, exclusively through the DataHub **MCP read path** — never the dbt SQL
(DETECTION PROVENANCE). Every signal below was written by the emitter
([`src/ortholineage_guardian/emitter/`](../src/ortholineage_guardian/emitter/)) and
read back through MCP by
[`scripts/mcp_verify_contract.py`](../scripts/mcp_verify_contract.py) (all PASS).

Source of truth for the values: [`emitter/contract.py`](../src/ortholineage_guardian/emitter/contract.py).
Dataset URNs are the **dbt-platform** nodes (Batch 2):
`urn:li:dataset:(urn:li:dataPlatform:dbt,ortholineage_guardian.faulty.main.<model>,PROD)`.

---

## Representation decision (why these aspect types)

The capability spike (BATCH2_CAPABILITY_MATRIX rows 6–7) proved what the MCP server
actually surfaces:

| Granularity | Representation used | MCP tool + exact shape |
|---|---|---|
| **Column** | **Glossary term** via `editableSchemaMetadata` | `list_schema_fields` → `fields[].editedGlossaryTerms: ["<TermName>"]` |
| **Dataset** (facts) | **Structured property** | `get_entities` → `structuredProperties.properties[]` (`qualifiedName` + `values[].stringValue`) |
| **Dataset** (class) | **Glossary term** | `get_entities` → `glossaryTerms.terms[].term.properties.name` |

Column glossary terms attached to the **schemaField entity** and column **structured
properties / tags** are NOT returned by the MCP field view, so they are unusable. Column
signals therefore go through `editableSchemaMetadata` only. Batch 4 parses column signals
from **`editedGlossaryTerms` (a list of term names)**.

---

## Column-level signals — glossary terms (`editedGlossaryTerms`)

Applied to a column wherever it exists in a dataset's schema.

| Governance key (§3.3) | Value | Glossary term (name) | Columns it lands on | Consuming check |
|---|---|---|---|---|
| `sensitivity` | `direct_identifier` | **`DirectIdentifier`** | `patient_id`, `medical_record_number` (stg, trauma_registry, research_export) | **PHI_EXPORT_PATH** |
| `sensitivity` | `quasi_identifier` | **`QuasiIdentifier`** | `ed_arrival_datetime`/`arrival_time`, `injury_datetime` (all datasets carrying them) | impact traversal (context) |
| `clinical_semantic` | `encounter_timestamp` | **`EncounterTimestamp`** | `ed_arrival_datetime`/`arrival_time` | impact traversal (hero field) |
| `missingness_contract` | `explicit` | **`ExplicitMissingness`** | `gcs_total`, `mechanism_category` **only** | **MISSINGNESS_COLLAPSE** |

**Exact MCP shape Batch 4 parses:**

```json
{"fieldPath": "patient_id", "nativeDataType": "VARCHAR", "nullable": false,
 "editedGlossaryTerms": ["DirectIdentifier"]}
{"fieldPath": "gcs_total",  "nativeDataType": "INTEGER", ...,
 "editedGlossaryTerms": ["ExplicitMissingness"]}
{"fieldPath": "ed_arrival_datetime", ...,
 "editedGlossaryTerms": ["EncounterTimestamp", "QuasiIdentifier"]}
```

> **STANDING PLAN AMENDMENT (binding):** `ExplicitMissingness` is emitted for `gcs_total`
> and `mechanism_category` ONLY — NEVER for `arrival_time` / `ed_arrival_datetime`
> (no paired `_missingness` column; tagging it would manufacture a guaranteed baseline
> false positive). Enforced by `contract.assert_amendment()`.

---

## Dataset-level signals — structured properties + a glossary term

| Governance key (§3.3) | Structured property (`qualifiedName`) | Value | Dataset glossary term | Dataset(s) | Consuming check |
|---|---|---|---|---|---|
| `validation_status` | `guardian_validation_status` | `unvalidated` | `UnvalidatedSource` | `stg_ed_documentation` | **UNVALIDATED_ML_SOURCE** |
| `validation_status` | `guardian_validation_status` | `validated` | `ValidatedSource` | `trauma_registry` | **UNVALIDATED_ML_SOURCE** (positive control) |
| `data_product` | `guardian_data_product` | `research_export` | `ResearchExport` | `research_export` | **PHI_EXPORT_PATH** |
| `deidentification_required` | `guardian_deidentification_required` | `true` | — | `research_export` | **PHI_EXPORT_PATH** |

**Exact MCP shape Batch 4 parses (`get_entities`):**

```json
"structuredProperties": {"properties": [
  {"structuredProperty": {"definition": {"qualifiedName": "guardian_validation_status"}},
   "values": [{"stringValue": "unvalidated"}]}]}
"glossaryTerms": {"terms": [
  {"term": {"properties": {"name": "UnvalidatedSource"}}}]}
```

---

## Deliberate additions beyond plan §3.2 (recorded per the DETECTION-PROVENANCE rule)

| Signal | Why added | Rationale |
|---|---|---|
| `EncounterTimestamp` glossary term | §3.2 mapped `clinical_semantic` to a **column structured property**, but column structured properties are **not MCP-readable**. | Represented as a column glossary term so the hero field's semantic is on the MCP read path. |
| `ValidatedSource` term + `validation_status=validated` on `trauma_registry` | §3.2 named only the unvalidated marker. | A positive control so `UNVALIDATED_ML_SOURCE` can confirm a *governed* source, not merely the absence of the unvalidated marker; also feeds the baseline false-positive test. |

Nothing else was invented. `sensitivity`, `missingness_contract`, `validation_status`,
`data_product`, `deidentification_required` are exactly the §3.2 keys.

---

## What each check reads (DETECTION-PROVENANCE summary)

- **PHI_EXPORT_PATH** — a column whose `editedGlossaryTerms` contains `DirectIdentifier`
  has column-lineage into a dataset whose structured property
  `guardian_data_product = research_export` (and `guardian_deidentification_required =
  true`) / glossary term `ResearchExport`.
- **MISSINGNESS_COLLAPSE** — a source column whose `editedGlossaryTerms` contains
  `ExplicitMissingness` (`gcs_total`) loses its paired `<field>_missingness` state column
  downstream (schema-shape diff, read from `schemaMetadata` / `list_schema_fields`).
- **UNVALIDATED_ML_SOURCE** — an `ml_feature_table` column whose lineage terminates in a
  dataset with structured property `guardian_validation_status = unvalidated` / glossary
  term `UnvalidatedSource` (`stg_ed_documentation`), bypassing the `ValidatedSource`
  `trauma_registry`.
- **Impact traversal** (shared substrate) — walks column-lineage from
  `ed_arrival_datetime` (`EncounterTimestamp` / `QuasiIdentifier`); the stale
  `arrival_time` reappears on `dashboard_report` (a naming inconsistency, reported
  alongside, not one of the three checks).

Lineage (table + column) and `schemaMetadata` come from the Batch-2 dbt ingestion; this
contract adds the clinical classification on top. Together they are everything the checks
need — no check reads SQL.

---

## Idempotency

The emitter uses a fixed audit timestamp and whole-aspect replaces, so re-running produces
byte-identical aspects. Verified: aspect SHA-256 hashes are unchanged after a second run
(see Batch-3 report). Re-run any time with:

```bash
export DATAHUB_GMS_URL=http://localhost:8090
uv run --with 'acryl-datahub[datahub-rest]' python scripts/emit_clinical_metadata.py
uv run --with mcp python scripts/mcp_verify_contract.py   # all PASS, exit 0
```
