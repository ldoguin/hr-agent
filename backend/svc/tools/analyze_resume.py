"""
Resume analysis tool for extracting structured information from resume text.
This tool uses the agentc catalog to load the resume analyzer prompt.
"""
import sys
import os
import json
import logging

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from svc.core.agent import AgentManager
from agentc_core.tool import tool

logger = logging.getLogger("uvicorn.error")


@tool(
    name="analyze_resume",
    description="Analyze resume text and extract structured information including name, contact details, skills, experience, and work history",
    annotations={"category": "hr", "type": "analysis"}
)
def analyze_resume(
    resume_text: str,
    agent_manager: AgentManager = None
) -> str:
    """
    Analyze resume text and extract structured information.

    Args:
        resume_text: The raw text content of a resume
        agent_manager: The agent manager instance with LLM access

    Returns:
        JSON string with structured resume information
    """
    try:
        if agent_manager is None or agent_manager.llm is None:
            return "Error: Agent manager or LLM not available"

        # Load the resume analyzer prompt from catalog
        if agent_manager.catalog is None:
            return "Error: Agent catalog not available"

        prompt_result = agent_manager.catalog.find("prompt", name="resume_analyzer")
        if prompt_result is None:
            return "Error: Could not find resume_analyzer prompt in catalog. Run 'agentc index' first."

        # Format the prompt with resume text
        prompt_content = prompt_result.content.replace("{resume_text}", resume_text[:3000])

        # Invoke LLM with the prompt
        response = agent_manager.llm.invoke(prompt_content)
        content = response.content.strip()

        # Clean the response to extract JSON (similar to original function)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        # Find JSON content
        start_brace = content.find("{")
        end_brace = content.rfind("}")
        if start_brace != -1 and end_brace != -1:
            content = content[start_brace:end_brace + 1]

        # Parse and validate JSON
        analysis = json.loads(content)

        # Ensure required fields exist (same as original function)
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

        logger.info(f"✅ Successfully analyzed resume for: {analysis.get('name', 'Unknown')}")

        return json.dumps(analysis, indent=2)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in resume analysis: {e}")
        return f"Error: Failed to parse resume analysis response as JSON: {str(e)}"

    except Exception as e:
        logger.error(f"Error in resume analysis: {e}")
        import traceback
        traceback.print_exc()
        return f"Error analyzing resume: {str(e)}"
