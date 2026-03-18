#!/bin/sh
# Starts Couchbase Server and initialises the cluster with all required
# services on first boot. On subsequent starts the data volume already
# contains a configured node, so the init calls are no-ops.

CB_USER="${CB_USER:-Administrator}"
CB_PASS="${CB_PASS:-password}"
BASE="http://127.0.0.1:8091"

# Start Couchbase in the background
/entrypoint.sh couchbase-server &
CB_PID=$!

# Wait for the REST API to respond
echo "[entrypoint] Waiting for Couchbase REST API..."
i=0
while [ $i -lt 60 ]; do
  if curl -sf "${BASE}/pools" -o /dev/null 2>/dev/null; then
    echo "[entrypoint] REST API ready"
    break
  fi
  sleep 2
  i=$((i + 1))
done

# Initialize node with all services (no-op if already done)
echo "[entrypoint] Configuring services..."
curl -sf -X POST "${BASE}/node/controller/setupServices" \
  -d "services=kv,n1ql,index,fts" -o /dev/null 2>/dev/null || true

curl -sf -X POST "${BASE}/pools/default" \
  -d "memoryQuota=1024&indexMemoryQuota=512&ftsMemoryQuota=512" \
  -o /dev/null 2>/dev/null || true

curl -sf -X POST "${BASE}/settings/web" \
  -d "username=${CB_USER}&password=${CB_PASS}&port=SAME" \
  -o /dev/null 2>/dev/null || true

curl -sf -X POST "${BASE}/settings/indexes" \
  -d "storageMode=plasma" \
  -o /dev/null 2>/dev/null || true

echo "[entrypoint] Node configuration done"

# Hand off to the Couchbase process
wait $CB_PID
