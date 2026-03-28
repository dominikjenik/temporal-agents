import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from temporal_agents.activities.agents import parse_intent_activity, run_claude_chat_activity
from temporal_agents.activities.hitl_db import execute_db_query, list_tasks, store_task, update_task_status
from temporal_agents.activities.lesson import capture_lesson
from temporal_agents.workflows import CommandDispatcher, IntentParser

WORKFLOWS = [IntentParser, CommandDispatcher]
ACTIVITIES = [
    parse_intent_activity,
    run_claude_chat_activity,
    store_task,
    list_tasks,
    update_task_status,
    execute_db_query,
    capture_lesson,
]


async def main() -> None:
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="temporal-agentic-workflow",
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        max_concurrent_activities=5,
    )
    print("Worker started, task_queue=temporal-agentic-workflow, max_concurrent_activities=5")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
