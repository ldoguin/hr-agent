"""
Conversation grading tool.
Formats a session's agentc logs into a readable transcript and asks the LLM
to score how well the email scheduling agent handled the conversation.
"""
import json
import logging

from agentc_core.tool import tool
from svc.core.agent import AgentManager

logger = logging.getLogger("uvicorn.error")


def _build_transcript(logs: list) -> str:
    """Convert a list of agentc log dicts into a human-readable transcript."""
    lines = []
    for log in sorted(logs, key=lambda l: l.get("timestamp", "")):
        content = log.get("content", {})
        kind = content.get("kind", "")
        ts = log.get("timestamp", "")[:19].replace("T", " ")

        if kind == "user":
            lines.append(f"[{ts}] CANDIDATE:\n{content.get('value', '')}\n")

        elif kind == "assistant":
            lines.append(f"[{ts}] AGENT REPLY:\n{content.get('value', '')}\n")

        elif kind == "tool-call":
            args = json.dumps(content.get("tool_args", {}), ensure_ascii=False)
            lines.append(f"[{ts}] TOOL CALL: {content.get('tool_name', '')}({args})")

        elif kind == "tool-result":
            status = content.get("status", "unknown")
            result = str(content.get("tool_result", ""))[:200]
            lines.append(f"[{ts}] TOOL RESULT [{status}]: {result}")

        elif kind == "chat-completion":
            output = content.get("output", "")[:300]
            lines.append(f"[{ts}] LLM: {output}")

    return "\n".join(lines) if lines else "(empty conversation)"


def _error_result(message: str) -> dict:
    """Return a valid grade dict that satisfies ConversationGradeResponse on error."""
    return {
        "score": 0,
        "label": "failed",
        "summary": "",
        "issues": [],
        "strengths": [],
        "off_topic": False,
        "anomalies": [],
        "error": message,
    }


@tool(
    name="grade_conversation",
    description="Grade an HR scheduling email conversation from agentc logs. Returns a score 0-10 with reasoning.",
    annotations={"category": "hr", "type": "evaluation"},
)
def grade_conversation(
    logs: list,
    agent_manager: AgentManager = None,
) -> str:
    """
    Grade a conversation session from agentc activity logs.

    Args:
        logs: List of agentc log dicts for a single session (from /api/traces).
        agent_manager: AgentManager instance with LLM and catalog access.

    Returns:
        JSON string with keys: score, label, summary, issues, strengths.
    """
    raw = ""
    try:
        if agent_manager is None or agent_manager.llm is None:
            return json.dumps(_error_result("LLM not available"))

        if agent_manager.catalog is None:
            return json.dumps(_error_result("Agent catalog not available"))

        prompt_result = agent_manager.catalog.find("prompt", name="conversation_grader")
        if prompt_result is None:
            return json.dumps(_error_result("conversation_grader prompt not found — run 'agentc index' first"))

        transcript = _build_transcript(logs)
        prompt_text = prompt_result.content.replace("{conversation}", transcript)

        response = agent_manager.llm.invoke(prompt_text)
        raw = response.content.strip()

        # Strip markdown fences if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        # Extract JSON object
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]

        result = json.loads(raw)

        # Normalise fields
        result.setdefault("score", 0)
        result.setdefault("label", "unknown")
        result.setdefault("summary", "")
        result.setdefault("issues", [])
        result.setdefault("strengths", [])
        result.setdefault("off_topic", False)
        result.setdefault("anomalies", [])

        # Clamp score
        result["score"] = max(0, min(10, int(result["score"])))

        logger.info(f"✅ Conversation graded: score={result['score']} label={result['label']}")
        return json.dumps(result)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in grade_conversation: {e}\nRaw output: {raw}")
        return json.dumps(_error_result(f"Failed to parse LLM response as JSON: {e}"))

    except Exception as e:
        logger.exception(f"Error in grade_conversation: {e}")
        return json.dumps(_error_result(str(e)))
