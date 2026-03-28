"""Tests for CommandDispatcher — intent routing and inline HITL.

Test 1: project_status intent → list_tasks → formatted output.
Test 2: unknown intent → capture_lesson called.
Test 3: _format_tasks groups by project.
Test 4: _format_tasks empty list.
"""
import json
import uuid
from datetime import datetime, timezone

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal_agents.activities.hitl_db import Task
from temporal_agents.command_dispatcher import CommandInput, CommandDispatcher, _format_tasks

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
# Test 1: project_status → list_tasks → formatted output
# ---------------------------------------------------------------------------

async def test_project_status_queries_db_and_formats():
    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="parse_intent_activity")
        async def mock_parse_intent(msg: str) -> str:
            return json.dumps({"intent": "project_status"})

        @activity.defn(name="list_tasks")
        async def mock_list_tasks(status: str) -> list[Task]:
            return _SAMPLE_TASKS

        async with Worker(
            env.client, task_queue="test-base-1",
            workflows=[CommandDispatcher],
            activities=[mock_parse_intent, mock_list_tasks],
        ):
            result = await env.client.execute_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="co na praci"),
                id="test-base-project-status", task_queue="test-base-1",
            )

    assert "zbornik" in result
    assert "ginidocs" in result
    assert "Fix PDF viewer crash" in result
    assert "Add auth endpoint" in result


# ---------------------------------------------------------------------------
# Test 2: unknown intent → capture_lesson
# ---------------------------------------------------------------------------

async def test_unknown_intent_triggers_capture_lesson():
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
            env.client, task_queue="test-base-2",
            workflows=[CommandDispatcher],
            activities=[mock_parse_intent, mock_capture_lesson],
        ):
            result = await env.client.execute_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="xyzzy gibberish"),
                id="test-base-unknown-intent", task_queue="test-base-2",
            )

    assert "unknown" in result.lower()
    assert len(lesson_calls) == 1
    assert lesson_calls[0]["agent_type"] == "manager"
    assert lesson_calls[0]["outcome"] == "failure"


# ---------------------------------------------------------------------------
# Unit tests for _format_tasks
# ---------------------------------------------------------------------------

async def test_format_tasks_groups_by_project():
    output = _format_tasks(_SAMPLE_TASKS)
    assert output.index("zbornik") < output.index("ginidocs")
    assert "Fix PDF viewer crash" in output
    assert "Update splash screen" in output


async def test_format_tasks_empty():
    assert _format_tasks([]) == "Žiadne úlohy."
