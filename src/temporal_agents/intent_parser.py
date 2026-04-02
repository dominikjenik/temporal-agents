"""IntentResolver + Validation layer.

Public API: resolve(message, client) — full pipeline.
  1. Call LLM agent, expect ParsedIntent JSON.
  2. Validate the response.
  3. chat   → return {"type": "chat"}
  4. not chat → dispatch to CommandDispatcher → return {"type": "dispatched", "workflow_id": ...}
  5. invalid  → return {"type": "clarification", "message": ...}
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
    INTENTS,
    PROJECTS,
    PLANNINGS,
    PROJECT_OPTIONAL_INTENTS,
)


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    return raw.strip()


def _validate(raw: str) -> tuple[bool, dict]:
    try:
        data = json.loads(raw)
        intent = data.get("intent")
        if intent not in INTENTS:
            return False, data
        if Intent(intent) in PROJECT_OPTIONAL_INTENTS:
            return True, data
        if data.get("project") not in PROJECTS:
            return False, data
        if data.get("planning") not in PLANNINGS:
            return False, data
        return True, data
    except (json.JSONDecodeError, TypeError):
        return False, {}


def _clarification_message(data: dict) -> str:
    missing = []
    intent = data.get("intent")
    if intent not in INTENTS:
        missing.append(f"zámer (možnosti: {', '.join(INTENTS)})")
    elif Intent(intent) not in PROJECT_OPTIONAL_INTENTS:
        if data.get("project") not in PROJECTS:
            missing.append(f"projekt (možnosti: {', '.join(PROJECTS)})")
        if data.get("planning") not in PLANNINGS:
            missing.append(f"plán (možnosti: {', '.join(PLANNINGS)})")
    return f"Nepodarilo sa určiť {' a '.join(missing)}. Môžeš to upresniť?"


async def _llm_resolve_and_parse(message: str) -> Union[ParsedIntent, dict]:
    """Call LLM and return ParsedIntent or {"clarification": str}."""
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
        return {"clarification": "Vypršal časový limit. Skús to znova."}

    raw = _strip_fences(stdout.decode())
    valid, data = _validate(raw)
    if not valid:
        return {"clarification": _clarification_message(data)}

    intent = Intent(data["intent"])
    if intent == Intent.chat or intent == Intent.query:
        return ParsedIntent(intent=intent)

    return ParsedIntent(
        intent=intent,
        project=Project(data["project"]),
        planning=Planning(data["planning"]),
    )


async def intent_parser_resolve(message: str, client: Client) -> dict:
    """Full pipeline: parse → route → dispatch if needed.

    Returns one of:
      {"type": "chat", "response": str}
      {"type": "query", "response": str}
      {"type": "dispatched", "workflow_id": str, "intent": str, "project": str}
      {"type": "todo_saved", "requirement_id": str, "project": str}
      {"type": "clarification", "message": str}
    """
    result = await _llm_resolve_and_parse(message)

    if isinstance(result, dict):
        return {"type": "clarification", "message": result["clarification"]}

    if result.intent == Intent.chat or result.intent == Intent.query:
        response = await _llm_chat_response(message)
        return {"type": result.intent.value, "response": response}

    return await dispatch_command(result, client)


async def _llm_chat_response(message: str) -> str:
    """Get chat response from LLM."""
    from temporal_agents.activities.base import _build_cmd, load_agent_model

    system_prompt = "You are a helpful assistant. Answer the user's question helpfully and concisely."
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
        return "Vypršal časový limit. Skús to znova."

    response = stdout.decode().strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[-1]
        if response.endswith("```"):
            response = response[: response.rfind("```")]
    return response.strip()
