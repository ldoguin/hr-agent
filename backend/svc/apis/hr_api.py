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

from svc.core.config import DEFAULT_BUCKET, DEFAULT_COLLECTION, DEFAULT_SCOPE, DEFAULT_INDEX, DEFAULT_RESUME_DIR, DEFAULT_AGENDA_COLLECTION, AGENT_CATALOG_BUCKET, AGENT_CATALOG_LOGS_SCOPE, AGENT_CATALOG_LOGS_COLLECTION, AGENT_CATALOG_GRADES_COLLECTION
from svc.core.agent import AgentManager
from agentmail import AgentMail
from jinja2 import Template
from svc.core.config import AGENTMAIL_API_KEY
from agentc.span import UserContent, AssistantContent
from svc.core.timeslot_manager import (
    upsert_application, _application_key, get_application, get_candidate_by_email,
    get_agenda_collection, _session_label, _is_session_label, _session_id_from_label,
    list_applications, list_meetings,
    upsert_pending_email, get_pending_email, mark_email_sent, update_pending_email_text,
    get_auto_send_settings, upsert_auto_send_settings, get_latest_assistant_text,
)
from svc.models.models import HealthResponse, JobMatchRequest, JobMatchResponse, ResumeUploadResponse, GenerateResumeRequest, CandidateResponse, InitialMeetingRequest, InitialMeetingResponse
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

            span = agent_manager.new_span("match_candidates")
            if span:
                span.enter()
                span.log(UserContent(value=request.job_description))

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

            reasoning = agent_output if agent_output else "Results extracted from vector search. See candidates below."
            if span:
                span.log(AssistantContent(value=reasoning))
                AgentManager.close_span(span)

            return JobMatchResponse(
                candidates=candidates,
                agent_reasoning=reasoning,
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
    def get_traces(agent_manager: AgentManager, limit: int = 50, offset: int = 0, session: str = None, date: str = None):
        """Return agent activity logs from the agentc Couchbase collection.

        Uses two queries so that LIMIT/OFFSET operate at the session level:
          1. Fetch distinct session IDs (with optional date/session filters).
          2. Fetch all logs for those sessions in one query.

        Args:
            session: Filter to a single session ID.
            date:    ISO date string (YYYY-MM-DD). Filters sessions whose
                     earliest log falls within that UTC day.
        """
        try:
            from couchbase.options import QueryOptions

            cluster = agent_manager.couchbase_client.cluster
            if cluster is None:
                return {"sessions": [], "total": 0}

            # ── Query 1: distinct sessions ────────────────────────────────────
            # Build WHERE filters that apply to the session-level aggregation.
            log_filters = ["l.`span` IS NOT MISSING"]
            params_1: dict = {}

            if session:
                log_filters.append("l.`span`.`session` = $session")
                params_1["session"] = session

            if date:
                log_filters.append("l.`timestamp` >= $day_start AND l.`timestamp` <= $day_end")
                params_1["day_start"] = f"{date}T00:00:00"
                params_1["day_end"]   = f"{date}T23:59:59.999"

            where_clause = " AND ".join(log_filters)

            # Group by session, keep the earliest timestamp per session so we
            # can sort newest-first and paginate correctly.
            sessions_query = f"""
                SELECT l.`span`.`session`  AS session,
                       MIN(l.`timestamp`)  AS started_at,
                       MIN(l.`span`.`name`) AS span_name
                FROM `{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_LOGS_COLLECTION}` AS l
                WHERE {where_clause}
                GROUP BY l.`span`.`session`
                ORDER BY MIN(l.`timestamp`) DESC
                LIMIT {int(limit)} OFFSET {int(offset)}
            """

            session_rows = list(cluster.query(sessions_query, QueryOptions(named_parameters=params_1)))

            if not session_rows:
                # Also fetch total count for pagination metadata
                count_query = f"""
                    SELECT COUNT(DISTINCT l.`span`.`session`) AS total
                    FROM `{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_LOGS_COLLECTION}` AS l
                    WHERE {where_clause}
                """
                count_rows = list(cluster.query(count_query, QueryOptions(named_parameters=params_1)))
                total = count_rows[0].get("total", 0) if count_rows else 0
                return {"sessions": [], "total": total}

            session_ids = [r["session"] for r in session_rows]

            # ── Query 2: all logs for the returned sessions ───────────────────
            # Use IN with positional parameters isn't supported for arrays in
            # N1QL, so build a literal IN list of quoted UUIDs (safe: UUIDs are
            # hex + hyphens only).
            id_list = ", ".join(f'"{sid}"' for sid in session_ids)
            logs_query = f"""
                SELECT l.identifier,
                       l.`span`,
                       l.`timestamp`,
                       l.content,
                       l.annotations
                FROM `{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_LOGS_COLLECTION}` AS l
                WHERE l.`span`.`session` IN [{id_list}]
                ORDER BY l.`timestamp` ASC
            """

            log_rows = list(cluster.query(logs_query))

            # ── Assemble sessions dict preserving query-1 order ───────────────
            sessions: dict = {r["session"]: {
                "session":    r["session"],
                "span_name":  r.get("span_name", []),
                "started_at": r.get("started_at", ""),
                "logs":       [],
            } for r in session_rows}

            for row in log_rows:
                sid = row.get("span", {}).get("session")
                if sid in sessions:
                    sessions[sid]["logs"].append(row)

            # Total distinct sessions matching the filter (for pagination)
            count_query = f"""
                SELECT COUNT(DISTINCT l.`span`.`session`) AS total
                FROM `{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_LOGS_COLLECTION}` AS l
                WHERE {where_clause}
            """
            count_rows = list(cluster.query(count_query, QueryOptions(named_parameters=params_1)))
            total = count_rows[0].get("total", 0) if count_rows else len(sessions)

            # Attach stored grades so the frontend gets everything in one round-trip
            stored_grades = HRAPI._load_grades(session_ids, agent_manager)
            for s in sessions.values():
                sid = s["session"]
                # Session-level grade
                s["stored_grade"] = stored_grades.get(sid)
                # Per-log grades keyed by log identifier
                s["log_grades"] = {
                    log["identifier"]: stored_grades[log["identifier"]]
                    for log in s["logs"]
                    if log.get("identifier") in stored_grades
                }

            return {"sessions": list(sessions.values()), "total": total}

        except Exception as e:
            logger.exception(f"❌ Error fetching traces: {e}")
            return {"sessions": [], "total": 0, "error": str(e)}

    @staticmethod
    def _ensure_grades_collection(agent_manager: AgentManager) -> bool:
        """Create the grades collection and its primary index if they don't exist."""
        try:
            from couchbase.exceptions import CollectionAlreadyExistsException, QueryIndexAlreadyExistsException
            from couchbase.management.queries import CreatePrimaryQueryIndexOptions
            import time as _time

            cluster = agent_manager.couchbase_client.cluster
            bucket = cluster.bucket(AGENT_CATALOG_BUCKET)
            collection_created = False

            try:
                bucket.collections().create_collection(
                    AGENT_CATALOG_LOGS_SCOPE,
                    AGENT_CATALOG_GRADES_COLLECTION,
                )
                logger.info(f"✅ Created grades collection: {AGENT_CATALOG_GRADES_COLLECTION}")
                collection_created = True
                _time.sleep(2)  # let the collection become addressable
            except CollectionAlreadyExistsException:
                pass

            # Always ensure the primary index exists — it may be missing even if
            # the collection was created in a previous run before this code existed.
            try:
                keyspace = f"`{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_GRADES_COLLECTION}`"
                cluster.query(f"CREATE PRIMARY INDEX IF NOT EXISTS ON {keyspace}").execute()
                if collection_created:
                    logger.info(f"✅ Created primary index on grades collection")
            except QueryIndexAlreadyExistsException:
                pass
            except Exception as idx_err:
                # IF NOT EXISTS should prevent this, but log just in case
                if "already exist" not in str(idx_err).lower():
                    logger.warning(f"⚠️ Could not create grades primary index: {idx_err}")

            return True
        except Exception as e:
            logger.error(f"❌ Could not ensure grades collection: {e}")
            return False

    @staticmethod
    def _grades_collection(agent_manager: AgentManager):
        """Return the grades Couchbase collection, creating it if needed."""
        HRAPI._ensure_grades_collection(agent_manager)
        bucket = agent_manager.couchbase_client.cluster.bucket(AGENT_CATALOG_BUCKET)
        return bucket.scope(AGENT_CATALOG_LOGS_SCOPE).collection(AGENT_CATALOG_GRADES_COLLECTION)

    @staticmethod
    def _store_grade(grade: dict, agent_manager: AgentManager) -> None:
        """Upsert a grade document. Key is grade::<scope>::<target_id>."""
        try:
            from datetime import datetime as _dt, timezone
            scope = grade.get("grade_scope", "session")
            target_id = grade.get("log_id") if scope == "log" else grade.get("session")
            key = f"grade::{scope}::{target_id}"
            grade["stored_at"] = _dt.now(timezone.utc).isoformat()
            col = HRAPI._grades_collection(agent_manager)
            col.upsert(key, grade)
            logger.info(f"✅ Grade stored: {key}")
        except Exception as e:
            logger.error(f"❌ Failed to store grade: {e}")

    @staticmethod
    def _load_grades(session_ids: list, agent_manager: AgentManager) -> dict:
        """Return all stored grades for the given session IDs, keyed by session or log_id.

        Returns an empty dict silently when the grades collection does not exist yet
        (i.e. no grade has ever been written).
        """
        if not session_ids:
            return {}
        try:
            from couchbase.options import QueryOptions
            cluster = agent_manager.couchbase_client.cluster
            id_list = ", ".join(f'"{sid}"' for sid in session_ids)
            query = f"""
                SELECT g.*
                FROM `{AGENT_CATALOG_BUCKET}`.`{AGENT_CATALOG_LOGS_SCOPE}`.`{AGENT_CATALOG_GRADES_COLLECTION}` AS g
                WHERE g.session IN [{id_list}]
            """
            rows = list(cluster.query(query))
            result: dict = {}
            for row in rows:
                scope = row.get("grade_scope", "session")
                key = row.get("log_id") if scope == "log" else row.get("session")
                if key:
                    result[key] = row
            return result
        except Exception as e:
            err_str = str(e)
            # KeyspaceNotFound (12003) = collection missing
            # No index available (4000) = primary index missing
            if any(marker in err_str for marker in (
                "KeyspaceNotFoundException", "Keyspace not found",
                "No index available", "QueryIndexNotFoundException",
            )):
                HRAPI._ensure_grades_collection(agent_manager)
                return {}
            logger.error(f"❌ Failed to load grades: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ Failed to load grades: {e}")
            return {}

    @staticmethod
    def grade_session(session_id: str, agent_manager: AgentManager):
        """Fetch logs for a session, grade the full conversation, and persist the result."""
        from svc.tools.grade_conversation import grade_conversation
        import json as _json

        traces = HRAPI.get_traces(agent_manager, limit=200, session=session_id)
        sessions = traces.get("sessions", [])
        if not sessions:
            return {
                "session": session_id, "score": 0, "label": "failed",
                "summary": "No logs found for this session.",
                "issues": ["Session not found"], "strengths": [],
                "off_topic": False, "anomalies": [], "error": "Session not found",
            }

        logs = sessions[0].get("logs", [])
        if not logs:
            return {
                "session": session_id, "score": 0, "label": "failed",
                "summary": "Session has no log entries.",
                "issues": ["Empty session"], "strengths": [],
                "off_topic": False, "anomalies": [], "error": "Empty session",
            }

        raw = grade_conversation(logs=logs, agent_manager=agent_manager)
        result = _json.loads(raw)
        result["session"] = session_id
        result["grade_scope"] = "session"
        HRAPI._store_grade(result, agent_manager)
        return result

    @staticmethod
    def grade_log(session_id: str, log_id: str, agent_manager: AgentManager):
        """Grade a single log entry against the interview scheduling goal and persist the result.

        Uses the dedicated log_entry_grader prompt which evaluates the entry in
        isolation — no session context, no conversation history. The question it
        answers is: does this specific event make sense for an agent whose job is
        to set up a job interview?
        """
        from svc.tools.grade_log_entry import grade_log_entry
        import json as _json

        traces = HRAPI.get_traces(agent_manager, limit=200, session=session_id)
        sessions = traces.get("sessions", [])
        if not sessions:
            return {
                "session": session_id, "log_id": log_id, "score": 0, "label": "failed",
                "summary": "Session not found.", "issues": [], "strengths": [],
                "off_topic": False, "anomalies": [], "error": "Session not found",
                "grade_scope": "log",
            }

        all_logs = sessions[0].get("logs", [])
        log = next((l for l in all_logs if l.get("identifier") == log_id), None)
        if not log:
            return {
                "session": session_id, "log_id": log_id, "score": 0, "label": "failed",
                "summary": "Log entry not found.", "issues": [], "strengths": [],
                "off_topic": False, "anomalies": [], "error": "Log not found",
                "grade_scope": "log",
            }

        raw = grade_log_entry(log=log, agent_manager=agent_manager)
        result = _json.loads(raw)
        result["session"] = session_id
        result["log_id"] = log_id
        result["grade_scope"] = "log"
        HRAPI._store_grade(result, agent_manager)
        return result

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

            span = agent_manager.new_span("upload_resume", filename=file.filename)
            if span:
                span.enter()
                span.log(UserContent(value=f"Resume upload: {file.filename}"))

            # Schedule background processing — pass span so it can be closed there
            background_tasks.add_task(
                HRAPI.process_resume_background,
                file_path,
                file.filename,
                agent_manager,
                span,
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
    async def generate_resume(request: GenerateResumeRequest, background_tasks: BackgroundTasks, agent_manager: AgentManager) -> ResumeUploadResponse:
        """Generate a random resume PDF and queue it for processing."""
        import random
        from svc.resume_generator import generate_resume as _gen, build_pdf, PROFILES, TEMPLATES

        rng = random.Random()
        profile = request.profile if request.profile in PROFILES else rng.choice(list(PROFILES.keys()))
        template = request.template if request.template in TEMPLATES else rng.choice(list(TEMPLATES))

        resume = _gen(rng=rng, profile=profile, template=template)

        # Apply caller-supplied overrides
        if request.first_name or request.last_name:
            first = request.first_name or resume.name.split()[0]
            last = request.last_name or (resume.name.split()[1] if len(resume.name.split()) > 1 else "")
            resume.name = f"{first} {last}".strip()
        if request.email:
            resume.email = request.email

        # Use the LLM to enrich the resume when extra instructions are provided
        if request.instructions and agent_manager.llm is not None:
            import json as _json
            _prompt = f"""You are helping generate a realistic fictional resume. A base resume has been randomly generated.
Your task: rewrite and enrich the resume fields to match the following instructions as closely as possible.

Instructions: {request.instructions}

Current resume (JSON):
{{
  "name": "{resume.name}",
  "title": "{resume.title}",
  "location": "{resume.location}",
  "summary": "{resume.summary}",
  "skills": {_json.dumps(resume.skills)},
  "experience": {_json.dumps(resume.experience)},
  "education": {_json.dumps(resume.education)},
  "projects": {_json.dumps(resume.projects)},
  "certifications": {_json.dumps(resume.certifications)}
}}

Return ONLY valid JSON with the same keys. Adjust years of experience, job titles, companies, skills, summary, and projects to reflect the instructions. Keep the structure identical. Do not add or remove keys.
"""
            try:
                _response = agent_manager.llm.invoke(_prompt)
                _content = _response.content.strip()
                if "```json" in _content:
                    _content = _content.split("```json")[1].split("```")[0]
                elif "```" in _content:
                    _content = _content.split("```")[1].split("```")[0]
                _start = _content.find("{")
                _end = _content.rfind("}")
                if _start != -1 and _end != -1:
                    _enriched = _json.loads(_content[_start:_end + 1])
                    resume.title = _enriched.get("title", resume.title)
                    resume.location = _enriched.get("location", resume.location)
                    resume.summary = _enriched.get("summary", resume.summary)
                    resume.skills = _enriched.get("skills", resume.skills)
                    resume.experience = _enriched.get("experience", resume.experience)
                    resume.education = _enriched.get("education", resume.education)
                    resume.projects = _enriched.get("projects", resume.projects)
                    resume.certifications = _enriched.get("certifications", resume.certifications)
                    logger.info(f"✅ LLM enriched resume for {resume.name}")
            except Exception as _e:
                logger.warning(f"⚠️ LLM enrichment failed, using base resume: {_e}")

        safe_name = resume.name.replace(" ", "_")
        filename = f"{safe_name}_{profile}.pdf"

        resume_dir = Path(DEFAULT_RESUME_DIR)
        resume_dir.mkdir(exist_ok=True)
        file_path = resume_dir / filename

        try:
            build_pdf(resume, str(file_path), template=template)
        except Exception as e:
            logger.exception(f"❌ Error generating resume PDF: {e}")
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

        logger.info(f"📄 Generated resume: {filename}")

        span = agent_manager.new_span("generate_resume", filename=filename)
        if span:
            span.enter()
            span.log(UserContent(value=f"Generated resume: {filename} ({profile}/{template})"))

        # Build analysis directly from the Resume dataclass — richer and more reliable
        # than re-extracting text from the generated PDF.
        import json as _json2
        _skills_flat = [s for skills in resume.skills.values() for s in skills]
        _exp_text = " | ".join(
            f"{e.get('title','')} at {e.get('company','')} ({e.get('duration','')})"
            for e in resume.experience
        )
        _edu_text = " | ".join(
            f"{e.get('degree','')} from {e.get('school','')}" for e in resume.education
        )
        pre_analyzed = {
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "location": resume.location,
            "years_experience": sum(
                int(w) for e in resume.experience
                for w in str(e.get("duration", "")).split()
                if w.isdigit()
            ) or len(resume.experience) * 2,
            "skills": _skills_flat,
            "technical_skills": resume.skills.get("Languages", []) + resume.skills.get("Frameworks", []),
            "soft_skills": [],
            "experience": _exp_text,
            "education": _edu_text,
            "summary": resume.summary,
            "work_history": [
                {
                    "company": e.get("company", ""),
                    "title": e.get("title", ""),
                    "duration": e.get("duration", ""),
                    "description": " ".join(e.get("bullets", [])),
                }
                for e in resume.experience
            ],
            "filename": filename,
            "profile": profile,
        }

        background_tasks.add_task(
            HRAPI.process_resume_background,
            file_path,
            filename,
            agent_manager,
            span,
            pre_analyzed,
        )

        return ResumeUploadResponse(
            success=True,
            message=f"Resume generated for {resume.name} and queued for processing",
            filename=filename,
            candidate_name=resume.name,
        )

    @staticmethod
    async def process_resume_background(file_path: Path, filename: str, agent_manager: AgentManager, span=None, pre_analyzed: dict = None):
        """Background task to process an uploaded or generated resume."""
        try:
            logger.info(f"🔄 Processing resume in background: {filename}")

            if pre_analyzed is not None:
                # Generated resume: use the pre-built analysis directly, skip PDF extraction.
                analysis = pre_analyzed
                analysis["filename"] = filename
                logger.info(f"📋 Using pre-analyzed data for {filename}")
            else:
                # Uploaded resume: extract text from PDF then analyze with LLM.
                text = extract_text_from_pdf(str(file_path))
                if not text.strip():
                    logger.warning(f"No text extracted from {filename}")
                    if span:
                        span.log(AssistantContent(value=f"No text extracted from {filename}"))
                        AgentManager.close_span(span)
                    return

                analysis = analyze_resume_with_llm(text, agent_manager.llm)
                analysis["filename"] = filename

            # Format for embedding
            formatted_text = format_candidate_for_embedding(analysis)

            # Store in Couchbase using direct KV upsert so the document layout
            # is consistent with load_resumes_to_couchbase (flat, no metadata wrapper).
            if agent_manager.couchbase_client and agent_manager.embeddings:
                embedding_vector = agent_manager.embeddings.embed_query(formatted_text)

                bucket = agent_manager.couchbase_client.cluster.bucket(DEFAULT_BUCKET)
                collection = bucket.scope(DEFAULT_SCOPE).collection(DEFAULT_COLLECTION)

                doc_id = f"candidate_{uuid.uuid4().hex[:12]}"
                document = {
                    "text": formatted_text,
                    "embedding": embedding_vector,
                    "type": "candidate",
                    **{k: v for k, v in analysis.items() if k != "type"},
                }
                collection.upsert(doc_id, document)

                logger.info(f"✅ Successfully processed resume: {filename}")
                if span:
                    candidate_name = analysis.get("name", "Unknown")
                    span.log(AssistantContent(
                        value=f"Processed and stored resume for {candidate_name}",
                        extra={
                            "candidate_name": candidate_name,
                            "years_experience": analysis.get("years_experience", 0),
                            "skills_count": len(analysis.get("skills", [])),
                        },
                    ))
            else:
                logger.warning("Cannot store resume - Couchbase client not initialized")
                if span:
                    span.log(AssistantContent(value=f"Resume {filename} parsed but not stored — Couchbase unavailable"))

        except Exception as e:
            logger.exception(f"❌ Error processing resume {filename}: {e}")
            if span:
                span.log(AssistantContent(value=f"Error processing {filename}: {e}"))
        finally:
            if span:
                AgentManager.close_span(span)

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

            span = agent_manager.new_span("search_direct")
            if span:
                span.enter()
                span.log(UserContent(value=request.job_description))

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

            reasoning = f"Direct vector search completed. Found {len(candidates)} matching candidates based on semantic similarity to your job description."
            if span:
                span.log(AssistantContent(value=reasoning))
                AgentManager.close_span(span)

            return JobMatchResponse(
                candidates=candidates,
                agent_reasoning=reasoning,
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

        span = agent_manager.new_span("send_meeting_request", position=position)
        if span:
            span.enter()
            span.log(UserContent(value=f"Meeting request for {first_name} {last_name} <{email}> — {position} at {company_name}"))

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
                company_name=company_name,
                session_id=getattr(span, "_session_id", None) or (span.identifier.session if span else None),
            )
            logger.info(f"Application document created: {application_id}")
        except Exception as e:
            logger.error(f"Error creating application document: {e}")
            if span:
                span.log(AssistantContent(value=f"Failed to create application: {e}"))
                AgentManager.close_span(span)
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
            if span:
                span.log(AssistantContent(value=f"Email template not found: {e}"))
                AgentManager.close_span(span)
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

        subject = f"Interview Invitation - {position} Position"
        session_id = getattr(span, "_session_id", None) or (span.identifier.session if span else None)

        # Log the actual email body to the agentc span so it can be read back
        # by get_latest_assistant_text when the pending email panel is opened.
        if span:
            span.log(AssistantContent(
                value=email_text,
                extra={"application_id": application_id, "session_id": session_id, "email_type": "initial"},
            ))
            AgentManager.close_span(span)

        # Check auto-send settings
        try:
            agenda_collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            settings = get_auto_send_settings(agenda_collection)
        except Exception:
            settings = {"enabled": False, "min_score": 9}

        auto_send = settings.get("enabled", False)

        # Store as pending for human review
        try:
            agenda_collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            upsert_pending_email(
                collection=agenda_collection,
                application_id=application_id,
                subject=subject,
                to=email,
                email_type="initial",
                inbox_id="hrbot@agentmail.to",
                message_id=None,
            )
        except Exception as pe:
            logger.warning(f"Could not store pending email: {pe}")
            auto_send = True  # fall back to sending directly if storage fails

        if auto_send:
            try:
                client = get_agentmail_client()
                labels = ["firstitw", "scheduling", _application_key(application_id)]
                if session_id:
                    labels.append(_session_label(session_id))
                sent_message = client.inboxes.messages.send(
                    inbox_id='hrbot@agentmail.to',
                    to=email,
                    labels=labels,
                    subject=subject,
                    text=email_text,
                    html=email_html
                )
                logger.info(f"Email sent (auto) with ID: {sent_message.message_id}")
                try:
                    mark_email_sent(agenda_collection, application_id)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error sending email: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Application created but email failed: {application_id}"
                )
        else:
            logger.info(f"Initial email stored as pending for {email} (application {application_id})")

        return InitialMeetingResponse(application_id=application_id)

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

        # Recover the trace session ID embedded in the email labels so the
        # reply span continues the same session as the original invitation.
        session_labels = list(filter(_is_session_label, labels))
        trace_session_id = _session_id_from_label(session_labels[0]) if session_labels else None

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
            args=(agent_manager.email_agent_executor, message_id, inbox_id, from_field, subject, message, application, application_key, trace_session_id)
        )
        thread.daemon = True
        thread.start()

        return "OK"

    @staticmethod
    def grade_application(application_id: str, agent_manager: AgentManager):
        """Grade the full email thread for an application via its linked session."""
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            doc = get_application(collection, _application_key(application_id))
            if doc is None:
                raise HTTPException(status_code=404, detail="Application not found")
            session_id = doc.get("session_id")
            if not session_id:
                raise HTTPException(status_code=404, detail="No session linked to this application")
            return HRAPI.grade_session(session_id, agent_manager)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error grading application: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_application_grade(application_id: str, agent_manager: AgentManager):
        """Return the stored grade for an application's session without re-grading."""
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            doc = get_application(collection, _application_key(application_id))
            if doc is None:
                raise HTTPException(status_code=404, detail="Application not found")
            session_id = doc.get("session_id")
            if not session_id:
                raise HTTPException(status_code=404, detail="No session linked to this application")
            # Reuse the existing grade loader
            grades = HRAPI._load_grades([session_id], agent_manager)
            grade = grades.get(session_id)
            if grade is None:
                raise HTTPException(status_code=404, detail="No grade yet")
            return grade
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_pending_email(application_id: str, agent_manager: AgentManager):
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            doc = get_pending_email(collection, application_id)
            if doc is None:
                raise HTTPException(status_code=404, detail="No pending email for this application")

            # Hydrate text: prefer user's edited override, otherwise read from agentc trace.
            # The agent reply is logged to the agentc span before the pending doc is created,
            # so it is always available there — we don't duplicate it in the pending doc.
            text = doc.get("text_override")
            if not text:
                app_doc = get_application(collection, _application_key(application_id))
                session_id = app_doc.get("session_id") if app_doc else None
                if session_id:
                    text = get_latest_assistant_text(
                        agent_manager.couchbase_client.cluster, session_id
                    )
            doc["text"] = text or ""
            return doc
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def update_pending_email(application_id: str, text: str, agent_manager: AgentManager):
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            update_pending_email_text(collection, application_id, text)
            doc = get_pending_email(collection, application_id)
            if doc is None:
                raise HTTPException(status_code=404, detail="No pending email for this application")
            return doc
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def send_pending_email(application_id: str, agent_manager: AgentManager):
        """Fetch the pending email, send it via AgentMail, then mark as sent."""
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            doc = get_pending_email(collection, application_id)
            if doc is None:
                raise HTTPException(status_code=404, detail="No pending email for this application")

            # Resolve text: override wins, otherwise read from agentc trace
            text = doc.get("text_override")
            if not text:
                app_doc = get_application(collection, _application_key(application_id))
                session_id = app_doc.get("session_id") if app_doc else None
                if session_id:
                    text = get_latest_assistant_text(
                        agent_manager.couchbase_client.cluster, session_id
                    )
            if not text:
                raise HTTPException(status_code=422, detail="Could not resolve email text from trace")

            client = get_agentmail_client()
            inbox_id = doc.get("inbox_id", "hrbot@agentmail.to")
            original_message_id = doc.get("message_id")

            if doc.get("email_type") == "reply" and original_message_id:
                client.inboxes.messages.reply(
                    inbox_id=inbox_id,
                    message_id=original_message_id,
                    to=[doc["to"]],
                    text=text,
                )
            else:
                labels = ["firstitw", "scheduling", _application_key(application_id)]
                client.inboxes.messages.send(
                    inbox_id=inbox_id,
                    to=doc["to"],
                    labels=labels,
                    subject=doc["subject"],
                    text=text,
                )

            mark_email_sent(collection, application_id)
            logger.info(f"Pending email for {application_id} sent manually")

            # Grade the session in the background now that the exchange is complete
            app_doc = get_application(collection, _application_key(application_id))
            session_id = app_doc.get("session_id") if app_doc else None
            if session_id:
                import threading as _threading
                def _grade():
                    try:
                        HRAPI.grade_session(session_id, agent_manager)
                        logger.info(f"Background grading complete for session {session_id}")
                    except Exception as ge:
                        logger.warning(f"Background grading failed: {ge}")
                _threading.Thread(target=_grade, daemon=True).start()

            return {"status": "sent"}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error sending pending email: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_ai_provider(agent_manager: AgentManager):
        from svc.core.config import OPENAI_MODEL, GOOGLE_MODEL
        provider = agent_manager.ai_provider
        model = GOOGLE_MODEL if provider == "gemini" else OPENAI_MODEL
        return {"provider": provider, "model": model}

    @staticmethod
    def set_ai_provider(provider: str, agent_manager: AgentManager):
        try:
            return agent_manager.switch_provider(provider)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception(f"Error switching provider: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_auto_send(agent_manager: AgentManager):
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            return get_auto_send_settings(collection)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def set_auto_send(enabled: bool, min_score: int, agent_manager: AgentManager):
        if agent_manager.couchbase_client is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            collection = get_agenda_collection(agent_manager.couchbase_client.cluster)
            return upsert_auto_send_settings(collection, enabled, min_score)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def _ensure_timeslots_index(agent_manager: AgentManager):
        """Create a primary index on the timeslots collection if it doesn't exist."""
        try:
            cluster = agent_manager.couchbase_client.cluster
            keyspace = f"`{DEFAULT_BUCKET}`.`{DEFAULT_SCOPE}`.`{DEFAULT_AGENDA_COLLECTION}`"
            cluster.query(f"CREATE PRIMARY INDEX IF NOT EXISTS ON {keyspace}").execute()
        except Exception as e:
            logger.warning(f"Could not ensure timeslots index: {e}")

    @staticmethod
    def get_applications(agent_manager: AgentManager):
        if agent_manager.couchbase_client is None or agent_manager.couchbase_client.cluster is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            HRAPI._ensure_timeslots_index(agent_manager)
            rows = list_applications(agent_manager.couchbase_client.cluster)
            logger.info(f"list_applications returned {len(rows)} rows")
            return rows
        except Exception as e:
            logger.exception(f"Error listing applications: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_meetings(agent_manager: AgentManager):
        if agent_manager.couchbase_client is None or agent_manager.couchbase_client.cluster is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        try:
            HRAPI._ensure_timeslots_index(agent_manager)
            rows = list_meetings(agent_manager.couchbase_client.cluster)
            logger.info(f"list_meetings returned {len(rows)} rows")
            return rows
        except Exception as e:
            logger.exception(f"Error listing meetings: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@staticmethod
def is_application(s):
    return s.startswith("application:")