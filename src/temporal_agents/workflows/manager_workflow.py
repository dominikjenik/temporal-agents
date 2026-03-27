"""ManagerWorkflow — intent-based orchestrator.

Flow:
  1. parse_intent_activity(user_message) -> {intent: "project_status" | ...}
  2. Route by intent:
     - project_status -> list_tasks() -> return formatted list
     - unknown        -> return "unknown intent" message
"""
import json
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.agents import parse_intent_activity
    from temporal_agents.activities.hitl_db import Task, list_tasks

INTENT_TIMEOUT = timedelta(seconds=30)
DB_TIMEOUT = timedelta(seconds=10)


@dataclass
class ManagerInput:
    user_message: str


@workflow.defn
class ManagerWorkflow:
    def __init__(self) -> None:
        self._status: str = "pending"
        self._intent: str = ""

    @workflow.run
    async def run(self, input: ManagerInput) -> str:
        # Step 1: Extract intent via LLM
        self._status = "parsing_intent"
        raw = await workflow.execute_activity(
            parse_intent_activity,
            input.user_message,
            start_to_close_timeout=INTENT_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        self._intent = json.loads(raw).get("intent", "unknown")
        workflow.logger.info(f"[Manager] intent={self._intent}")

        # Step 2: Route by intent
        if self._intent == "project_status":
            self._status = "querying_tasks"
            tasks: list[Task] = await workflow.execute_activity(
                list_tasks,
                "pending",
                start_to_close_timeout=DB_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            self._status = "done"
            return _format_tasks(tasks)

        self._status = "done"
        return f"Unknown intent: '{self._intent}'. Supported: project_status."

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def get_intent(self) -> str:
        return self._intent


def _format_tasks(tasks: list[Task]) -> str:
    if not tasks:
        return "Žiadne úlohy."
    lines = []
    current_project = None
    for t in tasks:
        if t.project != current_project:
            current_project = t.project
            lines.append(f"\n{t.project}:")
        lines.append(f"  [{t.priority}] {t.title}  ({t.status})")
    return "\n".join(lines).strip()
