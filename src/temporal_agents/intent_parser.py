"""IntentParser — plain Python LLM-based intent + project parser with clarification support."""
import asyncio
import json

from temporal_agents.activities.base import _build_cmd, load_agent_model, load_agent_prompt
from temporal_agents.intent_config import INTENTS, PROJECTS


def _validate(raw: str) -> tuple[bool, dict]:
    """Returns (is_valid, parsed_dict). Valid = intent in INTENTS and project in PROJECTS."""
    try:
        data = json.loads(raw)
        ok = data.get("intent") in INTENTS and data.get("project") in PROJECTS
        return ok, data
    except (json.JSONDecodeError, TypeError):
        return False, {}


def _clarification_message(data: dict) -> str:
    """Generate clarification question based on what's missing."""
    missing = []
    if data.get("intent") not in INTENTS:
        missing.append(f"zámer (možnosti: {', '.join(INTENTS)})")
    if data.get("project") not in PROJECTS:
        missing.append(f"projekt (možnosti: {', '.join(PROJECTS)})")
    return f"Nepodarilo sa určiť {' a '.join(missing)}. Môžeš to upresniť?"


async def parse(message: str) -> dict:
    """Call LLM intent_parser agent and return parsed intent.

    Returns:
        {"intent": str, "project": str}  — on success
        {"clarification": str}            — when intent or project is unclear
    """
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

    raw = stdout.decode().strip()
    valid, data = _validate(raw)
    if valid:
        return {"intent": data["intent"], "project": data["project"]}
    return {"clarification": _clarification_message(data)}
