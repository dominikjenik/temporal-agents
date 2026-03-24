import asyncio

from pydantic import BaseModel
from temporalio import activity


class ClaudeActivityInput(BaseModel):
    agent_name: str
    task: str


class ClaudeActivityOutput(BaseModel):
    result: str
    success: bool
    exit_code: int


async def _heartbeat_loop(interval: float = 30.0) -> None:
    """Send heartbeat every *interval* seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        activity.heartbeat()


@activity.defn
async def run_claude_activity(input: ClaudeActivityInput) -> ClaudeActivityOutput:
    """Run `claude --dangerously-skip-permissions -p <agent_name> "<task>"` as subprocess.

    A heartbeat task runs concurrently and calls activity.heartbeat() every 30 s so
    Temporal knows the activity is still alive during long-running claude invocations.
    """
    # Send one immediate heartbeat so Temporal registers activity start
    activity.heartbeat()

    process = await asyncio.create_subprocess_exec(
        "claude",
        "--dangerously-skip-permissions",
        "-p",
        input.agent_name,
        input.task,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Start heartbeat loop as a background task
    heartbeat_task = asyncio.create_task(_heartbeat_loop(30.0))

    try:
        stdout_bytes, _stderr_bytes = await process.communicate()
    finally:
        # Cancel heartbeat task regardless of communicate() outcome
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    return ClaudeActivityOutput(
        result=stdout_bytes.decode("utf-8", errors="replace"),
        success=(process.returncode == 0),
        exit_code=process.returncode,
    )
