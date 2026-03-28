import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from temporalio.api.enums.v1 import WorkflowExecutionStatus
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import TemporalError

from temporal_agents.workflows.claude_chat_workflow import ClaudeChatWorkflow
from temporal_agents.workflows.manager_workflow import ManagerInput, ManagerWorkflow

TASK_QUEUE = "temporal-agents"

app = FastAPI()
temporal_client: Optional[Client] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global temporal_client
    temporal_client = await Client.connect("localhost:7233")


@app.get("/")
def root():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Chat (ClaudeChatWorkflow)
# ---------------------------------------------------------------------------

CHAT_WORKFLOW_ID = "chat-workflow"


@app.post("/chat/start")
async def chat_start():
    await temporal_client.start_workflow(
        ClaudeChatWorkflow.run,
        id=CHAT_WORKFLOW_ID,
        task_queue=TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )
    return {"workflow_id": CHAT_WORKFLOW_ID}


@app.post("/chat/prompt")
async def chat_prompt(prompt: str):
    await temporal_client.start_workflow(
        ClaudeChatWorkflow.run,
        id=CHAT_WORKFLOW_ID,
        task_queue=TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        start_signal="user_prompt",
        start_signal_args=[prompt],
    )
    return {"message": "Prompt sent."}


@app.post("/chat/end")
async def chat_end():
    try:
        handle = temporal_client.get_workflow_handle(CHAT_WORKFLOW_ID)
        await handle.signal("end_chat")
        return {"message": "Chat ended."}
    except TemporalError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/chat/history")
async def chat_history():
    failed_states = [
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TERMINATED,
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_CANCELED,
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_FAILED,
    ]
    try:
        handle = temporal_client.get_workflow_handle(CHAT_WORKFLOW_ID)
        description = await handle.describe()
        if description.status in failed_states:
            return []
        history = await asyncio.wait_for(
            handle.query("get_conversation_history"), timeout=5
        )
        return history
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query timed out.")
    except TemporalError as e:
        err = str(e)
        if "workflow not found" in err or "sql: no rows" in err:
            return []
        raise HTTPException(status_code=500, detail=err)


# ---------------------------------------------------------------------------
# Manager (ManagerWorkflow)
# ---------------------------------------------------------------------------

class ManagerRequest(BaseModel):
    user_message: str


@app.post("/manager/start")
async def manager_start(body: ManagerRequest):
    workflow_id = f"manager-{body.user_message[:30].replace(' ', '-')}"
    await temporal_client.start_workflow(
        ManagerWorkflow.run,
        ManagerInput(user_message=body.user_message),
        id=workflow_id,
        task_queue=TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )
    return {"workflow_id": workflow_id}


@app.get("/manager/{workflow_id}/status")
async def manager_status(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    status = await handle.query("get_status")
    intent = await handle.query("get_intent")
    return {"status": status, "intent": intent}


@app.get("/manager/{workflow_id}/result")
async def manager_result(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    result = await handle.result()
    return {"result": result}
