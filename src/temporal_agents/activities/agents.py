import asyncio
import json

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .base import _heartbeat_loop


_STATUS_KEYWORDS = [
    "co na praci", "co je nove", "aku mame robotu", "aké máme",
    "co mame", "co máme", "ulohy", "úlohy", "tasks", "pending",
    "backlog", "what's new", "what is new", "project status",
]


@activity.defn
async def parse_intent_activity(user_message: str) -> str:
    """Dummy rule-based intent classifier — no LLM.
    Returns JSON string e.g. '{"intent": "new_feature"}'.
    """
    activity.heartbeat()
    msg = user_message.lower()
    for kw in _STATUS_KEYWORDS:
        if kw in msg:
            return json.dumps({"intent": "project_status"})
    return json.dumps({"intent": "new_feature"})


@activity.defn
async def run_claude_chat_activity(message: str) -> str:
    """Send a message to claude -p and return the response (no agent, plain chat)."""
    activity.heartbeat()
    process = await asyncio.create_subprocess_exec(
        "claude", "-p", message,
        "--allowedTools", "",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    heartbeat_task = asyncio.create_task(_heartbeat_loop(30.0))
    try:
        stdout_bytes, stderr_bytes = await process.communicate()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
    if process.returncode != 0:
        err = stderr_bytes.decode().strip()
        raise ApplicationError(f"claude -p failed: {err}", non_retryable=False)
    return stdout_bytes.decode().strip()
