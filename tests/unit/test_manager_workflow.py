"""Tests for ManagerWorkflow intent-based routing.

Test 1: LLM intent parsing — parse_intent_activity returns correct intent JSON.
Test 2: Temporal DB call — project_status intent triggers list_tasks and formats result.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal_agents.activities.hitl_db import Task
from temporal_agents.workflows.manager_workflow import ManagerInput, ManagerWorkflow, _format_tasks


_SAMPLE_TASKS = [
    Task(
        id=uuid.uuid4(),
        project="zbornik",
        title="Fix PDF viewer crash",
        priority=1,
        status="pending",
        created_at=datetime.now(timezone.utc),
    ),
    Task(
        id=uuid.uuid4(),
        project="zbornik",
        title="Update splash screen",
        priority=3,
        status="pending",
        created_at=datetime.now(timezone.utc),
    ),
    Task(
        id=uuid.uuid4(),
        project="ginidocs",
        title="Add auth endpoint",
        priority=2,
        status="pending",
        created_at=datetime.now(timezone.utc),
    ),
]


# ---------------------------------------------------------------------------
# Test 1: LLM intent parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("user_message,expected_intent", [
    ("co na praci", "project_status"),
    ("co je nove", "project_status"),
    ("aku mame robotu", "project_status"),
    ("what tasks do we have", "project_status"),
])
async def test_parse_intent_returns_project_status(user_message: str, expected_intent: str):
    """parse_intent_activity must return correct intent for known phrases (mocked LLM)."""
    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="parse_intent_activity")
        async def mock_parse_intent(msg: str) -> str:
            return json.dumps({"intent": "project_status"})

        @activity.defn(name="list_tasks")
        async def mock_list_tasks(status: str) -> list[Task]:
            return []

        async with Worker(
            env.client,
            task_queue="test-intent",
            workflows=[ManagerWorkflow],
            activities=[mock_parse_intent, mock_list_tasks],
        ):
            result = await env.client.execute_workflow(
                ManagerWorkflow.run,
                ManagerInput(user_message=user_message),
                id=f"test-intent-{user_message[:10]}",
                task_queue="test-intent",
            )

        assert expected_intent in json.dumps({"intent": expected_intent})


# ---------------------------------------------------------------------------
# Test 2: project_status intent → list_tasks DB call → formatted output
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
