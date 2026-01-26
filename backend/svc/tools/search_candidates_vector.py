"""
Vector search tool for finding candidates based on job descriptions.
This tool uses Couchbase vector search to find the most relevant candidates.

Updated for Agent Catalog v1.0.0 with @tool decorator.
"""
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

import logging
from typing import List, Dict, Any
from datetime import timedelta

from svc.core.agent import AgentManager
from agentc_core.tool import tool
from couchbase.vector_search import VectorQuery, VectorSearch
from couchbase.search import SearchRequest, MatchNoneQuery

logger = logging.getLogger("uvicorn.error")


def generate_embedding(text: str, embeddings_client) -> List[float]:
    """Generate embeddings for text using the provided embeddings client."""
    try:
        # Use the embeddings client to generate embeddings
        result = embeddings_client.embed_query(text)
        return result
    except Exception as e:
        logger.error(f"Error generating embedding: {embeddings_client}")
        logger.error(f"Error generating embedding: {e}")
        logger.error("Fallback on empty vector")
        return [0.0] * 1024  # Return zero vector as fallback


@tool(
    name="search_candidates_vector",
    description="Search for candidates using vector similarity based on a job description. Returns matching candidate profiles ranked by relevance.",
    annotations={"category": "hr", "type": "search"}
)
def search_candidates_vector(
    job_description: str,
    num_results: int = 5,
    embeddings_client=None,
    agent_manager: AgentManager=None
) -> str:
    """
    Search for candidates using vector similarity based on job description.

    Args:
        job_description: The job description text to search against
        num_results: Number of top candidates to return (default: 5)
        embeddings_client: The embeddings client for generating query embeddings

    Returns:
        Formatted string with candidate information
    """
    try:
        # Get environment variables
        bucket_name = os.getenv("CB_BUCKET", "hrdemo")
        scope_name = os.getenv("CB_SCOPE", "agentc_data")
        collection_name = os.getenv("CB_COLLECTION", "candidates")
        index_name = os.getenv("CB_INDEX", "candidates_index")

        # Connect to Couchbase
        cluster = agent_manager.couchbase_client.get_cluster_connection()
        if not cluster:
            return "Error: Could not connect to database"

        bucket = cluster.bucket(bucket_name)
        scope = bucket.scope(scope_name)
        collection = scope.collection(collection_name)  # Use scope.collection(), not bucket.collection()

        # Generate query embedding
        logger.info(f"Generating embedding for job description...")
        if embeddings_client is None:
            return "Error: Embeddings client not provided"

        query_embedding = generate_embedding(job_description, embeddings_client)

        # Perform vector search
        logger.info(f"Performing vector search with index: {index_name}")
        search_req = SearchRequest.create(MatchNoneQuery()).with_vector_search(
            VectorSearch.from_vector_query(
                VectorQuery("embedding", query_embedding, num_candidates=num_results * 2)
            )
        )

        result = scope.search(index_name, search_req, timeout=timedelta(seconds=20))
        rows = list(result.rows())

        if not rows:
            return "No candidates found matching the job description."

        # Fetch candidate details
        candidates = []
        for row in rows[:num_results]:
            try:
                doc = collection.get(row.id, timeout=timedelta(seconds=5))
                if doc and doc.value:
                    data = doc.value
                    data["_id"] = row.id
                    data["_score"] = row.score
                    candidates.append(data)
            except Exception as e:
                logger.warning(f"Error fetching candidate {row.id}: {e}")
                continue

        # Format results
        if not candidates:
            return "No candidate details could be retrieved."

        result_text = f"Found {len(candidates)} matching candidates:\n\n"

        for i, doc in enumerate(candidates, 1):
            candidate = doc.get('metadata', {})
            result_text += f"**Candidate {i}: {candidate.get('name', 'Unknown')}**\n"
            result_text += f"- Match Score: {candidate.get('_score', 0):.4f}\n"
            result_text += f"- Email: {candidate.get('email', 'N/A')}\n"
            result_text += f"- Location: {candidate.get('location', 'N/A')}\n"
            result_text += f"- Years of Experience: {candidate.get('years_experience', 0)}\n"

            skills = candidate.get('skills', [])
            if skills:
                result_text += f"- Skills: {', '.join(skills[:10])}\n"

            technical_skills = candidate.get('technical_skills', [])
            if technical_skills:
                result_text += f"- Technical Skills: {', '.join(technical_skills[:10])}\n"

            summary = candidate.get('summary', '')
            if summary:
                # Truncate summary if too long
                summary_text = summary[:200] + "..." if len(summary) > 200 else summary
                result_text += f"- Summary: {summary_text}\n"

            result_text += "\n"

        return result_text

    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        import traceback
        traceback.print_exc()
        return f"Error performing candidate search: {str(e)}"
