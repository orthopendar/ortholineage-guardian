#!/usr/bin/env bash
# OrthoLineage Guardian — the hero demo, one command, ordered for filming (Batch 7).
#
# The closed loop end to end: detect on faulty (3 findings + stale-ref observation) →
# render PR-ready artifacts → controlled write-back → read it back through MCP →
# prove zero false positives on baseline → reset the graph clean for a re-take.
#
# Prerequisite (one-time, slow — do this BEFORE filming):
#     guardian up        # start DataHub
#     guardian ingest    # build + ingest + emit both namespaces
#
# Then film:
#     bash scripts/demo.sh                 # run straight through
#     DEMO_PAUSE=1 bash scripts/demo.sh    # pause between stages so a narrator can talk
#
# The LLM (if ANTHROPIC_API_KEY is set) only enriches prose; with no key everything runs
# in deterministic template mode. The engine decides; write-back is application code.
set -euo pipefail

cd "$(dirname "$0")/.."
export DATAHUB_GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8090}"
GUARDIAN=(uv run guardian)

bold() { printf '\033[1m%s\033[0m\n' "$1"; }

pause() {
  if [[ "${DEMO_PAUSE:-0}" == "1" ]]; then
    printf '\n\033[2m— press Enter for: %s —\033[0m' "$1"
    read -r _
  fi
}

stage() {
  echo
  echo "==================================================================="
  bold "$1"
  echo "==================================================================="
}

# Fail fast with a friendly message if the graph isn't up yet.
if ! curl -sf "${DATAHUB_GMS_URL}/config" >/dev/null 2>&1; then
  echo "DataHub GMS is not reachable at ${DATAHUB_GMS_URL}."
  echo "Run the one-time setup first:  guardian up  &&  guardian ingest"
  exit 1
fi

stage "1/6  DETECT — scan the faulty world (expect 3 findings + 1 stale-ref observation)"
pause "guardian scan --namespace faulty"
"${GUARDIAN[@]}" scan --namespace faulty

stage "2/6  REMEDIATE — render PR-ready artifacts into examples/ (patch + report + findings)"
pause "guardian artifacts --namespace faulty"
"${GUARDIAN[@]}" artifacts --namespace faulty

stage "3/6  WRITE BACK — apply governance tag + description + incident to DataHub"
pause "guardian writeback --namespace faulty --apply"
"${GUARDIAN[@]}" writeback --namespace faulty --apply

stage "4/6  VERIFY — read the write-back back THROUGH MCP (the same path the engine reads)"
pause "guardian verify --namespace faulty --expect present"
"${GUARDIAN[@]}" verify --namespace faulty --expect present

stage "5/6  ZERO FALSE POSITIVES — scan the clean baseline world (expect 0 findings)"
pause "guardian scan --namespace baseline"
"${GUARDIAN[@]}" scan --namespace baseline

stage "6/6  RESET — remove everything the guardian wrote, leaving the graph clean"
pause "guardian reset --namespace faulty"
"${GUARDIAN[@]}" reset --namespace faulty

echo
bold "Demo complete — detect → remediate → write back → verify → baseline-clean → reset."
