import asyncio
import json

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .base import _build_cmd, _heartbeat_loop, load_agent_model, load_agent_prompt


@activity.defn
async def parse_intent_activity(user_message: str) -> str:
    """LLM intent + project classifier using intent_parser agent.
    Returns JSON string: {"intent": "...", "project": "...", "confidence": 0-100}.
    """
    activity.heartbeat()
    system_prompt = load_agent_prompt("intent_parser")
    model = load_agent_model("intent_parser")
    cmd = _build_cmd(user_message, system_prompt, model)

    process = await asyncio.create_subprocess_exec(
        *cmd,
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
        raise ApplicationError(f"intent_parser failed: {err}", non_retryable=False)
    return stdout_bytes.decode().strip()


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
