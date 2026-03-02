#!/bin/bash
set -e

echo "🚀 Deploying FastAPI Nano to Render..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if render CLI is installed
if ! command -v render &> /dev/null; then
    print_error "Render CLI not found. Installing..."
    
    # Install Render CLI
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install render
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl -fsSL https://raw.githubusercontent.com/render-oss/render-cli/main/install.sh | bash
    else
        print_error "Unsupported OS. Please install Render CLI manually:"
        echo "   https://render.com/docs/cli"
        exit 1
    fi
fi

print_status "Render CLI is installed"

# Check if user is logged in
if ! render config get default 2>/dev/null | grep -q "default"; then
    print_warning "Not logged in to Render. Please login:"
    render login
fi

print_status "Logged in to Render"

# Check for environment variables file
if [ ! -f "backend/.env.render" ]; then
    print_warning "backend/.env.render not found. Creating from template..."
    cat > backend/.env.render << 'EOF'
# Render Environment Variables Template
# Copy this file to .env.render and fill in your values
# Then upload to Render dashboard under your service's Environment section

API_USERNAME=
API_PASSWORD=
API_SECRET_KEY=
API_ALGORITHM=HS256
API_ACCESS_TOKEN_EXPIRE_MINUTES=5256000000

# Couchbase Configuration
CB_CONN_STRING=
CB_USERNAME=
CB_PASSWORD=
CB_BUCKET=
CB_SCOPE=agentc_data
CB_COLLECTION=candidates
CB_INDEX=candidates_index

# Capella AI Configuration
CAPELLA_API_ENDPOINT=
CAPELLA_API_LLM_KEY=
CAPELLA_API_LLM_MODEL=
CAPELLA_API_EMBEDDINGS_KEY=
CAPELLA_API_EMBEDDING_MODEL=

# OpenAI Configuration
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o

# Agent Catalog Configuration
AGENT_CATALOG_CONN_STRING=
AGENT_CATALOG_USERNAME=
AGENT_CATALOG_PASSWORD=
AGENT_CATALOG_BUCKET=

# AgentMail Configuration
AGENTMAIL_API_KEY=

# Ngrok Configuration
NGROK_AUTHTOKEN=
WEBHOOK_DOMAIN=
INBOX_USERNAME=

# Other
TOKENIZERS_PARALLELISM=false
BAMBOOHR_API_KEY=
EOF
    print_status "Created backend/.env.render template"
    echo "   Please fill in your environment variables in backend/.env.render"
    echo "   Then upload them in the Render dashboard"
fi

echo ""
echo "📋 Deployment Options:"
echo "   1. Deploy using Render Blueprint (recommended)"
echo "   2. Deploy directly to existing service"
echo "   3. Check deployment status"
echo ""

read -p "Select option (1-3): " option

case $option in
    1)
        echo ""
        print_status "Deploying using Render Blueprint..."
        echo "   This will use render.yaml to create/update the service"
        echo "   The single service will serve both API and frontend"
        echo ""
        
        # Check if blueprint already exists
        if render blueprint list 2>/dev/null | grep -q "fastapi-nano"; then
            print_status "Blueprint already exists. Updating..."
            render blueprint apply
        else
            print_status "Creating new Blueprint instance..."
            echo "   Please follow the instructions in the Render dashboard"
            echo "   to create a Blueprint from this repository."
            echo ""
            echo "   URL: https://dashboard.render.com/blueprints"
            echo ""
            echo "   The Blueprint will create a single service that:"
            echo "   - Builds the frontend (npm ci + npm run build)"
            echo "   - Copies frontend to backend/static/"
            echo "   - Installs Python dependencies with Poetry"
            echo "   - Serves everything via FastAPI + Gunicorn"
        fi
        ;;
    
    2)
        echo ""
        print_status "Deploying to existing service..."
        
        SERVICE_NAME=${1:-fastapi-nano}
        
        if render services list 2>/dev/null | grep -q "$SERVICE_NAME"; then
            print_status "Triggering deployment for $SERVICE_NAME..."
            render deploys create "$SERVICE_NAME"
        else
            print_error "Service '$SERVICE_NAME' not found."
            echo ""
            echo "   To create a new service manually:"
            echo "   render services create web --name fastapi-nano \\"
            echo "     --runtime python \\"
            echo "     --build-command './scripts/build.sh' \\"
            echo "     --start-command './scripts/start.sh'"
        fi
        ;;
    
    3)
        echo ""
        print_status "Checking deployment status..."
        echo ""
        echo "Services:"
        render services list 2>/dev/null | grep "fastapi-nano" || echo "   No fastapi-nano services found"
        echo ""
        echo "Recent Deploys:"
        render deploys list 2>/dev/null | head -20 || echo "   No deploys found"
        ;;
    
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

echo ""
print_status "Done!"
