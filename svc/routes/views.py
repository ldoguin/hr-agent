from __future__ import annotations

import logging

from fastapi import APIRouter, File, UploadFile, BackgroundTasks, Depends, Request
from typing import Any, Dict, List

from svc.apis.hr_api import HRAPI
from svc.core.agent import AgentManager
from svc.core.db import CouchbaseClient
from svc.models.models import HealthResponse, JobMatchRequest, JobMatchResponse, ResumeUploadResponse, CandidateResponse

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

# API Endpoints

@router.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Agentic HR Recruitment API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }

@router.get("/health", response_model=HealthResponse)
async def health_check(req: Request
):
    """Health check endpoint."""
    agent = req.state.agent_manager
    return HRAPI.get_health_status(agent)

@router.post("/api/match", response_model=JobMatchResponse)
async def match_candidates(req: Request, request: JobMatchRequest):
    """
    Match candidates to a job description using the AI agent.

    This endpoint uses the LangChain ReAct agent to:
    1. Analyze the job description
    2. Search for matching candidates using vector similarity
    3. Provide ranked recommendations with reasoning
    """
    agent = req.state.agent_manager
    return HRAPI.match_candidates(request, agent)

@router.post("/api/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(
    req: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a resume PDF for processing.

    The resume will be:
    1. Saved to the resumes directory
    2. Processed in the background (parsing + embedding generation)
    3. Stored in Couchbase for future searches
    """
    agent = req.state.agent_manager
    return await HRAPI.upload_resume(background_tasks, file, agent)

@router.get("/api/candidates", response_model=List[CandidateResponse])
async def list_candidates(req: Request, limit: int = 10, offset: int = 0):
    """
    List all candidates in the database.

    Useful for browsing the candidate pool or testing.
    """
    agent = req.state.agent_manager
    return HRAPI.list_candidates(limit, offset, agent)

@router.get("/api/stats", response_model=Dict[str, Any])
async def get_stats(req: Request):
    """
    Get statistics about the candidate database.
    """
    agent = req.state.agent_manager
    return HRAPI.get_stats(agent)

@router.post("/api/search", response_model=JobMatchResponse)
async def search_candidates_direct(req: Request, request: JobMatchRequest):
    """
    Direct vector search for candidates (FAST - bypasses agent reasoning).

    This endpoint directly calls the vector search tool without the ReAct agent loop,
    providing near-instant results.
    """
    agent = req.state.agent_manager
    return HRAPI.search_candidates_direct(agent, request)