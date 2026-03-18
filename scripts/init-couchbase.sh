#!/bin/sh
# ---------------------------------------------------------------------------
# init-couchbase.sh
#
# Configures Couchbase buckets, scopes, collections, GSI indexes, and the
# FTS vector index required by the hr-agent application.
#
# Usage:
#   ./scripts/init-couchbase.sh [--no-docker]
#
#   --no-docker   Skip container startup; connect to an already-running
#                 Couchbase instance (uses CB_HOST / CB_USER / CB_PASS).
#
# Environment overrides (all optional):
#   CB_HOST      Couchbase host  (default: localhost)
#   CB_USER      Admin username  (default: Administrator)
#   CB_PASS      Admin password  (default: password)
#   CB_PORT      Management port (default: 8091)
# ---------------------------------------------------------------------------
set -e

CB_HOST="${CB_HOST:-localhost}"
CB_USER="${CB_USER:-Administrator}"
CB_PASS="${CB_PASS:-password}"
CB_PORT="${CB_PORT:-8091}"

# Bucket / scope / collection names — match the app's env vars and defaults
CB_BUCKET="${CB_BUCKET:-default}"
CB_SCOPE="${CB_SCOPE:-agentc_data}"
CB_COLLECTION="${CB_COLLECTION:-candidates}"
CB_AGENDA_COLLECTION="${CB_AGENDA_COLLECTION:-timeslots}"
CB_INDEX="${CB_INDEX:-candidates_index}"
AGENT_CATALOG_BUCKET="${AGENT_CATALOG_BUCKET:-agentc}"
AGENT_CATALOG_LOGS_SCOPE="${AGENT_CATALOG_LOGS_SCOPE:-agent_activity}"
AGENT_CATALOG_LOGS_COLLECTION="${AGENT_CATALOG_LOGS_COLLECTION:-logs}"
AGENT_CATALOG_GRADES_COLLECTION="${AGENT_CATALOG_GRADES_COLLECTION:-grades}"

MGMT_BASE="http://${CB_HOST}:${CB_PORT}"
N1QL_BASE="http://${CB_HOST}:8093"
FTS_BASE="http://${CB_HOST}:8094"

CONTAINER_NAME="hr-agent-couchbase"
CB_IMAGE="couchbase/server:enterprise-8.0.0"

NO_DOCKER=false
for arg in "$@"; do
  if [ "$arg" = "--no-docker" ]; then
    NO_DOCKER=true
  fi
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

mgmt_curl() {
  curl -s -u "${CB_USER}:${CB_PASS}" "$@"
}

wait_for_port() {
  label="$1"
  url="$2"
  echo "Waiting for ${label}..."
  i=0
  while [ $i -lt 90 ]; do
    if curl -sf -u "${CB_USER}:${CB_PASS}" "$url" -o /dev/null 2>/dev/null; then
      echo "  ${label} ready"
      return 0
    fi
    sleep 2
    i=$((i + 1))
  done
  echo "  ${label} did not become ready in time" >&2
  exit 1
}

create_bucket() {
  name="$1"
  ram="${2:-256}"
  echo "  Bucket: ${name}"
  mgmt_curl -X POST "${MGMT_BASE}/pools/default/buckets" \
    -d "name=${name}&bucketType=couchbase&ramQuota=${ram}&replicaNumber=0&flushEnabled=1" \
    -o /dev/null
  sleep 1
}

create_scope() {
  bucket="$1"
  scope="$2"
  echo "  Scope: ${bucket}.${scope}"
  mgmt_curl -X POST "${MGMT_BASE}/pools/default/buckets/${bucket}/scopes" \
    -d "name=${scope}" -o /dev/null
  sleep 1
}

create_collection() {
  bucket="$1"
  scope="$2"
  coll="$3"
  echo "  Collection: ${bucket}.${scope}.${coll}"
  mgmt_curl -X POST "${MGMT_BASE}/pools/default/buckets/${bucket}/scopes/${scope}/collections" \
    -d "name=${coll}" -o /dev/null
  sleep 1
}

run_n1ql() {
  stmt="$1"
  escaped=$(printf '%s' "$stmt" | sed 's/\\/\\\\/g; s/"/\\"/g')
  result=$(mgmt_curl -X POST "${N1QL_BASE}/query/service" \
    -H "Content-Type: application/json" \
    -d "{\"statement\": \"${escaped}\"}")
  if echo "$result" | grep -q '"status": *"success"'; then
    echo "     OK"
  else
    errors=$(echo "$result" | grep -o '"errors": *\[[^]]*\]' | head -c 300 || true)
    if [ -n "$errors" ]; then
      echo "     WARN: ${errors}"
    else
      printf '     WARN: %.300s\n' "$result"
    fi
  fi
}

# ---------------------------------------------------------------------------
# 1. Start container (unless --no-docker)
# ---------------------------------------------------------------------------
if [ "$NO_DOCKER" = "false" ]; then
  echo ""
  echo "Starting Couchbase container..."

  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "   Container '${CONTAINER_NAME}' already exists — removing it"
    docker rm -f "${CONTAINER_NAME}" >/dev/null
  fi

  docker run -d \
    --name "${CONTAINER_NAME}" \
    -p 8091-8096:8091-8096 \
    -p 11210:11210 \
    "${CB_IMAGE}"

  echo "   Container started: ${CONTAINER_NAME}"
  sleep 10
fi

# ---------------------------------------------------------------------------
# 2. Wait for management API
# ---------------------------------------------------------------------------
wait_for_port "management (8091)" "${MGMT_BASE}/pools"

# ---------------------------------------------------------------------------
# 3. Cluster initialisation
#    clusterInit is a no-op on an already-initialised node, so we also call
#    setupServices to ensure n1ql/index/fts are enabled on the node.
# ---------------------------------------------------------------------------
echo ""
echo "Initialising cluster..."

mgmt_curl -X POST "${MGMT_BASE}/clusterInit" \
  -d "hostname=127.0.0.1&services=kv,n1ql,index,fts&sendStats=false" \
  -o /dev/null || true

mgmt_curl -X POST "${MGMT_BASE}/node/controller/setupServices" \
  -d "services=kv,n1ql,index,fts" \
  -o /dev/null || true

mgmt_curl -X POST "${MGMT_BASE}/pools/default" \
  -d "memoryQuota=1024&indexMemoryQuota=512&ftsMemoryQuota=512" \
  -o /dev/null || true

mgmt_curl -X POST "${MGMT_BASE}/settings/web" \
  -d "username=${CB_USER}&password=${CB_PASS}&port=SAME" \
  -o /dev/null || true

mgmt_curl -X POST "${MGMT_BASE}/settings/indexes" \
  -d "storageMode=plasma" \
  -o /dev/null || true

sleep 3

# ---------------------------------------------------------------------------
# 4. Buckets
# ---------------------------------------------------------------------------
echo ""
echo "Creating buckets..."
create_bucket "${CB_BUCKET}"             512
create_bucket "${AGENT_CATALOG_BUCKET}"  256
sleep 2

# ---------------------------------------------------------------------------
# 5. Scopes & collections
# ---------------------------------------------------------------------------
echo ""
echo "Creating scopes and collections..."

create_scope      "${CB_BUCKET}"            "${CB_SCOPE}"
create_collection "${CB_BUCKET}"            "${CB_SCOPE}"              "${CB_COLLECTION}"
create_collection "${CB_BUCKET}"            "${CB_SCOPE}"              "${CB_AGENDA_COLLECTION}"

create_scope      "${AGENT_CATALOG_BUCKET}" "${AGENT_CATALOG_LOGS_SCOPE}"
create_collection "${AGENT_CATALOG_BUCKET}" "${AGENT_CATALOG_LOGS_SCOPE}" "${AGENT_CATALOG_LOGS_COLLECTION}"
create_collection "${AGENT_CATALOG_BUCKET}" "${AGENT_CATALOG_LOGS_SCOPE}" "${AGENT_CATALOG_GRADES_COLLECTION}"

sleep 2

# ---------------------------------------------------------------------------
# 6. GSI (N1QL) indexes
# ---------------------------------------------------------------------------
echo ""
wait_for_port "query service (8093)" "${N1QL_BASE}/admin/ping"

echo "Creating GSI indexes..."

run_n1ql "CREATE PRIMARY INDEX IF NOT EXISTS ON \`${CB_BUCKET}\`.\`${CB_SCOPE}\`.\`${CB_COLLECTION}\`"
run_n1ql "CREATE PRIMARY INDEX IF NOT EXISTS ON \`${CB_BUCKET}\`.\`${CB_SCOPE}\`.\`${CB_AGENDA_COLLECTION}\`"
run_n1ql "CREATE PRIMARY INDEX IF NOT EXISTS ON \`${AGENT_CATALOG_BUCKET}\`.\`${AGENT_CATALOG_LOGS_SCOPE}\`.\`${AGENT_CATALOG_LOGS_COLLECTION}\`"
run_n1ql "CREATE PRIMARY INDEX IF NOT EXISTS ON \`${AGENT_CATALOG_BUCKET}\`.\`${AGENT_CATALOG_LOGS_SCOPE}\`.\`${AGENT_CATALOG_GRADES_COLLECTION}\`"

run_n1ql "CREATE INDEX IF NOT EXISTS idx_candidates_email   ON \`${CB_BUCKET}\`.\`${CB_SCOPE}\`.\`${CB_COLLECTION}\`(email)"
run_n1ql "CREATE INDEX IF NOT EXISTS idx_candidates_name    ON \`${CB_BUCKET}\`.\`${CB_SCOPE}\`.\`${CB_COLLECTION}\`(name)"
run_n1ql "CREATE INDEX IF NOT EXISTS idx_timeslots_type     ON \`${CB_BUCKET}\`.\`${CB_SCOPE}\`.\`${CB_AGENDA_COLLECTION}\`(type)"
run_n1ql "CREATE INDEX IF NOT EXISTS idx_logs_session       ON \`${AGENT_CATALOG_BUCKET}\`.\`${AGENT_CATALOG_LOGS_SCOPE}\`.\`${AGENT_CATALOG_LOGS_COLLECTION}\`(session_id)"
run_n1ql "CREATE INDEX IF NOT EXISTS idx_grades_application ON \`${AGENT_CATALOG_BUCKET}\`.\`${AGENT_CATALOG_LOGS_SCOPE}\`.\`${AGENT_CATALOG_GRADES_COLLECTION}\`(application_id)"

run_n1ql "CREATE INDEX IF NOT EXISTS idx_timeslots_appid ON \`${CB_BUCKET}\`.\`${CB_SCOPE}\`.\`${CB_AGENDA_COLLECTION}\`(META().id) WHERE META().id LIKE 'application::%' OR META().id LIKE 'pending_email::%'"

# ---------------------------------------------------------------------------
# 7. FTS vector index (candidates_index)
# ---------------------------------------------------------------------------
echo ""
wait_for_port "FTS service (8094)" "${FTS_BASE}/api/bucket/${CB_BUCKET}/scope/${CB_SCOPE}/index"

echo "Creating FTS vector index (candidates_index)..."

if [ -f "/agentcatalog_index.json" ]; then
  INDEX_JSON="/agentcatalog_index.json"
else
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  INDEX_JSON="${SCRIPT_DIR}/../backend/agentcatalog_index.json"
fi

if [ ! -f "$INDEX_JSON" ]; then
  echo "   agentcatalog_index.json not found — skipping FTS index"
else
  # Patch the index JSON for a self-managed scoped index:
  #   sourceName  → bucket name ("default"), not collection name
  #   sourceType  → "couchbase", not "gocbcore" (Capella internal type)
  # Patterns handle optional spaces around the colon.
  sed "s/\"sourceName\" *: *\"[^\"]*\"/\"sourceName\": \"${CB_BUCKET}\"/g;
       s/\"sourceType\" *: *\"[^\"]*\"/\"sourceType\": \"couchbase\"/g" \
    "$INDEX_JSON" > /tmp/fts_index_patched.json

  # Use the scoped FTS API (Couchbase 7.6+).
  # The global /api/index endpoint creates a bucket-wide index; the application
  # queries via /api/bucket/{bucket}/scope/{scope}/index so the index must live
  # at the scoped path to be found.
  HTTP_STATUS=$(curl -s -o /tmp/fts_response.json -w "%{http_code}" \
    -u "${CB_USER}:${CB_PASS}" \
    -X PUT "${FTS_BASE}/api/bucket/${CB_BUCKET}/scope/${CB_SCOPE}/index/${CB_INDEX}" \
    -H "Content-Type: application/json" \
    -d @/tmp/fts_index_patched.json)

  if [ "$HTTP_STATUS" = "200" ]; then
    echo "   FTS index created"
  else
    echo "   FTS index response ${HTTP_STATUS}:"
    cat /tmp/fts_response.json 2>/dev/null || true
    echo ""
    echo "   Create it manually: http://${CB_HOST}:${CB_PORT}/ui/index.html#/fts"
  fi
fi

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------
echo ""
echo "Couchbase initialisation complete"
echo ""
echo "   UI : http://${CB_HOST}:${CB_PORT}"
echo "   ${CB_BUCKET} > ${CB_SCOPE} > ${CB_COLLECTION}, ${CB_AGENDA_COLLECTION}"
echo "   ${AGENT_CATALOG_BUCKET} > ${AGENT_CATALOG_LOGS_SCOPE} > ${AGENT_CATALOG_LOGS_COLLECTION}, ${AGENT_CATALOG_GRADES_COLLECTION}"
