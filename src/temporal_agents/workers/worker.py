import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from temporal_agents.activities.tasks import (
    complete_task,
    create_task,
    execute_db_query,
    list_tasks,
    store_task,
    update_task_status,
)
from temporal_agents.activities.tickets import create_ticket, list_tickets
from temporal_agents.activities.conversations import (
    add_user_message,
    add_assistant_message,
    get_conversation,
)
from temporal_agents.activities.projects import (
    get_project_repos,
    get_project_env_file,
    store_project,
    list_projects,
    save_project,
)
from temporal_agents.workflows.feature_workflow import FeatureWorkflow

WORKFLOWS = [FeatureWorkflow]
ACTIVITIES = [
    store_task,
    list_tasks,
    update_task_status,
    create_task,
    complete_task,
    execute_db_query,
    create_ticket,
    list_tickets,
    add_user_message,
    add_assistant_message,
    get_conversation,
    get_project_repos,
    get_project_env_file,
    store_project,
    list_projects,
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
    print(
        "Worker started, task_queue=temporal-agentic-workflow, max_concurrent_activities=5"
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
