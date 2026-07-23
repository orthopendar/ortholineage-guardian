#!/usr/bin/env bash
# Bring up a local DataHub OSS instance via the official `datahub docker quickstart`.
#
# Why the GMS port is remapped: DataHub GMS publishes host port 8080 by default. On many
# dev machines 8080 is already taken; if the bind fails, GMS never attaches to the docker
# network (its resolver falls back to the host stub 127.0.0.53) and it hangs forever in
# its dependency-wait loop. We therefore publish GMS on ${DATAHUB_MAPPED_GMS_PORT}
# (default 8090) via the compose env override the quickstart file already exposes:
#     ports: { target: 8080, published: ${DATAHUB_MAPPED_GMS_PORT:-8080} }
#
# The DataHub CLI is used as an isolated uv tool (see README) so it never touches the dbt
# project environment.
set -euo pipefail

: "${DATAHUB_MAPPED_GMS_PORT:=8090}"     # host port for GMS (override if 8090 is taken)
export DATAHUB_MAPPED_GMS_PORT

DATAHUB_CLI=(uv tool run --python 3.11 --from acryl-datahub datahub)
GMS_URL="http://localhost:${DATAHUB_MAPPED_GMS_PORT}"
FRONTEND_URL="http://localhost:9002"

echo "Starting DataHub quickstart (GMS published on host port ${DATAHUB_MAPPED_GMS_PORT})..."
"${DATAHUB_CLI[@]}" docker quickstart

echo "Waiting for GMS health at ${GMS_URL}/health ..."
for i in $(seq 1 60); do
  if curl -sS --fail "${GMS_URL}/health" >/dev/null 2>&1; then
    echo "GMS healthy."
    break
  fi
  sleep 5
done

echo
echo "DataHub is up:"
echo "  UI (frontend):  ${FRONTEND_URL}    (default login: datahub / datahub)"
echo "  GMS / API:      ${GMS_URL}"
echo
echo "Set these for ingestion + the MCP server:"
echo "  export DATAHUB_GMS_URL=${GMS_URL}"
