# OrthoLineage Guardian

[![CI](https://github.com/orthopendar/ortholineage-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/orthopendar/ortholineage-guardian/actions/workflows/ci.yml)
&nbsp;License: Apache-2.0

**OrthoLineage Guardian is a clinically informed, governance-only agent that reads
DataHub lineage and metadata to catch healthcare-specific data-contract violations that a
generic data-quality tool would miss.** It detects three trauma-registry governance
defects and a stale migration reference purely from the metadata graph, drafts a
PR-ready dbt patch and impact report to fix them, and writes its findings back into
DataHub as tags, descriptions, and incidents. The whole loop — **detect → remediate →
write back** — runs from one `guardian` CLI over a synthetic, PHI-free pipeline.

> **Governance-only, synthetic data.** This system governs metadata, provenance, and data
> quality. It **never** emits diagnosis, treatment, triage, or any clinical
> recommendation. Every row in this repository is **synthetic, seeded, deterministic, and
> PHI-free**.

---

## Safety: the authority split

The claim that makes this safe to run against real governance metadata is that **a
language model never decides anything.**

> Deterministic code decides whether a violation exists. The LLM never decides — it turns
> a deterministic, lineage-grounded finding into a readable explanation and a *draft*
> remediation, which is schema-validated before any of it is written anywhere. Write-back
> is performed by validated application code, not by the model.

Three consequences follow, and each is enforced in code and tested:

- **Detection provenance.** The policy engine reads *only* DataHub metadata signals (tags,
  glossary terms, structured properties, lineage, schema aspects). It never opens the dbt
  SQL, the manifest, `catalog.json`, or a DuckDB file — enforced by a test with a CPython
  audit hook (`tests/test_detection_provenance.py`).
- **No hallucinated entities.** Every dataset, column, or term the LLM names must trace
  back to the finding's evidence or the frozen metadata contract; anything else is
  rejected and the output falls back to a deterministic template
  (`tests/test_schema_guard.py`).
- **Human-in-the-loop write-back.** Generated artifacts are *proposals* for human review.
  Write-back is application code, **dry-run by default**, idempotent, and reversible.

---

## 60-second quickstart (no Docker, no API key)

Requires Python 3.11 and [`uv`](https://docs.astral.sh/uv/). This builds the synthetic
pipeline, runs the full offline test suite (including the headline zero-false-positive
proof), and leaves the committed remediation artifacts inspectable — all with no DataHub
and no API key.

```bash
git clone https://github.com/orthopendar/ortholineage-guardian.git
cd ortholineage-guardian

uv sync                 # install the pinned toolchain from uv.lock
bash scripts/build.sh   # build baseline + faulty, run the offline test suite, generate docs
```

Then read the PR-ready artifacts the agent generated, already committed for inspection:

- [`examples/remediation/remediation.patch`](examples/remediation/remediation.patch) — a real, `git apply`-able dbt patch that fixes all four defects
- [`examples/reports/migration_impact_report.md`](examples/reports/migration_impact_report.md) — the migration-impact report
- [`examples/findings/findings.json`](examples/findings/findings.json) — the machine-readable findings

To watch the closed loop run live against DataHub, do the **hero demo** below.

---

## The hero demo (the closed loop, against DataHub)

One migration renames `arrival_time → ed_arrival_datetime`. The migration is faulty: the
`faulty` world carries exactly **three governance defects plus one stale reference**. The
agent traverses lineage from the changed field, names every affected dataset and column,
fires the three deterministic checks, drafts the remediation, and writes findings back.

Requires **Docker** (for the DataHub OSS quickstart) and `uv`. Everything is driven by the
unified `guardian` CLI. Activate the project venv once so the `guardian` command is on your
PATH (or prefix any command with `uv run`, e.g. `uv run guardian scan`):

```bash
uv sync                        # if you haven't already
source .venv/bin/activate      # puts `guardian` on PATH
export DATAHUB_GMS_URL=http://localhost:8090

guardian up        # start DataHub (docker quickstart; GMS on host port 8090)
guardian ingest    # build + ingest + emit clinical metadata for BOTH namespaces
```

`guardian up` / `ingest` are the one-time (slow) setup. Then run the hero path — either
one stage at a time, or all at once with the filming-ordered demo script:

```bash
bash scripts/demo.sh                  # the full loop, straight through
DEMO_PAUSE=1 bash scripts/demo.sh     # pause between stages for a narrator
```

`scripts/demo.sh` runs exactly these six stages (each is also a standalone `guardian`
subcommand you can run yourself):

| # | Command | Expected result |
|---|---|---|
| 1 | `guardian scan --namespace faulty` | **3 findings** (`PHI_EXPORT_PATH`, `MISSINGNESS_COLLAPSE`, `UNVALIDATED_ML_SOURCE`) + a stale-`arrival_time` observation |
| 2 | `guardian artifacts --namespace faulty` | writes the patch + impact report + findings.json into `examples/` |
| 3 | `guardian writeback --namespace faulty --apply` | writes a governance **tag** + editable **description** + **incident** to each affected dataset |
| 4 | `guardian verify --namespace faulty --expect present` | reads all three back **through MCP**, exits 0 |
| 5 | `guardian scan --namespace baseline` | **0 findings** — zero false positives on the clean world |
| 6 | `guardian reset --namespace faulty` | removes everything the guardian wrote; graph clean again |

`guardian writeback` without `--apply` is a **dry-run** — it prints the exact plan and
writes nothing. When finished, tear down with `guardian down` (or `guardian down --nuke`
to wipe the metadata volumes).

The DataHub UI is at **http://localhost:9002** (default login `datahub` / `datahub`), where
the written-back tags, descriptions, and incidents are visible on each dataset.

---

## What makes this non-native to DataHub

DataHub gives you lineage and a metadata graph. It does **not** know what a trauma registry
means. The value here is the clinical governance layer on top — three checks that read the
graph and decide, plus the closed loop that acts on the decision.

Each check reads **only** metadata signals (never SQL), and each maps to a real
clinical-governance rule class:

| Check | Fires when | Rule class |
|---|---|---|
| `PHI_EXPORT_PATH` | a `DirectIdentifier` column has column-level lineage into a dataset marked `data_product = research_export` | export-governance |
| `MISSINGNESS_COLLAPSE` | an `ExplicitMissingness` value column survives downstream but its paired `<field>_missingness` state column was dropped — collapsing ≥2 distinct governed states into a bare `NULL` | completeness |
| `UNVALIDATED_ML_SOURCE` | an `ml_feature_table` feature is sourced *directly* from a dataset marked `validation_status = unvalidated`, bypassing the validated registry | readiness |

The stale-`arrival_time` reference is reported as a migration-drift **observation** from
the impact traversal — surfaced alongside the findings, not counted as one of the three
checks.

**The closed loop** is the differentiator: the agent doesn't just report. It drafts a
mergeable dbt patch (verified `git apply`-able) and an impact report into `examples/`, then
writes its findings back into the graph so the governance state lives where the data does.

---

## The metadata contract, in brief

The dbt ingestion alone doesn't carry clinical meaning, so a custom **emitter** promotes
governance `meta` keys into first-class, MCP-readable DataHub signals. The policy engine
reads these — nothing else. The full frozen mapping is
[`docs/METADATA_CONTRACT.md`](docs/METADATA_CONTRACT.md); in brief:

- **Column glossary terms** — `DirectIdentifier`, `QuasiIdentifier`, `EncounterTimestamp`,
  `ExplicitMissingness` (attached at the column level via editable schema metadata).
- **Dataset structured properties** — `guardian_validation_status`,
  `guardian_data_product`, `guardian_deidentification_required`.
- **Lineage** — table- and column-level, from dbt `ref()` and named-column `SELECT`s.

The emitter is idempotent (re-running yields byte-identical aspects), uses no LLM, and
writes through the validated SDK. `docs/METADATA_CONTRACT.md` is the contract the engine
reads; if a check could only fire by reading SQL, the fix is to add a signal to the
emitter — never to read source in the check.

---

## Verify the claims yourself

Every headline claim is independently checkable:

- **Zero false positives on baseline.** Both scenarios are ingested under distinct URN
  namespaces (`faulty` → env `PROD`, `baseline` → env `DEV`), both carry the full clinical
  contract, and the engine finds **3** on faulty and **0** on baseline:
  ```bash
  guardian scan --namespace faulty     # 3 findings
  guardian scan --namespace baseline   # 0 findings
  ```
  Proven offline too: `tests/test_policy_baseline_zero_fp.py`.
- **The engine reads no source.** `tests/test_detection_provenance.py` installs a CPython
  audit hook and asserts the engine opens no `.sql`, manifest, `catalog.json`, or `.duckdb`.
- **The patch really applies.** `tests/test_artifacts.py` runs `git apply --check` on the
  generated patch and asserts every planted defect appears only on removed lines.
- **The LLM can't hallucinate entities.** `tests/test_schema_guard.py` feeds malformed,
  hallucinated-entity, and claimed-observation outputs and asserts each is rejected.

Run the offline suite (no Docker, no key) any time:

```bash
uv run pytest -q
```

This is exactly what CI runs on every push and PR — see the badge at the top.

---

## The LLM is optional (and never decides)

The LLM only improves the prose of explanations and remediation drafts. **It is never
required for correctness.** With no `ANTHROPIC_API_KEY` present — or with `--no-llm` — the
same validated objects render deterministically from templates, so a judge with no key
still gets a complete, useful artifact. When a key *is* present, the model's output is
schema-validated (entity whitelist + no-claimed-observations guard) before use, and a
rejected output silently falls back to the template. It never mutates the graph; write-back
is application code.

Set `ANTHROPIC_API_KEY` (and optionally `GUARDIAN_MODEL`, default `claude-opus-4-8`) in a
`.env` to enable it — see [`.env.example`](.env.example). Committed golden artifacts
([`tests/golden/`](tests/golden/)) make the template output inspectable without a stack or
a key.

---

## Honest simplifications

This is a synthetic teaching model. Three deliberate simplifications, each preserving the
governance semantic the checks depend on:

1. **Synthetic direct identifiers.** The seed carries raw `patient_id` /
   `medical_record_number`, and `PHI_EXPORT_PATH` demonstrates a raw identifier surviving
   into an export. A production registry would isolate direct PHI behind a vault pointer and
   never store it in registry tables; the raw-identifier-in-export failure is used here
   because it is universally legible and needs no vault architecture. The encounter
   timestamp (`arrival_time` / `ed_arrival_datetime`) is a **quasi-identifier**, never a
   direct identifier.
2. **Five-token missingness vocabulary.** Clinical fields that can be legitimately absent
   store an explicit state in a paired `<field>_missingness` column, not a bare `NULL`.
   This project freezes a compact set — `PRESENT | NOT_DOCUMENTED | NOT_ASSESSED |
   NOT_APPLICABLE | UNKNOWN` — a defensible synthesis of the richer two-axis vocabulary a
   production registry uses. The load-bearing semantic is preserved: an explicit governed
   reason is a *dispositioned* state, whereas a bare null on an expected field is the *only*
   blocking one. Collapsing two distinct explicit states into one downstream `NULL` is what
   `MISSINGNESS_COLLAPSE` violates.
3. **Binary validation status.** Real data maturity is a ladder (draft → verified, with
   evidence gates). This model simplifies it to `validated | unvalidated`, which is all
   `UNVALIDATED_ML_SOURCE` needs.

---

## The pipeline

One dbt model tree, six models, one raw seed source. The hero migration renames
`arrival_time → ed_arrival_datetime`; that rename lands in `trauma_registry` under **both**
scenarios. Every path carrying the timestamp or an identifier uses **named-column
`SELECT`s** so column-level lineage is traceable.

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

There is exactly one model tree; the scenario is chosen at run time with a dbt var. The two
scenarios differ **only** at the four planted-defect sites, each guarded by a
`{% if var('scenario') == 'faulty' %}` conditional and annotated `-- PLANTED DEFECT:`.
`baseline` is clean (the false-positive test bed); `faulty` carries exactly:

| Fixture ID | Model | What `faulty` does |
|---|---|---|
| `PHI_EXPORT_PATH` | `research_export` | retains the direct identifier `patient_id` in the export select list |
| `MISSINGNESS_COLLAPSE` | `trauma_registry` | collapses `NOT_DOCUMENTED` / `NOT_ASSESSED` into SQL `NULL` and drops the paired `_missingness` state column |
| `UNVALIDATED_ML_SOURCE` | `ml_feature_table` | derives a feature directly from `stg_ed_documentation` (raw, unvalidated), bypassing `trauma_registry` |
| `STALE_REFERENCE` | `dashboard_report` | still references the pre-rename `arrival_time` after `trauma_registry` renamed it |

To run a single scenario manually:

```bash
uv run dbt build --vars '{scenario: baseline}' --target baseline
uv run dbt build --vars '{scenario: faulty}'   --target faulty
```

---

## The `guardian` CLI

`guardian` is a thin façade over the scripts in `scripts/`; each subcommand shells out with
the dependency context that step needs and prints one line describing what it does.

| Command | What it does |
|---|---|
| `guardian up` | start DataHub (docker quickstart, GMS on :8090) |
| `guardian ingest` | build + ingest + emit clinical metadata for both namespaces |
| `guardian scan [--namespace]` | run the deterministic policy engine (metadata only) |
| `guardian artifacts [--namespace]` | render PR-ready artifacts into `examples/` |
| `guardian writeback [--namespace] [--apply]` | controlled write-back (dry-run unless `--apply`) |
| `guardian verify [--namespace] [--expect present\|clean]` | read the write-back back through MCP |
| `guardian reset [--namespace]` | remove everything the guardian wrote |
| `guardian down [--nuke]` | stop DataHub |

`--namespace` is `faulty` (default) or `baseline`. Run `guardian <command> --help` for
details.

---

## Repository layout

```
ortholineage-guardian/
├── LICENSE                     Apache-2.0
├── README.md
├── CLAUDE.md                   invariants + working rules for agents
├── pyproject.toml / uv.lock    pinned toolchain + `guardian` console script
├── dbt_project.yml             defines var `scenario` (default: baseline)
├── profiles/profiles.yml       baseline + faulty targets → separate DuckDB files
├── seeds/                      deterministic, hand-authored raw CSV
├── models/                     staging · registry · quality · export · ml · report + schema.yml
├── src/ortholineage_guardian/
│   ├── cli.py                  the unified `guardian` command
│   ├── mcp_client.py           MCP read path (lineage + schema/tags/properties)
│   ├── lineage.py              impact-graph traversal
│   ├── emitter/                clinical metadata emitter (glossary terms + structured properties)
│   ├── policy/                 the three deterministic checks + engine (decides)
│   ├── llm/                    explain + draft + schema guard (explains/drafts only)
│   ├── remediation/            renders the dbt patch + impact report
│   └── writeback/              controlled SDK write-back (tag + description + incident)
├── scripts/                    build.sh · demo.sh · datahub_*.sh · the wrapped step scripts
├── examples/                   generated PR-ready artifacts (patch + report + findings)
├── tests/                      scenario-diff · policy (zero-FP) · provenance · schema-guard · artifacts · write-back
└── docs/                       METADATA_CONTRACT.md · BATCH2_CAPABILITY_MATRIX.md · SUBMISSION_CHECKLIST.md
```

---

## Invariants

- **GOVERNANCE-ONLY.** Governs metadata, provenance, and data quality. Never emits
  diagnosis, treatment, triage, or clinical recommendation. All data synthetic and PHI-free.
- **AUTHORITY SPLIT.** Deterministic code decides; the LLM only explains and drafts
  (schema-validated); write-back is validated application code, never the model.
- **DETECTION PROVENANCE.** Violations detected exclusively from DataHub metadata — never by
  reading the dbt SQL where defects are planted.
- **SCENARIO INTEGRITY.** One model tree; scenario via a deterministic dbt var. `baseline` is
  clean; `faulty` carries exactly the four documented fixtures. Zero defects in baseline,
  proven by tests.

## License

Apache-2.0. See [LICENSE](LICENSE).
