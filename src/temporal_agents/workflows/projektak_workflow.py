"""ProjectakWorkflow — handles new_feature requests with HITL.

Flow:
  1. Store HITL task in DB (type='hitl', status='pending')
  2. Expose result JSON {intent: "duplicate", payload: "..."} via get_result query
  3. Loop: wait for confirm or comment signals
     - comment → append to conversation history, continue waiting
     - confirm → update task status to 'confirmed', return result JSON
"""
import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.hitl_db import store_task, update_task_status

_DUPLICATE_PAYLOAD = (
    "Táto požiadavka je pravdepodobne duplikát alebo v konflikte s existujúcimi úlohami. "
    "Prosím potvrďte alebo okomentujte."
)


@dataclass
class ProjectakInput:
    user_message: str


@workflow.defn
class ProjectakWorkflow:
    def __init__(self) -> None:
        self._confirmed = False
        self._pending_comment: Optional[str] = None
        self._comments: list = []

    @workflow.run
    async def run(self, input: ProjectakInput) -> str:
        wf_id = workflow.info().workflow_id
        await workflow.execute_activity(
            store_task,
            args=["manager", f"[DUPLICATE] {input.user_message}", 1, "hitl", wf_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        while not self._confirmed:
            await workflow.wait_condition(
                lambda: self._confirmed or self._pending_comment is not None
            )
            if self._pending_comment is not None:
                comment = self._pending_comment
                self._pending_comment = None
                self._comments.append({
                    "user": comment,
                    "bot": "Komentár zaznamenaný. Požiadavku prehodnotím a dám vám vedieť.",
                })
        await workflow.execute_activity(
            update_task_status,
            args=[wf_id, "confirmed"],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return json.dumps({"intent": "duplicate", "payload": _DUPLICATE_PAYLOAD})

    @workflow.signal
    def confirm(self) -> None:
        self._confirmed = True

    @workflow.signal
    def comment(self, text: str) -> None:
        self._pending_comment = text

    @workflow.query
    def get_status(self) -> str:
        return "confirmed" if self._confirmed else "waiting_hitl"

    @workflow.query
    def get_result(self) -> str:
        return json.dumps({"intent": "duplicate", "payload": _DUPLICATE_PAYLOAD})

    @workflow.query
    def get_comments(self) -> list:
        return self._comments
