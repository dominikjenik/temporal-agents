"""IntentResolver + Validation layer.

Public API: resolve(message, client) — full pipeline.
  1. Call LLM agent, expect action JSON.
  2. action=dispatch → start workflow
  3. action=chat → return chat response
  4. action=clarify → ask clarifying question
"""

import asyncio
import json
from typing import Union

from temporalio.client import Client

from temporal_agents.activities.base import (
    _build_cmd,
    load_agent_model,
    load_agent_prompt,
)
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


async def _llm_resolve_and_parse(message: str) -> dict:
    """Call LLM and return action dict."""
    system_prompt = load_agent_prompt("intent_parser")
    model = load_agent_model("intent_parser")
    cmd = _build_cmd(message, system_prompt, model)

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


async def intent_parser_resolve(message: str, client: Client) -> dict:
    """Full pipeline: LLM decides action → execute.

    Returns one of:
      {"type": "chat", "response": str}
      {"type": "dispatched", "workflow_id": str, "intent": str, "project": str}
      {"type": "todo_saved", "requirement_id": str, "project": str}
    """
    result = await _llm_resolve_and_parse(message)
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
