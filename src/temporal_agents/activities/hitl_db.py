import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Literal, Optional
import aiosqlite
from pydantic import BaseModel, Field
from temporalio import activity

# Module-level constant — patchable in tests
DB_URL: str = os.environ.get("HITL_DB_URL", "sqlite:////tmp/hitl.db")

# Only these tables are allowed in execute_db_query
WHITELIST_TABLES = {"tasks"}


def _db_path() -> str:
    url = DB_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


async def _init_db(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            title TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',
            type TEXT DEFAULT 'task',
            workflow_id TEXT,
            created_at TEXT NOT NULL
        )
    """)
    await db.commit()


class Task(BaseModel):
    id: uuid.UUID
    project: str
    title: str
    priority: int = 5
    status: Literal['pending', 'in_progress', 'done', 'confirmed', 'cancelled'] = 'pending'
    type: Literal['task', 'hitl', 'lesson'] = 'task'
    workflow_id: Optional[str] = None
    created_at: str


class DBQuery(BaseModel):
    table: str
    filter: dict = Field(default_factory=dict)
    order: str = ''
    limit: int = 100


@activity.defn
async def store_task(
    project: str,
    title: str,
    priority: int = 5,
    type: str = 'task',
    workflow_id: Optional[str] = None,
) -> Task:
    """Insert a new task (or HITL task) and return it."""
    record_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT INTO tasks (id, project, title, priority, status, type, workflow_id, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)",
            (str(record_id), project, title, priority, type, workflow_id, now.isoformat())
        )
        await db.commit()
    return Task(
        id=record_id,
        project=project,
        title=title,
        priority=priority,
        status='pending',
        type=type,
        workflow_id=workflow_id,
        created_at=now.isoformat(),
    )


async def _fetch_tasks(status: Optional[str] = None) -> list[Task]:
    """Fetch tasks from DB. If status is None, return all tasks."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY priority ASC, project ASC",
                (status,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks ORDER BY priority ASC, project ASC"
            )
        rows = await cursor.fetchall()
    return [
        Task(
            id=uuid.UUID(row['id']),
            project=row['project'],
            title=row['title'],
            priority=row['priority'],
            status=row['status'],
            type=row['type'],
            workflow_id=row['workflow_id'],
            created_at=row['created_at']
        )
        for row in rows
    ]


@activity.defn
async def list_tasks(status: str = 'pending') -> list[Task]:
    """Return tasks filtered by status, sorted by priority ASC then project ASC."""
    return await _fetch_tasks(status)


@activity.defn
async def update_task_status(workflow_id: str, status: str) -> None:
    """Update task status by workflow_id."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "UPDATE tasks SET status = ? WHERE workflow_id = ?",
            (status, workflow_id)
        )
        await db.commit()


@activity.defn
async def execute_db_query(query: DBQuery) -> list[dict]:
    """Execute a parameterized SELECT against a whitelisted table."""
    if query.table not in WHITELIST_TABLES:
        raise ValueError(f"Table '{query.table}' is not allowed. Allowed: {WHITELIST_TABLES}")

    sql = f"SELECT * FROM {query.table}"
    params = []

    if query.filter:
        conditions = [f"{k} = ?" for k in query.filter.keys()]
        sql += " WHERE " + " AND ".join(conditions)
        params.extend(query.filter.values())

    if query.order:
        sql += f" ORDER BY {query.order}"

    sql += f" LIMIT {query.limit}"

    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()

    return [dict(row) for row in rows]
