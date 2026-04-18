import os
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

import aiosqlite
from pydantic import BaseModel
from temporalio import activity

DB_URL: str = os.environ.get("HITL_DB_URL", "sqlite:////tmp/hitl.db")

WHITELIST_TABLES = {"tasks", "tickets"}


def _db_path() -> str:
    url = DB_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    if url.startswith("sqlite://"):
        return url[len("sqlite://") :]
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
    await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT 'todo',
            created_at TEXT NOT NULL
        )
    """)
    await db.commit()


class Task(BaseModel):
    id: uuid.UUID
    project: str
    title: str
    priority: int = 5
    status: Literal["pending", "in_progress", "done", "cancelled"] = "pending"
    type: Literal["task", "hitl"] = "task"
    workflow_id: Optional[str] = None
    created_at: str


class Ticket(BaseModel):
    id: str
    project: str
    description: str
    status: str = "todo"
    created_at: str


class DBQuery(BaseModel):
    table: str
    filter: dict = {}
    order: str = ""
    limit: int = 100


@activity.defn
async def store_task(
    project: str,
    title: str,
    priority: int = 5,
    type: str = "task",
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
            (
                str(record_id),
                project,
                title,
                priority,
                type,
                workflow_id,
                now.isoformat(),
            ),
        )
        await db.commit()
    return Task(
        id=record_id,
        project=project,
        title=title,
        priority=priority,
        status="pending",
        type=type,
        workflow_id=workflow_id,
        created_at=now.isoformat(),
    )


@activity.defn
async def store_ticket(project: str, description: str = "") -> Ticket:
    """Save a new ticket with status=todo."""
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT INTO tickets (id, project, description, status, created_at) "
            "VALUES (?, ?, ?, 'todo', ?)",
            (ticket_id, project, description, now),
        )
        await db.commit()
    return Ticket(
        id=ticket_id,
        project=project,
        description=description,
        status="todo",
        created_at=now,
    )


async def _fetch_tasks(status: Optional[str] = None) -> list[Task]:
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY priority ASC, project ASC",
                (status,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM tasks ORDER BY priority ASC, project ASC"
            )
        rows = await cursor.fetchall()
    return [
        Task(
            id=uuid.UUID(row["id"]),
            project=row["project"],
            title=row["title"],
            priority=row["priority"],
            status=row["status"],
            type=row["type"],
            workflow_id=row["workflow_id"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def _fetch_tickets(status: Optional[str] = None) -> list[Ticket]:
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                "SELECT * FROM tickets WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cursor = await db.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        rows = await cursor.fetchall()
    return [
        Ticket(
            id=row["id"],
            project=row["project"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@activity.defn
async def update_task_status(workflow_id: str, status: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "UPDATE tasks SET status = ? WHERE workflow_id = ?", (status, workflow_id)
        )
        await db.commit()


@activity.defn
async def list_tasks(status: str = "pending") -> list[Task]:
    return await _fetch_tasks(status)


@activity.defn
async def list_tickets(status: str = "todo") -> list[Ticket]:
    return await _fetch_tickets(status)


@activity.defn
async def create_task(
    project: str,
    title: str,
    priority: int = 5,
    type: str = "task",
    workflow_id: Optional[str] = None,
) -> Task:
    """Activity wrapper for store_task."""
    return await store_task(project, title, priority, type, workflow_id)


@activity.defn
async def create_ticket(project: str, description: str = "") -> Ticket:
    """Activity wrapper for store_ticket."""
    return await store_ticket(project, description)


@activity.defn
async def complete_task(workflow_id: str) -> None:
    """Activity wrapper for update_task_status with done status."""
    return await update_task_status(workflow_id, "done")


@activity.defn
async def execute_db_query(query: DBQuery) -> list[dict]:
    """Execute a read-only DB query with whitelist protection."""
    if query.table not in WHITELIST_TABLES:
        raise ValueError(
            f"Table '{query.table}' is not allowed. Allowed: {WHITELIST_TABLES}"
        )

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
