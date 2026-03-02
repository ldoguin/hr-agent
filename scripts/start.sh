#!/bin/bash
set -e

echo "🚀 Starting FastAPI Nano on Render..."

cd backend

# =============================================================================
# Handle Couchbase Root Certificate
# =============================================================================
# Option A: Secret file (recommended for Render)
# The certificate is mounted as a secret file at CB_ROOT_CERTIFICATE_PATH
if [ -n "$CB_ROOT_CERTIFICATE_PATH" ] && [ -f "$CB_ROOT_CERTIFICATE_PATH" ]; then
    echo "🔒 Using Couchbase root certificate from secret file: $CB_ROOT_CERTIFICATE_PATH"
    export AGENT_CATALOG_CONN_ROOT_CERTIFICATE="$CB_ROOT_CERTIFICATE_PATH"
    
# Option B: Base64-encoded certificate from environment variable
elif [ -n "$CB_ROOT_CERTIFICATE_B64" ]; then
    echo "🔒 Decoding Couchbase root certificate from environment variable..."
    CERT_FILE="/tmp/couchbase-root-cert.pem"
    echo "$CB_ROOT_CERTIFICATE_B64" | base64 -d > "$CERT_FILE"
    export AGENT_CATALOG_CONN_ROOT_CERTIFICATE="$CERT_FILE"
    echo "   ✓ Certificate written to $CERT_FILE"
    
# Option C: Check if certificate file exists in repo (fallback, not recommended)
elif [ -f "burgundydavidluckham-root-certificate.txt" ]; then
    echo "⚠️  Warning: Using certificate from repository (not recommended for production)"
    export AGENT_CATALOG_CONN_ROOT_CERTIFICATE="$(pwd)/burgundydavidluckham-root-certificate.txt"
    
else
    echo "⚠️  Warning: No Couchbase root certificate configured"
    echo "   Set either:"
    echo "   - CB_ROOT_CERTIFICATE_PATH (path to secret file)"
    echo "   - CB_ROOT_CERTIFICATE_B64 (base64-encoded certificate)"
fi

# =============================================================================
# Configuration
# =============================================================================
export WORKERS=${WORKERS:-2}
export BIND=${BIND:-0.0.0.0:8000}
export TIMEOUT=${TIMEOUT:-60}
export KEEPALIVE=${KEEPALIVE:-5}

echo "⚙️  Configuration:"
echo "   Workers: $WORKERS"
echo "   Bind: $BIND"
echo "   Timeout: $TIMEOUT"
echo "   Keepalive: $KEEPALIVE"

# Verify static files exist
if [ -d "static" ] && [ -f "static/index.html" ]; then
    echo "   Static files: ✓ found (frontend will be served)"
else
    echo "   ⚠️  Warning: static files not found, frontend may not be served correctly"
fi

# =============================================================================
# Start Application
# =============================================================================
echo "🌐 Starting Gunicorn with Uvicorn workers..."
exec gunicorn \
    -k uvicorn.workers.UvicornWorker \
    -w "$WORKERS" \
    -b "$BIND" \
    --timeout "$TIMEOUT" \
    --keep-alive "$KEEPALIVE" \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance \
    svc.main:app
