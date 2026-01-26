from contextlib import asynccontextmanager
import os
import logging
import httpx
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, Response
from typing import Any, Dict, List

from starlette.middleware.cors import CORSMiddleware
from svc.core.ws import ConnectionManager

from svc.routes import views
from svc.core.logger import configure_logger
from svc.core.agent import AgentManager
from svc.core.config import CB_CONN_STRING, CB_USERNAME, CB_PASSWORD, DEFAULT_BUCKET

# Configure logging at module level
configure_logger()
logger = logging.getLogger("hrapp" )

# Global WebSocket session storage
websocket_sessions: Dict[str, WebSocket] = {}
active_connections = set()

# Startup and shutdown events
async def init_couchbase():
    """Initialize the couchbase connection.
    """
    logger.info("🚀 Connecting to Couchbase...")
    # Initialize the agent manager
    from svc.core.db import CouchbaseClient
    couchbase_client = CouchbaseClient(CB_CONN_STRING, CB_USERNAME, CB_PASSWORD, DEFAULT_BUCKET)
    couchbase_client.connect()
    return couchbase_client

async def init_agent(couchbase_client):
    """Initialize the agent on startup.

    Uses Agent Catalog v1.0.0 API for catalog initialization.
    """
    logger.info("🚀 Starting Agentic HR API Server...")
    # Initialize the agent manager
    agent_manager = AgentManager(couchbase_client)
    await agent_manager.setup_environment()
    return agent_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.error("👋 Startring Lifespan...")
    couchbase_client = await init_couchbase()
    agent_manager = await init_agent(couchbase_client=couchbase_client) 
    logger.error("👋 fnishing Lifespan...")
    yield  {"couchbase_client": couchbase_client, "agent_manager": agent_manager }
    """Cleanup on shutdown."""
    logger.info("👋 Shutting down Agentic HR API Server...")
    couchbase_client.close()
    agent_manager.close()

# Initialize FastAPI app
app = FastAPI(
    title="Agentic HR Recruitment API",
    description="AI-powered candidate matching using Agent Catalog and Couchbase Vector Search",
    version="1.0.0",
    lifespan=lifespan
)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

def create_app() -> FastAPI:
    """Create a FastAPI application."""
    # Set all CORS enabled origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
        "http://localhost:5173",  # Vite default port
        "http://localhost:3000",  # Alternative port
        "http://localhost:8080",
        "*",  # Allow all origins in development
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    #app.include_router(auth.router)
    app.include_router(views.router)
    return app


app = create_app()