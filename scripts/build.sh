#!/usr/bin/env bash
# Build + test both scenarios of the OrthoLineage Guardian synthetic pipeline, then
# generate DataHub-ingestible docs on the FAULTY state.
#
# Flow:
#   1. build baseline  -> test baseline   (dbt build = seed + run + tests) -> baseline.duckdb
#   2. build faulty    -> test faulty                                       -> faulty.duckdb
#   3. pytest scenario-diff suite (baseline zero defects, faulty exactly four)
#   4. dbt docs generate on faulty -> target/manifest.json + target/catalog.json
#
# Each scenario builds into its OWN DuckDB file; the two states never share a database.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export DBT_PROFILES_DIR="$REPO_ROOT/profiles"

DBT="uv run dbt"

echo "=================================================================="
echo " [1/4] BUILD + TEST  scenario=baseline  ->  baseline.duckdb"
echo "=================================================================="
$DBT build --vars '{scenario: baseline}' --target baseline
cp target/manifest.json target/manifest.baseline.json

echo "=================================================================="
echo " [2/4] BUILD + TEST  scenario=faulty    ->  faulty.duckdb"
echo "=================================================================="
$DBT build --vars '{scenario: faulty}' --target faulty
cp target/manifest.json target/manifest.faulty.json

echo "=================================================================="
echo " [3/4] PYTEST  scenario-diff proofs (baseline clean / faulty x4)"
echo "=================================================================="
uv run pytest -q

echo "=================================================================="
echo " [4/4] DBT DOCS GENERATE  scenario=faulty  (manifest + catalog)"
echo "=================================================================="
$DBT docs generate --vars '{scenario: faulty}' --target faulty

echo
echo "DONE. Artifacts:"
echo "  baseline.duckdb / faulty.duckdb   (separate scenario databases)"
echo "  target/manifest.json + target/catalog.json  (FAULTY state, for DataHub ingest)"
