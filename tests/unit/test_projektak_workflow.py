"""Tests for CommandDispatcher — intent routing and inline HITL.

Test 1: new_feature intent → HITL → confirm → returns {intent: "duplicate_resolved"} JSON.
Test 2: new_feature → stores type='hitl' task, updates status to 'confirmed' after confirm signal.
Test 3: new_feature → comment signal appended, confirm still resolves.
Test 4: project_status intent → returns formatted task list, no HITL.
Test 5: End-to-end — real user message → Manager → HITL waiting state.
Test 6: get_log exposes key execution steps.
Test 7: intent progresses: duplicate_suggested (running) → duplicate_resolved (after confirm).
"""
import json
import uuid
from typing import Optional

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import asyncio

from temporal_agents.activities.hitl_db import Task
from temporal_agents.workflows.command_dispatcher import CommandInput, CommandDispatcher


async def _poll_query(handle, query_name: str, condition, timeout: float = 5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            result = await handle.query(query_name)
            if condition(result):
                return result
        except Exception:
            pass
        await asyncio.sleep(0.05)
    raise TimeoutError(f"Query '{query_name}' condition not met within {timeout}s")


# ---------------------------------------------------------------------------
# Shared mock activities
# ---------------------------------------------------------------------------

def _make_parse_intent_mock(intent: str = "new_feature"):
    @activity.defn(name="parse_intent_activity")
    async def mock_parse_intent(msg: str) -> str:
        return json.dumps({"intent": intent})
    return mock_parse_intent


def _make_store_task_mock(calls: list):
    @activity.defn(name="store_task")
    async def mock_store_task(
        project: str, title: str, priority: int = 5,
        type: str = "task", workflow_id: Optional[str] = None,
    ) -> Task:
        calls.append({"project": project, "title": title, "type": type, "workflow_id": workflow_id})
        return Task(
            id=uuid.uuid4(), project=project, title=title,
            priority=priority, status="pending", type=type,
            workflow_id=workflow_id, created_at="2026-01-01T00:00:00+00:00",
        )
    return mock_store_task


def _make_update_status_mock(calls: list):
    @activity.defn(name="update_task_status")
    async def mock_update_task_status(workflow_id: str, status: str) -> None:
        calls.append({"workflow_id": workflow_id, "status": status})
    return mock_update_task_status


def _make_list_tasks_mock(tasks: list):
    @activity.defn(name="list_tasks")
    async def mock_list_tasks(status: str) -> list:
        return tasks
    return mock_list_tasks


def _make_capture_lesson_mock():
    @activity.defn(name="capture_lesson")
    async def mock_capture_lesson(workflow_id: str, agent_type: str, outcome: str, lesson_text: str) -> None:
        pass
    return mock_capture_lesson


# ---------------------------------------------------------------------------
# Test 1: confirm → returns duplicate_resolved JSON
# ---------------------------------------------------------------------------

async def test_new_feature_confirm_returns_duplicate_resolved():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-1",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("new_feature"),
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="Add dark mode"),
                id="test-1", task_queue="test-1",
            )
            await handle.signal("confirm")
            result = await handle.result()

    data = json.loads(result)
    assert data["intent"] == "duplicate_resolved"
    assert "payload" in data


# ---------------------------------------------------------------------------
# Test 2: stores HITL task, updates status to confirmed
# ---------------------------------------------------------------------------

async def test_new_feature_stores_hitl_and_updates_status():
    store_calls, update_calls = [], []
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-2",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("new_feature"),
                _make_store_task_mock(store_calls),
                _make_update_status_mock(update_calls),
            ],
        ):
            handle = await env.client.start_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="Add dark mode"),
                id="test-2", task_queue="test-2",
            )
            await handle.signal("confirm")
            await handle.result()

    assert len(store_calls) == 1
    assert store_calls[0]["type"] == "hitl"
    assert "DUPLICATE" in store_calls[0]["title"]
    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Test 3: comment then confirm
# ---------------------------------------------------------------------------

async def test_new_feature_handles_comment_then_confirm():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-3",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("new_feature"),
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="Add dark mode"),
                id="test-3", task_queue="test-3",
            )
            await handle.signal("comment", "Toto nie je duplikát.")
            comments = await _poll_query(handle, "get_comments", lambda c: len(c) == 1)
            await handle.signal("confirm")
            result = await handle.result()

    data = json.loads(result)
    assert data["intent"] == "duplicate_resolved"
    assert len(comments) == 1
    assert comments[0]["user"] == "Toto nie je duplikát."
    assert "bot" in comments[0]


# ---------------------------------------------------------------------------
# Test 4: project_status → returns task list, no HITL
# ---------------------------------------------------------------------------

async def test_project_status_returns_task_list():
    from temporal_agents.activities.hitl_db import Task
    tasks = [
        Task(id=uuid.uuid4(), project="temporal", title="Fix bug", priority=1,
             status="pending", type="task", workflow_id=None, created_at="2026-01-01T00:00:00+00:00"),
    ]
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-4",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("project_status"),
                _make_list_tasks_mock(tasks),
            ],
        ):
            result = await env.client.execute_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="co na praci"),
                id="test-4", task_queue="test-4",
            )

    assert "Fix bug" in result
    assert "temporal" in result


# ---------------------------------------------------------------------------
# Test 5: end-to-end — new feature → HITL waiting state
# ---------------------------------------------------------------------------

async def test_new_feature_full_pipeline():
    store_calls = []
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-5",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("new_feature"),
                _make_store_task_mock(store_calls),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="nova feature temporal projektu - pridaj UI button"),
                id="test-5", task_queue="test-5",
            )
            status = await _poll_query(handle, "get_status", lambda s: s == "waiting_hitl")

    assert status == "waiting_hitl"
    assert len(store_calls) == 1
    assert store_calls[0]["type"] == "hitl"
    assert "nova feature temporal projektu" in store_calls[0]["title"]


# ---------------------------------------------------------------------------
# Test 6: get_log exposes key steps
# ---------------------------------------------------------------------------

async def test_log_contains_key_steps():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-6",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("new_feature"),
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="Add dark mode to the app"),
                id="test-6", task_queue="test-6",
            )
            log_before = await _poll_query(handle, "get_log", lambda l: len(l) >= 3)
            await handle.signal("confirm")
            await handle.result()
            log_after = await handle.query("get_log")

    assert any("Add dark mode" in e for e in log_before)
    assert any("duplicit" in e.lower() for e in log_before)
    assert any("databázy" in e for e in log_before)
    assert any("Potvrdenie" in e for e in log_after)


# ---------------------------------------------------------------------------
# Test 7: intent two-phase: duplicate_suggested → duplicate_resolved
# ---------------------------------------------------------------------------

async def test_intent_two_phase():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-7",
            workflows=[CommandDispatcher],
            activities=[
                _make_parse_intent_mock("new_feature"),
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                CommandDispatcher.run,
                CommandInput(user_message="Add search feature"),
                id="test-7", task_queue="test-7",
            )
            suggested = await _poll_query(
                handle, "get_result",
                lambda r: json.loads(r).get("intent") == "duplicate_suggested",
            )
            assert json.loads(suggested)["intent"] == "duplicate_suggested"

            await handle.signal("confirm")
            result = await handle.result()

    data = json.loads(result)
    assert data["intent"] == "duplicate_resolved"
    assert data["intent"] != "resolved_as_duplicate"
