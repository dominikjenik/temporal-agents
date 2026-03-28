"""CommandDispatcher — routes parsed intent to the correct operation and manages its lifecycle (start, signal, query, status).

Flow:
  1. Receives pre-parsed {intent, project, user_message} from IntentParser
  2. Switch on intent:
     - new_feature  -> project manager HITL mock (duplicate check, confirm/comment signals)
     - new_project  -> (not yet implemented)
     - unknown      -> capture_lesson, return error
"""
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.hitl_db import store_task, update_task_status
    from temporal_agents.activities.lesson import capture_lesson

_DUPLICATE_PAYLOAD = (
    "Táto požiadavka je pravdepodobne duplikát alebo v konflikte s existujúcimi úlohami. "
    "Prosím potvrďte alebo okomentujte."
)

DB_TIMEOUT = timedelta(seconds=10)
RETRY_ONCE = RetryPolicy(maximum_attempts=1)


@dataclass
class CommandInput:
    intent: str
    project: str
    user_message: str


@workflow.defn
class CommandDispatcher:
    """Routes parsed intent to the correct operation and manages its lifecycle (start, signal, query, status)."""

    def __init__(self) -> None:
        self._status: str = "pending"
        self._intent: str = ""
        self._confirmed: bool = False
        self._pending_comment: Optional[str] = None
        self._comments: list = []
        self._log: list[str] = []

    @workflow.run
    async def run(self, input: CommandInput) -> str:
        self._intent = input.intent
        workflow.logger.info(f"[Dispatcher] intent={input.intent} project={input.project}")

        if input.intent == "new_feature":
            return await self._handle_new_feature(input.project, input.user_message)

        if input.intent == "new_project":
            # TODO: start new project setup workflow
            self._status = "done"
            return json.dumps({"intent": "new_project", "project": input.project, "status": "not_implemented"})

        self._status = "done"
        # TODO
        # await workflow.execute_activity(
        #     capture_lesson,
        #     args=[
        #         workflow.info().workflow_id,
        #         "dispatcher",
        #         "failure",
        #         f"Unknown intent '{input.intent}' for project '{input.project}': '{input.user_message[:100]}'.",
        #     ],
        #     start_to_close_timeout=DB_TIMEOUT,
        #     retry_policy=RETRY_ONCE,
        # )
        return f"Unknown intent: '{input.intent}'. Supported: new_feature, new_project."

    async def _handle_new_feature(self, project: str, user_message: str) -> str:
        """Projektaka HITL mock — checks for duplicates, waits for user confirm/comment."""
        wf_id = workflow.info().workflow_id
        self._status = "waiting_hitl"
        self._log.append(f"Požiadavka prijatá [{project}]: {user_message[:120]}")
        self._log.append("Posúdenie: pravdepodobná duplicita s existujúcimi úlohami")

        await workflow.execute_activity(
            store_task,
            args=[project, f"[DUPLICATE] {user_message}", 1, "hitl", wf_id],
            start_to_close_timeout=DB_TIMEOUT,
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
            start_to_close_timeout=DB_TIMEOUT,
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
