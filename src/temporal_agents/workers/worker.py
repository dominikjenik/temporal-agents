import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from temporal_agents.activities.agents import (
    developer_activity,
    developer_zbornik_activity,
    devops_zbornik_activity,
    manager_activity,
    run_claude_chat_activity,
    run_project_stub_activity,
    tester_activity,
)
from temporal_agents.activities.base import run_claude_activity
from temporal_agents.workflows import (
    ClaudeChatWorkflow,
    FeatureWorkflow,
    ManagerWorkflow,
    ProjectWorkflow,
)

WORKFLOWS = [ClaudeChatWorkflow, FeatureWorkflow, ManagerWorkflow, ProjectWorkflow]
ACTIVITIES = [
    developer_activity,
    tester_activity,
    developer_zbornik_activity,
    devops_zbornik_activity,
    manager_activity,
    run_project_stub_activity,
    run_claude_chat_activity,
    run_claude_activity,
]


async def main() -> None:
    # Connect to local Temporal server
    client = await Client.connect("localhost:7233")

    # Start worker and keep it running until interrupted (graceful shutdown via async with)
    async with Worker(
        client,
        task_queue="temporal-agents",
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        max_concurrent_activities=5,
    ) as worker:
        print("Worker started, task_queue=temporal-agents, max_concurrent_activities=5")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
