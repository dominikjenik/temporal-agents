"""ClaudeChatWorkflow — simple chat via claude -p subprocess.

Signals:  user_prompt(str), end_chat()
Queries:  get_conversation_history()
"""
from collections import deque
from datetime import timedelta
from typing import Any, Deque, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.agents import run_claude_chat_activity


@workflow.defn
class ClaudeChatWorkflow:
    def __init__(self) -> None:
        self._messages: List[Dict[str, Any]] = []
        self._queue: Deque[str] = deque()
        self._ended: bool = False

    @workflow.run
    async def run(self, initial_prompt: str = "") -> str:
        if initial_prompt:
            self._queue.append(initial_prompt)

        while not self._ended:
            await workflow.wait_condition(
                lambda: bool(self._queue) or self._ended
            )

            while self._queue:
                prompt = self._queue.popleft()
                self._messages.append({
                    "actor": "user",
                    "response": {"response": prompt, "next": "question"},
                })

                response = await workflow.execute_activity(
                    run_claude_chat_activity,
                    prompt,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                self._messages.append({
                    "actor": "agent",
                    "response": {"response": response, "next": "question"},
                })

        if self._messages and self._messages[-1]["actor"] == "agent":
            self._messages[-1]["response"]["next"] = "done"

        return "Chat ended"

    @workflow.signal
    async def user_prompt(self, prompt: str) -> None:
        self._queue.append(prompt)

    @workflow.signal
    async def end_chat(self) -> None:
        self._ended = True

    @workflow.query
    def get_conversation_history(self) -> Dict[str, List]:
        return {"messages": list(self._messages)}
