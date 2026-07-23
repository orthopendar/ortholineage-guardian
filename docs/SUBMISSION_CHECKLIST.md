# Submission Checklist — Build with DataHub: The Agent Hackathon

Track: **Agents That Do Real Work.** Hard wall: **Aug 10, 2026, 5:00 pm EDT.**

| # | Requirement | Status | Where / evidence |
|---|---|---|---|
| 1 | **Public repo** | ✅ | `github.com/orthopendar/ortholineage-guardian` (public) |
| 2 | **Apache-2.0 license, visible in GitHub *About*** | ✅ | [`LICENSE`](../LICENSE); set the About panel's *License* field to **Apache-2.0** so GitHub detects and displays it |
| 3 | **New, in-window build** (no pre-existing main) | ✅ | Built fresh across Batches 1–7 within the submission window; no pre-existing history |
| 4 | **DataHub quickstart running; install a judge can follow** | ✅ | `guardian up` / `guardian ingest`; [README 60-second quickstart](../README.md#60-second-quickstart-no-docker-no-api-key) + hero demo |
| 5 | **MCP / Agent-Context requirement met** | ✅ | Read path is the official DataHub **MCP server** (`mcp-server-datahub`, stdio) via [`src/ortholineage_guardian/mcp_client.py`](../src/ortholineage_guardian/mcp_client.py); the engine and `guardian verify` read exclusively through it |
| 6 | **`baseline` + `faulty` scenarios; all three checks fire on faulty; zero false positives on baseline (tested)** | ✅ | `guardian scan --namespace faulty` → 3; `--namespace baseline` → 0; `tests/test_policy_faulty_positives.py`, `tests/test_policy_baseline_zero_fp.py` |
| 7 | **Impact analysis + generated dbt patch + impact report in `examples/`** | ✅ | [`examples/`](../examples/): `remediation/remediation.patch` (git apply-able), `reports/migration_impact_report.md`, `findings/findings.json` |
| 8 | **≥1 proven write-back type** | ✅ | Three: governance **tag** + editable **description** + **incident**, read back through MCP by `guardian verify`; idempotent, dry-run by default |
| 9 | **<3-min public video** (hero path only) | ⏳ | **PLACEHOLDER — record and paste link here:** `https://…` — film `DEMO_PAUSE=1 bash scripts/demo.sh` |
| 10 | **No-PHI pass over repo + logs** | ✅ | All identifiers synthetic (`PATIENT_0001`, `MRN_0001`, `CASE_0001`); see [honest simplifications](../README.md#honest-simplifications) |
| 11 | **Most-Valuable-Feedback survey opt-in** | ⏳ | Opt in on the Devpost submission form when submitting |
| 12 | **CI green** (offline suite on push + PR) | ✅ | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml); badge in the README |

Legend: ✅ done · ⏳ action required at submission time.

## Actions remaining before submitting

1. Record the <3-min hero-path video and paste the public link into row 9.
2. On the GitHub repo, set the *About* → *License* field to Apache-2.0 so it renders in the
   About panel (the `LICENSE` file is already Apache-2.0).
3. Opt into the Most-Valuable-Feedback survey on the Devpost form.
