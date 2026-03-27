"""CLI gateway for ManagerWorkflow.

Commands:
  request <project> <task>    — start ManagerWorkflow, print workflow ID
  confirm <workflow-id>       — send confirm signal
  cancel <workflow-id>        — send cancel signal
  status <workflow-id>        — print current status and plan
"""
import asyncio
import sys
import uuid

from shared.config import get_temporal_client
from workflows.manager_workflow import ManagerInput, ManagerWorkflow


async def cmd_request(project: str, task: str) -> None:
    client = await get_temporal_client()
    workflow_id = f"manager-{project}-{uuid.uuid4()}"
    handle = await client.start_workflow(
        ManagerWorkflow.run,
        ManagerInput(project=project, task=task, require_confirm=True),
        id=workflow_id,
        task_queue="agent-task-queue",
    )
    print(f"Workflow started: {handle.id}")


async def cmd_confirm(workflow_id: str) -> None:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(ManagerWorkflow.confirm)
    print(f"Confirmed: {workflow_id}")


async def cmd_cancel(workflow_id: str) -> None:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(ManagerWorkflow.cancel)
    print(f"Cancelled: {workflow_id}")


async def cmd_status(workflow_id: str) -> None:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    status = await handle.query(ManagerWorkflow.get_status)
    plan = await handle.query(ManagerWorkflow.get_plan)
    print(f"Status: {status}")
    print(f"Plan:\n{plan}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    command = args[0]
    if command == "request" and len(args) == 3:
        asyncio.run(cmd_request(args[1], args[2]))
    elif command == "confirm" and len(args) == 2:
        asyncio.run(cmd_confirm(args[1]))
    elif command == "cancel" and len(args) == 2:
        asyncio.run(cmd_cancel(args[1]))
    elif command == "status" and len(args) == 2:
        asyncio.run(cmd_status(args[1]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
