"""Unit tests for hitl_db activities (TDD — implementation does not exist yet).

All tests are intentionally RED until src/temporal_agents/activities/hitl_db.py
and the corresponding options in options.py are implemented.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestDBQueryModelDefaults:
    """DBQuery must expose correct default values for optional fields."""

    def test_dbquery_model_defaults(self):
        from temporal_agents.activities.hitl_db import DBQuery

        query = DBQuery(table="hitl_requests")

        assert query.filter == {}
        assert query.order == ""
        assert query.limit == 100


# ---------------------------------------------------------------------------
# store_hitl_request
# ---------------------------------------------------------------------------


class TestStoreHitlRequest:
    """store_hitl_request must insert a record and return a valid HitlRequest."""

    async def test_store_hitl_request(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import store_hitl_request

                result = await store_hitl_request(
                    workflow_id="wf-001", description="Approve deployment"
                )

        import uuid
        from datetime import datetime

        assert result.workflow_id == "wf-001"
        assert result.description == "Approve deployment"
        assert result.status == "pending"
        assert isinstance(result.id, uuid.UUID)
        assert isinstance(result.created_at, datetime)

    async def test_store_hitl_request_default_priority(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import store_hitl_request

                result = await store_hitl_request(
                    workflow_id="wf-002", description="Check config"
                )

        assert result.priority == 5


# ---------------------------------------------------------------------------
# list_hitl_requests
# ---------------------------------------------------------------------------


class TestListHitlRequests:
    """list_hitl_requests must filter and sort correctly."""

    async def test_list_hitl_requests_returns_pending_only(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import (
                    list_hitl_requests,
                    store_hitl_request,
                )

                pending = await store_hitl_request(
                    workflow_id="wf-p1", description="Pending task"
                )
                confirmed = await store_hitl_request(
                    workflow_id="wf-c1", description="Confirmed task"
                )

                # Manually flip one record to 'confirmed' via a second store call
                # with status override — or patch DB directly.
                # The confirmed record is stored as pending; we need to update it.
                # We use execute_db_query indirectly via raw manipulation:
                import aiosqlite

                db_path = db_url.removeprefix("sqlite:///")
                async with aiosqlite.connect(db_path) as db:
                    await db.execute(
                        "UPDATE hitl_requests SET status='confirmed' WHERE id=?",
                        (str(confirmed.id),),
                    )
                    await db.commit()

                results = await list_hitl_requests(status="pending")

        ids = [r.id for r in results]
        assert pending.id in ids
        assert confirmed.id not in ids

    async def test_list_hitl_requests_sorted_by_priority(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import (
                    list_hitl_requests,
                    store_hitl_request,
                )

                high = await store_hitl_request(
                    workflow_id="wf-h", description="High priority", priority=1
                )
                low = await store_hitl_request(
                    workflow_id="wf-l", description="Low priority", priority=9
                )
                mid = await store_hitl_request(
                    workflow_id="wf-m", description="Mid priority", priority=5
                )

                results = await list_hitl_requests(status="pending")

        priorities = [r.priority for r in results]
        assert priorities == sorted(priorities), (
            f"Expected ascending priority order, got: {priorities}"
        )


# ---------------------------------------------------------------------------
# execute_db_query
# ---------------------------------------------------------------------------


class TestExecuteDbQuery:
    """execute_db_query must enforce the table whitelist and support filters."""

    async def test_execute_db_query_unknown_table_raises(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import (
                    DBQuery,
                    execute_db_query,
                )

                with pytest.raises(ValueError):
                    await execute_db_query(DBQuery(table="users"))

    async def test_execute_db_query_hitl_requests(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import (
                    DBQuery,
                    execute_db_query,
                    store_hitl_request,
                )

                await store_hitl_request(
                    workflow_id="wf-q1", description="Query test"
                )

                results = await execute_db_query(DBQuery(table="hitl_requests"))

        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(row, dict) for row in results)

    async def test_execute_db_query_with_filter(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/hitl.db"

        with patch("temporal_agents.activities.hitl_db.DB_URL", db_url):
            with patch("temporalio.activity.heartbeat"):
                from temporal_agents.activities.hitl_db import (
                    DBQuery,
                    execute_db_query,
                    store_hitl_request,
                )

                r1 = await store_hitl_request(
                    workflow_id="wf-f1", description="Filter pending"
                )
                r2 = await store_hitl_request(
                    workflow_id="wf-f2", description="Filter confirmed"
                )

                import aiosqlite

                db_path = db_url.removeprefix("sqlite:///")
                async with aiosqlite.connect(db_path) as db:
                    await db.execute(
                        "UPDATE hitl_requests SET status='confirmed' WHERE id=?",
                        (str(r2.id),),
                    )
                    await db.commit()

                results = await execute_db_query(
                    DBQuery(table="hitl_requests", filter={"status": "pending"})
                )

        statuses = [row["status"] for row in results]
        assert all(s == "pending" for s in statuses), (
            f"Expected only pending rows, got statuses: {statuses}"
        )
        assert len(statuses) >= 1


# ---------------------------------------------------------------------------
# options.py — HITL activity options
# ---------------------------------------------------------------------------


class TestStoreHitlOptions:
    """STORE_HITL_OPTIONS must have start_to_close_timeout of 30 seconds."""

    def test_store_hitl_options_timeout(self):
        from temporal_agents.activities.options import STORE_HITL_OPTIONS

        assert STORE_HITL_OPTIONS.start_to_close_timeout == timedelta(seconds=30)


class TestListHitlOptions:
    """LIST_HITL_OPTIONS must have start_to_close_timeout of 10 seconds."""

    def test_list_hitl_options_timeout(self):
        from temporal_agents.activities.options import LIST_HITL_OPTIONS

        assert LIST_HITL_OPTIONS.start_to_close_timeout == timedelta(seconds=10)


class TestExecuteDbQueryOptions:
    """EXECUTE_DB_QUERY_OPTIONS must have start_to_close_timeout of 10 seconds."""

    def test_execute_db_query_options_timeout(self):
        from temporal_agents.activities.options import EXECUTE_DB_QUERY_OPTIONS

        assert EXECUTE_DB_QUERY_OPTIONS.start_to_close_timeout == timedelta(seconds=10)
