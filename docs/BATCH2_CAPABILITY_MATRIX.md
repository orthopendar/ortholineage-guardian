# Batch 2 — DataHub Capability Matrix (gate artifact)

This document is the **gate** for Batches 3–6. Everything below is backed by pasted
evidence produced against a live local DataHub OSS quickstart ingesting the **faulty**
dbt state. Reported-but-unproven claims are not accepted here.

**Status: all read primitives (Rows 1–2) and all write primitives (Rows 3–5) PROVEN.**
Column-level lineage **resolved**. Ownership **mapped**.

---

## Versions (resolved at execution time — not guessed)

| Component | Version | How obtained |
|---|---|---|
| DataHub CLI (`acryl-datahub`) | **1.6.0.15** | `uv tool install --python 3.11 acryl-datahub[dbt]` (isolated) |
| DataHub quickstart plan | **v1.5.0.6** | quickstart versioning (`docker_tag=v1.5.0.6`) |
| GMS image | `acryldata/datahub-gms:v1.5.0.6` | `docker ps` (also `gms_version: v1.5.0.6` in ingest sink report) |
| Frontend image | `acryldata/datahub-frontend-react:v1.5.0.6` | `docker ps` |
| Actions image | `acryldata/datahub-actions:v1.5.0.6-slim` | `docker ps` |
| MySQL | `mysql:8.2` | `docker ps` |
| Search | `opensearchproject/opensearch:2.19.3` | `docker ps` |
| Kafka | `confluentinc/cp-kafka:8.0.0` | `docker ps` |
| Official MCP server | **`mcp-server-datahub` 0.6.0** | `uvx mcp-server-datahub@latest` (stdio) |
| Python (CLI + MCP + SDK) | 3.11.14 | uv-managed |

### Dependency-resolution isolation

`acryl-datahub` is **not** added to the dbt project's `pyproject.toml`. It is installed as
an **isolated `uv tool`** (the `datahub` CLI + dbt ingestion), and SDK scripts run in
ephemeral overlays via `uv run --with 'acryl-datahub[datahub-rest]'`. This keeps the dbt
runtime environment (dbt-core 1.12.0 / dbt-duckdb 1.10.1) minimal and untouched.

For the record, this isolation is a **design choice, not forced by a conflict** — the two
resolve together cleanly in an overlay:

```
acryl-datahub 1.6.0.15 + dbt-core 1.12.0 coexist in overlay: OK
```

`acryl-datahub`'s dbt source additionally needs the `[dbt]` extra (a first attempt failed
with `dbt is disabled due to a missing dependency: boto3`); installing
`acryl-datahub[dbt]` fixes it.

---

## Environment quirk that had to be fixed (documented for reproducibility)

DataHub GMS publishes host port **8080** by default. On this machine 8080 was already held
by an unrelated local service. The bind failed
(`failed to bind host port 0.0.0.0:8080/tcp: address already in use`), so the GMS container
never attached to the docker network — its resolver fell back to the host stub
`127.0.0.53` (unreachable from inside a container) and it hung forever in its
dependency-wait loop (`Waiting for tcp://mysql:3306: ... lookup mysql on 127.0.0.53:53:
read: connection refused`). It was **not** OOM (`OOMKilled=false`) and not a DataHub bug.

**Fix (baked into `scripts/datahub_up.sh`):** remap GMS to a free host port via the compose
env override the quickstart file already exposes
(`published: ${DATAHUB_MAPPED_GMS_PORT:-8080}`). We publish GMS on **8090**. After the
remap GMS attached (`datahub_network ip=172.21.0.6`, resolver `127.0.0.11`) and booted
healthy. All other quickstart ports (frontend 9002, mysql 3306, kafka 9092, opensearch
9200) bound without conflict.

`docker ps` (healthy stack):

```
datahub-datahub-gms-quickstart-1     Up (healthy)   0.0.0.0:8090->8080/tcp
datahub-frontend-quickstart-1        Up (healthy)   0.0.0.0:9002->9002/tcp
datahub-datahub-actions-quickstart-1 Up
datahub-kafka-broker-1               Up (healthy)
datahub-mysql-1                      Up (healthy)
datahub-opensearch-1                 Up (healthy)
```

---

## Ingestion (faulty dbt state → DataHub)

Recipe: [`ingest/dbt_source.yml`](../ingest/dbt_source.yml) over the canonical
`target/manifest.json` + `target/catalog.json` (NOT the per-scenario pytest copies).

```
Source (dbt) report:  events_produced: 28 ; sql_parser_parse_failures: 0 ;
                      node_cll_failures: 0 ; failures: [] ; warnings: []
  aspects (Model x6): schemaMetadata:6  upstreamLineage:6  fineGrainedLineages:6
                      ownership:6  datasetProperties:6  subTypes:6
Sink (datahub-rest):  total_records_written: 30 ; failures: [] ; gms_version: v1.5.0.6
Pipeline finished successfully; produced 30 events in 2.07 seconds.
```

### Dataset URN scheme (load-bearing for Batches 3–4)

The dbt source emits **two** platforms. The **`dbt`-platform model nodes carry the rich
metadata** (schema, DAG lineage, column-level lineage, ownership); the `duckdb` datasets
are thin physical siblings (each with an upstream = its dbt node). **Batches 3–4 target the
dbt URNs:**

```
urn:li:dataset:(urn:li:dataPlatform:dbt,ortholineage_guardian.faulty.main.<model>,PROD)
```

### Table-level DAG (matches Batch 1 exactly, incl. the faulty dual-parent)

```
trauma_registry   <- ['stg_ed_documentation']
dq_metrics        <- ['trauma_registry']
research_export   <- ['trauma_registry']
ml_feature_table  <- ['stg_ed_documentation', 'trauma_registry']   <-- DUAL PARENT (UNVALIDATED_ML_SOURCE substrate)
dashboard_report  <- ['ml_feature_table']
```

### Column-level lineage — VERDICT: **RESOLVED** (not table-level fallback)

`node_cll_failures: 0`, `fineGrainedLineages: 6`. Field-level edges resolve, including the
two the checks depend on:

```
ml_feature_table.ed_arrival_datetime        <- [('trauma_registry', 'ed_arrival_datetime')]
ml_feature_table.raw_mode_of_arrival_feature <- [('stg_ed_documentation', 'mode_of_arrival')]  # the UNVALIDATED bypass, column-level
```

We are in the **column-lineage-resolved world** — the plan's table-level fallback
(risk register) is **not** needed.

### Ownership mapping — VERDICT: **MAPPED**

`schema.yml` `config.meta.owner` identifiers surface as DataHub **CorpUser owners** with
ownership type `DATAOWNER`:

```
stg_ed_documentation owner=urn:li:corpuser:ed-source-steward@ortholineage.example   type=DATAOWNER
trauma_registry      owner=urn:li:corpuser:registry-coordinator@ortholineage.example type=DATAOWNER
research_export      owner=urn:li:corpuser:research-export-owner@ortholineage.example type=DATAOWNER
```

(The owner string also appears as a `customProperties` entry `owner=...`.) The README may
state ownership is surfaced in DataHub. **Note for Batch 3:** the governance `meta` keys
(`data_product`, `deidentification_required`, `validation_status`, `sensitivity`,
`clinical_semantic`, `missingness_contract`) currently land as **dataset
`customProperties`**, NOT yet as tags / structured properties / glossary terms — promoting
them is exactly the Batch-3 emitter's job.

---

## The 5-row write-back capability matrix

| # | Capability | Path | Result | Evidence |
|---|---|---|---|---|
| 1 | Read lineage | MCP Server | ✅ **PROVEN** | `get_lineage` → upstream `stg_ed_documentation` |
| 2 | Read schema metadata + tags/properties | MCP Server | ✅ **PROVEN** | `list_schema_fields` → 10 fields incl. `patient_id`; `get_entities` → props + ownership |
| 3 | Write tag | Python SDK | ✅ **PROVEN** | tag written + read back + removed |
| 4 | Write description | Python SDK | ✅ **PROVEN** | editable description written + read back + cleared |
| 5 | Create incident / assertion | Python SDK | ✅ **PROVEN** | incident created + read back `ACTIVE` + hard-deleted |
| 6 | Glossary term: create + attach to dataset AND column | Python SDK / MCP | ✅ **PROVEN** (with a caveat) | term created; dataset attach MCP-readable; **column attach MCP-readable only via `editableSchemaMetadata` → `editedGlossaryTerms`** (schemaField-entity attach is not surfaced by MCP) |
| 7 | Structured property: define + apply to dataset AND column | Python SDK / MCP | ⚠️ **DATASET only** | dataset apply MCP-readable via `get_entities.structuredProperties`; **column apply is NOT returned by MCP `list_schema_fields`** — unusable for the checks |

### Rows 6–7 — glossary terms & structured properties (Batch-3 spike)

The Batch-3 emitter needs COLUMN-level clinical signals that the MCP read path returns.
The spike wrote a glossary term, a structured property, and a tag to both a dataset and a
column (`dashboard_report.case_count`), then read them back through MCP.

**Result — MCP readability by representation × granularity:**

| Representation | Dataset (MCP `get_entities`) | Column (MCP `list_schema_fields`) |
|---|---|---|
| Glossary term | ✅ `glossaryTerms` | ✅ `editedGlossaryTerms` *(only via `editableSchemaMetadata`)* |
| Structured property | ✅ `structuredProperties` | ❌ not returned |
| Tag | ✅ | ❌ not returned |

**Column readback proof** (`editableSchemaMetadata` path):

```json
{"fieldPath": "case_count", "nativeDataType": "BIGINT", ..., "editedGlossaryTerms": ["SpikeTerm"]}
```

Writing the term/property/tag to the **schemaField entity** (`urn:li:schemaField:(...)`)
did NOT surface in the MCP field view; only `editableSchemaMetadata` did.

**Representation chosen (frozen in `docs/METADATA_CONTRACT.md`):**

- **Column-level signals → glossary terms** via `editableSchemaMetadata`
  (sensitivity, clinical_semantic, missingness_contract). The only MCP-readable column
  option.
- **Dataset-level facts → structured properties** (validation_status, data_product,
  deidentification_required), **plus a dataset glossary term** for the semantic class
  (UnvalidatedSource / ValidatedSource / ResearchExport).

The pre-authorized namespaced-tag fallback was **not needed** — glossary terms are both
writable and MCP-readable at column granularity. All spike artifacts were cleaned up
(dataset aspects emptied; scratch term/property/schemaField hard-deleted; verified empty).

### Row 1 — read lineage via MCP (`scripts/mcp_smoke.py`)

```json
{"upstreams":{"total":1,"searchResults":[{"entity":{
  "urn":"urn:li:dataset:(urn:li:dataPlatform:duckdb,faulty.main.stg_ed_documentation,PROD)",
  "name":"faulty.main.stg_ed_documentation","platform":{"name":"duckdb"}},"degree":1}],
  "hasMore":false}}
```

### Row 2 — read schema + properties via MCP (`scripts/mcp_smoke.py`)

`list_schema_fields(research_export)` → all 10 fields, **including the faulty `patient_id`
leak** (trimmed):

```json
{"fields":[{"fieldPath":"ed_arrival_datetime","nativeDataType":"TIMESTAMP",...},
 {"fieldPath":"patient_id","nativeDataType":"VARCHAR","nullable":false}, ...],
 "totalFields":10}
```

`get_entities(research_export)` → dataset properties + ownership (trimmed):

```json
{"properties":{"customProperties":[
   {"key":"data_product","value":"research_export"},
   {"key":"deidentification_required","value":"True"},
   {"key":"owner","value":"research-export-owner@ortholineage.example"}, ...]},
 "ownership":{"owners":[{"owner":{"urn":"urn:li:corpuser:research-export-owner@ortholineage.example"},
   "type":"DATAOWNER"}]}}
```

### Row 3 — write tag via Python SDK (`scripts/capability_spike/row3_write_tag.py`)

```
[write] adding tag urn:li:tag:guardian_scratch_batch2 -> ...dashboard_report...
[read ] tags now on dataset: ['urn:li:tag:guardian_scratch_batch2']
[PROVEN] tag write + read-back succeeded
[clean] tags after cleanup: []
```

### Row 4 — write description via Python SDK (`scripts/capability_spike/row4_write_description.py`)

Uses the **editable** description layer so the dbt-ingested docs are never clobbered; also
demonstrates attaching a remediation summary (the Required tier's "attach a remediation
summary" action).

```
[write] setting editable description (remediation summary)
[read ] editable description now: '[OrthoLineage Guardian scratch] Governance finding STALE_REFERENCE: ...'
[PROVEN] description write + read-back succeeded
[clean] editable description after cleanup: ''
```

### Row 5 — create incident via Python SDK (`scripts/capability_spike/row5_incident.py`)

```
[write] creating incident urn:li:incident:guardian-scratch-batch2 on ...dashboard_report...
[read ] incident state='ACTIVE' entities=['urn:li:dataset:(urn:li:dataPlatform:dbt,...dashboard_report,PROD)']
[PROVEN] incident creation + read-back succeeded
[clean] incident hard-deleted; exists=False
```

Caveat found: the incident entity does **not** accept a standalone `status` aspect
(`422 Unknown aspect status for entity incident`), so soft-delete-by-status doesn't work;
cleanup uses `DataHubGraph.hard_delete_entity`.

### Cleanup verification (no scratch artifacts linger)

```
dashboard_report tags    : []
dashboard_report editDesc : ''
scratch tag entity exists : False
scratch incident exists   : False
```

---

## FROZEN WRITE-BACK DECISION (gate for Batches 3–6)

All five rows proved, so the write-back contract is frozen at its full extent:

- **Required tier (floor) — FROZEN, both proven:**
  1. add a governance-finding **tag** to affected datasets (Row 3), and
  2. write the finding + remediation summary into the dataset's **editable description**
     (Row 4).
- **Preferred tier — INCLUDED (Row 5 proved):** create a DataHub **incident** attached to
  the affected dataset, via `DataHubGraph` (create with `IncidentInfoClass`; resolve by
  re-emitting `IncidentInfo` with a `RESOLVED` status; remove with `hard_delete_entity`).

Mechanism decisions carried forward:

- **Platform:** write to the **`dbt`-platform** dataset URNs (they carry the schema +
  lineage the findings reference).
- **Read path:** the **official MCP server** (`mcp-server-datahub` 0.6.0, stdio,
  `DATAHUB_GMS_URL`/`DATAHUB_GMS_TOKEN`). Note its **mutation tools are disabled by
  default** — writes go through the **Python SDK** (`DataHubGraph` +
  `MetadataChangeProposalWrapper`), which matches the AUTHORITY-SPLIT invariant (writes are
  validated application code, never the model).
- **Ownership:** proven to ingest; safe to surface in the README.
- **Column lineage:** proven to resolve; the impact traversal can rely on field-level edges.

---

## Reproduce

```bash
# 1. bring DataHub up (GMS on 8090)
bash scripts/datahub_up.sh
export DATAHUB_GMS_URL=http://localhost:8090

# 2. build the faulty dbt artifacts, then ingest
bash scripts/build.sh
uv tool run --python 3.11 --from 'acryl-datahub[dbt]' datahub ingest -c ingest/dbt_source.yml

# 3. prove the MCP read path (Rows 1-2)
uv run --with mcp python scripts/mcp_smoke.py

# 4. prove the SDK write primitives (Rows 3-5); each cleans up after itself
cd scripts/capability_spike
uv run --with 'acryl-datahub[datahub-rest]' python row3_write_tag.py
uv run --with 'acryl-datahub[datahub-rest]' python row4_write_description.py
uv run --with 'acryl-datahub[datahub-rest]' python row5_incident.py

# teardown (keeps metadata volumes; --nuke wipes them)
bash scripts/datahub_down.sh
```
