from __future__ import annotations
import logging
import time
import concurrent.futures
import re
import threading
import uuid
import ngrok
from agentmail import AgentMail
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, File, UploadFile, HTTPException, Request
from jinja2 import Template

from svc.core.config import DEFAULT_BUCKET, DEFAULT_COLLECTION, DEFAULT_SCOPE, DEFAULT_INDEX, DEFAULT_RESUME_DIR
from svc.core.agent import AgentManager
from agentmail import AgentMail
from jinja2 import Template
from svc.core.config import AGENTMAIL_API_KEY
from svc.core.timeslot_manager import upsert_application, _application_key, get_application, get_candidate_by_email, get_agenda_collection
from svc.models.models import HealthResponse, JobMatchRequest, JobMatchResponse, ResumeUploadResponse, CandidateResponse, InitialMeetingRequest, InitialMeetingResponse
from svc.data.resume_loader import extract_text_from_pdf, analyze_resume_with_llm, format_candidate_for_embedding
from svc.tools.search_candidates_vector import search_candidates_vector
from langchain_couchbase.vectorstores import CouchbaseVectorStore

logger = logging.getLogger("uvicorn.error")

def get_agentmail_client():
    """Get AgentMail client with proper initialization."""
    api_key = AGENTMAIL_API_KEY
    if not api_key:
        raise ValueError("AGENTMAIL_API_KEY environment variable is required for AgentMail functionality")
    return AgentMail(api_key=api_key)

def render_email_template(template_content, template_vars):
    """Render Jinja2 template with variables."""
    template = Template(template_content)
    return template.render(**template_vars)

class HRAPI:
    """Main API class for HR-related operations."""

    @staticmethod
    def get_health_status(agent_manager: AgentManager) -> HealthResponse:
        """
        Get health status of the system.

        Called by the React frontend's AgentJobMatch component via GET /health to:
        - Check if the AI agent is properly initialized
        - Verify Couchbase database connectivity
        - Confirm AI services (embeddings, LLM) are available
        - Display real-time status indicators in the UI status bar
        """
        agent_ok = agent_manager.agent_executor is not None
        couchbase_ok = agent_manager.couchbase_client is not None and agent_manager.couchbase_client.cluster is not None
        ai_ok = agent_manager.embeddings is not None and agent_manager.llm is not None

        status = "healthy" if (agent_ok and couchbase_ok and ai_ok) else "degraded"

        return HealthResponse(
            status=status,
            agent_initialized=agent_ok,
            couchbase_connected=couchbase_ok,
            ai_services_available=ai_ok,
        )

    @staticmethod
    def match_candidates(request: JobMatchRequest, agent_manager: AgentManager) -> JobMatchResponse:
        """
        Match candidates to a job description using the AI agent.

        This method uses the LangChain ReAct agent to:
        1. Analyze the job description
        2. Search for matching candidates using vector similarity
        3. Provide ranked recommendations with reasoning
        """
        if agent_manager.agent_executor is None:
            raise HTTPException(
                status_code=503,
                detail="Agent not initialized. Please check server logs and restart."
            )

        try:
            start_time = time.time()

            logger.info(f"🔍 Processing job match request: {request.job_description[:100]}...")

            # Run the agent with timeout using thread pool
            def run_agent():
                return agent_manager.agent_executor.invoke({"input": request.job_description})

            # Execute with 60 second timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_agent)
                try:
                    response = future.result(timeout=60)
                except concurrent.futures.TimeoutError:
                    logger.warning("⏰ Agent execution timed out after 60 seconds")
                    response = {"output": "Search timed out. Please try a shorter query.", "intermediate_steps": []}

            # Extract the agent's response
            agent_output = response.get("output", "")
            intermediate_steps = response.get("intermediate_steps", [])

            # Try to extract structured candidate data from the agent's response
            candidates = []

            # Look through intermediate steps to find tool results (PRIORITIZE THIS)
            for step in intermediate_steps:
                if len(step) >= 2:
                    action, observation = step
                    if "search_candidates_vector" in str(action):
                        # Parse the observation text to extract candidate info
                        logger.info(f"📋 Found search results in intermediate steps")
                        candidates_data = HRAPI.parse_candidates_from_text(str(observation))
                        candidates.extend(candidates_data)

            # If no candidates from intermediate steps, try to parse from final output
            if not candidates:
                candidates = HRAPI.parse_candidates_from_text(agent_output)

            query_time = time.time() - start_time

            logger.info(f"✅ Found {len(candidates)} candidates in {query_time:.2f}s")

            return JobMatchResponse(
                candidates=candidates,
                agent_reasoning=agent_output if agent_output else "Results extracted from vector search. See candidates below.",
                total_found=len(candidates),
                query_time_seconds=round(query_time, 2),
            )

        except Exception as e:
            logger.exception(f"❌ Error processing match request: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def parse_candidates_from_text(text: str) -> List[CandidateResponse]:
        """
        Parse candidate information from agent's text output.
        This is a helper function to extract structured data from natural language.
        """
        candidates = []

        # Try to find candidate blocks in the text
        # Look for patterns like "**Candidate 1: Name**" or "1. **Name**"
        candidate_pattern = r'\*\*(?:Candidate \d+:|[^\*]+)\*\*'
        matches = re.finditer(candidate_pattern, text)

        for match in matches:
            start = match.start()
            # Find the next candidate or end of text
            next_match = re.search(candidate_pattern, text[start + len(match.group()):])
            end = start + len(match.group()) + next_match.start() if next_match else len(text)

            candidate_block = text[start:end]

            # Extract candidate data
            candidate_data = HRAPI.extract_candidate_data(candidate_block)
            if candidate_data:
                candidates.append(candidate_data)

        # If no structured candidates found, return a default response
        if not candidates:
            candidates.append(CandidateResponse(
                name="Results in agent reasoning",
                email="",
                location="",
                years_experience=0,
                skills=[],
                technical_skills=[],
                summary="See agent reasoning for full details",
                match_score=0.0,
            ))

        return candidates

    @staticmethod
    def extract_candidate_data(text: str) -> Optional[CandidateResponse]:
        """Extract structured candidate data from a text block."""
        try:
            # Extract name
            name_match = re.search(r'\*\*(?:Candidate \d+: )?([^\*\n]+)\*\*', text)
            name = name_match.group(1).strip() if name_match else "Unknown"

            # Extract email
            email_match = re.search(r'Email:\s*([^\n]+)', text)
            email = email_match.group(1).strip() if email_match else None

            # Extract location
            location_match = re.search(r'Location:\s*([^\n]+)', text)
            location = location_match.group(1).strip() if location_match else None

            # Extract years of experience
            years_match = re.search(r'(?:Years of Experience|Experience):\s*(\d+)', text)
            years_experience = int(years_match.group(1)) if years_match else 0

            # Extract match score
            score_match = re.search(r'Match Score:\s*([\d.]+)', text)
            match_score = float(score_match.group(1)) if score_match else 0.0

            # Extract skills
            skills_match = re.search(r'Skills:\s*([^\n]+)', text)
            skills = [s.strip() for s in skills_match.group(1).split(',')] if skills_match else []

            # Extract technical skills
            tech_skills_match = re.search(r'Technical Skills:\s*([^\n]+)', text)
            technical_skills = [s.strip() for s in tech_skills_match.group(1).split(',')] if tech_skills_match else []

            # Extract summary
            summary_match = re.search(r'Summary:\s*([^\n]+)', text)
            summary = summary_match.group(1).strip() if summary_match else None

            return CandidateResponse(
                name=name,
                email=email,
                location=location,
                years_experience=years_experience,
                skills=skills,
                technical_skills=technical_skills,
                summary=summary,
                match_score=match_score,
            )
        except Exception as e:
            logger.warning(f"Error extracting candidate data: {e}")
            return None

    @staticmethod
    async def upload_resume(background_tasks: BackgroundTasks, file: UploadFile, agent_manager: AgentManager) -> ResumeUploadResponse:
        """
        Upload a resume PDF for processing.

        The resume will be:
        1. Saved to the resumes directory
        2. Processed in the background (parsing + embedding generation)
        3. Stored in Couchbase for future searches
        """
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )

        try:
            # Save file to resumes directory
            resume_dir = Path(DEFAULT_RESUME_DIR)
            resume_dir.mkdir(exist_ok=True)

            file_path = resume_dir / file.filename

            # Save uploaded file
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            logger.info(f"📄 Saved resume: {file.filename}")

            # Schedule background processing
            background_tasks.add_task(
                HRAPI.process_resume_background,
                file_path,
                file.filename,
                agent_manager
            )

            return ResumeUploadResponse(
                success=True,
                message="Resume uploaded successfully and queued for processing",
                filename=file.filename,
            )

        except Exception as e:
            logger.exception(f"❌ Error uploading resume: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def process_resume_background(file_path: Path, filename: str, agent_manager: AgentManager):
        """Background task to process uploaded resume."""
        try:
            logger.info(f"🔄 Processing resume in background: {filename}")

            # Extract text
            text = extract_text_from_pdf(str(file_path))
            if not text.strip():
                logger.warning(f"No text extracted from {filename}")
                return

            # Analyze with LLM
            analysis = analyze_resume_with_llm(text, agent_manager.llm)
            analysis["filename"] = filename

            # Format for embedding
            formatted_text = format_candidate_for_embedding(analysis)

            # Store in Couchbase
            if agent_manager.couchbase_client and agent_manager.embeddings:
                vector_store = CouchbaseVectorStore(
                    cluster=agent_manager.couchbase_client.cluster,
                    bucket_name=DEFAULT_BUCKET,
                    scope_name=DEFAULT_SCOPE,
                    collection_name=DEFAULT_COLLECTION,
                    embedding=agent_manager.embeddings,
                    index_name=DEFAULT_INDEX,
                )

                vector_store.add_texts(
                    texts=[formatted_text],
                    metadatas=[analysis],
                )

                logger.info(f"✅ Successfully processed resume: {filename}")
            else:
                logger.warning("Cannot store resume - Couchbase client not initialized")

        except Exception as e:
            logger.exception(f"❌ Error processing resume {filename}: {e}")

    @staticmethod
    def list_candidates(agent_manager: AgentManager, limit: int = 10, offset: int = 0) -> List[CandidateResponse]:
        """
        List all candidates in the database.

        Useful for browsing the candidate pool or testing.
        """
        if agent_manager.couchbase_client is None or agent_manager.couchbase_client.cluster is None:
            raise HTTPException(
                status_code=503,
                detail="Database not connected"
            )

        try:
            bucket_name = DEFAULT_BUCKET
            scope_name = DEFAULT_SCOPE
            collection_name = DEFAULT_COLLECTION

            # Query candidates
            query = f"""
                SELECT name, email, location, years_experience, skills, technical_skills, summary
                FROM `{bucket_name}`.`{scope_name}`.`{collection_name}`
                LIMIT {limit} OFFSET {offset}
            """

            result = agent_manager.couchbase_client.cluster.query(query)

            candidates = []
            for row in result:
                candidates.append(CandidateResponse(
                    name=row.get("name", "Unknown"),
                    email=row.get("email"),
                    location=row.get("location"),
                    years_experience=row.get("years_experience", 0),
                    skills=row.get("skills", []),
                    technical_skills=row.get("technical_skills", []),
                    summary=row.get("summary"),
                    match_score=0.0,
                ))

            return candidates

        except Exception as e:
            logger.exception(f"❌ Error listing candidates: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_stats(agent_manager: AgentManager) -> Dict[str, Any]:
        """
        Get statistics about the candidate database.

        Called by the React frontend's AgentJobMatch component via GET /api/stats to:
        - Display the total number of candidates in the database
        - Show top skills distribution in the database overview section
        - Update statistics after resume uploads via React Query cache invalidation
        - Provide real-time database status information for the UI
        """
        if agent_manager.couchbase_client is None or agent_manager.couchbase_client.cluster is None:
            raise HTTPException(
                status_code=503,
                detail="Database not connected"
            )

        try:
            bucket_name = DEFAULT_BUCKET
            scope_name = DEFAULT_SCOPE
            collection_name = DEFAULT_COLLECTION

            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM `{bucket_name}`.`{scope_name}`.`{collection_name}`"
            count_result = agent_manager.couchbase_client.cluster.query(count_query)
            total_candidates = list(count_result)[0]["count"]

            # Get skills distribution
            skills_query = f"""
                SELECT DISTINCT skill
                FROM `{bucket_name}`.`{scope_name}`.`{collection_name}` AS c
                UNNEST c.metadata.skills AS skill
                LIMIT 50
            """
            skills_result = agent_manager.couchbase_client.cluster.query(skills_query)
            top_skills = [row["skill"] for row in skills_result]

            return {
                "total_candidates": total_candidates,
                "top_skills": top_skills[:20],
                "database_status": "connected",
            }

        except Exception as e:
            logger.exception(f"❌ Error getting stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def search_candidates_direct(agent_manager: AgentManager, request: JobMatchRequest) -> JobMatchResponse:
        """
        Direct vector search for candidates (FAST - bypasses agent reasoning).

        Called by the React frontend's AgentJobMatch component via POST /api/search to:
        - Quickly match job descriptions against candidate resumes using vector similarity
        - Return ranked candidates with match scores for immediate display in the UI
        - Provide simplified reasoning text for the results section
        - Enable fast user interactions without waiting for full AI agent processing

        This method directly calls the vector search tool without the ReAct agent loop,
        providing near-instant results.
        """
        if agent_manager.embeddings is None or agent_manager.couchbase_client is None:
            raise HTTPException(
                status_code=503,
                detail="Services not initialized. Please check server logs."
            )

        try:
            start_time = time.time()

            logger.info(f"⚡ Direct search request: {request.job_description[:100]}...")

            # Call the search tool directly
            results = search_candidates_vector(
                job_description=request.job_description,
                num_results=request.num_results,
                embeddings_client=agent_manager.embeddings,
                agent_manager=agent_manager
            )
            # Parse the results
            candidates = HRAPI.parse_candidates_from_text(results)

            query_time = time.time() - start_time

            logger.info(f"⚡ Direct search found {len(candidates)} candidates in {query_time:.2f}s")

            return JobMatchResponse(
                candidates=candidates,
                agent_reasoning=f"Direct vector search completed. Found {len(candidates)} matching candidates based on semantic similarity to your job description.",
                total_found=len(candidates),
                query_time_seconds=round(query_time, 2),
            )

        except Exception as e:
            logger.exception(f"❌ Error in direct search: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def send_meeting_request(request: InitialMeetingRequest, agent_manager: AgentManager) -> InitialMeetingResponse:
        """
        Send initial meeting request email and create application document.

        Creates an application in the database and sends an invitation email.
        """
        email = request.email
        first_name = request.first_name
        last_name = request.last_name
        position = request.position
        company_name = request.company_name

        # Generate unique application ID
        application_id = str(uuid.uuid4())

        # Create application document in database
        try:
            if agent_manager.couchbase_client is None or agent_manager.couchbase_client.cluster is None:
                raise HTTPException(
                    status_code=503,
                    detail="Database not connected"
                )

            # Get the collection for applications
            collection = get_agenda_collection( agent_manager.couchbase_client.cluster)

            application_doc = upsert_application(
                collection=collection,
                application_id=application_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                position=position,
                company_name=company_name
            )
            logger.info(f"Application document created: {application_id}")
        except Exception as e:
            logger.error(f"Error creating application document: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create application document."
            )

        # Read email content from template files
        try:
            with open('email_text_template.txt', 'r', encoding='utf-8') as text_file:
                email_text_template = text_file.read()

            with open('email_html_template.html', 'r', encoding='utf-8') as html_file:
                email_html_template = html_file.read()
        except FileNotFoundError as e:
            logger.error(f"Error reading email template files: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error reading email template files."
            )

        # Template variables for Jinja2 rendering
        template_variables = {
            'first_name': first_name,
            'last_name': last_name,
            'position': position,
            'company_name': company_name
        }

        # Render templates with Jinja2
        email_text = render_email_template(email_text_template, template_variables)
        email_html = render_email_template(email_html_template, template_variables)

        # Send email
        try:
            client = get_agentmail_client()
            sent_message = client.inboxes.messages.send(
                inbox_id='hrbot@agentmail.to',
                to=email,
                labels=["firstitw", "scheduling", _application_key(application_id)],
                subject=f"Interview Invitation - {position} Position",
                text=email_text,
                html=email_html
            )
            logger.info(f"Email sent successfully with ID: {sent_message.message_id}")
            logger.info(f"Email sent and application created: {application_id}")
            return InitialMeetingResponse(application_id = application_id)

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Application created but email failed: {application_id}"
            )

    @staticmethod
    async def receive_email_notification(req: Request, agent_manager: AgentManager):
        """
        Webhook endpoint to receive incoming email notifications.

        Handles email replies and processes them using the email agent.
        """
        # TODO: Import or implement get_application, is_application, processed_messages, email_agent_executor, process_and_reply
        payload = await req.json()
        event_type = payload.get('type') or payload.get('event_type')
        logger.info(f"Received payload: {payload}")

        # Ignore outgoing messages
        if event_type == 'message.sent':
            return "Ignoring outgoing message"

        message = payload.get('message', {})
        message_id = message.get('message_id')
        inbox_id = message.get('inbox_id')
        from_field = message.get('from_', '') or message.get('from', '')

        collection = get_agenda_collection( agent_manager.couchbase_client.cluster)

        labels = payload.get('thread', {}).get('labels', [])
        application_key = list(filter(is_application, labels)).pop()
        application = get_application(collection, application_key)

        logger.info(f"Retrieved application: {application}")

        # Validate required fields
        if not message_id or not inbox_id or not from_field:
            return "fields are invalid"

        # prevent duplicate
        if message_id in agent_manager.processed_messages:
            return "duplicate message"
        agent_manager.processed_messages.add(message_id)

        subject = message.get('subject', '(no subject)')

        if agent_manager.email_agent_executor is None:
            raise HTTPException(
                status_code=503,
                detail="Agent not initialized. Please check server logs and restart."
            )

        # Process in background thread and return immediately
        thread = threading.Thread(
            target=agent_manager.process_and_reply,
            args=(agent_manager.email_agent_executor, message_id, inbox_id, from_field, subject, message, application, application_key)
        )
        thread.daemon = True
        thread.start()

        return "OK"

@staticmethod
def is_application(s):
    return s.startswith("application:")