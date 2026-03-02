# Deploying to Render

This guide explains how to deploy the FastAPI Nano application to [Render](https://render.com/).

## Architecture

This application uses a **single service deployment** architecture:

- **One Web Service** hosts both the FastAPI backend AND serves the built frontend static files
- The frontend (Vite/React) is built during deployment and copied to `backend/static/`
- FastAPI's `StaticFiles` middleware serves the frontend at `/` and API at `/api/*`

```
┌─────────────────────────────────────────────────────────────┐
│                    Render Web Service                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  FastAPI + Gunicorn                   │   │
│  │  ┌─────────────────┐      ┌──────────────────────┐   │   │
│  │  │   API Routes    │      │   Static Files       │   │   │
│  │  │   (/api/*)      │      │   (/ - frontend)     │   │   │
│  │  │   (/health/)    │      │   (/assets/*)        │   │   │
│  │  └─────────────────┘      └──────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Using Render Blueprint (Recommended)

The easiest way to deploy is using Render's Blueprint feature, which uses Infrastructure as Code defined in `render.yaml`.

1. **Push your code to a Git repository** (GitHub, GitLab, or Bitbucket)

2. **Go to the Render Dashboard**: https://dashboard.render.com/blueprints

3. **Create a new Blueprint Instance**
   - Click "New Blueprint Instance"
   - Connect your repository
   - Render will automatically detect `render.yaml` and create the service

4. **Set Environment Variables**
   - After the service is created, go to the Environment section
   - Add all required secret environment variables (see below)

5. **Deploy**
   - Render will automatically build and deploy your application
   - The build process:
     1. Builds the frontend (`npm ci && npm run build`)
     2. Copies frontend to `backend/static/`
     3. Installs Python dependencies with Poetry
     4. Starts Gunicorn with Uvicorn workers

### Option 2: Using Render CLI

1. **Install the Render CLI**:
   ```bash
   # macOS
   brew install render

   # Linux
   curl -fsSL https://raw.githubusercontent.com/render-oss/render-cli/main/install.sh | bash
   ```

2. **Login to Render**:
   ```bash
   render login
   ```

3. **Run the deployment script**:
   ```bash
   ./scripts/deploy.sh
   ```

### Option 3: Manual Service Creation

1. **Create Web Service**:
   - Go to https://dashboard.render.com/create?type=web
   - Select your repository
   - Configure:
     - **Name**: `fastapi-nano`
     - **Runtime**: Python 3
     - **Build Command**: `./scripts/build.sh`
     - **Start Command**: `./scripts/start.sh`
   - Add environment variables
   - Create service

## Environment Variables

Copy `backend/.env.render.example` to create your environment configuration:

```bash
cp backend/.env.render.example backend/.env.render
```

Then edit `backend/.env.render` with your actual values and upload to Render's dashboard.

### Couchbase Root Certificate (Important!)

The Couchbase root certificate should **NOT** be committed to git. Use one of these cloud-native approaches:

#### Option A: Render Secret File (Recommended)

1. Go to your service in Render Dashboard
2. Click "Secret Files" in the left sidebar
3. Upload your certificate file:
   - **Name**: `couchbase-root-cert.pem`
   - **Content**: Paste the certificate content from `burgundydavidluckham-root-certificate.txt`
4. The certificate will be mounted at `/etc/secrets/couchbase-root-cert.pem`
5. Set environment variable: `CB_ROOT_CERTIFICATE_PATH=/etc/secrets/couchbase-root-cert.pem`

#### Option B: Base64-Encoded Environment Variable

Encode the certificate and set as environment variable:

```bash
# On macOS/Linux
cat burgundydavidluckham-root-certificate.txt | base64 -w 0

# Copy the output and set as CB_ROOT_CERTIFICATE_B64 in Render
```

### Required Variables

| Variable | Description |
|----------|-------------|
| `API_SECRET_KEY` | Secret key for JWT tokens |
| `API_USERNAME` | API authentication username |
| `API_PASSWORD` | API authentication password |
| `CB_CONN_STRING` | Couchbase connection string |
| `CB_USERNAME` | Couchbase username |
| `CB_PASSWORD` | Couchbase password |
| `CB_BUCKET` | Couchbase bucket name |
| `CAPELLA_API_LLM_KEY` | Capella AI LLM API key |
| `CAPELLA_API_EMBEDDINGS_KEY` | Capella AI Embeddings API key |
| `CB_ROOT_CERTIFICATE_PATH` | Path to Couchbase root cert (if using secret file) |

### Optional Variables

| Variable | Description |
|----------|-------------|
| `CB_ROOT_CERTIFICATE_B64` | Base64-encoded Couchbase root cert (alternative) |
| `OPENAI_API_KEY` | OpenAI API key (fallback) |
| `AGENTMAIL_API_KEY` | AgentMail API key |
| `NGROK_AUTHTOKEN` | Ngrok auth token (for webhooks) |
| `WORKERS` | Gunicorn workers (default: 2) |
| `TIMEOUT` | Request timeout in seconds (default: 60) |

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `build.sh` | Builds frontend, copies to backend/static, installs Python deps |
| `start.sh` | Starts Gunicorn with Uvicorn workers |
| `deploy.sh` | Interactive deployment helper with CLI |

## How It Works

### Build Process (`scripts/build.sh`)

1. **Build Frontend**:
   ```bash
   cd frontend
   npm ci
   npm run build
   ```

2. **Copy Static Files**:
   ```bash
   mkdir -p backend/static
   cp -r frontend/dist/* backend/static/
   ```

3. **Install Backend Dependencies**:
   ```bash
   cd backend
   poetry install --no-root --without dev
   ```

4. **Initialize Agent Catalog** (if available):
   ```bash
   git init  # Required for agentc
   agentc init
   agentc index svc/prompts/
   agentc index svc/tools/
   agentc publish
   ```

### Start Process (`scripts/start.sh`)

1. Change to backend directory
2. Verify static files exist
3. Start Gunicorn with Uvicorn workers:
   ```bash
   gunicorn -k uvicorn.workers.UvicornWorker svc.main:app
   ```

## Local Development

To test the production build locally:

```bash
# Build everything
./scripts/build.sh

# Start the server
./scripts/start.sh
```

The application will be available at `http://localhost:8000`

## Health Checks

The backend includes a health check endpoint at `/health/` that Render uses to verify the service is running.

## Troubleshooting

### Build Failures

1. **Check logs in Render Dashboard**: Go to your service → Logs
2. **Verify environment variables**: All required secrets must be set
3. **Check Node/Python versions**: Ensure compatible versions are selected

### Frontend Not Loading

1. **Verify static files**: Check build logs for `✓ Frontend files copied to backend/static/`
2. **Check static directory**: Ensure `backend/static/index.html` exists
3. **Review catch-all route**: The backend's `/{full_path:path}` route should serve `index.html`

### Runtime Issues

1. **Database connection**: Verify Couchbase connection string and credentials
2. **Memory issues**: Upgrade to a higher plan if you run out of memory
3. **Cold starts**: First request after deployment may be slow due to initialization

### Agent Catalog Issues

If Agent Catalog initialization fails during build:
- The build script continues even if `agentc` commands fail
- You may need to run initialization manually after first deployment

## Custom Domains

To use a custom domain:

1. Go to your service in Render Dashboard
2. Click "Settings" → "Custom Domains"
3. Add your domain and follow the DNS configuration instructions

## Updates and Redeployments

- **Automatic**: Push to your repository's main branch triggers auto-deployment
- **Manual**: Use the "Deploy Latest Commit" button in Render Dashboard
- **CLI**: Run `render deploys create fastapi-nano`

## Support

- [Render Documentation](https://render.com/docs)
- [Render CLI Documentation](https://render.com/docs/cli)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
