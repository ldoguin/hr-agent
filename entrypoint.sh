#!/bin/bash
set -e

# Write the Couchbase root certificate from environment variable
if [ -n "$CBCERT" ]; then
    echo -e "$CBCERT"  > /app/couchbase-root-cert.pem
fi

# Configure git if not already configured
git config --global user.email "bot@couchbase.com" || true
git config --global user.name "bot" || true

# Initialize git repo if not already initialized
if [ ! -d /app/.git ]; then
    cd /app && git init && git add . && git commit -m "Initial commit" || true
fi

# Initialize agentc if not already initialized
if [ ! -d /app/.agentc ]; then
    cd /app && agentc init || true
fi

# Index prompts and tools
cd /app
PYTHONPATH=/app poetry run agentc index svc/prompts/ || true
PYTHONPATH=/app poetry run agentc index svc/tools/ || true
PYTHONPATH=/app poetry run agentc publish || true
# Start the application
exec "$@"