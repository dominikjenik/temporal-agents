"""BaseWorkflow — intent router + inline HITL for new_feature.

Flow:
  1. parse_intent_activity(user_message) -> {intent: ...}
  2. Route:
     - project_status -> list_tasks() -> return formatted list
     - new_feature    -> store HITL task, wait for confirm/comment signals, return result
     - unknown        -> capture_lesson, return error
"""
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.agents import parse_intent_activity
    from temporal_agents.activities.hitl_db import Task, list_tasks, store_task, update_task_status
    from temporal_agents.activities.lesson import capture_lesson

_DUPLICATE_PAYLOAD = (
    "Táto požiadavka je pravdepodobne duplikát alebo v konflikte s existujúcimi úlohami. "
    "Prosím potvrďte alebo okomentujte."
)

INTENT_TIMEOUT = timedelta(seconds=60)
DB_TIMEOUT = timedelta(seconds=10)
RETRY_ONCE = RetryPolicy(maximum_attempts=1)


@dataclass
class BaseInput:
    user_message: str


@workflow.defn
class BaseWorkflow:
    def __init__(self) -> None:
        self._status: str = "pending"
        self._intent: str = ""
        self._confirmed: bool = False
        self._pending_comment: Optional[str] = None
        self._comments: list = []
        self._log: list[str] = []

    @workflow.run
    async def run(self, input: BaseInput) -> str:
        self._status = "parsing_intent"
        raw = await workflow.execute_activity(
            parse_intent_activity,
            input.user_message,
            start_to_close_timeout=INTENT_TIMEOUT,
            retry_policy=RETRY_ONCE,
        )
        self._intent = json.loads(raw).get("intent", "unknown")
        workflow.logger.info(f"[Manager] intent={self._intent}")

        if self._intent == "project_status":
            self._status = "querying_tasks"
            tasks: list[Task] = await workflow.execute_activity(
                list_tasks,
                "pending",
                start_to_close_timeout=DB_TIMEOUT,
                retry_policy=RETRY_ONCE,
            )
            self._status = "done"
            return _format_tasks(tasks)

        if self._intent == "new_feature":
            return await self._handle_new_feature(input.user_message)

        self._status = "done"
        await workflow.execute_activity(
            capture_lesson,
            args=[
                workflow.info().workflow_id,
                "manager",
                "failure",
                f"parse_intent returned 'unknown' for: '{input.user_message[:100]}'.",
            ],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RETRY_ONCE,
        )
        return f"Unknown intent: '{self._intent}'. Supported: project_status, new_feature."

    async def _handle_new_feature(self, user_message: str) -> str:
        wf_id = workflow.info().workflow_id
        self._status = "waiting_hitl"
        self._log.append(f"Požiadavka prijatá: {user_message[:120]}")
        self._log.append("Posúdenie: pravdepodobná duplicita s existujúcimi úlohami")

        await workflow.execute_activity(
            store_task,
            args=["manager", f"[DUPLICATE] {user_message}", 1, "hitl", wf_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RETRY_ONCE,
        )
        self._log.append("HITL úloha zapísaná do databázy — čakám na potvrdenie")

        while not self._confirmed:
            await workflow.wait_condition(
                lambda: self._confirmed or self._pending_comment is not None
            )
            if self._pending_comment is not None:
                comment = self._pending_comment
                self._pending_comment = None
                self._log.append(f"Komentár prijatý: {comment[:80]}")
                self._comments.append({
                    "user": comment,
                    "bot": "Komentár zaznamenaný. Požiadavku prehodnotím a dám vám vedieť.",
                })
                self._log.append("Komentár spracovaný")

        self._log.append("Potvrdenie prijaté — workflow sa ukončuje")
        await workflow.execute_activity(
            update_task_status,
            args=[wf_id, "confirmed"],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RETRY_ONCE,
        )
        self._status = "done"
        return json.dumps({"intent": "duplicate_resolved", "payload": _DUPLICATE_PAYLOAD})

    # --- Signals ---

    @workflow.signal
    def confirm(self) -> None:
        self._confirmed = True

    @workflow.signal
    def comment(self, text: str) -> None:
        self._pending_comment = text

    # --- Queries ---

    @workflow.query
    def get_status(self) -> str:
        return self._status

    @workflow.query
    def get_intent(self) -> str:
        return self._intent

    @workflow.query
    def get_result(self) -> str:
        if self._confirmed:
            return json.dumps({"intent": "duplicate_resolved", "payload": _DUPLICATE_PAYLOAD})
        return json.dumps({"intent": "duplicate_suggested", "payload": _DUPLICATE_PAYLOAD})

    @workflow.query
    def get_comments(self) -> list:
        return self._comments

    @workflow.query
    def get_log(self) -> list[str]:
        return self._log


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
