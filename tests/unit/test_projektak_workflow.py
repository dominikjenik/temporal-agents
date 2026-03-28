"""Tests for ProjectakWorkflow and ManagerWorkflow new_feature routing.

Test 1: ProjectakWorkflow resolves on confirm — returns {intent: "duplicate", payload: ...} JSON.
Test 2: ProjectakWorkflow stores HITL task and updates status to 'confirmed'.
Test 3: ProjectakWorkflow handles comment signal then resolves on confirm.
Test 4: ManagerWorkflow routes new_feature intent → starts ProjectakWorkflow child.
Test 5: End-to-end — real user message → Manager → Projektak HITL waiting state.
"""
import json
import uuid
from typing import Optional

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import asyncio

from temporal_agents.activities.hitl_db import Task
from temporal_agents.workflows.manager_workflow import ManagerInput, ManagerWorkflow
from temporal_agents.workflows.projektak_workflow import ProjectakInput, ProjectakWorkflow


async def _poll_query(handle, query_name: str, condition, timeout: float = 5.0):
    """Poll a workflow query until condition is met or timeout (seconds)."""
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
# Helpers — shared mock activities
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Test 1: confirm → returns duplicate JSON
# ---------------------------------------------------------------------------

async def test_projektak_confirm_returns_duplicate_json():
    """Confirm signal → result is JSON {intent: 'duplicate', payload: '...'}."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-projektak-1",
            workflows=[ProjectakWorkflow],
            activities=[
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                ProjectakWorkflow.run,
                ProjectakInput(user_message="Add dark mode"),
                id="test-projektak-json",
                task_queue="test-projektak-1",
            )
            await handle.signal("confirm")
            result = await handle.result()

    data = json.loads(result)
    assert data["intent"] == "duplicate"
    assert "payload" in data
    assert len(data["payload"]) > 0


# ---------------------------------------------------------------------------
# Test 2: stores HITL and updates status
# ---------------------------------------------------------------------------

async def test_projektak_stores_hitl_and_updates_status():
    """ProjectakWorkflow stores type='hitl' task and marks it 'confirmed' after signal."""
    store_calls: list = []
    update_calls: list = []

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-projektak-2",
            workflows=[ProjectakWorkflow],
            activities=[
                _make_store_task_mock(store_calls),
                _make_update_status_mock(update_calls),
            ],
        ):
            handle = await env.client.start_workflow(
                ProjectakWorkflow.run,
                ProjectakInput(user_message="Add dark mode"),
                id="test-projektak-status",
                task_queue="test-projektak-2",
            )
            await handle.signal("confirm")
            await handle.result()

    assert len(store_calls) == 1
    assert store_calls[0]["type"] == "hitl"
    assert "DUPLICATE" in store_calls[0]["title"]

    assert len(update_calls) == 1
    assert update_calls[0]["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Test 3: comment signal appended to history, confirm still resolves
# ---------------------------------------------------------------------------

async def test_projektak_handles_comment_then_confirm():
    """Comment signal is recorded; subsequent confirm still resolves the workflow."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-projektak-3",
            workflows=[ProjectakWorkflow],
            activities=[
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            handle = await env.client.start_workflow(
                ProjectakWorkflow.run,
                ProjectakInput(user_message="Add dark mode"),
                id="test-projektak-comment",
                task_queue="test-projektak-3",
            )
            await handle.signal("comment", "Toto nie je duplikát, je to nová funkcia.")
            comments = await _poll_query(handle, "get_comments", lambda c: len(c) == 1)
            await handle.signal("confirm")
            result = await handle.result()

    data = json.loads(result)
    assert data["intent"] == "duplicate"
    assert len(comments) == 1
    assert comments[0]["user"] == "Toto nie je duplikát, je to nová funkcia."
    assert "bot" in comments[0]


# ---------------------------------------------------------------------------
# Test 4: ManagerWorkflow routes new_feature to ProjectakWorkflow
# ---------------------------------------------------------------------------

async def test_manager_routes_new_feature():
    """ManagerWorkflow with new_feature intent starts ProjectakWorkflow and returns review message."""
    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="parse_intent_activity")
        async def mock_parse_intent(msg: str) -> str:
            return json.dumps({"intent": "new_feature"})

        async with Worker(
            env.client,
            task_queue="test-manager-nf",
            workflows=[ManagerWorkflow, ProjectakWorkflow],
            activities=[
                mock_parse_intent,
                _make_store_task_mock([]),
                _make_update_status_mock([]),
            ],
        ):
            result = await env.client.execute_workflow(
                ManagerWorkflow.run,
                ManagerInput(user_message="Add dark mode"),
                id="test-manager-new-feature",
                task_queue="test-manager-nf",
            )

    assert "projektovému manažérovi" in result


# ---------------------------------------------------------------------------
# Test 5: End-to-end — real user message triggers full pipeline
# ---------------------------------------------------------------------------

async def test_new_feature_message_full_pipeline():
    """'nova feature temporal projektu - pridaj UI button ok' → Manager routes to Projektak → HITL waiting."""
    store_calls: list = []
    manager_wf_id = "test-e2e-new-feature"

    async with await WorkflowEnvironment.start_time_skipping() as env:

        @activity.defn(name="parse_intent_activity")
        async def mock_parse_intent(msg: str) -> str:
            return json.dumps({"intent": "new_feature"})

        async with Worker(
            env.client,
            task_queue="test-e2e",
            workflows=[ManagerWorkflow, ProjectakWorkflow],
            activities=[
                mock_parse_intent,
                _make_store_task_mock(store_calls),
                _make_update_status_mock([]),
            ],
        ):
            manager_result = await env.client.execute_workflow(
                ManagerWorkflow.run,
                ManagerInput(user_message="nova feature temporal projektu - pridaj UI button ok"),
                id=manager_wf_id,
                task_queue="test-e2e",
            )

            child_id = f"projektak-{manager_wf_id}"
            child_handle = env.client.get_workflow_handle(child_id)
            child_status = await _poll_query(child_handle, "get_status", lambda s: s == "waiting_hitl")

    assert manager_result == "Požiadavka odoslaná projektovému manažérovi."
    assert child_status == "waiting_hitl"
    assert len(store_calls) == 1
    assert store_calls[0]["type"] == "hitl"
    assert "nova feature temporal projektu" in store_calls[0]["title"]
