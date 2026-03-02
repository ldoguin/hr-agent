#!/bin/bash
set -e

echo "🚀 Building FastAPI Nano for Render..."

# =============================================================================
# Build Frontend
# =============================================================================
echo "📦 Building Frontend..."
cd frontend

# Use npm ci for reproducible builds
echo "   Installing dependencies..."
npm ci

# Build the application
echo "   Building application..."
npm run build

cd ..

# =============================================================================
# Move frontend build to backend static directory
# =============================================================================
echo "📂 Moving frontend build to backend/static..."
mkdir -p backend/static
cp -r frontend/dist/* backend/static/
echo "   ✓ Frontend files copied to backend/static/"

# =============================================================================
# Build Backend
# =============================================================================
echo "📦 Building Backend..."
cd backend

# Install Poetry if not already installed
if ! command -v poetry &> /dev/null; then
    echo "   Installing Poetry..."
    pip install poetry
fi

# Configure Poetry to not create virtualenv (Render uses container isolation)
poetry config virtualenvs.create false

# Install dependencies
echo "   Installing dependencies with Poetry..."
poetry install --no-root --without dev

# Setup git for agentc (required for Agent Catalog)
echo "🔧 Setting up git for Agent Catalog..."
git config --global user.email "bot@couchbase.com"
git config --global user.name "bot"

# Initialize git repo if not exists
if [ ! -d .git ]; then
    git init
    git add .
    git commit -m "Initial commit for Render deployment"
fi

# Initialize Agent Catalog (if needed)
echo "🔧 Initializing Agent Catalog..."
if command -v agentc &> /dev/null; then
    agentc init || true
    
    # Index prompts and tools
    PYTHONPATH=$(pwd) poetry run agentc index svc/prompts/ || true
    PYTHONPATH=$(pwd) poetry run agentc index svc/tools/ || true
    PYTHONPATH=$(pwd) poetry run agentc publish || true
else
    echo "   ⚠️  agentc not found, skipping Agent Catalog initialization"
fi

cd ..

echo "✅ Build completed successfully!"
echo ""
echo "   Backend: ready with static files in backend/static/"
echo "   Frontend: built and served by backend at /"
