import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from temporal_agents.activities.agents import (
    developer_activity,
    developer_zbornik_activity,
    devops_zbornik_activity,
    manager_activity,
    parse_intent_activity,
    run_claude_chat_activity,
    run_project_stub_activity,
    tester_activity,
)
from temporal_agents.activities.base import run_claude_activity
from temporal_agents.activities.hitl_db import execute_db_query, list_tasks, store_task, update_task_status
from temporal_agents.activities.lesson import capture_lesson
from temporal_agents.workflows import (
    ClaudeChatWorkflow,
    FeatureWorkflow,
    ManagerWorkflow,
    ProjectWorkflow,
    ProjectakWorkflow,
)

WORKFLOWS = [ClaudeChatWorkflow, FeatureWorkflow, ManagerWorkflow, ProjectWorkflow, ProjectakWorkflow]
ACTIVITIES = [
    developer_activity,
    tester_activity,
    developer_zbornik_activity,
    devops_zbornik_activity,
    manager_activity,
    parse_intent_activity,
    run_project_stub_activity,
    run_claude_chat_activity,
    run_claude_activity,
    store_task,
    list_tasks,
    execute_db_query,
    update_task_status,
    capture_lesson,
]


async def main() -> None:
    # Connect to local Temporal server
    client = await Client.connect("localhost:7233")

    # Use worker.run() directly — async with + run() causes double validate() → Rust panic
    worker = Worker(
        client,
        task_queue="temporal-agents",
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        max_concurrent_activities=5,
    )
    print("Worker started, task_queue=temporal-agents, max_concurrent_activities=5")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
