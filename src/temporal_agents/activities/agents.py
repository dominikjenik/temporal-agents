from temporalio import activity

from .base import ClaudeActivityInput, ClaudeActivityOutput, run_claude_activity


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
