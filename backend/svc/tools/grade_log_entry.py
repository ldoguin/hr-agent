"""
Single log entry grading tool.
Evaluates one agentc activity log entry against the goal of setting up a job
interview, independently of any session or conversation context.
"""
import json
import logging

from agentc_core.tool import tool
from svc.core.agent import AgentManager

logger = logging.getLogger("uvicorn.error")


def _error_result(message: str) -> dict:
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


def _format_content(content: dict) -> str:
    """Render a log content dict as readable text for the prompt."""
    kind = content.get("kind", "unknown")

    if kind in ("user", "assistant"):
        return content.get("value", "(empty)")

    if kind == "tool-call":
        args = json.dumps(content.get("tool_args", {}), indent=2, ensure_ascii=False)
        return f"Tool: {content.get('tool_name', 'unknown')}\nArguments:\n{args}"

    if kind == "tool-result":
        status = content.get("status", "unknown")
        result = content.get("tool_result", "(no result)")
        return f"Status: {status}\nResult: {result}"

    if kind == "chat-completion":
        return content.get("output", "(empty)")

    # begin / end / key-value / other
    return json.dumps(content, indent=2, ensure_ascii=False)


@tool(
    name="grade_log_entry",
    description=(
        "Grade a single agentc activity log entry against the goal of setting up a job interview. "
        "Returns a score 0-10 with reasoning, independent of session context."
    ),
    annotations={"category": "hr", "type": "evaluation"},
)
def grade_log_entry(
    log: dict,
    agent_manager: AgentManager = None,
) -> str:
    """
    Grade one agentc log entry in isolation.

    Args:
        log:           A single agentc log dict (identifier, span, timestamp, content).
        agent_manager: AgentManager instance with LLM and catalog access.

    Returns:
        JSON string with keys: score, label, summary, issues, strengths,
        off_topic, anomalies.
    """
    raw = ""
    try:
        if agent_manager is None or agent_manager.llm is None:
            return json.dumps(_error_result("LLM not available"))

        if agent_manager.catalog is None:
            return json.dumps(_error_result("Agent catalog not available"))

        prompt_result = agent_manager.catalog.find("prompt", name="log_entry_grader")
        if prompt_result is None:
            return json.dumps(_error_result(
                "log_entry_grader prompt not found — run 'agentc index svc/prompts/' first"
            ))

        content = log.get("content", {})
        kind = content.get("kind", "unknown")
        timestamp = log.get("timestamp", "unknown")[:19].replace("T", " ")
        formatted_content = _format_content(content)

        prompt_text = (
            prompt_result.content
            .replace("{kind}", kind)
            .replace("{timestamp}", timestamp)
            .replace("{content}", formatted_content)
        )

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

        result.setdefault("score", 0)
        result.setdefault("label", "unknown")
        result.setdefault("summary", "")
        result.setdefault("issues", [])
        result.setdefault("strengths", [])
        result.setdefault("off_topic", False)
        result.setdefault("anomalies", [])
        result["score"] = max(0, min(10, int(result["score"])))

        logger.info(
            f"✅ Log entry graded: kind={kind} score={result['score']} label={result['label']}"
        )
        return json.dumps(result)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in grade_log_entry: {e}\nRaw: {raw}")
        return json.dumps(_error_result(f"Failed to parse LLM response as JSON: {e}"))

    except Exception as e:
        logger.exception(f"Error in grade_log_entry: {e}")
        return json.dumps(_error_result(str(e)))
