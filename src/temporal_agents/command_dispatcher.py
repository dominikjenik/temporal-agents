"""CommandDispatcher — routes ParsedIntent to the correct Temporal workflow and executes it.

Responsibilities:
- dispatch_command(): receives ParsedIntent, executes workflow or saves to DB
- get_hitl_state(): queries workflow state directly for HITL endpoints

Receives all non-chat ParsedIntent objects from IntentResolver.
Raw user messages and chat history must never reach this module.
IntentParser agent must NOT receive workflow_id or requirement_id as input/output.
"""

import time
from dataclasses import dataclass
from typing import Optional

from temporalio.client import Client

from temporal_agents.activities.tickets import store_ticket
from temporal_agents.intent_config import Intent, Planning, ParsedIntent
from temporal_agents.workflows.feature_workflow import FeatureInput, FeatureWorkflow

TASK_QUEUE = "temporal-agentic-workflow"


@dataclass
class HitlState:
    """HITL state returned from workflow queries.

    Attributes:
        signal_type: Intent type from workflow result (e.g., "duplicate_suggested", "duplicate_resolved")
        response: Human-readable payload message from the signal
        result: Parsed JSON result from workflow
        comments: List of user comments with bot responses
        status: Workflow status string
        log: List of log messages from workflow execution
    """

    signal_type: Optional[str]
    response: Optional[str]
    result: Optional[dict]
    comments: list
    status: str
    log: list[str]


async def get_hitl_state(workflow_id: str, client: Client) -> HitlState:
    """Get HITL state directly from workflow without CommandDispatcher knowledge of workflow_id."""
    handle = client.get_workflow_handle(workflow_id)
    desc = await handle.describe()

    from temporalio.api.enums.v1 import WorkflowExecutionStatus

    _terminal = {
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED,
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_FAILED,
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TERMINATED,
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_TIMED_OUT,
        WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_CANCELED,
    }

    if desc.status in _terminal:
        is_ok = (
            desc.status == WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED
        )
        try:
            final_result = await handle.result() if is_ok else None
        except Exception:
            final_result = None

        result_parsed = None
        if final_result:
            import json

            try:
                result_parsed = (
                    json.loads(final_result)
                    if isinstance(final_result, str)
                    else final_result
                )
            except Exception:
                result_parsed = {"raw": str(final_result)}

        return HitlState(
            signal_type="confirmed" if is_ok else "failed",
            response=result_parsed.get("payload") if result_parsed else None,
            result=result_parsed,
            comments=[],
            status="confirmed" if is_ok else "failed",
            log=[
                "Workflow ukončený — požiadavka potvrdená"
                if is_ok
                else f"Workflow skončil s chybou: {desc.status.name}"
            ],
        )

    result = await handle.query("get_result")
    comments = await handle.query("get_comments")
    status = await handle.query("get_status")

    try:
        log = await handle.query("get_log")
    except Exception:
        log = []

    result_parsed = None
    signal_type = None
    if result:
        import json

        try:
            result_parsed = json.loads(result) if isinstance(result, str) else result
            signal_type = (
                result_parsed.get("intent") if isinstance(result_parsed, dict) else None
            )
        except Exception:
            result_parsed = {"raw": str(result)}

    return HitlState(
        signal_type=signal_type,
        response=result_parsed.get("payload") if result_parsed else None,
        result=result_parsed,
        comments=comments,
        status=status,
        log=log,
    )


async def dispatch_command(parsed: ParsedIntent, client: Client) -> dict:
    """Execute the appropriate action and return a result dict.

    Returns:
        {"type": "dispatched",  "workflow_id": str, "intent": str, "project": str}
        {"type": "todo_saved",  "requirement_id": str, "project": str}

    Raises:
        ValueError: intent=chat must not be dispatched.
    """
    if parsed.intent == Intent.chat:
        raise ValueError(
            f"Intent.{parsed.intent} must not be dispatched — return it to the user."
        )

    if parsed.intent == Intent.new_feature:
        if parsed.planning == Planning.todo:
            ticket = await store_ticket(project=parsed.project or "")
            return {
                "type": "todo_saved",
                "ticket_id": ticket.id,
                "project": ticket.project,
            }

        if parsed.planning == Planning.implementing:
            workflow_id = f"{parsed.intent}-{parsed.project}-{int(time.time() * 1000)}"
            await client.start_workflow(
                FeatureWorkflow.run,
                FeatureInput(project=parsed.project or ""),
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            return {
                "type": "dispatched",
                "workflow_id": workflow_id,
                "intent": parsed.intent.value,
                "project": parsed.project.value if parsed.project else "",
            }

    raise ValueError(
        f"No action defined for intent='{parsed.intent}', planning='{parsed.planning}'."
    )
