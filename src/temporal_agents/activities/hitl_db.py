import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Literal
import aiosqlite
from pydantic import BaseModel, Field
from temporalio import activity

# Module-level constant — patchable in tests
DB_URL: str = os.environ.get("HITL_DB_URL", "sqlite:///tmp/hitl.db")

# Only these tables are allowed in execute_db_query
WHITELIST_TABLES = {"hitl_requests"}


def _db_path() -> str:
    """Extract filesystem path from sqlite:/// URL."""
    url = DB_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


async def _init_db(db: aiosqlite.Connection) -> None:
    """Create hitl_requests table if it does not exist (SQLite compatible schema)."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS hitl_requests (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            description TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)
    await db.commit()


class HitlRequest(BaseModel):
    id: uuid.UUID
    workflow_id: str
    description: str
    priority: int = 5
    status: Literal['pending', 'confirmed', 'cancelled'] = 'pending'
    created_at: datetime


class DBQuery(BaseModel):
    table: str
    filter: dict = Field(default_factory=dict)
    order: str = ''
    limit: int = 100


@activity.defn
async def store_hitl_request(workflow_id: str, description: str, priority: int = 5) -> HitlRequest:
    """Insert a new HITL request record and return it."""
    record_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        await db.execute(
            "INSERT INTO hitl_requests (id, workflow_id, description, priority, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (str(record_id), workflow_id, description, priority, now.isoformat())
        )
        await db.commit()
    return HitlRequest(
        id=record_id,
        workflow_id=workflow_id,
        description=description,
        priority=priority,
        status='pending',
        created_at=now
    )


@activity.defn
async def list_hitl_requests(status: str = 'pending') -> list[HitlRequest]:
    """Return HITL requests filtered by status, sorted by priority ASC then created_at ASC."""
    async with aiosqlite.connect(_db_path()) as db:
        await _init_db(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM hitl_requests WHERE status = ? ORDER BY priority ASC, created_at ASC",
            (status,)
        )
        rows = await cursor.fetchall()
    return [
        HitlRequest(
            id=uuid.UUID(row['id']),
            workflow_id=row['workflow_id'],
            description=row['description'],
            priority=row['priority'],
            status=row['status'],
            created_at=datetime.fromisoformat(row['created_at'])
        )
        for row in rows
    ]


@activity.defn
async def execute_db_query(query: DBQuery) -> list[dict]:
    """Execute a parameterized SELECT against a whitelisted table."""
    if query.table not in WHITELIST_TABLES:
        raise ValueError(f"Table '{query.table}' is not allowed. Allowed tables: {WHITELIST_TABLES}")

    sql = f"SELECT * FROM {query.table}"
    params = []

    # Build WHERE clause from filter dict
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
