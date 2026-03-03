# syntax = docker/dockerfile:1.4

# Multi-stage Dockerfile for building frontend and backend together
# The backend serves the frontend as static content

# ==========================================
# Stage 1: Build Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder

# Set working directory
WORKDIR /app/frontend

# Copy package files
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies (including devDependencies for build)
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build the frontend
RUN npm run build

# ==========================================
# Stage 2: Build Backend
# ==========================================
FROM python:3.13-slim AS backend-builder

# Python environment variables
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Poetry environment variables
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local' \
    POETRY_VERSION=1.8.3

# Set working directory
WORKDIR /app


# Install system dependencies
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry && poetry config virtualenvs.create false

# Copy backend dependency files
COPY backend/pyproject.toml backend/poetry.lock backend/LICENSE ./

# Install Python dependencies
RUN poetry install --no-root --without dev

# ==========================================
# Stage 3: Final Production Image
# ==========================================
FROM python:3.13-slim AS production

# Create non-root user
RUN useradd -m appuser

# Set working directory
WORKDIR /app

# Install system dependencies (curl for healthcheck, git for agentc)
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from backend-builder
COPY --from=backend-builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy backend application code
COPY backend/pyproject.toml backend/poetry.lock backend/LICENSE ./
COPY backend/svc/ ./svc/
COPY backend/email_html_template.html ./
COPY backend/email_text_template.txt ./
COPY backend/agentcatalog_index.json ./

# Copy built frontend static files to the static directory
COPY --from=frontend-builder /app/frontend/dist ./static

# Create necessary directories
RUN mkdir -p logs resumes

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser
# Environment variables
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    WORKERS=1 \
    BIND=0.0.0.0:8000 \
    TIMEOUT=60 \
    KEEPALIVE=5 \
    AGENT_CATALOG_CONN_ROOT_CERTIFICATE=/app/couchbase-root-cert.pem

# Configure git for agentc
RUN git config --global user.email "bot@couchbase.com" && \
    git config --global user.name "bot"

# Initialize git repo and agentc (at build time)
#RUN git init && git add . && git commit -m "Initial commit" &&     agentc init &&     PYTHONPATH=/app poetry run agentc index svc/prompts/ &&     PYTHONPATH=/app poetry run agentc index svc/tools/ &&     PYTHONPATH=/app poetry run agentc publish
RUN cat "$CBCERT"
RUN echo "$CBCERT" >> /app/couchbase-root-cert.pem

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/')" || exit 1

# Start the application
CMD ["bash", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WORKERS} -b ${BIND} --timeout ${TIMEOUT} --keep-alive ${KEEPALIVE} svc.main:app"]
