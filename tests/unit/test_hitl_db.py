import pytest
import os

os.environ["HITL_DB_URL"] = "postgresql://temporal:temporal@localhost:5432/temporal"


class TestDBQueryModelDefaults:
    def test_dbquery_model_defaults(self):
        from temporal_agents.activities.tasks import DBQuery

        query = DBQuery(table="tasks")
        assert query.filter == {}
        assert query.order == ""
        assert query.limit == 100


class TestStoreTask:
    async def test_store_regular_task(self):
        from temporal_agents.activities.tasks import store_task

        result = await store_task(project="zbornik", title="Fix crash")

        assert result.project == "zbornik"
        assert result.title == "Fix crash"
        assert result.type == "task"
        assert result.workflow_id is None
        assert result.status == "todo"
        assert "id" in result.id
        assert "T" in result.created_at

    async def test_store_hitl_task(self):
        from temporal_agents.activities.tasks import store_task

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

    async def test_store_task_default_priority(self):
        from temporal_agents.activities.tasks import store_task

        result = await store_task(project="zbornik", title="Some task")
        assert result.priority == 5


class TestListTasks:
    async def test_list_tasks_returns_pending_only(self):
        from temporal_agents.activities.tasks import list_tasks, store_task

        pending = await store_task(project="zbornik", title="Pending task")
        done = await store_task(project="zbornik", title="Done task")

        from temporal_agents.activities.tasks import _pg_connect
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET status='done' WHERE id=%s", (str(done.id),)
                )
            conn.commit()

        results = await list_tasks(status="todo")

        ids = [r.id for r in results]
        assert pending.id in ids

    async def test_list_tasks_sorted_by_priority(self):
        from temporal_agents.activities.tasks import list_tasks, store_task

        await store_task(project="zbornik", title="Low", priority=9)
        await store_task(project="zbornik", title="High", priority=1)
        await store_task(project="zbornik", title="Mid", priority=5)
        results = await list_tasks(status="todo")

        priorities = [r.priority for r in results]
        assert priorities == sorted(priorities)


class TestExecuteDbQuery:
    async def test_unknown_table_raises(self):
        from temporal_agents.activities.tasks import DBQuery, execute_db_query

        with pytest.raises(ValueError):
            await execute_db_query(DBQuery(table="users"))

    async def test_query_tasks_table(self):
        from temporal_agents.activities.tasks import (
            DBQuery,
            execute_db_query,
            store_task,
        )

        await store_task(project="zbornik", title="Query test")
        results = await execute_db_query(DBQuery(table="tasks"))

        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(row, dict) for row in results)

    async def test_query_with_filter(self):
        from temporal_agents.activities.tasks import (
            DBQuery,
            execute_db_query,
            store_task,
        )

        r1 = await store_task(project="zbornik", title="Pending")
        r2 = await store_task(project="zbornik", title="Done")

        from temporal_agents.activities.tasks import _pg_connect
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET status='done' WHERE id=%s", (str(r2.id),)
                )
            conn.commit()

        results = await execute_db_query(
            DBQuery(table="tasks", filter={"status": "todo"})
        )

        statuses = [row["status"] for row in results]
        assert all(s == "todo" for s in statuses)