import asyncio
import json
import re

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .base import ClaudeActivityInput, ClaudeActivityOutput, _heartbeat_loop, load_agent_model, load_agent_prompt, run_claude_activity


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


def _extract_intent(raw: str) -> str:
    """Parse intent JSON from LLM output. Pure function — testable without Temporal context."""
    match = re.search(r'\{[^{}]*"intent"[^{}]*\}', raw)
    if match:
        try:
            parsed = json.loads(match.group())
            return json.dumps({"intent": parsed.get("intent", "unknown")})
        except json.JSONDecodeError:
            pass
    return json.dumps({"intent": "unknown"})


@activity.defn
async def parse_intent_activity(user_message: str) -> str:
    """Extract intent from user message via claude -p (always, regardless of TEMPORAL_RUNNER).
    Returns JSON string e.g. '{"intent": "project_status"}'.
    Claude is used directly because intent extraction requires precise JSON output,
    not agentic behaviour (which Cline would produce).
    """
    activity.heartbeat()
    system_prompt = load_agent_prompt("manager")
    model = load_agent_model("manager")
    cmd = [
        "claude", "--dangerously-skip-permissions",
        "-p", user_message,
        "--system-prompt", system_prompt,
    ]
    if model:
        cmd += ["--model", model]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, _ = await process.communicate()
    raw = stdout_bytes.decode("utf-8", errors="replace").strip()
    return _extract_intent(raw)


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
