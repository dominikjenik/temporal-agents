"""FeatureWorkflow — project manager HITL handler for new_feature requests.

Stores the request as a potential duplicate, then waits for human confirm/comment signals.

Signals:  confirm(), comment(str)
Queries:  get_status(), get_result(), get_comments(), get_log()
"""

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.tasks import store_task, update_task_status

_DUPLICATE_PAYLOAD = (
    "Táto požiadavka je pravdepodobne duplikát alebo v konflikte s existujúcimi úlohami. "
    "Prosím potvrďte alebo okomentujte."
)

DB_TIMEOUT = timedelta(seconds=10)
RETRY_ONCE = RetryPolicy(maximum_attempts=1)


@dataclass
class FeatureInput:
    project: str
    user_message: str = ""


@workflow.defn
class FeatureWorkflow:
    """Project manager HITL handler for new_feature requests."""

    def __init__(self) -> None:
        self._confirmed: bool = False
        self._pending_comment: Optional[str] = None
        self._comments: list = []
        self._log: list[str] = []

    @workflow.run
    async def run(self, input: FeatureInput) -> str:
        wf_id = workflow.info().workflow_id
        self._log.append(
            f"Požiadavka prijatá [{input.project}]: {input.user_message[:120]}"
        )
        self._log.append("Posúdenie: pravdepodobná duplicita s existujúcimi úlohami")

        await workflow.execute_activity(
            store_task,
            args=[input.project, f"[DUPLICATE] {input.user_message}", 1, "hitl", wf_id],
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
                self._comments.append(
                    {
                        "user": comment,
                        "bot": "Komentár zaznamenaný. Požiadavku prehodnotím a dám vám vedieť.",
                    }
                )
                self._log.append("Komentár spracovaný")

        self._log.append("Potvrdenie prijaté — workflow sa ukončuje")
        await workflow.execute_activity(
            update_task_status,
            args=[wf_id, "done"],
            start_to_close_timeout=DB_TIMEOUT,
            retry_policy=RETRY_ONCE,
        )
        return json.dumps(
            {"intent": "duplicate_resolved", "payload": _DUPLICATE_PAYLOAD}
        )

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
        if self._pending_comment is not None:
            return "hitl_comment"
        if self._confirmed:
            return "confirmed"
        return "hitl"

    @workflow.query
    def get_result(self) -> str:
        if self._confirmed:
            return json.dumps(
                {"intent": "duplicate_resolved", "payload": _DUPLICATE_PAYLOAD}
            )
        return json.dumps(
            {"intent": "duplicate_suggested", "payload": _DUPLICATE_PAYLOAD}
        )

    @workflow.query
    def get_comments(self) -> list:
        return self._comments

    @workflow.query
    def get_log(self) -> list[str]:
        return self._log
