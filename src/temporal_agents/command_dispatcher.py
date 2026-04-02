"""CommandDispatcher — routes ParsedIntent to the correct Temporal workflow and executes it.

Receives all non-chat ParsedIntent objects from IntentResolver.
Raw user messages and chat history must never reach this module.
"""

import time

from temporalio.client import Client

from temporal_agents.activities.hitl_db import store_requirement
from temporal_agents.intent_config import Intent, Planning, ParsedIntent
from temporal_agents.workflows.feature_workflow import FeatureInput, FeatureWorkflow

TASK_QUEUE = "temporal-agentic-workflow"


async def dispatch_command(parsed: ParsedIntent, client: Client) -> dict:
    """Execute the appropriate action and return a result dict.

    Returns:
        {"type": "dispatched",  "workflow_id": str, "intent": str, "project": str}
        {"type": "todo_saved",  "requirement_id": str, "project": str}

    Raises:
        ValueError: intent=chat or intent=query must not be dispatched.
    """
    if parsed.intent == Intent.chat or parsed.intent == Intent.query:
        raise ValueError(
            f"Intent.{parsed.intent} must not be dispatched — return it to the user."
        )

    if parsed.intent == Intent.new_feature:
        if parsed.planning == Planning.todo:
            req = await store_requirement(project=parsed.project or "")
            return {
                "type": "todo_saved",
                "requirement_id": req.id,
                "project": req.project,
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
