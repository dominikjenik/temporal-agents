import asyncio
import json
import os
from pathlib import Path

from pydantic import BaseModel
from temporalio import activity

# Project root — works regardless of cwd
_AGENTS_DIR = Path(__file__).parents[3] / "agents"

# Runner: "claude" or "cline" — set via TEMPORAL_RUNNER env var or .env file
TEMPORAL_RUNNER: str = os.environ.get("TEMPORAL_RUNNER", "claude")

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse simple key: value frontmatter delimited by ---. Returns (meta, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[end + 4:].strip()


def load_agent_model(agent_name: str) -> str:
    """Return model ID from agent frontmatter, or empty string if not specified."""
    path = _AGENTS_DIR / f"{agent_name}.md"
    if not path.exists():
        return ""
    meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8").strip())
    return meta.get("model", "")


class ClaudeActivityInput(BaseModel):
    agent_name: str
    task: str


class ClaudeActivityOutput(BaseModel):
    result: str
    success: bool
    exit_code: int


def load_agent_prompt(agent_name: str) -> str:
    """Load agent system prompt body (without frontmatter) from agents/<agent_name>.md."""
    path = _AGENTS_DIR / f"{agent_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Agent definition not found: {path}")
    _, body = _parse_frontmatter(path.read_text(encoding="utf-8").strip())
    return body


def _build_cmd(task: str, system_prompt: str, model: str = "") -> list[str]:
    """Build CLI command for the configured runner."""
    runner = TEMPORAL_RUNNER
    if runner == "cline":
        # Cline has no --system-prompt flag — prepend to task
        full_task = f"<instructions>\n{system_prompt}\n</instructions>\n\n{task}"
        return ["cline", "task", "-a", "-y", "--json", full_task]
    else:
        cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "-p", task,
            "--system-prompt", system_prompt,
        ]
        if model:
            cmd += ["--model", model]
        return cmd


async def _heartbeat_loop(interval: float = 30.0) -> None:
    """Send heartbeat every *interval* seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        activity.heartbeat()


@activity.defn
async def run_claude_activity(input: ClaudeActivityInput) -> ClaudeActivityOutput:
    """Run agent via configured runner (claude or cline) with system prompt from agents/<agent_name>.md."""
    activity.heartbeat()

    system_prompt = load_agent_prompt(input.agent_name)
    model = load_agent_model(input.agent_name)
    cmd = _build_cmd(input.task, system_prompt, model)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Start heartbeat loop as a background task
    heartbeat_task = asyncio.create_task(_heartbeat_loop(30.0))

    try:
        stdout_bytes, _stderr_bytes = await process.communicate()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    raw = stdout_bytes.decode("utf-8", errors="replace")
    result = _parse_output(raw)

    return ClaudeActivityOutput(
        result=result,
        success=(process.returncode == 0),
        exit_code=process.returncode,
    )


def _parse_output(raw: str) -> str:
    """Extract result text from runner output.

    Claude: plain text → return as-is.
    Cline --json: NDJSON events → extract completion_result text.
    """
    if TEMPORAL_RUNNER != "cline":
        return raw.strip()

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "completion_result":
                return event.get("text", "").strip()
        except json.JSONDecodeError:
            continue
    return raw.strip()
