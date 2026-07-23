# CLAUDE.md — OrthoLineage Guardian

Guidance for any agent (or human) working in this repository.

## Invariants (binding — do not violate)

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

## Working rules

- One model tree only. Scenarios differ ONLY at the planted-defect sites, via
  `{% if var('scenario') == 'faulty' %}` conditionals. NEVER duplicate model folders
  per scenario.
- Direct identifiers are exactly `patient_id` and `medical_record_number`. Never tag
  `arrival_time` / `ed_arrival_datetime` as a direct identifier — it is a
  quasi-identifier (encounter timestamp).
- Seeds are deterministic and hand-authored. No Faker, no randomness.
- Never commit `*.duckdb`, `target/`, `__pycache__`, or `.venv`.
