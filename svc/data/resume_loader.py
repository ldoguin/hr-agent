"""
Resume data loading functions for the HR Agent Catalog system.
Handles loading resumes from PDF files and storing them in Couchbase with embeddings.
"""

import os
import logging
from typing import List, Dict, Any
from datetime import timedelta
from pathlib import Path

from pypdf import PdfReader
from langchain_couchbase.vectorstores import CouchbaseVectorStore
from tqdm import tqdm

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        texts = []
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    texts.append(text)
            except Exception as e:
                logger.warning(f"Error extracting text from page: {e}")
                continue
        return "\n".join(texts)
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
        return ""


def analyze_resume_with_llm(resume_text: str, llm_client) -> Dict[str, Any]:
    """Use LLM to analyze resume and extract structured information."""
    prompt = f"""
    Analyze this resume and extract structured information. Return ONLY valid JSON with the following structure:

    {{
        "name": "string",
        "email": "string",
        "phone": "string",
        "location": "string",
        "years_experience": 5,
        "skills": ["skill1", "skill2", "skill3"],
        "technical_skills": ["tech1", "tech2"],
        "soft_skills": ["soft1", "soft2"],
        "experience": "string",
        "education": "string",
        "summary": "string",
        "work_history": [
            {{
                "company": "string",
                "title": "string",
                "duration": "string",
                "description": "string"
            }}
        ]
    }}

    Resume Text:
    {resume_text[:3000]}

    Extract accurate information. Be precise about years of experience and skills.
    """

    try:
        response = llm_client.invoke(prompt)
        content = response.content.strip()

        # Clean the response to extract JSON
        import json
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        # Find JSON content
        start_brace = content.find("{")
        end_brace = content.rfind("}")
        if start_brace != -1 and end_brace != -1:
            content = content[start_brace:end_brace + 1]

        analysis = json.loads(content)

        # Ensure required fields exist
        analysis.setdefault("name", "Unknown")
        analysis.setdefault("email", "")
        analysis.setdefault("phone", "")
        analysis.setdefault("location", "")
        analysis.setdefault("years_experience", 0)
        analysis.setdefault("skills", [])
        analysis.setdefault("technical_skills", [])
        analysis.setdefault("soft_skills", [])
        analysis.setdefault("experience", "")
        analysis.setdefault("education", "")
        analysis.setdefault("summary", "")
        analysis.setdefault("work_history", [])

        return analysis

    except Exception as e:
        logger.error(f"Error analyzing resume with LLM: {e}")
        return {
            "name": "Unknown",
            "email": "",
            "phone": "",
            "location": "",
            "years_experience": 0,
            "skills": [],
            "technical_skills": [],
            "soft_skills": [],
            "experience": "",
            "education": "",
            "summary": "",
            "work_history": []
        }


def get_resume_texts(resume_dir: str, llm_client) -> List[Dict[str, Any]]:
    """Load resumes from directory and extract structured information."""
    resume_path = Path(resume_dir)

    if not resume_path.exists():
        logger.error(f"Resume directory not found: {resume_dir}")
        return []

    pdf_files = list(resume_path.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {resume_dir}")
        return []

    logger.info(f"Found {len(pdf_files)} resume PDFs")

    resume_data = []
    for pdf_file in tqdm(pdf_files, desc="Processing resumes"):
        try:
            # Extract text from PDF
            text = extract_text_from_pdf(str(pdf_file))
            if not text.strip():
                logger.warning(f"No text extracted from {pdf_file.name}")
                continue

            # Analyze with LLM
            analysis = analyze_resume_with_llm(text, llm_client)
            analysis["filename"] = pdf_file.name
            analysis["raw_text"] = text[:1000]  # Store first 1000 chars

            # Create formatted text for embedding
            formatted_text = format_candidate_for_embedding(analysis)
            analysis["formatted_text"] = formatted_text

            resume_data.append(analysis)

        except Exception as e:
            logger.error(f"Error processing {pdf_file.name}: {e}")
            continue

    logger.info(f"Successfully processed {len(resume_data)} resumes")
    return resume_data


def format_candidate_for_embedding(candidate: Dict[str, Any]) -> str:
    """Format candidate information for vector embedding."""
    parts = []

    # Basic info
    parts.append(f"{candidate.get('name', 'Unknown')} - {candidate.get('location', 'Unknown Location')}")

    # Experience
    years_exp = candidate.get('years_experience', 0)
    parts.append(f"Experience: {years_exp} years")

    # Skills
    skills = candidate.get('skills', [])
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")

    technical_skills = candidate.get('technical_skills', [])
    if technical_skills:
        parts.append(f"Technical Skills: {', '.join(technical_skills)}")

    # Summary
    summary = candidate.get('summary', '')
    if summary:
        parts.append(f"Summary: {summary}")

    # Work history
    work_history = candidate.get('work_history', [])
    if work_history:
        for i, job in enumerate(work_history[:3], 1):  # Top 3 jobs
            job_text = f"Job {i}: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}"
            if job.get('description'):
                job_text += f" - {job['description'][:200]}"
            parts.append(job_text)

    # Education
    education = candidate.get('education', '')
    if education:
        parts.append(f"Education: {education}")

    return ". ".join(parts)


def load_resumes_to_couchbase(
    cluster,
    bucket_name: str,
    scope_name: str,
    collection_name: str,
    embeddings,
    index_name: str,
    resume_dir: str,
    llm_client,
):
    """Load resume data into Couchbase with embeddings.
    
    This function stores documents directly to the collection without requiring
    the search index to exist first. Create the search index manually after
    documents are loaded.
    """
    try:
        # Check if data already exists
        count_query = f"SELECT COUNT(*) as count FROM `{bucket_name}`.`{scope_name}`.`{collection_name}`"
        count_result = cluster.query(count_query)
        count_row = list(count_result)[0]
        existing_count = count_row["count"]

        if existing_count > 0:
            logger.info(
                f"Found {existing_count} existing documents in collection, skipping data load"
            )
            return

        # Get resume data
        resume_data = get_resume_texts(resume_dir, llm_client)

        if not resume_data:
            logger.warning("No resume data to load")
            return

        # Get collection reference directly (no index check needed)
        bucket = cluster.bucket(bucket_name)
        scope = bucket.scope(scope_name)
        collection = scope.collection(collection_name)

        # Extract formatted texts for embeddings
        texts = [resume["formatted_text"] for resume in resume_data]
        
        logger.info(f"Loading {len(texts)} candidate profiles to {bucket_name}.{scope_name}.{collection_name}")
        logger.info("Generating embeddings for all candidates...")

        # Generate embeddings for all texts
        all_embeddings = embeddings.embed_documents(texts)
        logger.info(f"Generated {len(all_embeddings)} embeddings")

        # Store documents directly to collection
        import uuid
        
        with tqdm(total=len(resume_data), desc="Storing candidate documents") as pbar:
            for i, resume in enumerate(resume_data):
                # Create document with embedding
                doc_id = f"candidate_{uuid.uuid4().hex[:12]}"
                
                document = {
                    "text": texts[i],  # The formatted text for searching
                    "embedding": all_embeddings[i],  # Vector embedding
                    "name": resume.get("name", "Unknown"),
                    "email": resume.get("email", ""),
                    "phone": resume.get("phone", ""),
                    "location": resume.get("location", ""),
                    "years_experience": resume.get("years_experience", 0),
                    "skills": resume.get("skills", []),
                    "technical_skills": resume.get("technical_skills", []),
                    "soft_skills": resume.get("soft_skills", []),
                    "summary": resume.get("summary", ""),
                    "experience": resume.get("experience", ""),
                    "education": resume.get("education", ""),
                    "work_history": resume.get("work_history", []),
                    "filename": resume.get("filename", ""),
                    "type": "candidate",  # Type field for search index mapping
                }
                
                # Store document
                collection.upsert(doc_id, document)
                pbar.update(1)

        logger.info(f"✅ Successfully loaded {len(resume_data)} candidate profiles to collection")
        logger.info(f"📝 Now create the search index '{index_name}' manually in Capella UI")

    except Exception as e:
        logger.error(f"Error loading resumes to Couchbase: {str(e)}")
        raise


def get_candidate_count():
    """Get the count of candidates in the database."""
    try:
        cluster = get_cluster_connection()
        if not cluster:
            raise ConnectionError("Could not connect to Couchbase cluster")

        bucket_name = os.getenv("CB_BUCKET", "hrdata")
        scope_name = os.getenv("CB_SCOPE", "agentc_data")
        collection_name = os.getenv("CB_COLLECTION", "candidates")

        query = f"SELECT COUNT(*) as count FROM `{bucket_name}`.`{scope_name}`.`{collection_name}`"
        result = cluster.query(query)

        for row in result:
            return row["count"]

        return 0

    except Exception as e:
        logger.error(f"Error getting candidate count: {e}")
        return 0
