import asyncio
import json as _json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from temporalio.api.enums.v1 import EventType, WorkflowExecutionStatus
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import TemporalError

from temporal_agents.activities.hitl_db import _fetch_tasks
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


# ---------------------------------------------------------------------------
# Tasks (DB)
# ---------------------------------------------------------------------------

@app.get("/tasks")
async def get_tasks():
    tasks = await _fetch_tasks()
    return [t.model_dump() for t in tasks if t.status != "confirmed"]


# ---------------------------------------------------------------------------
# HITL signals + state
# ---------------------------------------------------------------------------

class CommentRequest(BaseModel):
    text: str


@app.get("/hitl/{workflow_id}/state")
async def hitl_state(workflow_id: str):
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        desc = await handle.describe()

        _terminal = {
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED,
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_FAILED,
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TERMINATED,
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TIMED_OUT,
            WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_CANCELED,
        }
        if desc.status in _terminal:
            is_ok = desc.status == WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED
            try:
                final_result = await handle.result() if is_ok else None
            except Exception:
                final_result = None
            return {
                "result": final_result,
                "comments": [],
                "status": "confirmed" if is_ok else "failed",
                "log": [
                    "Workflow ukončený — požiadavka potvrdená" if is_ok
                    else f"Workflow skončil s chybou: {desc.status.name}"
                ],
            }

        result = await handle.query("get_result")
        comments = await handle.query("get_comments")
        status = await handle.query("get_status")
        try:
            log = await handle.query("get_log")
        except TemporalError:
            log = []
        return {"result": result, "comments": comments, "status": status, "log": log}
    except TemporalError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _decode_payloads(payloads) -> object:
    """Decode Temporal Payloads list → Python value (single) or list (multiple)."""
    if not payloads:
        return None
    out = []
    for p in payloads:
        try:
            out.append(_json.loads(p.data))
        except Exception:
            try:
                out.append(p.data.decode("utf-8", errors="replace"))
            except Exception:
                out.append("<binary>")
    return out[0] if len(out) == 1 else out


def _parse_history_events(history_events, source: str) -> list[dict]:
    """Convert raw Temporal history events to structured dicts."""
    sched: dict[int, str] = {}
    out = []
    for e in history_events:
        et = e.event_type
        ts = e.event_time.ToJsonString() if e.event_time.seconds else None
        base = {"id": e.event_id, "time": ts, "source": source}

        if et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED:
            a = e.workflow_execution_started_event_attributes
            out.append({**base, "kind": "workflow_started",
                        "workflow": a.workflow_type.name,
                        "input": _decode_payloads(a.input.payloads)})

        elif et == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED:
            a = e.activity_task_scheduled_event_attributes
            sched[e.event_id] = a.activity_type.name
            out.append({**base, "kind": "activity_scheduled",
                        "activity": a.activity_type.name,
                        "input": _decode_payloads(a.input.payloads)})

        elif et == EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED:
            a = e.activity_task_completed_event_attributes
            out.append({**base, "kind": "activity_completed",
                        "activity": sched.get(a.scheduled_event_id, "?"),
                        "output": _decode_payloads(a.result.payloads)})

        elif et == EventType.EVENT_TYPE_ACTIVITY_TASK_FAILED:
            a = e.activity_task_failed_event_attributes
            out.append({**base, "kind": "activity_failed",
                        "activity": sched.get(a.scheduled_event_id, "?"),
                        "error": a.failure.message or "unknown"})

        elif et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_SIGNALED:
            a = e.workflow_execution_signaled_event_attributes
            out.append({**base, "kind": "signal",
                        "signal": a.signal_name,
                        "input": _decode_payloads(a.input.payloads)})

        elif et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED:
            a = e.workflow_execution_completed_event_attributes
            out.append({**base, "kind": "workflow_completed",
                        "output": _decode_payloads(a.result.payloads)})

        elif et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_FAILED:
            a = e.workflow_execution_failed_event_attributes
            out.append({**base, "kind": "workflow_failed",
                        "error": a.failure.message or "unknown"})

    return out


@app.get("/hitl/{workflow_id}/history")
async def hitl_history(workflow_id: str):
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        history = await handle.fetch_history()

        # Detect parent workflow from the first event
        parent_wf_id = None
        if history.events:
            first = history.events[0]
            if first.event_type == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED:
                parent = first.workflow_execution_started_event_attributes.parent_workflow_execution
                if parent.workflow_id:
                    parent_wf_id = parent.workflow_id

        all_events: list[dict] = []

        # Prepend parent (manager) history so intent resolution is visible first
        if parent_wf_id:
            try:
                parent_history = await temporal_client.get_workflow_handle(parent_wf_id).fetch_history()
                all_events.extend(_parse_history_events(parent_history.events, "manager"))
            except Exception:
                pass

        all_events.extend(_parse_history_events(history.events, "projektak"))
        return {"events": all_events}

    except TemporalError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hitl/{workflow_id}/confirm")
async def hitl_confirm(workflow_id: str):
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.signal("confirm")
        return {"status": "confirmed"}
    except TemporalError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/hitl/{workflow_id}/comment")
async def hitl_comment(workflow_id: str, body: CommentRequest):
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        await handle.signal("comment", body.text)
        return {"status": "comment_sent"}
    except TemporalError as e:
        raise HTTPException(status_code=404, detail=str(e))
