import asyncio
import json as _json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from temporalio.api.enums.v1 import EventType, WorkflowExecutionStatus
from temporalio.client import Client
from temporalio.exceptions import TemporalError

from temporal_agents.activities.tasks import _fetch_tasks
from temporal_agents.activities.tickets import _fetch_tickets
from temporal_agents.command_dispatcher import get_hitl_state
from temporal_agents.intent_parser import intent_parser_resolve
from temporal_agents.intent_config import ParsedIntent

app = FastAPI()
temporal_client: Optional[Client] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8003", "http://127.0.0.1:8003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global temporal_client
    last_err = None
    for attempt in range(30):
        try:
            temporal_client = await Client.connect("localhost:7233")
            return
        except Exception as e:
            last_err = e
            await asyncio.sleep(2)
    raise RuntimeError(f"Temporal not ready after 60s: {last_err}")


@app.get("/")
def root():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# IntentResolver — full pipeline: parse → validate → route → dispatch
# API passes message + Temporal client. IntentResolver handles the rest.
# ---------------------------------------------------------------------------


class RequestBody(BaseModel):
    message: str
    user_id: str = "default"
    task_id: Optional[str] = None


@app.post("/request")
async def handle_request(body: RequestBody):
    try:
        from temporal_agents.activities.conversations import get_conversation_history

        # Get conversation history for context
        history = await get_conversation_history(
            user_id=body.user_id, limit=50, task_id=body.task_id
        )

        # Store user message
        from temporal_agents.activities.conversations import store_message

        await store_message(body.user_id, "user", body.message, body.task_id)

        # Build context from history
        context_messages = [{"role": m.role, "content": m.content} for m in history]

        result = await intent_parser_resolve(
            body.message,
            temporal_client,
            user_id=body.user_id,
            conversation_history=context_messages,
        )

        # Store assistant response
        if isinstance(result, dict) and "response" in result:
            await store_message(
                body.user_id, "assistant", result["response"], body.task_id
            )

        return result
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except TemporalError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Workflow status + result
# ---------------------------------------------------------------------------


@app.get("/manager/{workflow_id}/status")
async def manager_status(workflow_id: str):
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
        return {"status": "done"}
    status = await handle.query("get_status")
    return {"status": status}


@app.get("/manager/{workflow_id}/result")
async def manager_result(workflow_id: str):
    handle = temporal_client.get_workflow_handle(workflow_id)
    try:
        result = await handle.result()
        return {"result": result}
    except TemporalError as e:
        return {"result": f"Chyba: {str(e)[:300]}"}


# ---------------------------------------------------------------------------
# Tasks & Tickets (DB)
# ---------------------------------------------------------------------------


@app.get("/tasks")
async def get_tasks():
    tasks = await _fetch_tasks()
    tickets = await _fetch_tickets()
    return [t.model_dump() for t in tasks if t.status != "confirmed"] + [
        r.model_dump() for r in tickets
    ]


# ---------------------------------------------------------------------------
# HITL signals + state
# Uses CommandDispatcher.get_hitl_state() to query workflow directly.
# Response includes signal_type (intent from workflow) and response (payload message).
# ---------------------------------------------------------------------------


class CommentRequest(BaseModel):
    text: str


@app.get("/hitl/{workflow_id}/state")
async def hitl_state(workflow_id: str):
    try:
        state = await get_hitl_state(workflow_id, temporal_client)
        return {
            "signal_type": state.signal_type,
            "response": state.response,
            "result": state.result,
            "comments": state.comments,
            "status": state.status,
            "log": state.log,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


def _decode_payloads(payloads) -> object:
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


def _extract_intent(output) -> str | None:
    if isinstance(output, str):
        try:
            parsed = _json.loads(output)
            if isinstance(parsed, dict):
                return parsed.get("intent") or None
        except (_json.JSONDecodeError, TypeError):
            pass
    if isinstance(output, dict):
        title = output.get("title", "")
        if isinstance(title, str) and "[DUPLICATE]" in title:
            return "resolved_as_duplicate"
    return None


def _parse_history_events(history_events, source: str) -> list[dict]:
    sched: dict[int, str] = {}
    out = []
    for e in history_events:
        et = e.event_type
        ts = e.event_time.ToJsonString() if e.event_time.seconds else None
        base = {"id": e.event_id, "time": ts, "source": source}

        if et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED:
            a = e.workflow_execution_started_event_attributes
            out.append(
                {
                    **base,
                    "kind": "workflow_started",
                    "workflow": a.workflow_type.name,
                    "input": _decode_payloads(a.input.payloads),
                }
            )
        elif et == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED:
            a = e.activity_task_scheduled_event_attributes
            sched[e.event_id] = a.activity_type.name
            out.append(
                {
                    **base,
                    "kind": "activity_scheduled",
                    "activity": a.activity_type.name,
                    "input": _decode_payloads(a.input.payloads),
                }
            )
        elif et == EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED:
            a = e.activity_task_completed_event_attributes
            act_name = sched.get(a.scheduled_event_id, "?")
            output = _decode_payloads(a.result.payloads)
            event = {
                **base,
                "kind": "activity_completed",
                "activity": act_name,
                "output": output,
            }
            intent = _extract_intent(output)
            if intent:
                event["intent"] = intent
            out.append(event)
        elif et == EventType.EVENT_TYPE_ACTIVITY_TASK_FAILED:
            a = e.activity_task_failed_event_attributes
            out.append(
                {
                    **base,
                    "kind": "activity_failed",
                    "activity": sched.get(a.scheduled_event_id, "?"),
                    "error": a.failure.message or "unknown",
                }
            )
        elif et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_SIGNALED:
            a = e.workflow_execution_signaled_event_attributes
            out.append(
                {
                    **base,
                    "kind": "signal",
                    "signal": a.signal_name,
                    "input": _decode_payloads(a.input.payloads),
                }
            )
        elif et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED:
            a = e.workflow_execution_completed_event_attributes
            output = _decode_payloads(a.result.payloads)
            event = {**base, "kind": "workflow_completed", "output": output}
            intent = _extract_intent(output)
            if intent:
                event["intent"] = intent
            out.append(event)
        elif et == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_FAILED:
            a = e.workflow_execution_failed_event_attributes
            out.append(
                {
                    **base,
                    "kind": "workflow_failed",
                    "error": a.failure.message or "unknown",
                }
            )

    return out


@app.get("/hitl/{workflow_id}/history")
async def hitl_history(workflow_id: str):
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        history = await handle.fetch_history()
        return {"events": _parse_history_events(history.events, "manager")}
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
