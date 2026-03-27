import asyncio
import json

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .base import ClaudeActivityInput, ClaudeActivityOutput, _heartbeat_loop, run_claude_activity

_INTENT_PROMPT = """\
Extract the intent from the user message. Reply with ONLY a JSON object, no other text.

Known intents:
- "project_status": user asks what work there is, what tasks, what's new, what's pending

Examples:
  "co na praci" -> {{"intent": "project_status"}}
  "co je nove" -> {{"intent": "project_status"}}
  "aku mame robotu" -> {{"intent": "project_status"}}
  "what tasks do we have" -> {{"intent": "project_status"}}

If no known intent matches, return {{"intent": "unknown"}}.

User message: {message}"""


@activity.defn
async def developer_activity(task: str) -> ClaudeActivityOutput:
    return await run_claude_activity(ClaudeActivityInput(agent_name="developer", task=task))


@activity.defn
async def tester_activity(task: str) -> ClaudeActivityOutput:
    return await run_claude_activity(ClaudeActivityInput(agent_name="tester", task=task))


@activity.defn
async def developer_zbornik_activity(task: str) -> ClaudeActivityOutput:
    return await run_claude_activity(ClaudeActivityInput(agent_name="developer-zbornik", task=task))


@activity.defn
async def devops_zbornik_activity(task: str) -> ClaudeActivityOutput:
    return await run_claude_activity(ClaudeActivityInput(agent_name="devops-zbornik", task=task))


@activity.defn
async def parse_intent_activity(user_message: str) -> str:
    """Call LLM to extract intent from user message. Returns JSON string, e.g. '{"intent": "project_status"}'."""
    activity.heartbeat()
    prompt = _INTENT_PROMPT.format(message=user_message)
    process = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
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
    raw = stdout_bytes.decode().strip()
    # Validate it's parseable JSON with an intent field
    try:
        parsed = json.loads(raw)
        if "intent" not in parsed:
            return json.dumps({"intent": "unknown"})
        return json.dumps({"intent": parsed["intent"]})
    except (json.JSONDecodeError, KeyError):
        return json.dumps({"intent": "unknown"})


@activity.defn
async def manager_activity(task: str) -> ClaudeActivityOutput:
    return await run_claude_activity(ClaudeActivityInput(agent_name="manager", task=task))


@activity.defn
async def run_project_stub_activity(project: str, task: str) -> str:
    """Stub — simulates project execution without running real agents."""
    activity.logger.info(f"[stub] project={project} task={task[:80]}")
    return f"[stub] {project}: done"


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
