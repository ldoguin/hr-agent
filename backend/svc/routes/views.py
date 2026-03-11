from __future__ import annotations

import logging
import threading
import uuid

from fastapi import APIRouter, File, UploadFile, BackgroundTasks, Depends, Request, HTTPException
from typing import Any, Dict, List

from svc.apis.hr_api import HRAPI
from svc.core.agent import AgentManager
from svc.core.db import CouchbaseClient
from svc.models.models import HealthResponse, JobMatchRequest, JobMatchResponse, ResumeUploadResponse, CandidateResponse, InitialMeetingRequest, InitialMeetingResponse, ConversationGradeResponse

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
    """
    Health check endpoint.

    Used by the React frontend (AgentJobMatch component) to:
    - Display agent initialization status in the UI
    - Show database connection status
    - Indicate AI services availability
    - Update the status bar with real-time health information
    """
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

    Used by the React frontend (UploadResumes page) to:
    - Accept PDF resume uploads from users
    - Save files to the resumes directory
    - Process resumes in background (text extraction, LLM analysis, vector embedding)
    - Store candidate data in Couchbase for future candidate searches
    - Update the frontend with success/error messages via toast notifications

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

    Used by the React frontend (AgentJobMatch component) to:
    - Display total number of candidates in the database
    - Show top skills distribution for database overview
    - Update statistics in the UI after resume uploads
    - Provide real-time database status information
    """
    agent = req.state.agent_manager
    return HRAPI.get_stats(agent)

@router.post("/api/search", response_model=JobMatchResponse)
async def search_candidates_direct(req: Request, request: JobMatchRequest):
    """
    Direct vector search for candidates (FAST - bypasses agent reasoning).

    Used by the React frontend (AgentJobMatch component) to:
    - Perform near-instant candidate matching for job descriptions
    - Display search results with match scores and candidate details
    - Show agent reasoning (though simplified compared to full agent)
    - Update the results tab with found candidates and query time
    - Handle loading states and error messages in the UI

    This endpoint directly calls the vector search tool without the ReAct agent loop,
    providing near-instant results.
    """
    agent = req.state.agent_manager
    return HRAPI.search_candidates_direct(agent, request)

@router.post('/api/send_meeting_request', response_model=InitialMeetingResponse)
async def send_meeting_request(req: Request, request: InitialMeetingRequest):
    """
    Send initial meeting request email and create application document.

    Creates an application in the database and sends an invitation email.
    """
    agent = req.state.agent_manager
    return HRAPI.send_meeting_request(request, agent)

@router.get("/api/traces")
async def get_traces(req: Request, limit: int = 50, offset: int = 0, session: str = None, date: str = None):
    """Return agent activity logs grouped by session. Pass date=YYYY-MM-DD to filter by day."""
    agent = req.state.agent_manager
    return HRAPI.get_traces(agent, limit=limit, offset=offset, session=session, date=date)

@router.post("/api/traces/{session_id}/grade", response_model=ConversationGradeResponse)
async def grade_session(session_id: str, req: Request):
    """Grade the full session conversation using the LLM evaluator."""
    agent = req.state.agent_manager
    return HRAPI.grade_session(session_id, agent)

@router.post("/api/traces/{session_id}/logs/{log_id}/grade", response_model=ConversationGradeResponse)
async def grade_log(session_id: str, log_id: str, req: Request):
    """Grade a single log entry in isolation."""
    agent = req.state.agent_manager
    return HRAPI.grade_log(session_id, log_id, agent)

@router.get("/api/traces/{session_id}/grades")
async def get_session_grades(session_id: str, req: Request):
    """Return all stored grades for a session (both session-level and per-log)."""
    agent = req.state.agent_manager
    grades = HRAPI._load_grades([session_id], agent)
    return {"grades": list(grades.values())}

@router.post('/webhook/agentmail')
async def receive_email_notification(req: Request):
    """
    Webhook endpoint to receive incoming email notifications.

    Handles email replies and processes them using the email agent.
    """
    agent = req.state.agent_manager
    return await HRAPI.receive_email_notification(req, agent)
