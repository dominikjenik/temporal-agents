import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from temporalio.api.enums.v1 import WorkflowExecutionStatus
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import TemporalError

from goals import goal_list
from models.data_types import AgentGoalWorkflowParams, CombinedInput
from shared.config import TEMPORAL_TASK_QUEUE, get_temporal_client
from workflows.agent_goal_workflow import AgentGoalWorkflow
from workflows.claude_chat_workflow import ClaudeChatWorkflow
from workflows.manager_workflow import ManagerWorkflow, ManagerInput

app = FastAPI()
temporal_client: Optional[Client] = None

# Load environment variables
load_dotenv()


def get_initial_agent_goal():
    """Get the agent goal from environment variables."""
    env_goal = os.getenv(
        "AGENT_GOAL", "goal_event_flight_invoice"
    )  # if no goal is set in the env file, default to single agent mode
    for listed_goal in goal_list:
        if listed_goal.id == env_goal:
            return listed_goal


@app.on_event("startup")
async def startup_event():
    global temporal_client
    temporal_client = await get_temporal_client()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://100.123.195.81:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartManagerRequest(BaseModel):
    project: str = "auto"
    task: str
    require_confirm: bool = True


@app.get("/")
def root():
    return {"message": "Temporal AI Agent!"}


@app.get("/tool-data")
async def get_tool_data():
    """Calls the workflow's 'get_tool_data' query."""
    try:
        # Get workflow handle
        handle = temporal_client.get_workflow_handle("agent-workflow")

        # Check if the workflow is completed
        workflow_status = await handle.describe()
        if workflow_status.status == 2:
            # Workflow is completed; return an empty response
            return {}

        # Query the workflow
        tool_data = await handle.query("get_latest_tool_data")
        return tool_data
    except TemporalError as e:
        # Workflow not found; return an empty response
        print(e)
        return {}


@app.get("/get-conversation-history")
async def get_conversation_history():
    """Calls the workflow's 'get_conversation_history' query."""
    try:
        handle = temporal_client.get_workflow_handle("agent-workflow")

        failed_states = [
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TERMINATED,
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_CANCELED,
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_FAILED,
        ]

        description = await handle.describe()
        if description.status in failed_states:
            print("Workflow is in a failed state. Returning empty history.")
            return []

        # Set a timeout for the query
        try:
            conversation_history = await asyncio.wait_for(
                handle.query("get_conversation_history"),
                timeout=5,  # Timeout after 5 seconds
            )
            return conversation_history
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=404,
                detail="Temporal query timed out (worker may be unavailable).",
            )

    except TemporalError as e:
        error_message = str(e)
        print(f"Temporal error: {error_message}")

        # If worker is down or no poller is available, return a 404
        if "no poller seen for task queue recently" in error_message:
            raise HTTPException(
                status_code=404, detail="Workflow worker unavailable or not found."
            )

        if "workflow not found" in error_message or "sql: no rows in result set" in error_message:
            return []
        else:
            # For other Temporal errors, return a 500
            raise HTTPException(
                status_code=500, detail="Internal server error while querying workflow."
            )


@app.get("/agent-goal")
async def get_agent_goal():
    """Calls the workflow's 'get_agent_goal' query."""
    try:
        # Get workflow handle
        handle = temporal_client.get_workflow_handle("agent-workflow")

        # Check if the workflow is completed
        workflow_status = await handle.describe()
        if workflow_status.status == 2:
            # Workflow is completed; return an empty response
            return {}

        # Query the workflow
        agent_goal = await handle.query("get_agent_goal")
        return agent_goal
    except TemporalError as e:
        # Workflow not found; return an empty response
        print(e)
        return {}


@app.post("/send-prompt")
async def send_prompt(prompt: str):
    workflow_id = "agent-workflow"

    await temporal_client.start_workflow(
        ClaudeChatWorkflow.run,
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        start_signal="user_prompt",
        start_signal_args=[prompt],
    )

    return {"message": f"Prompt '{prompt}' sent to workflow {workflow_id}."}


@app.post("/confirm")
async def send_confirm():
    """Sends a 'confirm' signal to the workflow."""
    workflow_id = "agent-workflow"
    handle = temporal_client.get_workflow_handle(workflow_id)
    await handle.signal("confirm")
    return {"message": "Confirm signal sent."}


@app.post("/end-chat")
async def end_chat():
    """Sends a 'end_chat' signal to the workflow."""
    workflow_id = "agent-workflow"

    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.signal("end_chat")
        return {"message": "End chat signal sent."}
    except TemporalError as e:
        print(e)
        # Workflow not found; return an empty response
        return {}


@app.post("/start-workflow")
async def start_workflow():
    workflow_id = "agent-workflow"

    await temporal_client.start_workflow(
        ClaudeChatWorkflow.run,
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE,
    )

    return {"message": "Chat workflow started."}


@app.post("/start-manager")
async def start_manager(body: StartManagerRequest):
    workflow_id = f"manager-{body.project}-{body.task[:20].replace(' ', '-')}"
    await temporal_client.start_workflow(
        ManagerWorkflow.run,
        ManagerInput(project=body.project, task=body.task, require_confirm=body.require_confirm),
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE,
    )
    return {"workflow_id": workflow_id}


@app.post("/manager-confirm/{workflow_id}")
async def manager_confirm(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    await handle.signal("confirm")
    return {"message": "Confirm signal sent."}


@app.post("/manager-cancel/{workflow_id}")
async def manager_cancel(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    await handle.signal("cancel")
    return {"message": "Cancel signal sent."}


@app.post("/manager-terminate/{workflow_id}")
async def manager_terminate(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    await handle.terminate(reason="Terminated by user")
    return {"message": "Workflow terminated."}


@app.get("/manager-status/{workflow_id}")
async def manager_status(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    status = await handle.query("get_status")
    return {"status": status}


@app.get("/manager-plan/{workflow_id}")
async def manager_plan(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    plan = await handle.query("get_plan")
    return {"plan": plan}
