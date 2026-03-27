"""Unit tests for unified tasks DB activities."""

from datetime import timedelta
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class TestDBQueryModelDefaults:
    def test_dbquery_model_defaults(self):
        from temporal_agents.activities.hitl_db import DBQuery
        query = DBQuery(table="tasks")
        assert query.filter == {}
        assert query.order == ""
        assert query.limit == 100


# ---------------------------------------------------------------------------
# store_task
# ---------------------------------------------------------------------------

class TestStoreTask:
    async def test_store_regular_task(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import store_task
            result = await store_task(project="zbornik", title="Fix crash")

        import uuid
        from datetime import datetime
        assert result.project == "zbornik"
        assert result.title == "Fix crash"
        assert result.type == "task"
        assert result.workflow_id is None
        assert result.status == "pending"
        assert isinstance(result.id, uuid.UUID)
        assert isinstance(result.created_at, datetime)

    async def test_store_hitl_task(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import store_task
            result = await store_task(
                project="ginidocs",
                title="Approve deployment",
                priority=1,
                type="hitl",
                workflow_id="wf-123",
            )

        assert result.type == "hitl"
        assert result.workflow_id == "wf-123"
        assert result.priority == 1

    async def test_store_task_default_priority(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import store_task
            result = await store_task(project="zbornik", title="Some task")
        assert result.priority == 5


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    async def test_list_tasks_returns_pending_only(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import list_tasks, store_task
            import aiosqlite

            pending = await store_task(project="zbornik", title="Pending task")
            done = await store_task(project="zbornik", title="Done task")

            db_path = db_url.removeprefix("sqlite:///")
            async with aiosqlite.connect(db_path) as db:
                await db.execute("UPDATE tasks SET status='done' WHERE id=?", (str(done.id),))
                await db.commit()

            results = await list_tasks(status="pending")

        ids = [r.id for r in results]
        assert pending.id in ids
        assert done.id not in ids

    async def test_list_tasks_sorted_by_priority(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import list_tasks, store_task
            await store_task(project="zbornik", title="Low", priority=9)
            await store_task(project="zbornik", title="High", priority=1)
            await store_task(project="zbornik", title="Mid", priority=5)
            results = await list_tasks(status="pending")

        priorities = [r.priority for r in results]
        assert priorities == sorted(priorities)

    async def test_list_tasks_hitl_and_task_together(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import list_tasks, store_task
            t = await store_task(project="zbornik", title="Regular", type="task")
            h = await store_task(project="zbornik", title="HITL confirm", type="hitl", workflow_id="wf-1")
            results = await list_tasks(status="pending")

        types = {r.type for r in results}
        assert "task" in types
        assert "hitl" in types


# ---------------------------------------------------------------------------
# execute_db_query
# ---------------------------------------------------------------------------

class TestExecuteDbQuery:
    async def test_unknown_table_raises(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import DBQuery, execute_db_query
            with pytest.raises(ValueError):
                await execute_db_query(DBQuery(table="users"))

    async def test_query_tasks_table(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import DBQuery, execute_db_query, store_task
            await store_task(project="zbornik", title="Query test")
            results = await execute_db_query(DBQuery(table="tasks"))

        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(row, dict) for row in results)

    async def test_query_with_filter(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/tasks.db"
        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            from temporal_agents.activities.hitl_db import DBQuery, execute_db_query, store_task
            import aiosqlite

            r1 = await store_task(project="zbornik", title="Pending")
            r2 = await store_task(project="zbornik", title="Done")

            db_path = db_url.removeprefix("sqlite:///")
            async with aiosqlite.connect(db_path) as db:
                await db.execute("UPDATE tasks SET status='done' WHERE id=?", (str(r2.id),))
                await db.commit()

            results = await execute_db_query(DBQuery(table="tasks", filter={"status": "pending"}))

        statuses = [row["status"] for row in results]
        assert all(s == "pending" for s in statuses)
        assert len(statuses) >= 1


# ---------------------------------------------------------------------------
# options.py
# ---------------------------------------------------------------------------

class TestStoreTaskOptions:
    def test_store_task_options_timeout(self):
        from temporal_agents.activities.options import STORE_TASK_OPTIONS
        assert STORE_TASK_OPTIONS.start_to_close_timeout == timedelta(seconds=30)


class TestExecuteDbQueryOptions:
    def test_execute_db_query_options_timeout(self):
        from temporal_agents.activities.options import EXECUTE_DB_QUERY_OPTIONS
        assert EXECUTE_DB_QUERY_OPTIONS.start_to_close_timeout == timedelta(seconds=10)
