# OrthoLineage Guardian

A clinically informed **data-governance agent** for orthopaedic-trauma registry
pipelines. It uses data lineage to detect healthcare-specific data-contract violations,
generate mergeable remediation, and preserve findings in the metadata graph. Lineage is
the substrate; the value is the clinical policy layer and the closed loop
(**detect → remediate → write back**).

> **Status: governance-only, synthetic-data project.** This system governs metadata,
> provenance, and data quality. It never emits diagnosis, treatment, triage, or any
> clinical recommendation. All data in this repository is **synthetic, seeded,
> deterministic, and PHI-free**.

This repository is being built in batches. **Batch 1 (this content)** delivers the
synthetic dbt + DuckDB pipeline: a six-model tree with two scenarios (`baseline` and
`faulty`), four planted governance fixtures, and a test suite that proves the scenario
difference. Later batches add DataHub ingestion, the clinical metadata emitter, the
deterministic policy engine, LLM-drafted remediation, and controlled write-back.

---

## Invariants

These bind every batch of this project.

- **GOVERNANCE-ONLY.** The agent governs metadata, provenance, and data quality. It
  NEVER emits diagnosis, treatment, triage, or clinical recommendation. All data is
  SYNTHETIC and PHI-free.
- **IP WALL-OFF.** `ortholineage-guardian` is a NEW public Apache-2.0 repo. NEVER copy
  source, file paths, protocol-pack YAML, or the CDS-firewall / two-lane authority
  *implementation* from any private predecessor codebase into it. Any private
  predecessor was read ONLY to abstract domain patterns. Apache-2.0 is irrevocable
  public disclosure — patentable firewall / two-lane internals are OFF-LIMITS for
  transplant.
- **AUTHORITY SPLIT (public-safe analogue, derived fresh).** Deterministic code decides
  whether a violation exists; the LLM only explains and drafts remediation,
  schema-validated; write-back is performed by validated application code, never by the
  model.
- **DETECTION PROVENANCE.** The policy engine detects violations EXCLUSIVELY from
  DataHub metadata signals (tags, properties, lineage, schema aspects) — NEVER by
  reading the dbt SQL where defects are planted. If a check can only pass by reading
  source code, the metadata model is incomplete: fix the emitter, not the check.
- **SCENARIO INTEGRITY.** One model tree; scenario switched by a deterministic dbt var.
  `baseline` is clean (the false-positive test bed); `faulty` carries exactly the four
  documented planted fixtures. Every defect is annotated in-code
  `-- PLANTED DEFECT: <id>`; zero defects exist in baseline (proven by tests).
- **NEW-WORK.** Everything in this repo is built fresh within the submission window.

---

## The pipeline

One dbt model tree, six models, one raw seed source. The hero migration renames
`arrival_time → ed_arrival_datetime`; that rename lands in `trauma_registry` under
**both** scenarios.

```
stg_ed_documentation      (staging  · raw, "unvalidated" source)
        │
        ▼
trauma_registry           (registry · the rename lands here: arrival_time → ed_arrival_datetime)
        │
        ├──────────────► dq_metrics        (quality · completeness / temporal metrics)
        │
        ├──────────────► research_export   (export  · de-identified research product)
        │
        ▼
ml_feature_table          (ml      · features for downstream models)
        │
        ▼
dashboard_report          (report  · summary surface)
```

Every path that carries the timestamp or an identifier uses **named-column `SELECT`s**
(no `SELECT *` on those chains) so that column-level lineage is traceable downstream.

### Scenarios

There is exactly one model tree. The scenario is chosen at run time with a dbt var; the
two scenarios differ ONLY at the four planted-defect sites, each guarded by a
`{% if var('scenario') == 'faulty' %}` conditional and annotated `-- PLANTED DEFECT:`.

- **`baseline`** — clean. No governance defects. This is the false-positive test bed.
- **`faulty`** — carries exactly four documented defects (three governance defects plus
  one stale reference):

  | Fixture ID | Model | What `faulty` does |
  |---|---|---|
  | `PHI_EXPORT_PATH` | `research_export` | retains the direct identifier `patient_id` in the export select list |
  | `MISSINGNESS_COLLAPSE` | `trauma_registry` | collapses ≥2 distinct explicit missingness states (`NOT_DOCUMENTED`, `NOT_ASSESSED`) into SQL `NULL` **and drops the paired `_missingness` state column** |
  | `UNVALIDATED_ML_SOURCE` | `ml_feature_table` | derives at least one feature directly from `stg_ed_documentation` (the raw, unvalidated source), bypassing `trauma_registry` |
  | `STALE_REFERENCE` | `dashboard_report` | still references the pre-rename `arrival_time` name after `trauma_registry` renamed it to `ed_arrival_datetime` |

---

## Quickstart

Requires Python 3.11 and [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Install the pinned toolchain (creates .venv from pyproject.toml + uv.lock)
uv sync

# 2. Build + test both scenarios and generate docs on the faulty state
bash scripts/build.sh
```

`scripts/build.sh` runs the full flow end to end:

1. build `baseline` → test `baseline` (dbt tests + pytest) → **zero defects**;
2. build `faulty` → test `faulty` (dbt tests + pytest) → **exactly the four fixtures**;
3. `dbt docs generate` on `faulty`, producing `target/manifest.json` and
   `target/catalog.json` (the metadata a later batch ingests into DataHub).

Each scenario builds into its **own** DuckDB file (`baseline.duckdb`, `faulty.duckdb`)
so the two states never share a database.

To run a single scenario manually:

```bash
uv run dbt build --vars '{scenario: baseline}' --target baseline
uv run dbt build --vars '{scenario: faulty}'   --target faulty
```

---

## Data-model notes (honest simplifications)

This synthetic model deliberately simplifies two things relative to a production trauma
registry. Both simplifications are documented here so the design is honest; neither
changes the governance semantics the checks depend on.

### 1. Missingness controlled vocabulary

Clinical fields that can be legitimately absent do not store a bare SQL `NULL`; they
store an **explicit missingness state** in a paired `<field>_missingness` column
alongside the value column. This project freezes a compact **five-token** vocabulary:

```
PRESENT | NOT_DOCUMENTED | NOT_ASSESSED | NOT_APPLICABLE | UNKNOWN
```

with these meanings:

| Token | Meaning |
|---|---|
| `PRESENT` | the value is documented and valid |
| `NOT_DOCUMENTED` | the item was not documented |
| `NOT_ASSESSED` | a clinician documented that the item was **not assessed** (distinct from simply not documented) |
| `NOT_APPLICABLE` | the item does not apply to this case |
| `UNKNOWN` | genuinely unknown |

A production registry typically splits explicit missingness across two governed axes (a
richer *missingness-state* axis and a separate *documentation-status* axis). The
five-token set here is a deliberate, defensible **synthesis** of those two axes, small
enough for a demo while preserving the load-bearing semantic: **an explicit governed
reason is a dispositioned (answered) state, whereas a bare null on an expected field is
the only blocking state.** Collapsing two distinct explicit states into one downstream
`NULL` is exactly what the `MISSINGNESS_COLLAPSE` fixture violates.

**Paired-column guarantee.** Every value column governed by an explicit missingness
contract (`gcs_total`, `mechanism_category`) is stored as a value column **plus** a
dedicated `<field>_missingness` state column, and that pairing is carried through every
baseline downstream model that carries the value. In `faulty`, the
`MISSINGNESS_COLLAPSE` defect both nulls the collapsed values **and drops the paired
`_missingness` state column** downstream — a schema-shape difference that a
metadata-only policy engine can detect without reading any SQL.

### 2. Direct-identifier realism

The seed carries raw `patient_id` and `medical_record_number` columns, and the
`PHI_EXPORT_PATH` fixture demonstrates a raw identifier surviving into a research export.

In a production architecture, raw direct identifiers are typically **never** stored in
registry tables at all — direct PHI is isolated behind a vault pointer and write APIs
reject direct identifiers outright — so a literal "identifier retained in export" is not
how such a system actually fails. For this synthetic teaching demo we deliberately use
the simpler, universally legible failure mode (a raw identifier surviving into an
export) because it is pedagogically clearer than a vault-pointer leak and needs no
vault architecture. This is a synthetic simplification, not a model of any real system.

For this project, the **only** direct identifiers are `patient_id` and
`medical_record_number`. The encounter timestamp (`arrival_time` /
`ed_arrival_datetime`) is a **quasi-identifier**, never a direct identifier.

---

## Run DataHub locally (Batch 2)

Batch 2 stands up DataHub OSS via the official quickstart, ingests the **faulty** dbt
state (with real table- and column-level lineage), and proves the read + write metadata
primitives. Requires **Docker** and the [`uv`](https://docs.astral.sh/uv/) toolchain.

The DataHub CLI is installed as an **isolated `uv` tool** so it never touches this dbt
project's environment:

```bash
uv tool install --python 3.11 'acryl-datahub[dbt]'
```

Bring DataHub up, build + ingest the faulty state, and prove the MCP read path:

```bash
# 1. Start DataHub. GMS is published on host port 8090 (remapped off the default 8080,
#    which is commonly taken; override with DATAHUB_MAPPED_GMS_PORT).
bash scripts/datahub_up.sh
export DATAHUB_GMS_URL=http://localhost:8090        # see .env.example

# 2. Build the faulty dbt artifacts, then ingest them into DataHub.
bash scripts/build.sh
uv tool run --python 3.11 --from 'acryl-datahub[dbt]' datahub ingest -c ingest/dbt_source.yml

# 3. Smoke-test the DataHub MCP read path (lineage + schema/properties).
uv run --with mcp python scripts/mcp_smoke.py

# 4. Emit the clinical governance metadata (Batch 3), then verify every signal is
#    readable back through the MCP path at the correct granularity.
uv run --with 'acryl-datahub[datahub-rest]' python scripts/emit_clinical_metadata.py
uv run --with mcp python scripts/mcp_verify_contract.py     # all PASS, exit 0

# Tear down (keeps metadata volumes; pass --nuke to wipe them).
bash scripts/datahub_down.sh
```

The DataHub UI is at **http://localhost:9002** (default login `datahub` / `datahub`).

**Secrets:** no tokens are committed. Copy [`.env.example`](.env.example) to `.env`
(gitignored). The local quickstart runs with metadata-service auth disabled, so
`DATAHUB_GMS_TOKEN` may be empty; set it for a secured instance.

**Proven in Batch 2** (see [docs/BATCH2_CAPABILITY_MATRIX.md](docs/BATCH2_CAPABILITY_MATRIX.md)):
all 6 models ingest with the table-level DAG (including `ml_feature_table`'s dual parents),
**column-level lineage resolves**, `schema.yml` owners **map to DataHub ownership**, the
MCP read path works, and the Python-SDK write primitives (tag, description, incident) all
succeed. That document is the frozen contract the remaining batches build against.

### Clinical metadata (Batch 3)

The dbt ingestion alone does not carry the clinical governance semantics the checks need.
The **emitter** ([`src/ortholineage_guardian/emitter/`](src/ortholineage_guardian/emitter/),
run via [`scripts/emit_clinical_metadata.py`](scripts/emit_clinical_metadata.py)) promotes
the governance `meta` keys into first-class, **MCP-readable** DataHub signals at the right
granularity: **column-level glossary terms** (`DirectIdentifier`, `QuasiIdentifier`,
`EncounterTimestamp`, `ExplicitMissingness`) and **dataset-level structured properties**
(`guardian_validation_status`, `guardian_data_product`,
`guardian_deidentification_required`) plus dataset glossary terms. The emitter is
idempotent (re-running yields byte-identical aspects), uses no LLM, and writes through the
validated SDK. [`docs/METADATA_CONTRACT.md`](docs/METADATA_CONTRACT.md) is the **frozen
contract** the policy engine (Batch 4) reads — nothing else.

### Policy engine + dual-namespace graph (Batch 4)

The deterministic governance engine ([`src/ortholineage_guardian/policy/`](src/ortholineage_guardian/policy/))
runs three checks and decides whether a violation exists **purely from DataHub metadata
read over MCP** — it never opens the dbt SQL, the manifest, `catalog.json`, or a DuckDB
database (enforced by a test with a CPython audit hook). No LLM, no write-back.

| Check | Fires when | Rule class |
|---|---|---|
| `PHI_EXPORT_PATH` | a `DirectIdentifier` column has column-lineage into a `research_export` dataset | export-governance |
| `MISSINGNESS_COLLAPSE` | an `ExplicitMissingness` value column survives downstream but its paired `_missingness` column was dropped | completeness |
| `UNVALIDATED_ML_SOURCE` | an `ml_feature_table` feature is sourced directly from an `unvalidated` dataset, bypassing the validated registry | readiness |

The stale-`arrival_time` reference is reported as a migration-drift **observation** (the
impact traversal), not one of the three checks.

To make the **zero-false-positives-on-baseline** claim provable on one GMS, both scenarios
are ingested under **distinct URN namespaces** (`faulty` → env `PROD`, `baseline` → env
`DEV`) and both carry the full clinical contract. One command builds, ingests, emits, and
MCP-verifies the whole dual-world graph:

```bash
export DATAHUB_GMS_URL=http://localhost:8090
bash scripts/ingest_all.sh
```

Then run the engine against either world:

```bash
uv run --with mcp python scripts/run_policy_engine.py --namespace faulty     # 3 findings
uv run --with mcp python scripts/run_policy_engine.py --namespace baseline    # 0 findings
```

Tests (run with `uv run --with mcp pytest -q`): `tests/test_policy_faulty_positives.py`
(all three fire with correct evidence), `tests/test_policy_baseline_zero_fp.py` (the
headline zero-false-positive claim), and `tests/test_detection_provenance.py` (the engine
opens no SQL/manifest/DuckDB). They skip gracefully when DataHub/MCP is unavailable.

### Explanation + remediation drafting (Batch 5)

**Authority split (the judging narrative):**

> Deterministic code decides whether a violation exists. The LLM never decides — it turns a
> deterministic, lineage-grounded finding into an understandable explanation and a draft
> remediation, which is schema-validated before any of it is written anywhere. Write-back is
> performed by validated application code, not by the model.

The LLM layer ([`src/ortholineage_guardian/llm/`](src/ortholineage_guardian/llm/)) takes the
engine's `Finding` objects as **input** and produces prose + a draft dbt patch as **output**.
`schema_guard.py` validates everything the model returns and rejects on mismatch, with two
load-bearing guards: an **entity whitelist** (every dataset/column/term named in the output
must come from the finding's evidence or the metadata contract — the anti-hallucination
property) and a **contract-knowledge guard** (the output may never assert observed row data,
since the engine reads metadata only). A rejected output falls back to template mode; it is
never silently used.

The LLM is **never required for correctness.** With no API key present — or with `--no-llm`
— the same validated objects are rendered deterministically from templates, so a judge with
no key still gets a complete, useful artifact:

```bash
export DATAHUB_GMS_URL=http://localhost:8090
uv run --with mcp python scripts/generate_remediation.py --namespace faulty            # LLM if ANTHROPIC_API_KEY set, else template
uv run --with mcp python scripts/generate_remediation.py --namespace faulty --no-llm   # force deterministic template mode
```

Set `ANTHROPIC_API_KEY` (and optionally `GUARDIAN_MODEL`, default `claude-opus-4-8`) to
enable the LLM — see [`.env.example`](.env.example). Committed golden artifacts
([`tests/golden/`](tests/golden/)) make the template output inspectable without a running
stack or a key; regenerate them with `uv run python scripts/generate_goldens.py`. Offline
tests: `tests/test_schema_guard.py` (malformed / hallucinated-entity / claimed-observation
rejections, mocked — no network), `tests/test_no_llm_fallback.py`, `tests/test_golden_stability.py`.

### Remediation artifacts + controlled write-back (Batch 6) — the closed loop

The agent renders **PR-ready artifacts** from the validated findings and performs
**controlled write-back** into DataHub, closing the loop **detect → remediate → write back**.

Generated artifacts (deterministic — no timestamps, diff-reviewable), in
[`examples/`](examples/):

- [`examples/remediation/remediation.patch`](examples/remediation/remediation.patch) — a
  **real, `git apply`-able** dbt patch fixing all four fixtures (drop `patient_id` from the
  export, restore the paired `gcs_total_missingness` column, repoint the ML feature to the
  validated registry, rename the stale `arrival_time`). Verified with `git apply --check`.
- [`examples/reports/migration_impact_report.md`](examples/reports/migration_impact_report.md)
  — the rename, the lineage-traversed affected datasets/columns, the three findings with
  evidence, and the stale-reference observation.
- [`examples/findings/findings.json`](examples/findings/findings.json) — machine-readable findings.

Write-back is **application code, never LLM-driven**, **dry-run by default**, and
**idempotent**. Per the frozen contract (`docs/BATCH2_CAPABILITY_MATRIX.md`): a
governance-finding **tag** + an editable **description** (Required tier) and a DataHub
**incident** (Preferred tier) on each affected dataset. Baseline (0 findings) writes nothing.

**One-command closed-loop demo:**

```bash
export DATAHUB_GMS_URL=http://localhost:8090
bash scripts/datahub_up.sh                                                   # 1. DataHub
bash scripts/ingest_all.sh                                                   # 2. build + ingest + emit both namespaces
uv run --with mcp python scripts/run_policy_engine.py --namespace faulty      # 3. detect (3 findings)
uv run --with mcp python scripts/generate_remediation.py --namespace faulty   # 4. explain + draft (LLM if key, else template)
uv run --with mcp python scripts/render_artifacts.py --namespace faulty        # 5. render examples/
uv run --with mcp --with 'acryl-datahub[datahub-rest]' python scripts/writeback.py --namespace faulty            # 6. dry-run (writes nothing)
uv run --with mcp --with 'acryl-datahub[datahub-rest]' python scripts/writeback.py --namespace faulty --apply    # 7. write tag + description + incident
uv run --with mcp python scripts/writeback_verify.py --namespace faulty --expect present   # 8. read back through MCP
uv run --with 'acryl-datahub[datahub-rest]' python scripts/writeback_reset.py --namespace faulty                 # 9. clean the graph for re-recording
```

Tests: `tests/test_artifacts.py` (the patch applies + golden-stable) and
`tests/test_writeback.py` (dry-run plan, baseline-zero, validated-only) — offline.

---

## Repository layout (Batch 1)

```
ortholineage-guardian/
├── LICENSE                  Apache-2.0
├── README.md
├── CLAUDE.md                invariants + working rules for agents
├── pyproject.toml           pinned toolchain (dbt-core, dbt-duckdb, duckdb)
├── uv.lock                  locked resolution
├── dbt_project.yml          defines var `scenario` (default: baseline)
├── profiles/profiles.yml    baseline + faulty targets → separate DuckDB files
├── seeds/                   deterministic, hand-authored raw CSV
├── models/
│   ├── staging/             stg_ed_documentation
│   ├── registry/            trauma_registry  (rename + MISSINGNESS_COLLAPSE)
│   ├── quality/             dq_metrics
│   ├── export/              research_export  (PHI_EXPORT_PATH)
│   ├── ml/                  ml_feature_table (UNVALIDATED_ML_SOURCE)
│   ├── report/              dashboard_report (STALE_REFERENCE)
│   └── schema.yml           model/column metadata + governance meta keys
├── tests/                   dbt singular tests + pytest scenario-diff suite
├── examples/                (generated remediation artifacts — later batches)
└── scripts/build.sh         build + test both scenarios + docs generate
```

## License

Apache-2.0. See [LICENSE](LICENSE).
