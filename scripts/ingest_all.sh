#!/usr/bin/env bash
# Build BOTH scenarios, ingest each under a DISTINCT DataHub URN namespace, emit the
# clinical metadata into both, and verify both through the MCP read path. One command so
# a judge can reproduce the whole dual-world graph the policy engine reasons over.
#
#   baseline  -> env=DEV   URN: (...,ortholineage_guardian.baseline.main.<model>,DEV)
#   faulty    -> env=PROD  URN: (...,ortholineage_guardian.faulty.main.<model>,PROD)
#
# DataHub must be up (scripts/datahub_up.sh). Faulty is built LAST so target/manifest.json
# + target/catalog.json are left in the faulty state (what Batch 2 documents).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export DBT_PROFILES_DIR="$REPO_ROOT/profiles"
export DATAHUB_GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8090}"

DBT=(uv run dbt)
DATAHUB=(uv tool run --python 3.11 --from 'acryl-datahub[dbt]' datahub)
SDK=(uv run --with 'acryl-datahub[datahub-rest]' python)
MCP=(uv run --with mcp python)

ingest_scenario() {  # $1=scenario  $2=env
  local scenario="$1" env="$2"
  echo "=================================================================="
  echo " INGEST  scenario=${scenario}  env=${env}"
  echo "=================================================================="
  "${DBT[@]}" build --vars "{scenario: ${scenario}}" --target "${scenario}"
  "${DBT[@]}" docs generate --vars "{scenario: ${scenario}}" --target "${scenario}"
  DBT_INGEST_ENV="${env}" "${DATAHUB[@]}" ingest -c ingest/dbt_source.yml
}

# 1) baseline (DEV), then 2) faulty (PROD) — faulty last leaves target/ in faulty state.
ingest_scenario baseline DEV
ingest_scenario faulty PROD

# 3) emit the clinical governance metadata into BOTH namespaces (idempotent).
echo "== EMIT clinical metadata (baseline + faulty) =="
"${SDK[@]}" scripts/emit_clinical_metadata.py --namespace baseline
"${SDK[@]}" scripts/emit_clinical_metadata.py --namespace faulty

# 4) verify EVERY contract signal is MCP-readable in BOTH namespaces.
echo "== VERIFY contract via MCP (both namespaces) =="
"${MCP[@]}" scripts/mcp_verify_contract.py --namespace baseline
"${MCP[@]}" scripts/mcp_verify_contract.py --namespace faulty

echo
echo "DONE. Dual-namespace graph is live:"
echo "  faulty   : urn:li:dataset:(dbt,ortholineage_guardian.faulty.main.<model>,PROD)"
echo "  baseline : urn:li:dataset:(dbt,ortholineage_guardian.baseline.main.<model>,DEV)"
