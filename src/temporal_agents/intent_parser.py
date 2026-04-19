"""IntentResolver + Validation layer.

Public API: resolve(message, client) — full pipeline.
  1. Call LLM agent, expect action JSON.
  2. action=dispatch → start workflow
  3. action=chat → return chat response
  4. action=clarify → ask clarifying question
"""

import asyncio
import json
from typing import Optional

from temporalio.client import Client

from temporal_agents.activities.base import (
    _build_cmd,
    load_agent_model,
    load_agent_prompt,
)
from temporal_agents.activities.projects import list_projects
from temporal_agents.command_dispatcher import dispatch_command
from temporal_agents.intent_config import (
    Intent,
    Project,
    Planning,
    ParsedIntent,
)


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    return raw.strip()


async def _build_context_message(
    message: str,
    conversation_history: list[dict] = None,
    project_name: str = None,
) -> str:
    """Build full message with conversation context and project repos."""
    parts = []

    # Add project repos context if available
    if project_name:
        from temporal_agents.activities.projects import get_project

        project = await get_project(project_name)
        if project and project.repos:
            repos_context = "Dostupné komponenty projektu:\n"
            for repo in project.repos:
                repos_context += f"- {repo.title}: {repo.url}\n"
            parts.append(repos_context)

    # Add conversation history
    if conversation_history:
        parts.append("Konverzačná história:\n")
        for msg in conversation_history:
            role = "Používateľ" if msg.get("role") == "user" else "Asistent"
            parts.append(f"{role}: {msg.get('content', '')}")

    parts.append(f"Aktuálna správa: {message}")
    return "\n\n".join(parts)


async def _llm_resolve_and_parse(message: str, context: str = "") -> dict:
    """Call LLM and return action dict."""
    system_prompt = load_agent_prompt("intent_parser")
    model = load_agent_model("intent_parser")

    full_message = f"{context}\n\n{message}" if context else message
    cmd = _build_cmd(full_message, system_prompt, model)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=120)
    except asyncio.TimeoutError:
        process.kill()
        return {"action": "chat", "message": "Vypršal časový limit. Skús to znova."}

    raw = _strip_fences(stdout.decode())

    try:
        data = json.loads(raw)
        return data
    except (json.JSONDecodeError, TypeError):
        return {"action": "chat", "message": raw}


async def intent_parser_resolve(
    message: str,
    client: Client,
    user_id: str = "default",
    conversation_history: list[dict] = None,
    task_id: str = None,
    project_name: str = None,
) -> dict:
    """Full pipeline: LLM decides action → execute.

    Returns one of:
      {"type": "chat", "response": str}
      {"type": "dispatched", "workflow_id": str, "intent": str, "project": str}
      {"type": "todo_saved", "ticket_id": str, "project": str}
    """
    # Build context from conversation history and project repos
    context = await _build_context_message(
        message=message,
        conversation_history=conversation_history,
        project_name=project_name,
    )

    result = await _llm_resolve_and_parse(message, context)
    action = result.get("action")

    if action == "dispatch":
        parsed = ParsedIntent(
            intent=Intent.new_feature,
            project=Project(result.get("project", "")),
            planning=Planning(result.get("planning", "implementing")),
        )
        return await dispatch_command(parsed, client)

    return {
        "type": "chat",
        "response": result.get("message") or result.get("question", ""),
    }
