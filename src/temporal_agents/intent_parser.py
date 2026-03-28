"""IntentParser — accepts user messages via signals and resolves them to structured intent via LLM.

Iterates with the user until intent + project are unambiguously identified.

Signals:  user_prompt(str), end_chat()
Queries:  get_conversation_history()
"""
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.activities.agents import parse_intent_activity
    from temporal_agents.intent_config import INTENTS, PROJECTS


def _validate(raw: str) -> tuple[bool, dict]:
    """Returns (is_valid, parsed_dict). Valid = intent in INTENTS and project in PROJECTS."""
    try:
        data = json.loads(raw)
        ok = data.get("intent") in INTENTS and data.get("project") in PROJECTS
        return ok, data
    except (json.JSONDecodeError, TypeError):
        return False, {}


def _clarification_message(data: dict) -> str:
    """Generate clarification question based on what's missing."""
    missing = []
    if data.get("intent") not in INTENTS:
        missing.append(f"zámer (možnosti: {', '.join(INTENTS)})")
    if data.get("project") not in PROJECTS:
        missing.append(f"projekt (možnosti: {', '.join(PROJECTS)})")
    return f"Nepodarilo sa určiť {' a '.join(missing)}. Môžeš to upresniť?"


@workflow.defn
class IntentParser:
    """Accepts user messages via signals and resolves them to structured intent via LLM."""

    def __init__(self) -> None:
        self._messages: List[Dict[str, Any]] = []
        self._pending: List[str] = []
        self._ended: bool = False
        self._result: Optional[str] = None

    @workflow.run
    async def run(self, initial_prompt: str = "") -> str:
        if initial_prompt:
            self._pending.append(initial_prompt)

        while not self._ended:
            await workflow.wait_condition(
                lambda: bool(self._pending) or self._ended
            )

            while self._pending and not self._ended:
                prompt = self._pending.pop(0)
                self._messages.append({
                    "actor": "user",
                    "response": {"response": prompt, "next": "question"},
                })

                raw = await workflow.execute_activity(
                    parse_intent_activity,
                    prompt,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                valid, data = _validate(raw)

                if valid:
                    self._result = raw
                    self._ended = True
                    self._messages.append({
                        "actor": "agent",
                        "response": {"response": raw, "next": "done"},
                    })
                    return raw

                clarification = _clarification_message(data)
                self._messages.append({
                    "actor": "agent",
                    "response": {"response": clarification, "next": "question"},
                })

        return self._result or json.dumps(
            {"intent": "unknown", "project": "unknown", "confidence": 0}
        )

    @workflow.signal
    async def user_prompt(self, prompt: str) -> None:
        self._pending.append(prompt)

    @workflow.signal
    async def end_chat(self) -> None:
        self._ended = True

    @workflow.query
    def get_conversation_history(self) -> Dict[str, List]:
        return {"messages": list(self._messages)}
