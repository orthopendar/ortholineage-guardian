#!/usr/bin/env bash
# Tear down the local DataHub quickstart.
#
#   ./scripts/datahub_down.sh          # stop + remove containers, KEEP metadata volumes
#   ./scripts/datahub_down.sh --nuke   # also delete volumes (wipes all ingested metadata)
set -euo pipefail

DATAHUB_CLI=(uv tool run --python 3.11 --from acryl-datahub datahub)

if [[ "${1:-}" == "--nuke" ]]; then
  echo "Stopping DataHub and REMOVING all volumes (metadata will be wiped)..."
  "${DATAHUB_CLI[@]}" docker nuke
else
  echo "Stopping DataHub containers (metadata volumes preserved)..."
  "${DATAHUB_CLI[@]}" docker quickstart --stop
fi
echo "Done."
