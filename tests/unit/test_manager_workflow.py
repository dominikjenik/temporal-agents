"""Tests for ManagerWorkflow intent-based routing.

Test 1: _extract_intent — pure function, LLM output parsing.
Test 2: ManagerWorkflow routing — project_status → list_tasks → formatted output.
Test 3: ManagerWorkflow unknown intent → capture_lesson called.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal_agents.activities.agents import _extract_intent
from temporal_agents.activities.hitl_db import Task
from temporal_agents.workflows.manager_workflow import ManagerInput, ManagerWorkflow, _format_tasks

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_SAMPLE_TASKS = [
    Task(id=uuid.uuid4(), project="zbornik", title="Fix PDF viewer crash",
         priority=1, status="pending", created_at=_NOW.isoformat()),
    Task(id=uuid.uuid4(), project="zbornik", title="Update splash screen",
         priority=3, status="pending", created_at=_NOW.isoformat()),
    Task(id=uuid.uuid4(), project="ginidocs", title="Add auth endpoint",
         priority=2, status="pending", created_at=_NOW.isoformat()),
]


# ---------------------------------------------------------------------------
# Test 1: _extract_intent — pure function, no Temporal context needed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("llm_response,expected_intent", [
    ('{"intent": "project_status"}', "project_status"),
    ('```json\n{"intent": "project_status"}\n```', "project_status"),
    ('{"intent": "unknown"}', "unknown"),
    ("some garbage output", "unknown"),
    ('Sure! {"intent": "project_status"} here you go', "project_status"),
])
def test_extract_intent_parses_llm_output(llm_response: str, expected_intent: str):
    """_extract_intent must correctly parse clean JSON, markdown-fenced JSON, and garbage."""
    result = _extract_intent(llm_response)
    assert json.loads(result)["intent"] == expected_intent


# ---------------------------------------------------------------------------
# Test 2: ManagerWorkflow routing — project_status → list_tasks → formatted output
# ---------------------------------------------------------------------------

async def test_project_status_queries_db_and_formats():
    """ManagerWorkflow with project_status intent must call list_tasks and return formatted output."""
    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="parse_intent_activity")
        async def mock_parse_intent(msg: str) -> str:
            return json.dumps({"intent": "project_status"})

        @activity.defn(name="list_tasks")
        async def mock_list_tasks(status: str) -> list[Task]:
            return _SAMPLE_TASKS

        async with Worker(
            env.client,
            task_queue="test-db",
            workflows=[ManagerWorkflow],
            activities=[mock_parse_intent, mock_list_tasks],
        ):
            result = await env.client.execute_workflow(
                ManagerWorkflow.run,
                ManagerInput(user_message="co na praci"),
                id="test-manager-project-status",
                task_queue="test-db",
            )

        assert "zbornik" in result
        assert "ginidocs" in result
        assert "Fix PDF viewer crash" in result
        assert "Add auth endpoint" in result


# ---------------------------------------------------------------------------
# Unit tests for _format_tasks (no Temporal needed)
# ---------------------------------------------------------------------------

async def test_format_tasks_groups_by_project():
    output = _format_tasks(_SAMPLE_TASKS)
    zbornik_pos = output.index("zbornik")
    ginidocs_pos = output.index("ginidocs")
    assert zbornik_pos < ginidocs_pos
    assert "Fix PDF viewer crash" in output
    assert "Update splash screen" in output


async def test_format_tasks_empty():
    assert _format_tasks([]) == "Žiadne úlohy."


# ---------------------------------------------------------------------------
# Test 3: unknown intent → capture_lesson
# ---------------------------------------------------------------------------

async def test_unknown_intent_triggers_capture_lesson():
    """ManagerWorkflow calls capture_lesson when intent cannot be resolved."""
    lesson_calls: list = []

    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="parse_intent_activity")
        async def mock_parse_intent(msg: str) -> str:
            return json.dumps({"intent": "unknown"})

        @activity.defn(name="capture_lesson")
        async def mock_capture_lesson(
            workflow_id: str, agent_type: str, outcome: str, lesson_text: str
        ) -> None:
            lesson_calls.append({"agent_type": agent_type, "outcome": outcome})

        async with Worker(
            env.client,
            task_queue="test-manager-lesson",
            workflows=[ManagerWorkflow],
            activities=[mock_parse_intent, mock_capture_lesson],
        ):
            result = await env.client.execute_workflow(
                ManagerWorkflow.run,
                ManagerInput(user_message="xyzzy gibberish"),
                id="test-manager-unknown-intent",
                task_queue="test-manager-lesson",
            )

    assert "unknown" in result.lower()
    assert len(lesson_calls) == 1
    assert lesson_calls[0]["agent_type"] == "manager"
    assert lesson_calls[0]["outcome"] == "failure"
