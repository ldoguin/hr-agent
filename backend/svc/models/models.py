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

class InitialMeetingRequest(BaseModel):
    """Request model for initial meeting request."""
    email: str = Field(..., description="The email of the candidate")
    first_name: str = Field( default = "Candidate", description="The first name of the candidate")
    last_name: str = Field( default = "", description="The last name of the candidate")
    position: str = Field(default = "Software Developer",  description="The position the candidate is applying to")
    company_name: str = Field(default = "TechCorp Inc.",  description="The name of the hiring company")

class InitialMeetingResponse(BaseModel):
    """Response for Initial meeting request."""
    application_id: str

class ApplicationResponse(BaseModel):
    """A candidate application document."""
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    position: Optional[str] = None
    company_name: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    email_sent_at: Optional[str] = None
    session_id: Optional[str] = None


class MeetingResponse(BaseModel):
    """A booked timeslot extracted from a month calendar document."""
    meeting_id: str          # application:: key of the linked application
    start_time: str
    end_time: str
    duration_minutes: Optional[int] = None
    month: Optional[str] = None


class PendingEmailResponse(BaseModel):
    """An outgoing email queued for human review before sending."""
    application_id: str
    subject: str
    to: str
    text: str = ""                   # hydrated at read time from agentc trace or text_override
    text_override: Optional[str] = None  # set when user edits the draft
    email_type: str = "reply"        # "initial" | "reply"
    status: str = "pending"          # "pending" | "sent" | "discarded"
    created_at: Optional[str] = None
    sent_at: Optional[str] = None
    inbox_id: Optional[str] = None
    message_id: Optional[str] = None


class AutoSendSettings(BaseModel):
    """Global toggle: auto-send agent emails when grade >= threshold."""
    enabled: bool = False
    min_score: int = 9


class ConversationGradeResponse(BaseModel):
    """Result of grading an email scheduling conversation."""
    session: str
    log_id: Optional[str] = None        # set when grading a single log entry
    grade_scope: str = "session"        # "session" | "log"
    score: int = Field(..., ge=0, le=10)
    label: str
    summary: str
    issues: List[str] = []
    strengths: List[str] = []
    off_topic: bool = False
    anomalies: List[str] = []
    stored_at: Optional[str] = None
    error: Optional[str] = None