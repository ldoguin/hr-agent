from pydantic import BaseModel, Field
from typing import Dict, List, Optional

# Pydantic models for API requests/responses
class JobMatchRequest(BaseModel):
    """Request model for job matching."""
    job_description: str = Field(..., description="The job description text to match against")
    num_results: int = Field(5, ge=1, le=20, description="Number of top candidates to return")


class CandidateResponse(BaseModel):
    """Response model for a single candidate."""
    name: str
    email: Optional[str] = None
    location: Optional[str] = None
    years_experience: int = 0
    skills: List[str] = []
    technical_skills: List[str] = []
    summary: Optional[str] = None
    match_score: float = 0.0


class JobMatchResponse(BaseModel):
    """Response model for job matching."""
    candidates: List[CandidateResponse]
    agent_reasoning: str
    total_found: int
    query_time_seconds: float


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    agent_initialized: bool
    couchbase_connected: bool
    ai_services_available: bool


class ResumeUploadResponse(BaseModel):
    """Response for resume upload."""
    success: bool
    message: str
    filename: str
    candidate_name: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None

